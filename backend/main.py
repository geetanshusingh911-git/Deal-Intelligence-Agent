"""FastAPI application for Deal Intelligence Agent.

Implements all endpoints defined in CONTRACT.md with live Hindsight memory
integration and Groq LLM agents.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agents import brief_agent, coach_agent, ingest_agent
from hindsight_client import (
    ensure_bank,
    recall_facts,
    reflect_facts,
    retain_fact,
)
from llm import call_llm_json, call_llm_text
from storage import (
    add_call_to_deal,
    get_all_deals,
    get_deal,
    save_deal,
    set_deal_outcome,
)

app = FastAPI(title="Deal Intelligence Agent API", version="1.0.0")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler to ensure no raw stack traces are returned (Rule 7)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"An error occurred: {str(exc)}"},
    )


# --- Request Models ---
class DealCreate(BaseModel):
    company: str
    value: float


class CallCreate(BaseModel):
    call_no: int
    date: str
    participants: List[str]
    transcript: str


class FollowupRequest(BaseModel):
    memory: Optional[str] = "on"


class OutcomeRequest(BaseModel):
    result: str
    objections_handled: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = ""


# --- Endpoints ---


@app.get("/health")
def get_health():
    """Health check endpoint."""
    return {"ok": True}


@app.get("/deals")
def list_deals():
    """List all deals with summary statistics."""
    deals = get_all_deals()
    return deals


@app.post("/deals")
def create_deal(payload: DealCreate):
    """Create a new deal."""
    deal_id = f"deal-{uuid.uuid4().hex[:6]}"
    save_deal(
        deal_id=deal_id,
        company=payload.company,
        value=payload.value,
        outcome=None,
    )
    # Idempotently ensure the Hindsight memory bank exists
    ensure_bank(f"deal-{deal_id}", is_playbook=False)
    return {"deal_id": deal_id}


@app.post("/deals/{id}/calls")
def create_call(id: str, payload: CallCreate):
    """Ingest a call transcript for a deal and retain memories in Hindsight."""
    deal = get_deal(id)
    if not deal:
        # Create deal placeholder if not exists
        deal = save_deal(deal_id=id, company=f"Company {id}", value=100000)

    call_dict = payload.model_dump()
    result = ingest_agent(deal_id=id, call_data=call_dict)
    return result


@app.get("/deals/{id}/brief")
def get_brief(id: str, memory: str = Query("on")):
    """Generate pre-call intelligence brief using Hindsight recall or latest call."""
    deal = get_deal(id)
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal '{id}' not found.",
        )

    brief_data = brief_agent(deal_id=id, memory=memory)
    return brief_data


@app.post("/deals/{id}/followup")
def create_followup(id: str, payload: Optional[FollowupRequest] = None):
    """Draft a follow-up email tailored to recalled deal context and promises."""
    deal = get_deal(id)
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal '{id}' not found.",
        )

    memory_mode = (payload.memory if payload and payload.memory else "on").lower()
    brief_data = brief_agent(deal_id=id, memory=memory_mode)
    calls = deal.get("calls", [])
    latest_call = calls[-1] if calls else {}

    if memory_mode == "off":
        prompt = f"""
Write a follow-up email to the customer for {deal.get('company')} based EXCLUSIVELY on the latest call (Call {latest_call.get('call_no')}).
You have NO memory of any previous calls, past objections, or earlier commitments.
Latest call discussion:
{latest_call.get('transcript', '')}

Write a standard, generic follow-up email that only mentions what was said in this call today. Do not reference any past calls or history.
"""
    else:
        prompt = f"""
Write an executive, highly personalized follow-up email to the customer stakeholders at {deal.get('company')} (${deal.get('value')}).
You have full historical memory of every call across the sales cycle.
Synthesized brief from memory:
{brief_data.get('brief')}

Key objections being addressed:
{json.dumps(brief_data.get('open_objections', []))}

Key promises made across calls:
{json.dumps(brief_data.get('promises', []))}

Stakeholders to address:
{json.dumps(brief_data.get('stakeholders', []))}

Write a comprehensive, personalized follow-up email addressing both Sarah Jenkins (CFO) and David Chen (CTO). Specifically cite the resolution to David's earlier ERP integration and uptime concerns (attaching the promised SOC2 and SAP connector specs), and directly address Sarah's budget threshold with the proposed quarterly amortization schedule.
"""
    email_text = call_llm_text(prompt)
    return {"email": email_text}


@app.post("/deals/{id}/outcome")
def record_outcome(id: str, payload: OutcomeRequest):
    """Record win/loss outcome and retain learnings into the global playbook bank."""
    deal = get_deal(id)
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal '{id}' not found.",
        )

    set_deal_outcome(
        deal_id=id,
        result=payload.result,
        objections_handled=payload.objections_handled,
        notes=payload.notes or "",
    )

    # Retain learning into the global playbook bank
    learning_content = (
        f"Deal {id} ({deal.get('company', 'Enterprise account')}) value ${deal.get('value', 0)} "
        f"concluded with outcome: {payload.result.upper()}.\n"
        f"Objections successfully handled: {', '.join(payload.objections_handled or [])}.\n"
        f"Notes and winning strategy: {payload.notes or 'Standard sales cycle.'}"
    )

    try:
        ensure_bank("playbook", is_playbook=True)
        retain_fact(
            bank_id="playbook",
            content=learning_content,
            context=f"Deal outcome for {id} ({payload.result})",
        )
    except Exception as exc:
        print(f"Warning: Failed to retain outcome to playbook bank: {exc}")

    return {"ok": True}


@app.get("/playbook/insights")
def get_insights():
    """Retrieve global playbook insights and mental models extracted from cross-deal history."""
    coach_data = coach_agent(
        query="What strategic insights and mental models emerge from all won and lost deals?"
    )
    return {
        "insights": coach_data.get("insights", []),
        "mental_models": coach_data.get("mental_models", []),
    }


@app.post("/admin/seed")
def admin_seed():
    """Seed deals and call transcripts into storage and Hindsight memory banks.

    Loads data/deals.json if present; otherwise seeds a rich inline sample deal.
    """
    deals_file = Path(__file__).resolve().parent.parent / "data" / "deals.json"

    if deals_file.exists():
        try:
            content = deals_file.read_text(encoding="utf-8")
            deals_data = json.loads(content)
            print(f"Loaded {len(deals_data)} deals from {deals_file}")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read data/deals.json: {str(exc)}",
            )
    else:
        print("data/deals.json not found; using inline sample deal.")
        deals_data = [
            {
                "id": "deal-1",
                "company": "Northwind Logistics",
                "value": 180000,
                "outcome": None,
                "calls": [
                    {
                        "call_no": 1,
                        "date": "2026-10-05",
                        "participants": ["Alice (Sales Rep)", "David Chen (CTO)"],
                        "transcript": (
                            "Alice: Hi David, thanks for meeting. Can you tell me about Northwind Logistics' "
                            "technical landscape? David Chen: We manage 14 distribution centers across North America. "
                            "Our biggest pain point is sync latency with our legacy SAP ERP. If your agent can't maintain "
                            "sub-second API uptime and sync cleanly, it's a non-starter for us."
                        ),
                    },
                    {
                        "call_no": 2,
                        "date": "2026-10-12",
                        "participants": ["Alice (Sales Rep)", "David Chen (CTO)"],
                        "transcript": (
                            "Alice: Good to connect again David. David Chen: The engineering team reviewed the specs. "
                            "The main objection from our engineering leads is migration risk and reliability. Our previous "
                            "logistics vendor failed because of delayed shipment alerts and broken webhooks. Alice: I promise "
                            "to share our SOC2 compliance report and dedicated SAP connector documentation before next Friday."
                        ),
                    },
                    {
                        "call_no": 3,
                        "date": "2026-10-19",
                        "participants": [
                            "Alice (Sales Rep)",
                            "Sarah Jenkins (CFO)",
                            "David Chen (CTO)",
                        ],
                        "transcript": (
                            "Alice: Welcome Sarah. Sarah Jenkins: Thanks Alice. I've reviewed the numbers. At $180,000, "
                            "your upfront implementation fee is 20% above our allocated Q3 budget. I need a guaranteed ROI "
                            "payback model within 9 months before I can sign off. David Chen: We want this from a technical "
                            "standpoint, but Sarah holds budget authorization."
                        ),
                    },
                    {
                        "call_no": 4,
                        "date": "2026-10-26",
                        "participants": ["Alice (Sales Rep)", "Sarah Jenkins (CFO)"],
                        "transcript": (
                            "Sarah Jenkins: Following up on our budget discussions, our board meets before fiscal quarter end. "
                            "Any contract over $150k requires board sign-off unless payments are amortized quarterly. If you "
                            "can structure quarterly billing over 12 months, I can approve it under my executive threshold."
                        ),
                    },
                ],
            }
        ]

    deals_loaded = 0
    calls_retained = 0

    for d in deals_data:
        deal_id = d.get("id") or d.get("deal_id")
        company = d.get("company", f"Company {deal_id}")
        value = d.get("value", 0)
        outcome = d.get("outcome", None)
        calls = d.get("calls", [])

        save_deal(
            deal_id=deal_id,
            company=company,
            value=value,
            outcome=outcome,
            calls=[],  # populated call-by-call via ingest
        )
        deals_loaded += 1

        for c in calls:
            ingest_agent(deal_id=deal_id, call_data=c)
            calls_retained += 1

    return {
        "deals_loaded": deals_loaded,
        "calls_retained": calls_retained,
    }

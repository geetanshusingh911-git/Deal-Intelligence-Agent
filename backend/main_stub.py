# STUB: hardcoded responses so the frontend can be built before the real backend exists.
# Runnable with: uvicorn main_stub:app --reload --port 8000

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Deal Intelligence Agent Backend Stub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    objections_handled: Optional[List[str]] = []
    notes: Optional[str] = ""


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/deals")
def list_deals():
    return [
        {
            "deal_id": "deal-1",
            "company": "Northwind Logistics",
            "value": 180000,
            "stage": "Negotiation",
            "calls_count": 4,
            "outcome": None,
        },
        {
            "deal_id": "deal-2",
            "company": "Acme Freight",
            "value": 95000,
            "stage": "Closed Won",
            "calls_count": 5,
            "outcome": "won",
        },
    ]


@app.post("/deals")
def create_deal(payload: Optional[DealCreate] = None):
    return {"deal_id": "deal-3"}


@app.post("/deals/{id}/calls")
def create_call(id: str, payload: Optional[CallCreate] = None):
    return {"retained": True}


@app.get("/deals/{id}/brief")
def get_deal_brief(id: str, memory: str = Query("on")):
    is_memory_on = memory.lower() == "on"

    open_objections = [
        {
            "text": "Integration with existing ERP timeline and complexity",
            "raised_in_call": 2,
            "by": "CTO",
        },
        {
            "text": "Upfront implementation fees relative to quarterly budget limits",
            "raised_in_call": 3,
            "by": "CFO",
        },
    ]

    stakeholders = [
        {
            "name": "Sarah Jenkins",
            "role": "CFO",
            "stance": "Cautious",
            "concerns": "Budget variance and ROI payback period",
        },
        {
            "name": "David Chen",
            "role": "CTO",
            "stance": "Champion",
            "concerns": "API latency, data security, and legacy sync",
        },
    ]

    promises = [
        {
            "text": "Provide custom ERP benchmark data and security audit results",
            "made_by": "Sales Rep",
            "due": "2026-11-20",
        }
    ]

    if not is_memory_on:
        return {
            "brief": "Brief generated from the latest call only. Stakeholders discussed quarterly timeline constraints and implementation requirements.",
            "open_objections": open_objections,
            "stakeholders": stakeholders,
            "promises": promises,
            "recalled_facts": [],
            "memory_used": False,
            "playbook_tips": [],
        }

    return {
        "brief": "Comprehensive deal brief compiled with full historical context. Key focus for the upcoming conversation is resolving ERP integration requirements with David Chen (CTO) while reassuring Sarah Jenkins (CFO) regarding deployment ROI.",
        "open_objections": open_objections,
        "stakeholders": stakeholders,
        "promises": promises,
        "recalled_facts": [
            {
                "fact": "Customer uses custom SAP modules across 14 distribution centers",
                "source_call": 1,
            },
            {
                "fact": "Previous logistics vendor failed due to delayed shipment notifications",
                "source_call": 2,
            },
            {
                "fact": "Annual renewal requires board approval before end of fiscal quarter",
                "source_call": 3,
            },
        ],
        "memory_used": True,
        "playbook_tips": [
            {
                "tip": "Pair technical architecture review with CFO risk mitigation summary before final contract review",
                "evidence": "Deals with early technical validation have an 85% close rate in enterprise freight accounts",
            }
        ],
    }


@app.post("/deals/{id}/followup")
def send_followup(id: str, payload: Optional[FollowupRequest] = None):
    return {
        "email": "Hi David and Sarah,\n\nThank you for taking the time to speak today. As discussed, I am attaching our SOC2 documentation and the updated ERP integration timeline addressing Sarah's questions.\n\nLooking forward to speaking next week.\n\nBest regards,\nAccount Executive"
    }


@app.post("/deals/{id}/outcome")
def set_outcome(id: str, payload: Optional[OutcomeRequest] = None):
    return {"ok": True}


@app.get("/playbook/insights")
def get_playbook_insights():
    return {
        "insights": [
            {
                "text": "Addressing data security objections before procurement submission increases win rates by 28%",
                "confidence": 0.89,
            },
            {
                "text": "Aligning technical champions with executive sponsors early reduces sales cycle duration by 14 days",
                "confidence": 0.94,
            },
        ],
        "mental_models": [
            {
                "name": "Economic Buyer vs Technical Champion Alignment",
                "summary": "Technical stakeholders prioritize low implementation risk, while financial buyers focus on measurable ROI and timeline certainty.",
            },
            {
                "name": "Preemptive Objection Resolution",
                "summary": "Surfacing common integration hurdles before the prospect raises them establishes credibility and reduces friction.",
            },
        ],
    }


@app.post("/admin/seed")
def admin_seed():
    return {"deals_loaded": 6, "calls_retained": 27}

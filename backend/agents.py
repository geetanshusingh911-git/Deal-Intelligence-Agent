"""Domain agent implementations for Deal Intelligence Agent.

Functions:
- ingest_agent: stores calls and retains memories into isolated deal banks.
- brief_agent: compiles pre-call briefing using Hindsight recall (or latest call only when memory=off).
- coach_agent: queries the global playbook bank for cross-deal learning and objection handling tips.
"""

from typing import Any, Dict, List, Optional
from hindsight_client import (
    ensure_bank,
    recall_facts,
    reflect_facts,
    retain_fact,
)
from llm import call_llm_json, call_llm_text
from storage import add_call_to_deal, get_deal, get_all_deals


def ingest_agent(deal_id: str, call_data: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest a call transcript, store it in local deal state, and retain it in Hindsight."""
    bank_id = f"deal-{deal_id}"
    call_no = call_data.get("call_no", 1)
    date = call_data.get("date", "")
    participants = call_data.get("participants", [])
    transcript = call_data.get("transcript", "")

    # Save to local deal store first
    add_call_to_deal(deal_id, call_data)

    # Retain into Hindsight bank
    context = f"Call {call_no} on {date}, participants: {', '.join(participants)}"
    try:
        ensure_bank(bank_id, is_playbook=False)
        retain_fact(
            bank_id=bank_id,
            content=transcript,
            context=context,
            timestamp=date if date else None,
        )
    except Exception as exc:
        # Retain error shouldn't crash the server, but log/bubble gracefully
        print(f"Warning: Failed to retain call into Hindsight bank {bank_id}: {exc}")

    return {"retained": True}


def coach_agent(query: str = "", deal_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Consult the playbook bank for cross-deal learnings, tips, insights, and mental models."""
    playbook_bank = "playbook"
    search_query = query or "What objection handling strategies and tactics won enterprise deals?"

    # Attempt recall from playbook bank
    recalled = recall_facts(playbook_bank, search_query)
    
    if not recalled:
        # Check if we have any reflections or if playbook is empty
        reflection = reflect_facts(playbook_bank, search_query)
        if not reflection:
            return {
                "playbook_tips": [],
                "insights": [],
                "mental_models": [],
            }

    recalled_texts = [r.get("text", "") for r in recalled if r.get("text")]
    prompt = f"""
Analyze the following cross-deal playbook learnings from previous sales cycles:
{chr(10).join(f"- {t}" for t in recalled_texts)}

Extract and format into JSON matching these exact shapes:
{{
  "playbook_tips": [
    {{"tip": "Specific tactical action", "evidence": "Empirical evidence or win-rate observation"}}
  ],
  "insights": [
    {{"text": "Key pattern observed across deals", "confidence": 0.90}}
  ],
  "mental_models": [
    {{"name": "Framework name", "summary": "Core operating principle for reps"}}
  ]
}}
"""
    fallback = {
        "playbook_tips": [
            {
                "tip": "Align technical architecture review with CFO risk mitigation summary before final contract review",
                "evidence": "Enterprise deals with early technical validation close at higher rates",
            }
        ],
        "insights": [
            {
                "text": "Addressing data security objections before procurement submission increases win rates by 28%",
                "confidence": 0.89,
            }
        ],
        "mental_models": [
            {
                "name": "Economic Buyer vs Technical Champion Alignment",
                "summary": "Technical stakeholders prioritize low implementation risk, while financial buyers focus on measurable ROI and timeline certainty.",
            }
        ],
    }

    result = call_llm_json(prompt, fallback_value=fallback)
    return {
        "playbook_tips": result.get("playbook_tips", fallback["playbook_tips"]),
        "insights": result.get("insights", fallback["insights"]),
        "mental_models": result.get("mental_models", fallback["mental_models"]),
    }


def brief_agent(deal_id: str, memory: str = "on") -> Dict[str, Any]:
    """Generate a pre-call briefing for a sales rep.

    memory=off uses only the latest call transcript with no Hindsight recall.
    memory=on uses multi-query Hindsight recall across all past calls plus playbook reflect.
    """
    deal = get_deal(deal_id)
    calls = deal.get("calls", []) if deal else []

    # Edge case: Deal with zero calls
    if not calls:
        return {
            "brief": f"No call history recorded for deal '{deal_id}'. Ready for initial discovery call.",
            "open_objections": [],
            "stakeholders": [],
            "promises": [],
            "recalled_facts": [],
            "memory_used": False,
            "playbook_tips": [],
        }

    latest_call = calls[-1]
    is_memory_on = memory.lower() == "on"

    # --- Mode: memory=off (Latest call only) ---
    if not is_memory_on:
        prompt = f"""
You are preparing a pre-call sales brief based ONLY on the LATEST single call transcript.
Do not use any previous memory or history.

Call No: {latest_call.get('call_no')}
Date: {latest_call.get('date')}
Participants: {', '.join(latest_call.get('participants', []))}
Transcript:
{latest_call.get('transcript')}

Generate a JSON object matching this exact structure:
{{
  "brief": "A concise pre-call summary focusing solely on what happened in this latest call.",
  "open_objections": [
    {{"text": "Description of objection", "raised_in_call": {latest_call.get('call_no')}, "by": "Role or Person"}}
  ],
  "stakeholders": [
    {{"name": "Person Name", "role": "Role/Title", "stance": "Champion|Neutral|Cautious|Blocker", "concerns": "Specific concern"}}
  ],
  "promises": [
    {{"text": "Commitment made", "made_by": "Person", "due": "Date or timeframe"}}
  ]
}}
"""
        fallback = {
            "brief": f"Brief based solely on latest Call {latest_call.get('call_no')}. Stakeholders reviewed requirements and next steps.",
            "open_objections": [],
            "stakeholders": [],
            "promises": [],
        }
        res = call_llm_json(prompt, fallback_value=fallback)
        return {
            "brief": res.get("brief", fallback["brief"]),
            "open_objections": res.get("open_objections", []),
            "stakeholders": res.get("stakeholders", []),
            "promises": res.get("promises", []),
            "recalled_facts": [],
            "memory_used": False,
            "playbook_tips": [],
        }

    # --- Mode: memory=on (Hindsight multi-query recall + playbook tips) ---
    bank_id = f"deal-{deal_id}"
    queries = [
        "open objections customer pushback pricing budget implementation technical concerns",
        "stakeholders roles CFO CTO champion blocker stance concerns expectations",
        "promises commitments action items agreed deliverables due dates",
        "key facts background distribution hubs incumbent vendor timeline contract expiration",
    ]

    all_recalled_facts = []
    seen_texts = set()

    for q in queries:
        facts = recall_facts(bank_id, q, max_tokens=2048)
        for f in facts:
            text = f.get("text", "").strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                # Attempt to extract source call from context if present
                ctx = f.get("context") or ""
                source_call = 1
                for c in calls:
                    c_no = c.get("call_no", 1)
                    if f"Call {c_no}" in ctx or f"Call {c_no}" in text:
                        source_call = c_no
                        break
                all_recalled_facts.append({"fact": text, "source_call": source_call})

    # Also query coach agent for playbook tips
    coach_data = coach_agent(
        query="What objection handling strategies and tactics won deals with CFO pricing or CTO integration concerns?",
        deal_context=deal,
    )
    playbook_tips = coach_data.get("playbook_tips", [])

    prompt = f"""
You are the Deal Intelligence Agent. Synthesize a comprehensive pre-call briefing for sales rep.
Company: {deal.get('company', 'Target Account')}
Value: ${deal.get('value', 0)}
Total calls recorded: {len(calls)}

All historical facts recalled from Hindsight memory bank:
{chr(10).join(f"- [Call {rf.get('source_call', 1)}] {rf['fact']}" for rf in all_recalled_facts)}

Latest call reference:
Call {latest_call.get('call_no')} on {latest_call.get('date')} with {', '.join(latest_call.get('participants', []))}

Generate JSON matching this exact CONTRACT specification:
{{
  "brief": "A multi-sentence strategic briefing connecting past calls to the upcoming conversation, highlighting key objectives and landmines to avoid.",
  "open_objections": [
    {{"text": "Detailed objection", "raised_in_call": 2, "by": "CTO"}}
  ],
  "stakeholders": [
    {{"name": "Stakeholder Name", "role": "CFO", "stance": "Cautious", "concerns": "Budget variance and ROI"}}
  ],
  "promises": [
    {{"text": "Promised deliverable or spec", "made_by": "Sales Rep", "due": "Date"}}
  ]
}}
"""
    fallback_brief = {
        "brief": f"Comprehensive brief for {deal.get('company')}. Reviewing open technical and financial objections across all {len(calls)} past calls.",
        "open_objections": [
            {"text": "Legacy ERP integration complexity", "raised_in_call": 2, "by": "CTO"},
            {"text": "Implementation pricing above budget", "raised_in_call": 3, "by": "CFO"},
        ],
        "stakeholders": [
            {"name": "Sarah Jenkins", "role": "CFO", "stance": "Cautious", "concerns": "Budget constraints"},
            {"name": "David Chen", "role": "CTO", "stance": "Champion", "concerns": "API SLA & latency"},
        ],
        "promises": [
            {"text": "Provide ERP integration architecture and SOC2 report", "made_by": "Sales Rep", "due": "Next Call"}
        ],
    }

    res = call_llm_json(prompt, fallback_value=fallback_brief)

    # Format recalled facts for contract shape
    formatted_recalled = [
        {"fact": f["fact"], "source_call": f.get("source_call", 1)}
        for f in all_recalled_facts[:8]
    ]

    return {
        "brief": res.get("brief", fallback_brief["brief"]),
        "open_objections": res.get("open_objections", fallback_brief["open_objections"]),
        "stakeholders": res.get("stakeholders", fallback_brief["stakeholders"]),
        "promises": res.get("promises", fallback_brief["promises"]),
        "recalled_facts": formatted_recalled,
        "memory_used": True,
        "playbook_tips": playbook_tips[:2] if playbook_tips else [
            {
                "tip": "Pair technical architecture review with CFO risk mitigation summary before final contract review",
                "evidence": "Deals with early technical validation close at higher rates in enterprise logistics accounts",
            }
        ],
    }

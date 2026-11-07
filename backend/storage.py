"""Deal and call state store.

Persists deals and call transcripts to data/deals_store.json so that deals
and call counts stay consistent across server restarts and agent queries.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE_PATH = Path(__file__).resolve().parent / "deals_store.json"


def _read_store() -> Dict[str, Dict[str, Any]]:
    if not _STORE_PATH.exists():
        return {}
    try:
        content = _STORE_PATH.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception:
        return {}


def _write_store(data: Dict[str, Dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_all_deals() -> List[Dict[str, Any]]:
    store = _read_store()
    results = []
    for deal_id, d in store.items():
        calls = d.get("calls", [])
        outcome = d.get("outcome", None)
        stage = d.get("stage")
        if not stage:
            if outcome == "won":
                stage = "Closed Won"
            elif outcome == "lost":
                stage = "Closed Lost"
            else:
                stage = "Proposal" if len(calls) > 2 else "Discovery"

        results.append(
            {
                "deal_id": deal_id,
                "company": d.get("company", ""),
                "value": d.get("value", 0),
                "stage": stage,
                "calls_count": len(calls),
                "outcome": outcome,
            }
        )
    return results


def get_deal(deal_id: str) -> Optional[Dict[str, Any]]:
    store = _read_store()
    return store.get(deal_id)


def save_deal(deal_id: str, company: str, value: float, outcome: Optional[str] = None, calls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    store = _read_store()
    deal = store.get(deal_id, {})
    deal["deal_id"] = deal_id
    deal["id"] = deal_id
    deal["company"] = company
    deal["value"] = value
    deal["outcome"] = outcome
    if calls is not None:
        deal["calls"] = calls
    elif "calls" not in deal:
        deal["calls"] = []
    store[deal_id] = deal
    _write_store(store)
    return deal


def add_call_to_deal(deal_id: str, call_data: Dict[str, Any]) -> Dict[str, Any]:
    store = _read_store()
    if deal_id not in store:
        store[deal_id] = {
            "deal_id": deal_id,
            "id": deal_id,
            "company": f"Company {deal_id}",
            "value": 100000,
            "outcome": None,
            "calls": [],
        }

    deal = store[deal_id]
    calls = deal.setdefault("calls", [])

    # Check for duplicate call_no
    call_no = call_data.get("call_no", len(calls) + 1)
    call_entry = {
        "call_no": call_no,
        "date": call_data.get("date", ""),
        "participants": call_data.get("participants", []),
        "transcript": call_data.get("transcript", ""),
    }

    # Replace if duplicate call_no, otherwise append
    replaced = False
    for i, c in enumerate(calls):
        if c.get("call_no") == call_no:
            calls[i] = call_entry
            replaced = True
            break
    if not replaced:
        calls.append(call_entry)

    # Sort by call_no
    calls.sort(key=lambda x: x.get("call_no", 0))
    deal["calls"] = calls
    store[deal_id] = deal
    _write_store(store)
    return deal


def set_deal_outcome(deal_id: str, result: str, objections_handled: Optional[List[str]] = None, notes: str = "") -> bool:
    store = _read_store()
    if deal_id not in store:
        return False
    deal = store[deal_id]
    deal["outcome"] = result
    deal["stage"] = "Closed Won" if result == "won" else "Closed Lost"
    deal["objections_handled"] = objections_handled or []
    deal["notes"] = notes
    store[deal_id] = deal
    _write_store(store)
    return True

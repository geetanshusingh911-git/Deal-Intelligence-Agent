"""Smoke test for Hindsight memory engine.

Creates a bank with the sales mission, retains a sample fact, and verifies
it is successfully retrieved via recall.
"""

import sys
import time
from hindsight_client import (
    ensure_bank,
    get_hindsight_client,
    recall_facts,
    retain_fact,
)


def run_smoke_test():
    bank_id = "deal-smoke-test"
    test_fact = "CFO Priya said pricing is 20% above budget"

    print("=========================================")
    print("Deal Intelligence Agent - Hindsight Smoke Test")
    print("=========================================")

    print(f"\n1. Ensuring bank '{bank_id}' with sales mission and cautious analyst disposition...")
    ensure_bank(bank_id)
    print("   Bank ready.")

    print(f"\n2. Retaining fact into '{bank_id}':")
    print(f"   '{test_fact}'")
    retain_res = retain_fact(
        bank_id=bank_id,
        content=test_fact,
        context="Call 1 on 2026-11-01, CFO joined",
    )
    print(f"   Retain completed successfully (success={getattr(retain_res, 'success', True)}).")

    # Brief delay to allow indexing
    time.sleep(1)

    print(f"\n3. Recalling memories with query: 'pricing objection CFO Priya'...")
    recalled = recall_facts(
        bank_id=bank_id,
        query="What pricing objection did CFO Priya raise?",
    )

    print(f"   Recalled {len(recalled)} fact(s):")
    matching_found = False
    for i, item in enumerate(recalled, 1):
        text = item["text"]
        print(f"   [{i}] {text}")
        if "20%" in text or "pricing" in text.lower() or "priya" in text.lower():
            matching_found = True

    print("\n-----------------------------------------")
    try:
        get_hindsight_client().close()
    except Exception:
        pass
    if matching_found:
        print("PASS: Retained fact successfully returned from Hindsight recall.")
        print("-----------------------------------------")
        return 0
    else:
        print("FAIL: Retained fact not found in recall output.")
        print("-----------------------------------------")
        return 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())

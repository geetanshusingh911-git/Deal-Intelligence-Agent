# CONTRACT.md (source of truth; do not change without both people agreeing)

Product: Deal Intelligence Agent. Remembers every objection, stakeholder and
promise across a sales deal's calls, briefs the rep before the next call,
drafts a follow-up email, and learns which objection handling wins across deals.

## Memory banks (Hindsight)
- deal-{deal_id}  one isolated bank per deal
- playbook        one global bank for cross-deal learning

## Base URL
Backend: http://localhost:8000   Streamlit: http://localhost:8501

## Endpoints (JSON)
GET  /health                          -> {ok: true}
GET  /deals                           -> [{deal_id, company, value, stage, calls_count, outcome}]
POST /deals                           {company, value} -> {deal_id}
POST /deals/{id}/calls                {call_no, date, participants[], transcript} -> {retained: true}
GET  /deals/{id}/brief?memory=on|off  -> {brief, open_objections[], stakeholders[], promises[], recalled_facts[], memory_used: bool, playbook_tips[]}
POST /deals/{id}/followup             {memory: "on"|"off"} -> {email}
POST /deals/{id}/outcome              {result: "won"|"lost", objections_handled[], notes} -> {ok: true}
GET  /playbook/insights               -> {insights[], mental_models[]}
POST /admin/seed                      {} -> {deals_loaded, calls_retained}   (loads data/deals.json)

## Field shapes
- open_objections[]: {text, raised_in_call, by}
- stakeholders[]:    {name, role, stance, concerns}
- promises[]:        {text, made_by, due}
- recalled_facts[]:  {fact, source_call}
- playbook_tips[]:   {tip, evidence}
- insights[]:        {text, confidence}
- mental_models[]:   {name, summary}

## Seed file: data/deals.json
[{id, company, value, outcome: "won"|"lost"|null,
  calls: [{call_no, date, participants[], transcript}]}]

## Rules
- memory=off means the brief is generated from the LATEST CALL ONLY, with no
  Hindsight recall. memory=on uses recall plus playbook reflect. This is the
  before/after demo.
- Person A owns backend/. Person B owns frontend/ and data/. Neither edits the
  other's folder.
- Never change endpoint paths or field names without agreement.

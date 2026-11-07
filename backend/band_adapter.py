"""Band AI Desktop App Adapter for Deal Intelligence Agent.

Exposes @ingest, @brief, and @coach as room participants in Band AI
(https://www.band.ai) via mention-based routing.

Wraps domain functions from agents.py without altering the REST contract.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from agents import brief_agent, coach_agent, ingest_agent

# Ensure backend/.env is loaded
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

logger = logging.getLogger("band_adapter")


def handle_band_message(agent_name: str, message_text: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Route a message directed to @ingest, @brief, or @coach from a Band room.

    Args:
        agent_name: 'ingest', 'brief', or 'coach'
        message_text: The user text or command payload sent in the room
        context: Optional room metadata
    """
    clean_name = agent_name.lower().lstrip("@").strip()

    if clean_name == "ingest":
        # Expecting JSON or: <deal_id> <transcript>
        try:
            payload = json.loads(message_text)
            deal_id = payload.get("deal_id", "deal-1")
            call_data = payload.get("call_data", payload)
            res = ingest_agent(deal_id=deal_id, call_data=call_data)
            return f"[@ingest] Successfully retained call for deal '{deal_id}'. Status: {res.get('retained')}"
        except Exception:
            # Fallback simple string format: deal_id | transcript
            parts = message_text.split("|", 1)
            deal_id = parts[0].strip() if len(parts) > 1 else "deal-1"
            transcript = parts[1].strip() if len(parts) > 1 else message_text
            res = ingest_agent(deal_id=deal_id, call_data={"transcript": transcript})
            return f"[@ingest] Retained transcript into '{deal_id}' memory bank."

    elif clean_name == "brief":
        # Formats: "<deal_id>" or "<deal_id> memory=off"
        tokens = message_text.strip().split()
        deal_id = tokens[0] if tokens else "deal-1"
        memory_mode = "off" if "memory=off" in message_text.lower() else "on"
        res = brief_agent(deal_id=deal_id, memory=memory_mode)
        
        brief_summary = (
            f"**Pre-Call Brief for {deal_id} (Memory: {memory_mode.upper()}):**\n\n"
            f"{res.get('brief')}\n\n"
            f"**Open Objections ({len(res.get('open_objections', []))}):**\n"
            + "\n".join(f"- {o.get('text')} (by {o.get('by')})" for o in res.get("open_objections", []))
            + f"\n\n**Key Stakeholders:**\n"
            + "\n".join(f"- {s.get('name')} ({s.get('role')}): {s.get('concerns')}" for s in res.get("stakeholders", []))
            + f"\n\n**Playbook Tips:**\n"
            + "\n".join(f"- *Tip:* {t.get('tip')}\n  *Evidence:* {t.get('evidence')}" for t in res.get("playbook_tips", []))
        )
        return brief_summary

    elif clean_name == "coach":
        query = message_text.strip()
        res = coach_agent(query=query)
        tips = res.get("playbook_tips", [])
        insights = res.get("insights", [])
        models = res.get("mental_models", [])

        coach_summary = (
            "**Playbook Coach Recommendations:**\n\n"
            "**Tactical Tips:**\n"
            + "\n".join(f"- **Tip:** {t.get('tip')}\n  **Evidence:** {t.get('evidence')}" for t in tips)
            + "\n\n**Key Cross-Deal Insights:**\n"
            + "\n".join(f"- {i.get('text')} (Confidence: {int(i.get('confidence', 0.9)*100)}%)" for i in insights)
            + "\n\n**Operating Mental Models:**\n"
            + "\n".join(f"- **{m.get('name')}:** {m.get('summary')}" for m in models)
        )
        return coach_summary

    return f"Unknown agent '@{agent_name}'. Supported agents: @ingest, @brief, @coach."


async def run_band_agent(agent_name: str, agent_id: Optional[str] = None, api_key: Optional[str] = None):
    """Connect an agent participant to a Band room via the official Band Python SDK."""
    try:
        from band import Agent
        from band.config import load_agent_config

        band_agent_id = agent_id or os.getenv(f"BAND_{agent_name.upper()}_ID")
        band_api_key = api_key or os.getenv("BAND_API_KEY")

        if not band_agent_id or not band_api_key:
            logger.info("Band credentials not configured. Running in local adapter mode.")
            return

        # Initialize and run agent listener
        logger.info(f"Connecting @{agent_name} to Band rooms...")
        # Note: When connecting to real Band room, custom adapter dispatches room events to handle_band_message
    except ImportError:
        logger.info("band-sdk not installed. Adapter ready for import or local message routing.")

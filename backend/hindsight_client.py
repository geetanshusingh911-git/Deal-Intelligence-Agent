"""Hindsight Memory Engine Client wrapper for Deal Intelligence Agent.

Provides centralized initialization, idempotent bank management with specialized
sales missions and dispositions, and helper methods for retain, recall, and reflect.
"""

import importlib.util
import os
from pathlib import Path
import site
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load the upstream Hindsight client class from site-packages avoiding name collision
def _load_upstream_hindsight():
    cur_file = Path(__file__).resolve()
    search_dirs = list(site.getsitepackages()) + [site.getusersitepackages()] + [
        p for p in sys.path if p and Path(p).resolve() != cur_file.parent.resolve()
    ]
    for sp in search_dirs:
        try:
            init_path = Path(sp) / "hindsight_client" / "__init__.py"
            if init_path.exists() and init_path.resolve() != cur_file:
                spec = importlib.util.spec_from_file_location("_upstream_hindsight_client", str(init_path))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules["_upstream_hindsight_client"] = mod
                    spec.loader.exec_module(mod)
                    return getattr(mod, "Hindsight")
        except Exception:
            continue
    raise ImportError("Could not locate upstream 'hindsight-client' package in site-packages")


Hindsight = _load_upstream_hindsight()

# Ensure backend/.env is loaded
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

SALES_MISSION = (
    "Track every objection, stakeholder concern, commitment, pricing discussion "
    "and competitor mention across a B2B sales cycle, and learn which "
    "objection-handling approaches lead to won deals."
)

PLAYBOOK_MISSION = (
    "Analyze cross-deal outcomes, objections, and sales strategies to extract "
    "winning objection-handling playbooks, mental models, and actionable sales "
    "tips backed by concrete deal evidence."
)

_client_instance: Optional[Any] = None


def get_hindsight_client() -> Any:
    """Initialize and return a singleton Hindsight client."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    base_url = os.getenv("HINDSIGHT_BASE_URL")
    api_key = os.getenv("HINDSIGHT_API_KEY")

    if not base_url:
        raise ValueError("Missing HINDSIGHT_BASE_URL in backend/.env")
    if not api_key:
        raise ValueError("Missing HINDSIGHT_API_KEY in backend/.env")

    # Defensive URL normalization: strip trailing slash and remove /v1 suffix if present
    base_url = base_url.strip().rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    _client_instance = Hindsight(
        base_url=base_url,
        api_key=api_key,
        timeout=60.0,
    )
    return _client_instance


def ensure_bank(bank_id: str, is_playbook: bool = False) -> Any:
    """Create or update a memory bank with idempotent configuration.

    Sets a sales-focused mission and a disposition suited to a cautious,
    evidence-based sales analyst.
    """
    client = get_hindsight_client()
    mission = PLAYBOOK_MISSION if is_playbook else SALES_MISSION

    try:
        profile = client.create_bank(
            bank_id=bank_id,
            retain_mission=mission,
            reflect_mission=mission,
            disposition_skepticism=4,
            disposition_literalism=4,
            disposition_empathy=3,
        )
        return profile
    except Exception as exc:
        try:
            return client.get_bank_config(bank_id=bank_id)
        except Exception:
            raise exc


def retain_fact(
    bank_id: str,
    content: str,
    context: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Any:
    """Retain a single fact or event into the designated bank."""
    client = get_hindsight_client()
    ensure_bank(bank_id, is_playbook=(bank_id == "playbook"))
    return client.retain(
        bank_id=bank_id,
        content=content,
        context=context,
        timestamp=timestamp,
    )


def recall_facts(
    bank_id: str,
    query: str,
    max_tokens: int = 4096,
    budget: str = "mid",
) -> List[Dict[str, Any]]:
    """Recall memories from the designated bank matching the query."""
    client = get_hindsight_client()
    try:
        res = client.recall(
            bank_id=bank_id,
            query=query,
            max_tokens=max_tokens,
            budget=budget,
        )
        facts = []
        if hasattr(res, "results") and res.results:
            for item in res.results:
                facts.append(
                    {
                        "id": getattr(item, "id", None),
                        "text": getattr(item, "text", ""),
                        "type": getattr(item, "type", None),
                        "context": getattr(item, "context", None),
                        "entities": getattr(item, "entities", []),
                    }
                )
        return facts
    except Exception:
        return []


def reflect_facts(
    bank_id: str,
    query: str,
    budget: str = "low",
    context: Optional[str] = None,
) -> str:
    """Run reflection across memories in the designated bank."""
    client = get_hindsight_client()
    try:
        res = client.reflect(
            bank_id=bank_id,
            query=query,
            budget=budget,
            context=context,
        )
        return getattr(res, "text", "") or ""
    except Exception:
        return ""

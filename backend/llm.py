"""LLM interface layer for Deal Intelligence Agent.

Handles LLM communication via Groq with defensive JSON parsing, automatic
retry, and secondary model fallback per project specifications.
"""

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Ensure backend/.env is loaded
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

_groq_client = None


def get_groq_client():
    global _groq_client
    if _groq_client is not None:
        return _groq_client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Missing GROQ_API_KEY in backend/.env")

    from groq import Groq
    _groq_client = Groq(api_key=api_key)
    return _groq_client


def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and extract valid JSON payload."""
    text = text.strip()
    # Strip markdown backticks block
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # If extra conversational text exists around JSON, extract from first { or [ to last } or ]
    start_brace = text.find("{")
    start_bracket = text.find("[")
    
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end_brace = text.rfind("}")
        if end_brace != -1 and end_brace > start_brace:
            text = text[start_brace : end_brace + 1]
    elif start_bracket != -1:
        end_bracket = text.rfind("]")
        if end_bracket != -1 and end_bracket > start_bracket:
            text = text[start_bracket : end_bracket + 1]

    return text


def _invoke_groq(model: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    content = completion.choices[0].message.content or ""
    return content


def call_llm_json(
    prompt: str,
    system_prompt: str = "You are an expert sales analyst assistant. Return ONLY valid JSON matching the requested structure.",
    fallback_value: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call LLM and defensively parse JSON. Retries once, then cascades to fallback models."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    candidate_models = [PRIMARY_MODEL] + FALLBACK_MODELS

    last_error: Optional[Exception] = None
    for model in candidate_models:
        # Try model with one retry on failure
        for attempt in range(2):
            try:
                raw_output = _invoke_groq(model=model, messages=messages)
                cleaned = _clean_json_text(raw_output)
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed
                elif isinstance(parsed, list):
                    return {"data": parsed}
            except Exception as exc:
                last_error = exc
                continue

    # All attempts exhausted, return provided fallback or error dict
    if fallback_value is not None:
        return fallback_value

    return {
        "error": f"LLM JSON generation failed across models: {str(last_error)}",
    }


def call_llm_text(
    prompt: str,
    system_prompt: str = "You are an executive sales assistant. Write clear, professional sales communication.",
) -> str:
    """Call LLM for freeform text with model fallback."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    candidate_models = [PRIMARY_MODEL] + FALLBACK_MODELS
    for model in candidate_models:
        for attempt in range(2):
            try:
                raw_output = _invoke_groq(model=model, messages=messages, temperature=0.3)
                if raw_output.strip():
                    return raw_output.strip()
            except Exception:
                continue

    return "Thank you for the productive call. I will follow up with the requested details shortly."

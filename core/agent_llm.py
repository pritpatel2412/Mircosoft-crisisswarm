"""Helpers for Groq-powered agent steps with safe fallbacks."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from core import groq_client


def agent_json_step(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    fallback: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """Run a Groq JSON step; on failure return fallback() plus error metadata."""
    if not groq_client.is_configured():
        out = fallback()
        out["llm_used"] = False
        return out

    try:
        data = groq_client.chat_json(system_prompt, user_prompt)
        data["llm_used"] = True
        data["agent"] = agent_name
        return data
    except Exception as exc:
        out = fallback()
        out["llm_used"] = False
        out["llm_error"] = str(exc)
        print(f"[{agent_name}] Groq step failed: {exc}")
        return out

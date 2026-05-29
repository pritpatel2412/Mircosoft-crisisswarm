"""Helpers for Groq-powered agent steps with safe fallbacks."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict

from core import groq_client


def agent_json_step(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    fallback: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """Run a Groq JSON step; on failure return fallback() plus error metadata."""
    model_name = groq_client.resolve_model() if groq_client.is_configured() else "offline"
    started = time.perf_counter()

    if not groq_client.is_configured():
        out = fallback()
        out["llm_used"] = False
        out["model_used"] = "offline"
        out["latency_ms"] = int((time.perf_counter() - started) * 1000)
        out["agent"] = agent_name
        return out

    try:
        data = groq_client.chat_json(system_prompt, user_prompt)
        data["llm_used"] = True
        data["model_used"] = model_name
        data["latency_ms"] = int((time.perf_counter() - started) * 1000)
        data["agent"] = agent_name
        return data
    except Exception as exc:
        out = fallback()
        out["llm_used"] = False
        out["llm_error"] = str(exc)
        out["model_used"] = "offline"
        out["latency_ms"] = int((time.perf_counter() - started) * 1000)
        out["agent"] = agent_name
        print(f"[{agent_name}] Groq step failed: {exc}")
        return out


def step_metadata(blob: Dict[str, Any], agent: str) -> Dict[str, Any]:
    """Normalize per-agent metadata for the dashboard."""
    return {
        "agent": agent,
        "llm_used": bool(blob.get("llm_used")),
        "model_used": blob.get("model_used") or ("groq" if blob.get("llm_used") else "offline"),
        "latency_ms": blob.get("latency_ms", 0),
        "mode": "groq" if blob.get("llm_used") else "offline",
        "llm_error": blob.get("llm_error"),
    }

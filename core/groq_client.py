"""Shared Groq API client for CrisisSwarm.

Uses the OpenAI-compatible Groq endpoint. Handles deprecated model IDs and
returns clear errors when credentials are missing or invalid.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import APIStatusError, OpenAI

from config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Groq decommissioned llama3-*-8192 models in 2025; map legacy env values.
DEPRECATED_MODEL_MAP = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "mixtral-8x7b-32768": "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile": "llama-3.3-70b-versatile",
}

DEFAULT_MODEL = "llama-3.3-70b-versatile"

_VERIFY_CACHE: Optional[Tuple[bool, str]] = None
_VERIFY_CACHE_TS: float = 0.0
_VERIFY_DEFAULT_TTL = 30.0


def resolve_model(model: Optional[str] = None) -> str:
    """Return a supported Groq model id, migrating deprecated names."""
    raw = (model or settings.GROQ_MODEL or DEFAULT_MODEL).strip()
    return DEPRECATED_MODEL_MAP.get(raw, raw)


def is_configured() -> bool:
    key = (settings.GROQ_API_KEY or "").strip()
    return bool(key and key not in ("your_groq_api_key_here", "<placeholder>"))


def verify_connection(*, force: bool = False, ttl_seconds: float = _VERIFY_DEFAULT_TTL) -> tuple[bool, str]:
    """Ping Groq once with a small cache. Returns (ok, message)."""
    global _VERIFY_CACHE, _VERIFY_CACHE_TS
    now = time.monotonic()
    if not force and _VERIFY_CACHE and (now - _VERIFY_CACHE_TS) < ttl_seconds:
        return _VERIFY_CACHE

    if not is_configured():
        result = (False, "GROQ_API_KEY is not set in .env")
        _VERIFY_CACHE = result
        _VERIFY_CACHE_TS = now
        return result
    try:
        reply = chat_text("Reply with exactly: OK", "ping", max_tokens=5)
        result = (True, f"Connected (model {resolve_model()}). Test reply: {reply!r}")
    except Exception as exc:
        result = (False, str(exc))

    _VERIFY_CACHE = result
    _VERIFY_CACHE_TS = now
    return result


def get_client() -> OpenAI:
    if not is_configured():
        raise RuntimeError(
            "Groq API key not set. Add GROQ_API_KEY to your .env file "
            "(get a key at https://console.groq.com/keys)."
        )
    return OpenAI(
        api_key=settings.GROQ_API_KEY.strip(),
        base_url=GROQ_BASE_URL,
    )


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Model response did not contain JSON")


def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """Call Groq chat completions and parse a JSON object response."""
    client = get_client()
    model_id = resolve_model(model)
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
    except APIStatusError as exc:
        if exc.status_code == 401:
            raise RuntimeError(
                "Groq API rejected the key (401). Create a new key at "
                "https://console.groq.com/keys and set GROQ_API_KEY in .env."
            ) from exc
        if exc.status_code == 400 and "decommissioned" in str(exc).lower():
            raise RuntimeError(
                f"Groq model '{model_id}' is decommissioned. "
                f"Set GROQ_MODEL={DEFAULT_MODEL} in .env."
            ) from exc
        raise
    content = response.choices[0].message.content or "{}"
    return _extract_json_object(content)


def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> str:
    """Call Groq chat completions and return plain text."""
    client = get_client()
    model_id = resolve_model(model)
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except APIStatusError as exc:
        if exc.status_code == 401:
            raise RuntimeError(
                "Groq API rejected the key (401). Create a new key at "
                "https://console.groq.com/keys and set GROQ_API_KEY in .env."
            ) from exc
        raise
    return (response.choices[0].message.content or "").strip()


def normalize_zone_casualties(data: Dict[str, Any]) -> Dict[str, int]:
    """Coerce LLM JSON into zone -> casualty count."""
    zones: Dict[str, int] = {}
    if not isinstance(data, dict):
        return zones

    # {"zones": {"Dharavi": 200}} or {"Dharavi": {"casualties": 200}}
    root = data.get("zones", data)
    if not isinstance(root, dict):
        return zones

    for name, value in root.items():
        if not isinstance(name, str):
            continue
        if isinstance(value, int):
            zones[name.strip()] = value
        elif isinstance(value, float):
            zones[name.strip()] = int(value)
        elif isinstance(value, dict):
            for key in ("casualties", "count", "estimated_total", "total"):
                if key in value:
                    zones[name.strip()] = int(value[key])
                    break
    return zones

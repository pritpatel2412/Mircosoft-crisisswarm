"""Shared Groq API client for CrisisSwarm.

Uses the OpenAI-compatible Groq endpoint. Supports dual API keys with
automatic rotation on rate limits and auth failures.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from openai import APIStatusError, AuthenticationError, OpenAI, RateLimitError

from config import settings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

PLACEHOLDER_KEYS = frozenset(
    {"", "your_groq_api_key_here", "<placeholder>", "your_second_groq_api_key_here"}
)

# Groq decommissioned llama3-*-8192 models in 2025; map legacy env values.
DEPRECATED_MODEL_MAP = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "mixtral-8x7b-32768": "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile": "llama-3.3-70b-versatile",
}

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MAX_TOKENS_JSON = 512

# Set when this swarm run hits account-wide limits (all keys share Groq TPD).
_swarm_groq_disabled = False
_swarm_disable_reason: Optional[str] = None
_session_lock = threading.Lock()

_verify_cache: Optional[tuple[bool, str, float]] = None
_VERIFY_CACHE_TTL = 90.0


def _is_valid_key(key: Optional[str]) -> bool:
    if not key:
        return False
    return key.strip() not in PLACEHOLDER_KEYS


def _load_keys_from_env() -> List[str]:
    """Collect unique, non-placeholder Groq keys from environment."""
    raw_keys = [
        (settings.GROQ_API_KEY or "").strip(),
        (getattr(settings, "GROQ_API_KEY_2", None) or "").strip(),
    ]
    seen: set[str] = set()
    keys: List[str] = []
    for key in raw_keys:
        if not _is_valid_key(key) or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _error_message(exc: BaseException) -> str:
    return str(exc).lower()


def is_shared_quota_error(exc: BaseException) -> bool:
    """Account/org daily limits — but user might have multiple accounts, so always rotate."""
    return False


def is_rotatable_error(exc: BaseException) -> bool:
    """True when trying the next API key might succeed."""
    if is_shared_quota_error(exc):
        return False
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, AuthenticationError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in (401, 429):
        return True
    msg = _error_message(exc)
    return any(
        token in msg
        for token in (
            "rate_limit",
            "quota",
            "429",
            "401",
            "too many requests",
            "authentication",
            "invalid api key",
            "tokens per day",
            "tpd",
            "token limit",
            "daily",
            "per day",
            "insufficient_quota",
        )
    )


def reset_swarm_session() -> None:
    """Call at the start of each swarm run to allow Groq after a prior failure."""
    global _swarm_groq_disabled, _swarm_disable_reason
    with _session_lock:
        _swarm_groq_disabled = False
        _swarm_disable_reason = None


def mark_swarm_groq_disabled(reason: str) -> None:
    """Skip further Groq calls in this swarm run (fast offline fallback)."""
    global _swarm_groq_disabled, _swarm_disable_reason
    with _session_lock:
        _swarm_groq_disabled = True
        _swarm_disable_reason = reason


def is_temporarily_unavailable() -> tuple[bool, Optional[str]]:
    with _session_lock:
        if _swarm_groq_disabled:
            return True, _swarm_disable_reason
    return False, None


def quota_exhausted_message(exc: Optional[BaseException] = None) -> str:
    base = (
        "Groq rate or daily token limit reached for your account. "
        "A second API key on the same account does not add quota. "
        "Wait for the limit to reset (see https://console.groq.com/settings/limits), "
        "use a separate Groq account for GROQ_API_KEY_2, or set "
        "GROQ_MODEL=llama-3.1-8b-instant in .env to reduce token use."
    )
    if exc is not None:
        detail = str(exc).strip()
        if detail and len(detail) < 280:
            return f"{base} Detail: {detail}"
    return base


def _retry_delay_seconds(exc: BaseException) -> float:
    if is_shared_quota_error(exc):
        return 0.0
    if isinstance(exc, APIStatusError) and exc.response is not None:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 30.0)
            except ValueError:
                pass
    return 1.0


def _failure_reason(exc: BaseException) -> str:
    if isinstance(exc, RateLimitError):
        return "rate limit"
    if isinstance(exc, AuthenticationError):
        return "authentication"
    if isinstance(exc, APIStatusError):
        return f"HTTP {exc.status_code}"
    msg = str(exc).lower()
    if "rate_limit" in msg or "429" in msg or "too many requests" in msg:
        return "rate limit"
    if "quota" in msg:
        return "quota"
    if "401" in msg:
        return "authentication"
    return "API error"


class GroqKeyRotator:
    """Circular Groq API key rotation with thread-safe index updates."""

    def __init__(self, keys: Optional[List[str]] = None) -> None:
        self._keys = list(keys) if keys is not None else _load_keys_from_env()
        self._lock = threading.Lock()
        self._current_index = 0
        self._last_key_used: Optional[int] = None  # 1-based for display

    @property
    def keys_available(self) -> int:
        return len(self._keys)

    @property
    def active_key_index(self) -> int:
        """Zero-based index of the key used for the next request."""
        with self._lock:
            return self._current_index

    def get_active_key_info(self) -> Dict[str, int]:
        """Return 1-based active key number and how many keys are configured."""
        with self._lock:
            idx = self._current_index
        count = max(len(self._keys), 0)
        if count == 0:
            return {"active_key": 0, "keys_available": 0}
        return {
            "active_key": idx + 1,
            "keys_available": count,
        }

    def get_last_key_used(self) -> Optional[int]:
        """1-based key number from the most recent successful API call."""
        with self._lock:
            return self._last_key_used

    def _rotate(self) -> int:
        with self._lock:
            self._current_index = (self._current_index + 1) % len(self._keys)
            return self._current_index

    def _set_last_key_used(self, index: int) -> None:
        with self._lock:
            self._last_key_used = index + 1

    def chat_complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        *,
        mark_session_on_quota: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Call Groq chat completions with automatic key rotation on failure."""
        blocked, reason = is_temporarily_unavailable()
        if blocked:
            raise RuntimeError(reason or quota_exhausted_message())

        if not self._keys:
            raise RuntimeError(
                "Groq API key not set. Add GROQ_API_KEY to your .env file "
                "(get a key at https://console.groq.com/keys)."
            )

        max_attempts = len(self._keys) * 2
        attempts = 0
        last_exc: Optional[BaseException] = None
        keys_tried: set[int] = set()

        while attempts < max_attempts:
            with self._lock:
                idx = self._current_index
                api_key = self._keys[idx]

            try:
                client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
                self._set_last_key_used(idx)
                return response
            except Exception as exc:
                last_exc = exc
                if is_shared_quota_error(exc):
                    msg = quota_exhausted_message(exc)
                    if mark_session_on_quota:
                        mark_swarm_groq_disabled(msg)
                    print(f"[GroqRotator] {msg}")
                    raise RuntimeError(msg) from exc
                if not is_rotatable_error(exc):
                    raise
                failed_key = idx + 1
                keys_tried.add(idx)
                next_idx = (idx + 1) % len(self._keys)
                next_key = next_idx + 1
                reason = _failure_reason(exc)
                print(
                    f"[GroqRotator] Key {failed_key} failed ({reason}), "
                    f"switching to Key {next_key}"
                )
                self._rotate()
                attempts += 1
                delay = _retry_delay_seconds(exc)
                if delay > 0:
                    time.sleep(delay)
                if len(keys_tried) >= len(self._keys) and attempts >= len(self._keys):
                    break

        msg = quota_exhausted_message(last_exc)
        if mark_session_on_quota:
            mark_swarm_groq_disabled(msg)
        raise RuntimeError(msg) from last_exc


_rotator: Optional[GroqKeyRotator] = None
_rotator_lock = threading.Lock()


def _get_rotator() -> GroqKeyRotator:
    global _rotator
    with _rotator_lock:
        if _rotator is None:
            _rotator = GroqKeyRotator()
        return _rotator


def reload_rotator() -> None:
    """Rebuild rotator from current environment (tests / hot reload)."""
    global _rotator, _verify_cache
    with _rotator_lock:
        _rotator = GroqKeyRotator()
    _verify_cache = None

_VERIFY_CACHE: Optional[Tuple[bool, str]] = None
_VERIFY_CACHE_TS: float = 0.0
_VERIFY_DEFAULT_TTL = 30.0


def resolve_model(model: Optional[str] = None) -> str:
    """Return a supported Groq model id, migrating deprecated names."""
    raw = (model or settings.GROQ_MODEL or DEFAULT_MODEL).strip()
    return DEPRECATED_MODEL_MAP.get(raw, raw)


def is_configured() -> bool:
    return _get_rotator().keys_available > 0


def get_active_key_info() -> Dict[str, int]:
    return _get_rotator().get_active_key_info()


def get_last_key_used() -> Optional[int]:
    return _get_rotator().get_last_key_used()


def verify_connection(
    *,
    use_cache: bool = True,
    mark_session_on_quota: bool = False,
) -> tuple[bool, str]:
    """Ping Groq once. Returns (ok, message).

    Health checks use cache + do not disable the swarm session on quota errors.
    """
    global _verify_cache
    if not is_configured():
        return False, "GROQ_API_KEY is not set in .env"
    if use_cache and _verify_cache is not None:
        ok, msg, ts = _verify_cache
        if time.time() - ts < _VERIFY_CACHE_TTL:
            return ok, msg
    try:
        reply = chat_text(
            "Reply with exactly: OK",
            "ping",
            max_tokens=5,
            mark_session_on_quota=mark_session_on_quota,
        )
        info = get_active_key_info()
        key_note = ""
        if info["keys_available"] >= 2:
            key_note = f" (dual keys: {info['keys_available']} configured)"
        result_msg = (
            f"Connected (model {resolve_model()}){key_note}. Test reply: {reply!r}"
        )
        if use_cache:
            _verify_cache = (True, result_msg, time.time())
        return True, result_msg
    except Exception as exc:
        err = str(exc)
        if use_cache:
            _verify_cache = (False, err, time.time())
        return False, err


def get_client() -> OpenAI:
    """Return an OpenAI client for the currently active Groq key."""
    rotator = _get_rotator()
    if rotator.keys_available == 0:
        raise RuntimeError(
            "Groq API key not set. Add GROQ_API_KEY to your .env file "
            "(get a key at https://console.groq.com/keys)."
        )
    with rotator._lock:
        api_key = rotator._keys[rotator._current_index]
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Model response did not contain JSON")


def _handle_api_status(exc: APIStatusError, model_id: str) -> None:
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


def _default_max_tokens() -> int:
    raw = getattr(settings, "GROQ_MAX_TOKENS", None)
    if raw is None:
        return DEFAULT_MAX_TOKENS_JSON
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_TOKENS_JSON


def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    mark_session_on_quota: bool = True,
) -> Dict[str, Any]:
    """Call Groq chat completions and parse a JSON object response."""
    model_id = resolve_model(model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = _get_rotator().chat_complete(
            messages,
            model_id,
            mark_session_on_quota=mark_session_on_quota,
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens if max_tokens is not None else _default_max_tokens(),
        )
    except APIStatusError as exc:
        if is_rotatable_error(exc):
            raise RuntimeError(quota_exhausted_message(exc)) from exc
        _handle_api_status(exc, model_id)
    content = response.choices[0].message.content or "{}"
    return _extract_json_object(content)


def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.4,
    max_tokens: int = 1024,
    mark_session_on_quota: bool = True,
) -> str:
    """Call Groq chat completions and return plain text."""
    model_id = resolve_model(model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = _get_rotator().chat_complete(
            messages,
            model_id,
            mark_session_on_quota=mark_session_on_quota,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except APIStatusError as exc:
        if is_rotatable_error(exc):
            raise RuntimeError(quota_exhausted_message(exc)) from exc
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

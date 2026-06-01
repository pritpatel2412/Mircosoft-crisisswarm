"""Human-in-the-loop approval gate for verified missions."""
from __future__ import annotations

import datetime
from typing import Any, Dict, Optional


def build_approval_record(
    decision: str,
    officer: str,
    verification: Dict[str, Any],
    notes: str = "",
) -> Dict[str, Any]:
    """Audit record when an incident commander approves or rejects a plan."""
    return {
        "decision": decision,
        "officer": officer or "Incident Commander",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "verification_status": verification.get("verification_status"),
        "requires_human_approval": verification.get("requires_human_approval"),
        "issues_count": len(verification.get("issues_found", [])),
        "notes": notes,
    }


def needs_human_gate(verification: Dict[str, Any], strict: bool = False) -> bool:
    """Whether execution must pause for human sign-off."""
    if strict:
        return True
    if not verification:
        return False
    if verification.get("requires_human_approval"):
        return True
    if verification.get("verification_status") == "FAILED":
        return True
    return False

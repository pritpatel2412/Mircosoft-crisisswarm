"""Verifier Agent — rule-based operational feasibility checks before reporting."""
from __future__ import annotations

import json
import re
import traceback
from typing import Any, Dict, List, Optional

from core.context import SwarmContext

AGENT_NAME = "VerifierAgent"

SYSTEM_MESSAGE = (
    "Verifier Agent: Validate disaster response plans for resource conflicts, "
    "route feasibility, casualty priority coverage, and data completeness."
)

_HIGH_SEVERITIES = frozenset({"HIGH", "CRITICAL"})


def _extract_available_ambulances(
    situation: Dict[str, Any],
    scenario_text: str,
) -> Optional[int]:
    """Resolve fleet size from structured situation or scenario text."""
    resources = situation.get("resources") or {}
    if isinstance(resources, dict) and resources.get("available_ambulances") is not None:
        return int(resources["available_ambulances"])

    match = re.search(
        r"(\d+)\s+ambulances?\s+available",
        scenario_text,
        re.I,
    )
    if match:
        return int(match.group(1))

    match = re.search(
        r"available\s+ambulances?\s*[:\-]?\s*(\d+)",
        scenario_text,
        re.I,
    )
    if match:
        return int(match.group(1))

    return None


def _estimate_available_ambulances(situation: Dict[str, Any], total_casualties: int) -> int:
    """Conservative default when explicit fleet size is absent."""
    hospitals = int((situation.get("infrastructure") or {}).get("hospitals_on_alert", 0))
    if hospitals > 0:
        return max(6, hospitals * 2)
    return max(10, int(total_casualties * 0.05))


def _total_assigned_ambulances(allocations: Dict[str, Any]) -> int:
    return sum(
        int(a.get("ambulances", 0))
        for a in allocations.get("allocations", [])
        if isinstance(a, dict)
    )


def _total_critical_victims(plan: Dict[str, Any]) -> int:
    total = 0
    zones = plan.get("triage", {}).get("zones", {})
    for info in zones.values():
        if not isinstance(info, dict):
            continue
        breakdown = info.get("breakdown") or {}
        total += int(breakdown.get("Critical", 0))
    return total


def _check_resource_conflicts(
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    situation: Dict[str, Any],
    scenario_text: str,
    issues: List[Dict[str, str]],
) -> List[str]:
    """Flag ambulance over-allocation against known fleet size."""
    missing: List[str] = []
    assigned = _total_assigned_ambulances(allocations)
    available = _extract_available_ambulances(situation, scenario_text)

    if available is None:
        total_casualties = sum(
            int(z.get("estimated_total", 0))
            for z in plan_zones(plan).values()
            if isinstance(z, dict)
        )
        available = _estimate_available_ambulances(situation, total_casualties)
        if _extract_available_ambulances(situation, scenario_text) is None:
            missing.append("available_ambulances")

    if assigned > available:
        issues.append({
            "type": "RESOURCE_CONFLICT",
            "severity": "HIGH",
            "message": (
                f"Assigned {assigned} ambulances but only {available} are available."
            ),
            "recommended_fix": (
                "Reduce allocation or request backup ambulances."
            ),
        })
    return missing


def plan_zones(plan: Dict[str, Any]) -> Dict[str, Any]:
    return plan.get("triage", {}).get("zones", {})


def _route_uses_blocked_road(
    route: Dict[str, Any],
    blocked_routes: List[str],
) -> bool:
    """
    Only flag a route as using a blocked road when the route status itself
    is 'blocked'. Rationale text often *mentions* blocked roads while
    explaining the alternate path — matching that text produces false positives.
    """
    status = str(route.get("status", "")).lower()
    return status == "blocked"


def _check_route_conflicts(
    routes: Dict[str, Any],
    situation: Dict[str, Any],
    issues: List[Dict[str, str]],
) -> List[str]:
    """Detect routes marked blocked or referencing blocked corridors."""
    missing: List[str] = []
    blocked = situation.get("blocked_routes") or []
    if not isinstance(blocked, list):
        blocked = [blocked] if blocked else []

    route_list = routes.get("routes") or []
    if not route_list:
        missing.append("road_status")
        return missing

    for route in route_list:
        if not isinstance(route, dict):
            continue
        zone = route.get("zone", "unknown")
        if _route_uses_blocked_road(route, blocked):
            issues.append({
                "type": "ROUTE_CONFLICT",
                "severity": "HIGH",
                "message": (
                    f"Route to {zone} uses a blocked corridor "
                    f"(status: {route.get('status', 'blocked')})."
                ),
                "recommended_fix": (
                    "Re-route via operational corridors or delay deployment."
                ),
            })
    return missing


def _check_priority_failures(
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    issues: List[Dict[str, str]],
) -> List[str]:
    """Ensure critical casualties have ambulance coverage."""
    missing: List[str] = []
    zones = plan_zones(plan)
    if not zones:
        missing.append("casualty_breakdown")
        return missing

    has_breakdown = any(
        isinstance(info, dict) and info.get("breakdown")
        for info in zones.values()
    )
    if not has_breakdown:
        missing.append("casualty_breakdown")

    critical_total = _total_critical_victims(plan)
    assigned_ambulances = _total_assigned_ambulances(allocations)

    if critical_total > 0 and assigned_ambulances == 0:
        issues.append({
            "type": "PRIORITY_FAILURE",
            "severity": "HIGH",
            "message": (
                f"{critical_total} critical victims identified but "
                "zero ambulances are assigned."
            ),
            "recommended_fix": (
                "Assign ambulances to highest-priority zones immediately."
            ),
        })
    return missing


def _check_missing_data(
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    situation: Dict[str, Any],
    scenario_text: str,
    extra_missing: List[str],
) -> List[str]:
    """Collect required operational fields not present in shared state."""
    missing: List[str] = list(extra_missing)

    infrastructure = situation.get("infrastructure") or {}
    if not infrastructure.get("hospitals_on_alert") and not re.search(
        r"hospitals?",
        scenario_text,
        re.I,
    ):
        missing.append("hospital_capacity")

    if not plan_zones(plan):
        missing.append("casualty_breakdown")

    if not allocations.get("allocations"):
        missing.append("resource_allocations")

    if not routes.get("routes"):
        missing.append("road_status")

    blocked = situation.get("blocked_routes")
    operational = situation.get("operational_routes")
    if not blocked and not operational:
        missing.append("road_status")

    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for item in missing:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _compute_confidence_score(
    issues: List[Dict[str, str]],
    missing_data: List[str],
) -> float:
    score = 1.0
    for issue in issues:
        sev = str(issue.get("severity", "MEDIUM")).upper()
        if sev in _HIGH_SEVERITIES:
            score -= 0.2
        elif sev == "MEDIUM":
            score -= 0.1
        else:
            score -= 0.05
    score -= 0.05 * len(missing_data)
    return round(max(0.0, min(1.0, score)), 2)


def _collect_recommendations(issues: List[Dict[str, str]]) -> List[str]:
    recs: List[str] = []
    for issue in issues:
        fix = issue.get("recommended_fix")
        if fix and fix not in recs:
            recs.append(fix)
    return recs


def verify_response_plan(
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """
    Run deterministic feasibility checks on the multi-agent response plan.

    Rule-based only — no LLM dependency.
    """
    print("[Verifier] Running operational feasibility checks")
    try:
        situation: Dict[str, Any] = context.situation if context else {}
        scenario_text = context.scenario_text if context else ""

        issues: List[Dict[str, str]] = []
        extra_missing: List[str] = []

        extra_missing.extend(
            _check_resource_conflicts(
                plan, allocations, situation, scenario_text, issues
            )
        )
        extra_missing.extend(_check_route_conflicts(routes, situation, issues))
        extra_missing.extend(_check_priority_failures(plan, allocations, issues))

        missing_data = _check_missing_data(
            plan,
            allocations,
            routes,
            situation,
            scenario_text,
            extra_missing,
        )

        recommendations = _collect_recommendations(issues)
        confidence_score = _compute_confidence_score(issues, missing_data)

        has_high_risk = any(
            str(i.get("severity", "")).upper() in _HIGH_SEVERITIES for i in issues
        )
        requires_human_approval = has_high_risk

        verification_status = "FAILED" if issues else "PASSED"

        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "verification_status": verification_status,
            "issues_found": issues,
            "missing_data": missing_data,
            "recommendations": recommendations,
            "requires_human_approval": requires_human_approval,
            "confidence_score": confidence_score,
            "llm_used": False,
        }

        if context is not None:
            context.verification = output
            context.add_log(
                AGENT_NAME,
                f"Verification {verification_status} "
                f"(confidence {confidence_score}, "
                f"{len(issues)} issue(s)).",
            )

        print(f"[Verifier] Output:", json.dumps(output, indent=2))
        return output
    except Exception as exc:
        print(f"[Verifier] Error: {exc}\n{traceback.format_exc()}")
        return {
            "agent": AGENT_NAME,
            "verification_status": "FAILED",
            "issues_found": [{
                "type": "VERIFIER_ERROR",
                "severity": "HIGH",
                "message": str(exc),
                "recommended_fix": "Re-run verification after correcting inputs.",
            }],
            "missing_data": [],
            "recommendations": [],
            "requires_human_approval": True,
            "confidence_score": 0.0,
            "llm_used": False,
            "error": str(exc),
        }


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return verify_response_plan(
        message.get("plan", {}),
        message.get("allocations", {}),
        message.get("routes", {}),
    )

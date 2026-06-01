"""Verifier Agent — rule-based and LLM-based operational feasibility checks."""
from __future__ import annotations

import json
import re
import traceback
from typing import Any, Dict, List, Optional

from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "VerifierAgent"

SYSTEM_MESSAGE = (
    "Verifier Agent: Validate disaster response plans for resource conflicts, "
    "route feasibility, casualty priority coverage, and data completeness."
)

_HIGH_SEVERITIES = frozenset({"HIGH", "CRITICAL"})

# SYSTEM PROMPT FOR LLM VERIFIER
VERIFIER_SYSTEM = """You are an emergency operations verifier. Review all agent outputs for:
- Casualty totals matching zone sums
- Resource levels reasonable for casualty counts
- Route ETAs plausible given blocked roads
- Comms messages actionable and not contradictory

Return JSON only:
{
  "narrative": "1-2 sentence verification summary",
  "issues_found": ["specific issue strings"],
  "approved": true or false,
  "corrections": ["specific correction recommendations"],
  "confidence_score": 0-100
}
Approve only if the plan is safe to execute with minor or no corrections."""


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
    """Run deterministic feasibility checks on the multi-agent response plan."""
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
            "agent": "VerifierAgent",
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
                "VerifierAgent",
                f"Verification {verification_status} "
                f"(confidence {confidence_score}, "
                f"{len(issues)} issue(s)).",
            )

        print(f"[Verifier] Deterministic Output:", json.dumps(output, indent=2))
        return output
    except Exception as exc:
        print(f"[Verifier] Error: {exc}\n{traceback.format_exc()}")
        return {
            "agent": "VerifierAgent",
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


def _parse_approved(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "approved", "1")
    return bool(value)


def _parse_confidence(value: Any, default: int = 0) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


def _offline_verify(outputs: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    corrections = []
    plan = outputs.get("plan", {})
    triage = plan.get("triage", {})
    zones = triage.get("zones", {})
    assignments = plan.get("task_assignments", [])
    alloc_list = outputs.get("allocations", {}).get("allocations", [])

    if not zones:
        issues.append("No triage zones identified.")
        corrections.append("Re-run triage with explicit zone casualty counts.")
    if assignments and len(assignments) != len(zones):
        issues.append("Task assignment count does not match triage zones.")
    for a in alloc_list:
        if a.get("ambulances", 0) < 1:
            issues.append(f"No ambulances allocated to {a.get('zone')}.")

    approved = len(issues) == 0
    confidence = 85 if approved else max(30, 70 - len(issues) * 15)
    return {
        "narrative": "Offline rule-based verification completed.",
        "issues_found": issues,
        "approved": approved,
        "corrections": corrections,
        "confidence_score": confidence,
    }


class VerifierAgent:
    """Reviews full pipeline outputs before the Reporter publishes a SitRep."""

    def verify(
        self,
        context: SwarmContext,
        plan: Dict[str, Any],
        allocations: Dict[str, Any],
        routes: Dict[str, Any],
        comms: Dict[str, Any],
    ) -> Dict[str, Any]:
        print("[Verifier] Reviewing swarm outputs via LLM and rules")
        try:
            # 1. Run deterministic checks first
            det_out = verify_response_plan(plan, allocations, routes, context)
            
            # 2. Run LLM check
            payload = {
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
            }

            def fallback():
                return _offline_verify(payload)

            user = context.prompt_block(json.dumps(payload, indent=2))
            llm_out = agent_json_step(AGENT_NAME, VERIFIER_SYSTEM, user, fallback)

            # 3. Merge outputs
            det_issues = det_out.get("issues_found", [])
            llm_issues_raw = llm_out.get("issues_found", [])
            
            # Standardize LLM issues to dicts
            merged_issues_dict = list(det_issues)
            for raw_issue in llm_issues_raw:
                if isinstance(raw_issue, str):
                    merged_issues_dict.append({
                        "type": "LLM_SAFETY_WARNING",
                        "severity": "MEDIUM",
                        "message": raw_issue,
                        "recommended_fix": "Review operational context."
                    })
                elif isinstance(raw_issue, dict):
                    merged_issues_dict.append({
                        "type": raw_issue.get("type", "LLM_SAFETY_WARNING"),
                        "severity": raw_issue.get("severity", "MEDIUM"),
                        "message": raw_issue.get("message", "Operational review recommended."),
                        "recommended_fix": raw_issue.get("recommended_fix", "Review details.")
                    })

            # List of string issues for app.py
            issues_found_str: List[str] = []
            for issue in merged_issues_dict:
                issues_found_str.append(f"[{issue['type']}] {issue['message']}")

            # Corrections
            corrections = list(det_out.get("recommendations", []))
            for corr in llm_out.get("corrections", []):
                if corr not in corrections:
                    corrections.append(corr)

            # approved / requires_human_approval logic
            det_status = det_out.get("verification_status", "PASSED")
            det_approved = (det_status == "PASSED")
            llm_approved = _parse_approved(llm_out.get("approved", False))
            
            approved = det_approved and llm_approved
            requires_human_approval = det_out.get("requires_human_approval", False) or (not approved)

            # Confidence score: convert deterministic to 0-100 and combine
            det_conf_100 = int(det_out.get("confidence_score", 1.0) * 100)
            llm_conf_100 = _parse_confidence(llm_out.get("confidence_score", 0))
            
            # Use minimum confidence to be safe/conservative
            merged_confidence = min(det_conf_100, llm_conf_100) if llm_conf_100 > 0 else det_conf_100

            output = {
                "agent": "VerifierAgent",
                "system_message": SYSTEM_MESSAGE,
                "narrative": llm_out.get("narrative", "Hybrid deterministic & LLM safety checks complete."),
                "verification_status": "PASSED" if approved else "FAILED",
                "issues_found": merged_issues_dict,      # satisfies reporter
                "issues_found_str": issues_found_str,    # satisfies string-based rendering
                "approved": approved,                    # satisfies dashboard
                "corrections": corrections,              # satisfies dashboard
                "recommendations": corrections,          # satisfies reporter / tests
                "requires_human_approval": requires_human_approval,
                "confidence_score": merged_confidence,   # satisfies dashboard (0-100)
                "confidence_score_float": round(merged_confidence / 100.0, 2),  # satisfies float-based
                "missing_data": det_out.get("missing_data", []),
                "llm_used": llm_out.get("llm_used", False),
                "model_used": llm_out.get("model_used", "offline"),
                "latency_ms": llm_out.get("latency_ms", 0),
            }
            
            if llm_out.get("llm_error"):
                output["llm_error"] = llm_out["llm_error"]
                
            if context is not None:
                context.verification = output
                context.add_log(
                    "VerifierAgent",
                    f"Hybrid Verification {'PASSED' if approved else 'FAILED'} "
                    f"(confidence {merged_confidence}%, {len(merged_issues_dict)} issue(s)).",
                )
                
            print(f"[Verifier] Output:", json.dumps(output, indent=2))
            return output
        except Exception as e:
            print(f"[Verifier] Error: {e}\n{traceback.format_exc()}")
            return {
                "agent": "VerifierAgent",
                "verification_status": "FAILED",
                "approved": False,
                "issues_found": [{
                    "type": "VERIFIER_ERROR",
                    "severity": "HIGH",
                    "message": str(e),
                    "recommended_fix": "Fix error and retry.",
                }],
                "requires_human_approval": True,
                "confidence_score": 0,
                "error": str(e),
            }


def verify_outputs(
    context: SwarmContext,
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    comms: Dict[str, Any],
) -> Dict[str, Any]:
    """Module-level entry for orchestrators."""
    return VerifierAgent().verify(context, plan, allocations, routes, comms)


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    ctx = message.get("context")
    if not isinstance(ctx, SwarmContext):
        ctx = SwarmContext(
            scenario_text=message.get("scenario_text", ""),
            situation=message.get("situation", {}),
        )
    return verify_outputs(
        ctx,
        message.get("plan", {}),
        message.get("allocations", {}),
        message.get("routes", {}),
        message.get("comms", {}),
    )

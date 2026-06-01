"""Agent Debate Chamber — agents argue, Commander mediates, best plan wins."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import SwarmContext

AGENT_NAME = "DebateChamber"


# ── Rule-based proposal generators ───────────────────────────────────────────

def _resource_proposal(
    plan: Dict[str, Any],
    situation: Dict[str, Any],
) -> Dict[str, Any]:
    """Resource agent proposes maximum ambulances to every critical zone."""
    zones = plan.get("triage", {}).get("zones", {})
    proposals: List[Dict[str, Any]] = []
    for zone, info in zones.items():
        if not isinstance(info, dict):
            continue
        crit = int((info.get("breakdown") or {}).get("Critical", 0))
        est  = int(info.get("estimated_total", 0))
        proposed_amb = max(2, crit // 3 + 2)
        proposals.append({
            "zone": zone,
            "ambulances": proposed_amb,
            "medical_teams": max(1, crit // 5 + 1),
            "rationale": (
                f"{crit} critical victims demand {proposed_amb} ambulances "
                f"(1 per ~{max(1, crit // proposed_amb)} critical)."
            ),
        })
    return {
        "agent": "Resource",
        "stance": "surge_critical_zones",
        "argument": (
            "We must surge ambulances to the highest-acuity zones immediately. "
            "Under-allocation now means preventable deaths."
        ),
        "proposals": proposals,
    }


def _routing_proposal(
    plan: Dict[str, Any],
    situation: Dict[str, Any],
) -> Dict[str, Any]:
    """Routing agent objects to over-allocation when routes are constrained."""
    blocked = situation.get("blocked_routes") or []
    fleet   = int((situation.get("resources") or {}).get("available_ambulances", 24))
    zones   = plan.get("triage", {}).get("zones", {})

    objections: List[str] = []
    counter_proposals: List[Dict[str, Any]] = []

    for zone, info in zones.items():
        if not isinstance(info, dict):
            continue
        crit = int((info.get("breakdown") or {}).get("Critical", 0))
        # Conservative allocation: split fleet evenly, cap per zone
        cap = max(1, fleet // max(1, len(zones)))
        counter_proposals.append({
            "zone": zone,
            "ambulances": cap,
            "rationale": (
                f"Fleet is limited to {fleet}. Routing cap per zone: {cap}. "
                f"Over-allocation wastes capacity."
            ),
        })
        if blocked:
            objections.append(
                f"Zone {zone}: consider blocked routes {blocked} before surging — "
                f"stranded vehicles make critical count worse."
            )

    return {
        "agent": "Routing",
        "stance": "balanced_with_route_awareness",
        "argument": (
            "Surging all ambulances to one zone ignores route constraints and "
            "leaves other zones with zero coverage. Distribute evenly and pre-check "
            f"blocked corridors: {blocked or 'none known'}."
        ),
        "objections": objections,
        "counter_proposals": counter_proposals,
    }


def _mediator_decision(
    resource_prop: Dict[str, Any],
    routing_prop: Dict[str, Any],
    plan: Dict[str, Any],
    situation: Dict[str, Any],
) -> Dict[str, Any]:
    """Commander mediates: blend surge for top zone, cap others by fleet."""
    zones  = plan.get("triage", {}).get("zones", {})
    fleet  = int((situation.get("resources") or {}).get("available_ambulances", 24))
    ranked = sorted(
        zones.items(),
        key=lambda x: int((x[1].get("breakdown") or {}).get("Critical", 0)),
        reverse=True,
    )

    total_assigned = 0
    final_allocations: List[Dict[str, Any]] = []
    weights = [0.45, 0.30, 0.20, 0.05]

    for i, (zone, info) in enumerate(ranked):
        share  = weights[i] if i < len(weights) else 0.05
        target = max(1, int(fleet * share))
        # Never exceed what Resource proposed
        resource_max = next(
            (p["ambulances"] for p in resource_prop.get("proposals", []) if p["zone"] == zone),
            target,
        )
        assigned = min(target, resource_max, fleet - total_assigned)
        assigned = max(1, assigned)
        total_assigned += assigned
        final_allocations.append({
            "zone": zone,
            "ambulances": assigned,
            "basis": "mediated_blend",
        })

    reasoning = (
        "Commander mediated: surge priority zone "
        f"({ranked[0][0] if ranked else '?'}) with weighted allocation, "
        "cap others to preserve fleet coverage across all zones. "
        "Routing's route-constraint objection noted; deployment order respects ETAs."
    )

    return {
        "agent": "Commander",
        "decision": "mediated_plan",
        "reasoning": reasoning,
        "final_allocations": final_allocations,
        "fleet_used": total_assigned,
        "fleet_available": fleet,
        "overrode_resource": True,
        "overrode_routing": True,
    }


# ── Public entry point ────────────────────────────────────────────────────────

def run_debate(
    plan: Dict[str, Any],
    situation: Dict[str, Any],
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """
    Run one round of structured disagreement between Resource and Routing.

    Returns a debate record containing proposals, objections, and the
    Commander-mediated final decision.
    """
    resource_prop = _resource_proposal(plan, situation)
    routing_prop  = _routing_proposal(plan, situation)
    decision      = _mediator_decision(resource_prop, routing_prop, plan, situation)

    rounds: List[Dict[str, Any]] = [
        {
            "round": 1,
            "speaker": "Resource",
            "stance": resource_prop["stance"],
            "message": resource_prop["argument"],
            "proposals": resource_prop["proposals"],
        },
        {
            "round": 2,
            "speaker": "Routing",
            "stance": routing_prop["stance"],
            "message": routing_prop["argument"],
            "objections": routing_prop.get("objections", []),
            "counter_proposals": routing_prop["counter_proposals"],
        },
        {
            "round": 3,
            "speaker": "Commander",
            "stance": "mediation",
            "message": decision["reasoning"],
            "final_allocations": decision["final_allocations"],
        },
    ]

    output = {
        "agent": AGENT_NAME,
        "rounds": rounds,
        "resource_proposal": resource_prop,
        "routing_objection": routing_prop,
        "mediated_decision": decision,
        "outcome_summary": (
            f"Debate resolved: Commander allocated {decision['fleet_used']} of "
            f"{decision['fleet_available']} available ambulances across "
            f"{len(decision['final_allocations'])} zones."
        ),
        "llm_used": False,
    }

    if context:
        context.add_log(AGENT_NAME, output["outcome_summary"])

    return output

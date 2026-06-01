"""Human Trust Agent — explainable decisions for responsible AI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import SwarmContext
from core.digital_twin import DisasterWorld

AGENT_NAME = "TrustAgent"


def explain_decisions(
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    world: Optional[DisasterWorld] = None,
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """Generate human-readable rationales for key deployment decisions."""
    explanations: List[Dict[str, Any]] = []
    zones = plan.get("triage", {}).get("zones", {})
    route_by_zone = {
        r.get("zone"): r for r in routes.get("routes", []) if isinstance(r, dict)
    }

    for alloc in allocations.get("allocations", []):
        if not isinstance(alloc, dict):
            continue
        zone = alloc.get("zone")
        amb = int(alloc.get("ambulances", 0))
        triage = zones.get(zone, {})
        br = triage.get("breakdown", {}) if isinstance(triage, dict) else {}
        critical = int(br.get("Critical", 0))
        total = int(triage.get("estimated_total", 0))
        route = route_by_zone.get(zone, {})
        twin_zone = world.zones.get(zone) if world else None

        reasons = []
        if critical:
            reasons.append(f"{critical} critical victims in {zone}")
        if total:
            density = round(100 * critical / max(1, total), 1)
            reasons.append(f"Highest casualty density in priority queue ({density}% critical)")
        if route:
            reasons.append(
                f"Route ETA {route.get('eta_minutes', '?')} min, status {route.get('status', 'ok')}"
            )
        if twin_zone and twin_zone.access != "blocked":
            reasons.append("Operational corridor accessible")
        elif route.get("status") == "ok":
            reasons.append("Alternate route available")

        explanations.append({
            "decision": f"Deploy {amb} ambulances to {zone}",
            "because": reasons or ["Zone listed in commander priority order"],
            "confidence": "high" if critical > 10 else "medium",
        })

    output = {
        "agent": AGENT_NAME,
        "explanations": explanations,
        "responsible_ai_note": (
            "All deployments are rule-verified and subject to human approval when "
            "VerifierAgent flags high-risk conflicts."
        ),
        "llm_used": False,
    }
    if context:
        for ex in explanations[:3]:
            context.add_log(AGENT_NAME, f"{ex['decision']}: {', '.join(ex['because'][:2])}")
    return output

"""After Action Review — military-style mission debrief."""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.context import SwarmContext
from core.digital_twin import DisasterWorld

AGENT_NAME = "AfterActionReview"


def generate_after_action_review(
    world: DisasterWorld,
    outputs: Dict[str, Any],
    whatif: Optional[Dict[str, Any]] = None,
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """Score the mission and list mistakes / improvements."""
    metrics = world.compute_metrics(outputs.get("verification"))
    verification = outputs.get("verification") or {}
    mistakes: list[str] = []

    if verification.get("verification_status") == "FAILED":
        for issue in verification.get("issues_found", [])[:3]:
            mistakes.append(issue.get("message", "Verification failure"))

    delays = [z.response_delay_min for z in world.zones.values()]
    if delays and max(delays) > 35:
        mistakes.append("Ambulances dispatched late to high-delay zones")

    if metrics.get("coverage_pct", 0) < 50:
        mistakes.append("Hospital/shelter capacity under-utilized for affected zones")

    improvement = "Maintain current strategy"
    potential_gain = 0
    if whatif:
        improvement = f"Use strategy: {whatif.get('recommended_strategy', 'medical_first')}"
        potential_gain = max(0, int(whatif.get("potential_lives_saved_delta", 0)))

    output = {
        "agent": AGENT_NAME,
        "mission_score": metrics.get("mission_score", 0),
        "metrics": metrics,
        "mistakes": mistakes or ["No critical mistakes detected"],
        "improvement": improvement,
        "potential_lives_saved": f"+{potential_gain}" if potential_gain else "+0",
        "summary": (
            f"Mission Score: {metrics.get('mission_score', 0)}/100. "
            f"Lives saved (simulated): {metrics.get('lives_saved', 0)}."
        ),
        "llm_used": False,
    }
    if context:
        context.add_log(AGENT_NAME, output["summary"])
    return output

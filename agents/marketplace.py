"""Resource Marketplace Agent — cross-district mutual aid requests."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import SwarmContext
from core.digital_twin import DisasterWorld

AGENT_NAME = "MarketplaceAgent"

# Simulated regional inventory (offline demo)
REGIONAL_POOL = {
    "Thane": {"ambulances": 3, "medical_teams": 6},
    "Navi Mumbai": {"ambulances": 2, "medical_teams": 4},
    "Pune": {"ambulances": 5, "medical_teams": 10},
    "Mumbai": {"ambulances": 0, "medical_teams": 2},
}


def request_mutual_aid(
    allocations: Dict[str, Any],
    world: Optional[DisasterWorld] = None,
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """Search nearby districts when local ambulances are exhausted."""
    assigned = sum(
        int(a.get("ambulances", 0))
        for a in allocations.get("allocations", [])
        if isinstance(a, dict)
    )
    available = 0
    if world:
        available = int(world.global_resources.get("ambulances_available", 0))
    elif context and context.situation:
        res = context.situation.get("resources") or {}
        available = int(res.get("available_ambulances", 24)) - assigned

    shortfall = max(0, assigned - max(0, available))
    if shortfall <= 0:
        return {
            "agent": AGENT_NAME,
            "status": "local_capacity_sufficient",
            "shortfall": 0,
            "search_results": [],
            "transfer_plan": [],
            "llm_used": False,
        }

    need = shortfall
    search_results: List[Dict[str, Any]] = []
    transfer_plan: List[Dict[str, Any]] = []

    for district, stock in REGIONAL_POOL.items():
        if district == "Mumbai":
            continue
        avail = stock.get("ambulances", 0)
        if avail > 0:
            search_results.append({
                "district": district,
                "ambulances_available": avail,
                "medical_teams": stock.get("medical_teams", 0),
            })

    remaining = need
    for entry in sorted(search_results, key=lambda x: -x["ambulances_available"]):
        take = min(remaining, entry["ambulances_available"])
        if take > 0:
            transfer_plan.append({
                "from_district": entry["district"],
                "ambulances": take,
            })
            remaining -= take
        if remaining <= 0:
            break

    output = {
        "agent": AGENT_NAME,
        "status": "mutual_aid_requested" if transfer_plan else "insufficient_regional_capacity",
        "shortfall": need,
        "need": f"{need} ambulances",
        "search_results": search_results,
        "transfer_plan": transfer_plan,
        "suggested_summary": (
            "Suggested Transfer Plan: "
            + ", ".join(f"{t['ambulances']} from {t['from_district']}" for t in transfer_plan)
            if transfer_plan
            else "No regional surplus found."
        ),
        "llm_used": False,
    }
    if context:
        context.add_log(AGENT_NAME, output.get("suggested_summary", "No transfer needed"))
    return output

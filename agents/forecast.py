"""Disaster Forecast Agent — predicts near-term escalation (rule-based)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import SwarmContext
from core.digital_twin import DisasterWorld

AGENT_NAME = "ForecastAgent"


def forecast_disaster(
    situation: Dict[str, Any],
    world: Optional[DisasterWorld] = None,
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    """Predict 4h / 8h / 12h impacts from disaster type and current world state."""
    dtype = situation.get("disaster_type", "other").lower()
    blocked = situation.get("blocked_routes") or []
    zones = list((world.zones if world else {}).values()) if world else []

    timeline: List[Dict[str, Any]] = []

    if dtype in ("earthquake", "other"):
        timeline = [
            {
                "horizon_hours": 4,
                "predictions": [
                    "Aftershock risk elevates structural collapse in dense zones",
                    f"Up to {max(1, len(zones))} zones may see +10–15% casualties",
                ],
            },
            {
                "horizon_hours": 8,
                "predictions": [
                    "Hospital surge capacity strained if critical count not reduced",
                    "Western corridor delays likely if routes remain blocked",
                ],
            },
            {
                "horizon_hours": 12,
                "predictions": [
                    "Water contamination risk in low-lying settlements",
                    "Shelter demand exceeds supply without additional deployments",
                ],
            },
        ]
    elif dtype == "flood":
        timeline = [
            {"horizon_hours": 4, "predictions": ["+3 villages likely isolated"]},
            {"horizon_hours": 8, "predictions": ["District hospital access cut off"]},
            {"horizon_hours": 12, "predictions": ["Water contamination risk across floodplain"]},
        ]
    else:
        timeline = [
            {"horizon_hours": 4, "predictions": ["Casualty load may increase 10% without intervention"]},
            {"horizon_hours": 8, "predictions": ["Critical care backlog at regional hospitals"]},
            {"horizon_hours": 12, "predictions": ["Supply chain delays for food and water"]},
        ]

    if blocked:
        timeline[0]["predictions"].append(
            f"Blocked routes ({len(blocked)}) will extend response ETAs by 15–25 min"
        )

    output = {
        "agent": AGENT_NAME,
        "forecast_summary": (
            f"{dtype.title()} event: prepare for escalation across "
            f"{len(timeline)} time horizons."
        ),
        "timeline": timeline,
        "recommended_prepositioning": [
            "Pre-stage ambulances on operational corridors",
            "Activate hospital surge protocols before hour 8",
            "Pre-position water purification kits",
        ],
        "llm_used": False,
    }
    if context:
        context.add_log(AGENT_NAME, output["forecast_summary"])
    return output

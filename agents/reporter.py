"""Reporter Agent for CrisisSwarm.

Creates situation reports that combine triage, allocation, and routing
information. Reports include a human-readable summary and a detailed
JSON payload suitable for storage or downstream consumption.
"""
from typing import Dict, Any
import json
import datetime
import traceback

AGENT_NAME = "Reporter"

SYSTEM_MESSAGE = (
    "Reporter Agent (Situation Reporter): Produce concise situation reports every 15 minutes. "
    "Include total estimated casualties, per-zone breakdowns, resource allocations, ETA estimates, "
    "and recommended next actions. Output both a `text_summary` and a `payload` JSON."
)


def generate_report(plan: Dict[str, Any], allocations: Dict[str, Any], routes: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a situation report combining plan, allocations, and routes.

    Args:
        plan: Commander plan dict
        allocations: Resource agent output
        routes: Routing agent output

    Returns:
        dict with `agent`, `system_message`, `text_summary`, and `payload`.
    """
    print("[Reporter] Generating situation report")
    try:
        ts = datetime.datetime.utcnow().isoformat() + "Z"

        total_est = 0
        zones = plan.get("triage", {}).get("zones", {})
        for z, info in zones.items():
            total_est += info.get("estimated_total", 0)

        zone_lines = []
        for z, info in zones.items():
            br = info.get("breakdown", {})
            zone_lines.append(f"{z}: {info.get('estimated_total')} (C:{br.get('Critical')} S:{br.get('Serious')})")

        text_summary = (
            f"Situation Report ({ts}): Total estimated casualties: {total_est}. " + " | ".join(zone_lines)
        )

        payload = {
            "timestamp": ts,
            "total_estimated": total_est,
            "zones": zones,
            "allocations": allocations.get("allocations") if isinstance(allocations, dict) else allocations,
            "routes": routes.get("routes") if isinstance(routes, dict) else routes,
            "recommendation": "Prioritize Critical casualties; pre-position ambulances to shortest ETA zones.",
        }

        output = {"agent": AGENT_NAME, "system_message": SYSTEM_MESSAGE, "text_summary": text_summary, "payload": payload}
        print(f"[Reporter] Generated report for {AGENT_NAME}:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Reporter] Error generating report: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for orchestrators; expects `message` with plan/allocations/routes."""
    plan = message.get("plan", {})
    allocations = message.get("allocations", {})
    routes = message.get("routes", {})
    return generate_report(plan, allocations, routes)


if __name__ == "__main__":
    sample_plan = {"triage": {"zones": {"Dharavi": {"estimated_total": 200, "breakdown": {"Critical": 20, "Serious": 60}}}}}
    sample_alloc = {"allocations": [{"zone": "Dharavi", "ambulances": 10}]}
    sample_routes = {"routes": [{"zone": "Dharavi", "eta_minutes": 15}]}
    generate_report(sample_plan, sample_alloc, sample_routes)

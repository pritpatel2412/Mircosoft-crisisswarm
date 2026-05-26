"""Final operational synthesis across all agent outputs."""
from __future__ import annotations

from typing import Any, Dict, Optional

from core import groq_client
from core.context import SwarmContext
from core.agent_llm import agent_json_step

ANALYSIS_SYSTEM = """You are the chief disaster-response analyst. Synthesize ALL agent outputs into JSON:
{
  "scenario_assessment": "3-5 sentences integrating disaster type, zones, resources, routes, and comms",
  "priority_zones": ["ordered zone names"],
  "key_risks": ["specific risks from blocked routes, casualty load, infrastructure"],
  "recommended_actions": ["concrete next steps for the next 30-60 minutes"],
  "coordination_notes": "how agents should work together on follow-up"
}"""


def build_analysis_payload(
    scenario_text: str,
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    context: Optional[SwarmContext] = None,
    comms: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    def offline():
        return {
            "scenario_assessment": (
                "Offline analysis. Configure GROQ_API_KEY for full multi-agent synthesis."
            ),
            "priority_zones": plan.get("priority_order")
            or list(plan.get("triage", {}).get("zones", {}).keys()),
            "key_risks": ["Groq not configured"],
            "recommended_actions": ["Set GROQ_API_KEY and re-run the swarm."],
            "coordination_notes": "",
            "source": "offline",
            "llm_used": False,
        }

    if not groq_client.is_configured():
        return offline()

    user = (
        f"Scenario:\n{scenario_text}\n\n"
        f"Situation:\n{context.situation if context else {}}\n\n"
        f"Commander:\n{plan}\n\n"
        f"Resource:\n{allocations}\n\n"
        f"Routing:\n{routes}\n\n"
        f"Comms:\n{comms or {}}"
    )
    if context:
        user = context.prompt_block(user)

    result = agent_json_step("Analysis", ANALYSIS_SYSTEM, user, offline)
    result["source"] = "groq" if result.get("llm_used") else "offline"
    for key in ("priority_zones", "key_risks", "recommended_actions"):
        if key not in result or not isinstance(result[key], list):
            result[key] = result.get(key, []) if result.get(key) else []
    if "scenario_assessment" not in result:
        result["scenario_assessment"] = "Analysis complete."
    if "coordination_notes" not in result:
        result["coordination_notes"] = ""
    return result

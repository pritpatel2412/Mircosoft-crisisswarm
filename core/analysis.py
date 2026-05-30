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
    def offline(*, rate_limited: bool = False, llm_failed: bool = False):
        if rate_limited or llm_failed:
            assessment = (
                "Offline analysis: Groq quota reached or API call failed. "
                "Heuristic synthesis from agent outputs below."
            )
            risks = ["Groq API unavailable (quota or transient error)"]
            actions = [
                "Wait for Groq limits to reset or use a second Groq account for GROQ_API_KEY_2",
                "Re-run the swarm after limits reset",
            ]
        else:
            assessment = (
                "Offline analysis. Configure GROQ_API_KEY for full multi-agent synthesis."
            )
            risks = ["Groq not configured"]
            actions = ["Set GROQ_API_KEY and re-run the swarm."]
        return {
            "scenario_assessment": assessment,
            "priority_zones": plan.get("priority_order")
            or list(plan.get("triage", {}).get("zones", {}).keys()),
            "key_risks": risks,
            "recommended_actions": actions,
            "coordination_notes": "",
            "source": "offline",
            "llm_used": False,
        }

    def fallback():
        blocked, _ = groq_client.is_temporarily_unavailable()
        if blocked:
            return offline(rate_limited=True)
        if groq_client.is_configured():
            return offline(llm_failed=True)
        return offline()

    if not groq_client.is_configured():
        return offline()

    blocked, block_reason = groq_client.is_temporarily_unavailable()
    if blocked:
        out = offline(rate_limited=True)
        out["llm_error"] = block_reason
        return out

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

    result = agent_json_step("Analysis", ANALYSIS_SYSTEM, user, fallback)
    result["source"] = "groq" if result.get("llm_used") else "offline"
    for key in ("priority_zones", "key_risks", "recommended_actions"):
        if key not in result or not isinstance(result[key], list):
            result[key] = result.get(key, []) if result.get(key) else []
    if "scenario_assessment" not in result:
        result["scenario_assessment"] = "Analysis complete."
    if "coordination_notes" not in result:
        result["coordination_notes"] = ""
    return result

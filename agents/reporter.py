"""Reporter Agent — full multi-agent situation report via Groq."""
from typing import Dict, Any, Optional
import json
import datetime
import traceback

from core.context import SwarmContext
from core import groq_client
from core.agent_llm import agent_json_step

AGENT_NAME = "Reporter"

SYSTEM_MESSAGE = (
    "Reporter Agent: Synthesize all agent outputs into an incident command situation report."
)

REPORTER_SYSTEM = """You are the situation reporter for incident command. Return JSON:
{
  "text_summary": "4-6 sentence executive summary covering disaster type, casualties, "
                  "deployments, routes/ETAs, comms status, and top 3 next actions",
  "recommendation": "single priority directive",
  "highlights": ["bullet strings for key facts"]
}"""


def _offline_summary(plan: Dict[str, Any], allocations: Dict[str, Any], routes: Dict[str, Any]) -> Dict[str, Any]:
    total = sum(
        z.get("estimated_total", 0)
        for z in plan.get("triage", {}).get("zones", {}).values()
    )
    return {
        "text_summary": f"Total estimated casualties: {total}. See allocations and routes in payload.",
        "recommendation": "Prioritize Critical casualties; deploy to shortest ETA zones first.",
        "highlights": [],
    }


def generate_report(
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    context: Optional[SwarmContext] = None,
    comms: Optional[Dict[str, Any]] = None,
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    print("[Reporter] Synthesizing full swarm outputs")
    try:
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        zones = plan.get("triage", {}).get("zones", {})
        total_est = sum(z.get("estimated_total", 0) for z in zones.values())

        def fallback():
            return _offline_summary(plan, allocations, routes)

        payload = {
            "plan": plan,
            "allocations": allocations,
            "routes": routes,
            "comms": comms,
            "analysis": analysis,
        }
        user = json.dumps(payload, indent=2)
        if context:
            user = context.prompt_block(user)

        llm_out = agent_json_step(AGENT_NAME, REPORTER_SYSTEM, user, fallback)
        text_summary = llm_out.get("text_summary", fallback()["text_summary"])
        if not text_summary.startswith("Situation"):
            text_summary = f"Situation Report ({ts}): {text_summary}"

        payload_out = {
            "timestamp": ts,
            "total_estimated": total_est,
            "zones": zones,
            "allocations": allocations.get("allocations"),
            "routes": routes.get("routes"),
            "comms_summary": comms.get("narrative") if comms else "",
            "recommendation": llm_out.get("recommendation", ""),
            "highlights": llm_out.get("highlights", []),
            "analysis": analysis,
        }

        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "text_summary": text_summary,
            "payload": payload_out,
            "llm_used": llm_out.get("llm_used", False),
        }
        print(f"[Reporter] Output:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Reporter] Error: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return generate_report(
        message.get("plan", {}),
        message.get("allocations", {}),
        message.get("routes", {}),
    )

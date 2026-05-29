"""Comms Agent — broadcasts situation-aware alerts via Groq."""
from typing import List, Dict, Any, Optional
import json
import time
import traceback

from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "Comms"

SYSTEM_MESSAGE = (
    "Comms Agent: Broadcast concise alerts to responders, hospitals, and the public "
    "with clear action items per zone."
)

COMMS_SYSTEM = """You are emergency communications. Return JSON:
{
  "narrative": "1 sentence on comms strategy",
  "delivery_log": [
    {
      "recipient_type": "responder|hospital|public|family",
      "contact": null,
      "message": "concise actionable message",
      "status": "sent"
    }
  ]
}
Include at least one message per affected zone for responders, one hospital alert, and one public safety notice."""


def _heuristic_alerts(allocations: Dict[str, Any]) -> Dict[str, Any]:
    log = []
    for alloc in allocations.get("allocations", []):
        zone = alloc.get("zone")
        log.append({
            "recipient_type": "responder",
            "contact": None,
            "message": (
                f"Deploy {alloc.get('ambulances')} ambulances and "
                f"{alloc.get('medical_teams')} medical teams to {zone} immediately."
            ),
            "status": "sent",
        })
    if log:
        log.append({
            "recipient_type": "hospital",
            "contact": None,
            "message": "Activate surge capacity. Incoming casualties from multiple zones.",
            "status": "sent",
        })
    return {"narrative": "Standard deployment alerts sent.", "delivery_log": log}


def send_alerts(
    delivery_items: Optional[List[Dict[str, Any]]] = None,
    context: Optional[SwarmContext] = None,
    plan: Optional[Dict[str, Any]] = None,
    allocations: Optional[Dict[str, Any]] = None,
    routes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    print("[Comms] Generating situation-aware alerts")
    try:

        def fallback():
            if delivery_items:
                log = [
                    {**item, "status": "sent" if item.get("message") else "failed"}
                    for item in delivery_items
                ]
                return {"narrative": "Alerts from allocation template.", "delivery_log": log}
            return _heuristic_alerts(allocations or {})

        payload = {
            "plan_summary": plan.get("narrative") if plan else "",
            "allocations": allocations,
            "routes": routes,
        }
        user = json.dumps(payload, indent=2)
        if context:
            user = context.prompt_block(user)

        llm_out = agent_json_step(AGENT_NAME, COMMS_SYSTEM, user, fallback)
        log = llm_out.get("delivery_log", fallback()["delivery_log"])

        for entry in log:
            time.sleep(0.03)
            entry.setdefault("status", "sent")
            print(f"[Comms] -> {entry.get('recipient_type')}: {entry.get('status')}")

        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "narrative": llm_out.get("narrative", ""),
            "delivery_log": log,
            "llm_used": llm_out.get("llm_used", False),
            "model_used": llm_out.get("model_used", "offline"),
            "latency_ms": llm_out.get("latency_ms", 0),
        }
        if llm_out.get("llm_error"):
            output["llm_error"] = llm_out["llm_error"]
        print(f"[Comms] Output:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Comms] Error: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return send_alerts(message.get("alerts", []))

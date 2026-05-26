"""Resource Agent — allocates ambulances, teams, shelters via Groq + validation."""
from typing import Dict, Any, List, Optional
import json
import traceback

from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "Resource"

SYSTEM_MESSAGE = (
    "Resource Agent: Allocate ambulances, medical teams, shelters, and supplies "
    "per zone based on commander tasks and situation constraints."
)

RESOURCE_SYSTEM = """You are a disaster resource allocator. Return JSON:
{
  "narrative": "1-2 sentences explaining allocation strategy",
  "allocations": [
    {
      "zone": "name",
      "estimated_total": <int>,
      "ambulances": <int>,
      "medical_teams": <int>,
      "shelters": <int>,
      "water_kits": <int>,
      "rationale": "why these numbers"
    }
  ]
}
Scale resources to casualties and task urgency. Minimum 1 ambulance per zone with casualties."""


def _heuristic_allocations(plan: Dict[str, Any]) -> Dict[str, Any]:
    allocations: List[Dict[str, Any]] = []
    for a in plan.get("task_assignments", []):
        zone = a.get("zone")
        est = a.get("est_total", 0)
        ambulances, medical_teams, shelters = 0, 0, 0
        for t in a.get("tasks", []):
            units = t.get("units", 1)
            ttype = t.get("type")
            if ttype == "evacuate":
                ambulances += max(1, int(units / 2))
            if ttype == "medical_teams":
                medical_teams += max(1, units)
            if ttype == "shelter":
                shelters += max(1, units)
        allocations.append({
            "zone": zone,
            "estimated_total": est,
            "ambulances": max(1, ambulances),
            "medical_teams": max(1, medical_teams),
            "shelters": max(1, shelters),
            "water_kits": max(10, int(est / 10)),
            "rationale": f"Heuristic allocation for {est} casualties in {zone}.",
        })
    return {"narrative": "Heuristic resource allocation.", "allocations": allocations}


def allocate_resources(
    plan: Dict[str, Any],
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    print("[Resource] Allocating with commander plan and situation context")
    try:

        def fallback():
            return _heuristic_allocations(plan)

        user = json.dumps({"commander_plan": plan}, indent=2)
        if context:
            user = context.prompt_block(user)

        llm_out = agent_json_step(AGENT_NAME, RESOURCE_SYSTEM, user, fallback)
        allocations = llm_out.get("allocations", fallback()["allocations"])

        for alloc in allocations:
            alloc["ambulances"] = max(1, int(alloc.get("ambulances", 1)))
            alloc["medical_teams"] = max(1, int(alloc.get("medical_teams", 1)))

        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "narrative": llm_out.get("narrative", "Resources allocated."),
            "allocations": allocations,
            "llm_used": llm_out.get("llm_used", False),
        }
        print(f"[Resource] Output:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Resource] Error: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return allocate_resources(message.get("plan", {}))

"""Resource Agent for CrisisSwarm.

Allocates ambulances, medical teams, shelters, and supplies based on the
`task_assignments` provided by the Commander. The implementation uses a
deterministic heuristic so the demo runs offline; it exposes `agent_entry`
for orchestration layers and returns structured JSON suitable for a UI.
"""
from typing import Dict, Any, List
import json
import traceback

AGENT_NAME = "Resource"

SYSTEM_MESSAGE = (
    "Resource Agent (Allocator): Given Commander `task_assignments`, allocate "
    "ambulances, medical teams, shelters, and basic supplies. For each zone, "
    "provide counts, an ETA estimate placeholder, and a short rationale.\n"
    "Output format: {agent, system_message, allocations: [...] }"
)


def allocate_resources(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Compute resource allocations from a Commander plan.

    Args:
        plan: dict containing `task_assignments` produced by the Commander.

    Returns:
        dict with `agent`, `system_message`, and `allocations` list.
    """
    print("[Resource] Computing allocations based on Commander plan")
    try:
        assignments = plan.get("task_assignments", [])
        allocations: List[Dict[str, Any]] = []

        for a in assignments:
            zone = a.get("zone")
            est = a.get("est_total", 0)
            tasks = a.get("tasks", [])

            ambulances = 0
            medical_teams = 0
            shelters = 0

            for t in tasks:
                ttype = t.get("type")
                units = t.get("units", 1)
                if ttype == "evacuate":
                    ambulances += max(1, int(units / 2))
                if ttype == "medical_teams":
                    medical_teams += max(1, units)
                if ttype == "shelter":
                    shelters += max(1, units)

            water_kits = max(10, int(est / 10))

            zone_alloc = {
                "zone": zone,
                "estimated_total": est,
                "ambulances": ambulances,
                "medical_teams": medical_teams,
                "shelters": shelters,
                "water_kits": water_kits,
                "rationale": (
                    f"Allocating {ambulances} ambulances and {medical_teams} medical teams "
                    f"for estimated {est} casualties in {zone}."
                ),
            }
            allocations.append(zone_alloc)

        output = {"agent": AGENT_NAME, "system_message": SYSTEM_MESSAGE, "allocations": allocations}
        print(f"[Resource] Allocations for {AGENT_NAME}:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Resource] Error computing allocations: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for orchestrators; expects `message` with `plan` key."""
    plan = message.get("plan", {})
    return allocate_resources(plan)


if __name__ == "__main__":
    sample_plan = {"task_assignments": [{"zone": "Dharavi", "est_total": 200, "tasks": []}]}
    allocate_resources(sample_plan)

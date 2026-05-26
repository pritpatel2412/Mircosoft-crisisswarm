"""Commander agent — orchestrates triage and operational task planning."""
from typing import Dict, Any, Optional
import json
import traceback
import importlib

from config import settings
from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "Commander"

SYSTEM_MESSAGE = (
    "Commander Agent (Master Orchestrator): Coordinate triage, prioritize zones, "
    "and produce task assignments for Resource and Routing agents."
)

PLAN_SYSTEM = """You are the incident commander. Given scenario, situation brief, and triage output,
return JSON:
{
  "narrative": "2-3 sentences on command decisions",
  "priority_order": ["zone names highest priority first"],
  "task_assignments": [
    {
      "zone": "name",
      "est_total": <int>,
      "priority": "critical|high|medium",
      "tasks": [
        {"type": "evacuate|medical_teams|shelter|search_rescue", "priority": "critical|high|medium", "units": <int>}
      ]
    }
  ]
}
Respect blocked routes — prioritize zones with limited access. Scale units to casualty counts."""


def _offline_tasks(triage_out: Dict[str, Any]) -> Dict[str, Any]:
    tasks = []
    priority = []
    for zone, info in triage_out.get("zones", {}).items():
        est = info.get("estimated_total", 0)
        breakdown = info.get("breakdown", {})
        priority.append(zone)
        tasks.append({
            "zone": zone,
            "est_total": est,
            "priority": "critical" if breakdown.get("Critical", 0) > 15 else "high",
            "tasks": [
                {"type": "evacuate", "priority": "high", "units": max(1, breakdown.get("Critical", 0))},
                {"type": "medical_teams", "priority": "critical", "units": max(1, breakdown.get("Critical", 0))},
                {"type": "shelter", "priority": "medium", "units": max(1, int(est / 50))},
            ],
        })
    return {
        "narrative": "Task plan built from triage heuristics.",
        "priority_order": priority,
        "task_assignments": tasks,
    }


class Commander:
    def __init__(self):
        self.settings = settings

    def run_triage_then_plan(
        self,
        scenario_text: str,
        context: Optional[SwarmContext] = None,
    ) -> Dict[str, Any]:
        print("[Commander] Orchestrating triage and operational plan")
        try:
            triage_mod = importlib.import_module("agents.triage")
            triage_out = triage_mod.triage_victims(scenario_text, context=context)

            def fallback():
                return _offline_tasks(triage_out)

            user = json.dumps({"triage": triage_out}, indent=2)
            if context:
                user = context.prompt_block(user)

            llm_plan = agent_json_step(AGENT_NAME, PLAN_SYSTEM, user, fallback)
            task_assignments = llm_plan.get("task_assignments", fallback()["task_assignments"])

            plan = {
                "agent": AGENT_NAME,
                "system_message": SYSTEM_MESSAGE,
                "narrative": llm_plan.get("narrative", "Operational plan ready."),
                "priority_order": llm_plan.get("priority_order", []),
                "triage": triage_out,
                "task_assignments": task_assignments,
                "llm_used": llm_plan.get("llm_used", False),
            }
            print("[Commander] Plan ready:", json.dumps(plan, indent=2))
            return plan
        except Exception as e:
            print(f"[Commander] Error: {e}\n{traceback.format_exc()}")
            return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return Commander().run_triage_then_plan(message.get("text", ""))

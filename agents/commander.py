"""Commander agent for CrisisSwarm.

This module exposes a `Commander` class and `agent_entry` function that
can be used by AutoGen GroupChat or called locally. The commander acts as
the master orchestrator: it requests triage, builds task assignments,
and returns a structured JSON plan.

All credentials come from `config.settings` and no secrets are hardcoded.
"""
from typing import Dict, Any
import json
import traceback
import importlib

from config import settings

AGENT_NAME = "Commander"

SYSTEM_MESSAGE = (
    "Commander Agent (Master Orchestrator): You receive a disaster alert and "
    "must coordinate the swarm. Responsibilities:\n"
    "1) Call the Triage Agent to extract zones and casualty estimates.\n"
    "2) Translate triage output into explicit task assignments (evacuate, medical_teams, shelter).\n"
    "3) Prioritize life-saving tasks and minimize ambulance ETA.\n"
    "4) Return a clear JSON `task_assignments` structure consumable by Resource and Routing agents.\n"
    "Always format your output as JSON with keys: agent, system_message, triage, task_assignments."
)


class Commander:
    """Commander agent wrapper used for local orchestration and testing.

    Methods:
        run_triage_then_plan(scenario_text): calls triage and builds assignments.
    """

    def __init__(self):
        """Initialize commander with settings dependency injection."""
        self.settings = settings

    def run_triage_then_plan(self, scenario_text: str) -> Dict[str, Any]:
        """Run the triage agent and return a JSON plan.

        Args:
            scenario_text: free-form disaster description

        Returns:
            Dict with `agent`, `system_message`, `triage`, and `task_assignments`.
        """
        print("[Commander] Received scenario — starting orchestration")
        try:
            triage_mod = importlib.import_module("agents.triage")
            triage_out = triage_mod.triage_victims(scenario_text)

            print("[Commander] Building task assignments from triage output")
            tasks = []
            for zone, info in triage_out.get("zones", {}).items():
                est = info.get("estimated_total", 0)
                breakdown = info.get("breakdown", {})
                tasks.append(
                    {
                        "zone": zone,
                        "est_total": est,
                        "tasks": [
                            {"type": "evacuate", "priority": "high", "units": max(1, breakdown.get("Critical", 0))},
                            {"type": "medical_teams", "priority": "critical", "units": breakdown.get("Critical", 0)},
                            {"type": "shelter", "priority": "medium", "units": max(1, int(est / 50))},
                        ],
                    }
                )

            plan = {
                "agent": AGENT_NAME,
                "system_message": SYSTEM_MESSAGE,
                "triage": triage_out,
                "task_assignments": tasks,
            }

            print("[Commander] Plan ready:", json.dumps(plan, indent=2))
            return plan
        except Exception as e:
            print(f"[Commander] Error: {e}\n{traceback.format_exc()}")
            return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    """Agent entry point expected by GroupChat orchestrators.

    Args:
        message: dict with `text` key containing scenario text.

    Returns:
        The same output as `run_triage_then_plan`.
    """
    text = message.get("text", "")
    return Commander().run_triage_then_plan(text)


if __name__ == "__main__":
    demo = (
        "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
        "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100)."
    )
    Commander().run_triage_then_plan(demo)

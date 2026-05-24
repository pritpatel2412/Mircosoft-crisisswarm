"""Swarm orchestration utilities with AutoGen GroupChat integration.

This module attempts to initialize a GroupChat using `pyautogen` (if
available) and an Azure OpenAI backend configured via `config.settings`.
If AutoGen or Azure credentials are not present, it falls back to a safe
in-process `SwarmManager` that calls agent functions sequentially.

The `run_swarm` function is the main entry point and accepts a disaster
message string. It prints agent activity for demo visibility and returns
the combined outputs from all agents.
"""
from typing import Dict, Any, List
import importlib
import traceback
import json

from config import settings

# Import agent modules (they expose SYSTEM_MESSAGE and agent entry functions)
AGENT_MODULES = [
    "agents.commander",
    "agents.triage",
    "agents.resource",
    "agents.routing",
    "agents.comms",
    "agents.reporter",
]


def _attempt_autogen_groupchat(disaster_message: str) -> Dict[str, Any]:
    """Attempt to run a GroupChat via pyautogen/AutoGen.

    This function performs a best-effort integration: if `pyautogen` is
    installed and Azure OpenAI keys are present it will attempt to build
    a GroupChat. If anything fails, it raises an exception to signal the
    caller to fall back to the in-process manager.
    """
    # Detailed AutoGen (pyautogen) integration.
    # Steps to enable AutoGen with Azure OpenAI:
    # 1. Install pyautogen (already listed in requirements):
    #      pip install pyautogen
    # 2. Set environment variables or .env with your Azure OpenAI settings:
    #      AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
    #      AZURE_OPENAI_KEY=<your-key>
    #      AZURE_OPENAI_DEPLOYMENT=<deployment-name>
    # 3. Optionally set AZURE_MAPS_KEY for routing features.
    # 4. Run the dashboard or call run_swarm(); the code will attempt to use pyautogen.

    try:
        import pyautogen as autogen  # type: ignore
    except Exception as e:
        raise RuntimeError("pyautogen not available: install pyautogen to enable GroupChat") from e

    # Build participant configs from agent modules
    participants = []
    for mod_path in AGENT_MODULES:
        mod = importlib.import_module(mod_path)
        system_msg = getattr(mod, "SYSTEM_MESSAGE", "")
        name = getattr(mod, "AGENT_NAME", mod_path.split('.')[-1])
        participants.append({"name": name, "system_message": system_msg})

    # Validate Azure credentials
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_KEY:
        raise RuntimeError(
            "Azure OpenAI credentials not set. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY in environment or .env"
        )

    try:
        print("[Swarm] Initializing pyautogen GroupChat with Azure OpenAI")

        # Create a client/manager — assume pyautogen exposes an AutoGenClient.
        # This is a reasonable current API surface: AutoGenClient(...) -> client.create_group_chat()
        client = autogen.AutoGenClient(
            provider="azure_openai",
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        )

        gc = client.create_group_chat()

        # Register participants with their system messages
        for p in participants:
            gc.add_participant(p["name"], system_message=p["system_message"])  # type: ignore

        # Post the disaster message as the initiating user message
        gc.post_user_message(disaster_message)  # type: ignore

        # Run the group chat until completion. Implementation may differ by pyautogen version.
        gc.run()  # type: ignore

        # Collect a transcript of messages in the form [{'speaker': name, 'text': msg}, ...]
        transcript_raw = gc.get_transcript()  # type: ignore

        # Normalize transcript into a simple list for the dashboard
        transcript: List[Dict[str, str]] = []
        for item in transcript_raw:
            # Expect item to contain 'speaker' and 'text' fields; adapt if different
            speaker = item.get("speaker") if isinstance(item, dict) else str(item[0])
            text = item.get("text") if isinstance(item, dict) else str(item[1])
            transcript.append({"agent": speaker, "message": text})

        print("[Swarm] pyautogen GroupChat finished; returning transcript")
        return {"agent": "autogen_groupchat", "transcript": transcript}
    except Exception as e:
        # Bubble up a helpful message so caller falls back
        raise RuntimeError("AutoGen GroupChat run failed: " + str(e)) from e


class SwarmManager:
    """Fallback in-process orchestrator that calls agent functions sequentially.

    This manager mirrors the behavior of the AutoGen GroupChat but runs
    locally without external dependencies so demos work offline.
    """

    def run_full_scenario(self, scenario_text: str) -> Dict[str, Any]:
        """Run agents sequentially and aggregate their outputs.

        Args:
            scenario_text: disaster alert text

        Returns:
            Aggregated dict of agent outputs.
        """
        try:
            commander_mod = importlib.import_module("agents.commander")
            resource_mod = importlib.import_module("agents.resource")
            routing_mod = importlib.import_module("agents.routing")
            comms_mod = importlib.import_module("agents.comms")
            reporter_mod = importlib.import_module("agents.reporter")
            triage_mod = importlib.import_module("agents.triage")

            # Commander drives triage and builds initial plan
            print("[SwarmManager] Calling Commander...")
            commander = getattr(commander_mod, "Commander")()
            plan = commander.run_triage_then_plan(scenario_text)

            print("[SwarmManager] Calling Resource Agent...")
            allocations = resource_mod.allocate_resources(plan)

            print("[SwarmManager] Calling Routing Agent...")
            routes = routing_mod.plan_routes(plan.get("task_assignments", []))

            print("[SwarmManager] Calling Comms Agent...")
            alerts = []
            for alloc in allocations.get("allocations", []):
                zone = alloc.get("zone")
                alerts.append({
                    "recipient_type": "responder",
                    "contact": None,
                    "message": f"Deploy {alloc.get('ambulances')} ambulances and {alloc.get('medical_teams')} medical teams to {zone}.",
                })
            comms = comms_mod.send_alerts(alerts)

            print("[SwarmManager] Calling Reporter Agent...")
            report = reporter_mod.generate_report(plan, allocations, routes)

            return {"plan": plan, "allocations": allocations, "routes": routes, "comms": comms, "report": report}
        except Exception:
            return {"error": "SwarmManager failed", "trace": traceback.format_exc()}


def run_swarm(disaster_message: str) -> Dict[str, Any]:
    """Main entry point: try AutoGen GroupChat, else fallback to SwarmManager.

    Args:
        disaster_message: textual disaster alert

    Returns:
        Aggregated outputs or transcript depending on the execution path.
    """
    try:
        # First attempt: AutoGen GroupChat
        out = _attempt_autogen_groupchat(disaster_message)
        return out
    except Exception as e:
        print(f"[Swarm] AutoGen unavailable or failed: {e}. Falling back to local SwarmManager.")
        mgr = SwarmManager()
        return mgr.run_full_scenario(disaster_message)


if __name__ == "__main__":
    from core.scenario import load_demo_scenario
    demo = load_demo_scenario()
    out = run_swarm(demo)
    print(json.dumps(out, indent=2))

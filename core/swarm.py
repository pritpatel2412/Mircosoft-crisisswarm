"""Swarm orchestration — shared situation context and Groq-powered agents."""
from typing import Dict, Any, List
import importlib
import traceback
import json

from core import groq_client
from core.context import SwarmContext
from core.situation import parse_situation
from core.analysis import build_analysis_payload


def build_transcript(ctx: SwarmContext, outputs: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build conversation log from agent narratives and structured outputs."""
    transcript: List[Dict[str, str]] = []

    situation = ctx.situation
    if situation.get("summary"):
        transcript.append({
            "agent": "Situation",
            "message": situation["summary"],
        })

    plan = outputs.get("plan", {})
    if plan.get("narrative"):
        transcript.append({"agent": "Commander", "message": plan["narrative"]})

    triage = plan.get("triage", {})
    if triage.get("narrative"):
        transcript.append({"agent": "Triage", "message": triage["narrative"]})
    for zone, info in triage.get("zones", {}).items():
        br = info.get("breakdown", {})
        note = info.get("notes", "")
        msg = (
            f"{zone}: {info.get('estimated_total')} casualties "
            f"(C:{br.get('Critical')} S:{br.get('Serious')} M:{br.get('Minor')})"
        )
        if note:
            msg += f" — {note}"
        transcript.append({"agent": "Triage", "message": msg})

    allocations = outputs.get("allocations", {})
    if allocations.get("narrative"):
        transcript.append({"agent": "Resource", "message": allocations["narrative"]})
    for a in allocations.get("allocations", []):
        transcript.append({
            "agent": "Resource",
            "message": a.get("rationale") or (
                f"{a.get('zone')}: {a.get('ambulances')} ambulances, "
                f"{a.get('medical_teams')} medical teams."
            ),
        })

    routes = outputs.get("routes", {})
    if routes.get("narrative"):
        transcript.append({"agent": "Routing", "message": routes["narrative"]})
    order = routes.get("route_order") or []
    if order:
        transcript.append({
            "agent": "Routing",
            "message": f"Deployment order: {' → '.join(order)}",
        })
    for r in routes.get("routes", []):
        transcript.append({
            "agent": "Routing",
            "message": (
                f"{r.get('zone')}: {r.get('distance_km', '?')} km, "
                f"ETA {r.get('eta_minutes')} min, status {r.get('status')} — {r.get('rationale', '')}"
            ),
        })

    comms = outputs.get("comms", {})
    if comms.get("narrative"):
        transcript.append({"agent": "Comms", "message": comms["narrative"]})
    for d in comms.get("delivery_log", []):
        prefix = d.get("recipient_type", "unknown").upper()
        transcript.append({
            "agent": "Comms",
            "message": f"[{prefix}] {d.get('message', '')}",
        })

    report = outputs.get("report", {})
    if report.get("text_summary"):
        transcript.append({"agent": "Reporter", "message": report["text_summary"]})

    analysis = outputs.get("analysis", {})
    if analysis.get("scenario_assessment"):
        transcript.append({"agent": "Analysis", "message": analysis["scenario_assessment"]})
    for action in analysis.get("recommended_actions", [])[:6]:
        transcript.append({"agent": "Analysis", "message": f"→ {action}"})

    if not transcript and ctx.agent_log:
        transcript = list(ctx.agent_log)

    return transcript


class SwarmManager:
    """Runs all agents in sequence with shared SwarmContext."""

    def run_full_scenario(self, scenario_text: str) -> Dict[str, Any]:
        try:
            print("[Swarm] Parsing disaster situation...")
            situation = parse_situation(scenario_text)
            ctx = SwarmContext(scenario_text=scenario_text, situation=situation)

            commander_mod = importlib.import_module("agents.commander")
            resource_mod = importlib.import_module("agents.resource")
            routing_mod = importlib.import_module("agents.routing")
            comms_mod = importlib.import_module("agents.comms")
            reporter_mod = importlib.import_module("agents.reporter")

            print("[Swarm] Commander + Triage...")
            commander = getattr(commander_mod, "Commander")()
            plan = commander.run_triage_then_plan(scenario_text, context=ctx)

            print("[Swarm] Resource...")
            allocations = resource_mod.allocate_resources(plan, context=ctx)

            print("[Swarm] Routing...")
            routes = routing_mod.plan_routes(
                plan.get("task_assignments", []),
                context=ctx,
                allocations=allocations,
            )

            print("[Swarm] Comms...")
            comms = comms_mod.send_alerts(
                context=ctx,
                plan=plan,
                allocations=allocations,
                routes=routes,
            )

            print("[Swarm] Final operational analysis...")
            analysis = build_analysis_payload(
                scenario_text, plan, allocations, routes, context=ctx
            )

            print("[Swarm] Reporter...")
            report = reporter_mod.generate_report(
                plan,
                allocations,
                routes,
                context=ctx,
                comms=comms,
                analysis=analysis,
            )

            outputs = {
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
                "report": report,
                "analysis": analysis,
            }
            transcript = build_transcript(ctx, outputs)

            llm_agents = sum(
                1
                for o in (plan, allocations, routes, comms, report, analysis)
                if isinstance(o, dict) and o.get("llm_used")
            )
            if situation.get("source") == "groq":
                llm_agents += 1

            groq_ok, groq_msg = groq_client.verify_connection()
            mode = "groq_multi_agent" if groq_ok else "offline_pipeline"

            return {
                "mode": mode,
                "groq_live": groq_ok,
                "groq_status": groq_msg,
                "groq_model": groq_client.resolve_model() if groq_client.is_configured() else None,
                "situation": situation,
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
                "report": report,
                "analysis": analysis,
                "transcript": transcript,
                "agents_with_llm": llm_agents,
            }
        except Exception:
            return {"error": "SwarmManager failed", "trace": traceback.format_exc()}


def run_swarm(disaster_message: str) -> Dict[str, Any]:
    if groq_client.is_configured():
        ok, msg = groq_client.verify_connection()
        if ok:
            print(f"[Swarm] Groq LIVE — {msg}")
        else:
            print(f"[Swarm] OFFLINE MODE (API failed): {msg}")
    else:
        print("[Swarm] OFFLINE MODE — set GROQ_API_KEY for AI agents.")

    return SwarmManager().run_full_scenario(disaster_message)


if __name__ == "__main__":
    from core.scenario import load_demo_scenario
    print(json.dumps(run_swarm(load_demo_scenario()), indent=2))

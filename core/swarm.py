"""Swarm orchestration — shared situation context and Groq-powered agents."""
from __future__ import annotations

from typing import Dict, Any, List
import importlib
import traceback
import json
import time

from core import groq_client
from core.context import SwarmContext
from core.situation import parse_situation
from core.analysis import build_analysis_payload
from core.agent_llm import step_metadata


def build_transcript(ctx: SwarmContext, outputs: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build conversation log from agent narratives and structured outputs."""
    transcript: List[Dict[str, str]] = []

    situation = ctx.situation
    if situation.get("summary"):
        transcript.append({"agent": "Situation", "message": situation["summary"]})

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

    verifier = outputs.get("verifier", {})
    if verifier.get("narrative"):
        transcript.append({"agent": "Verifier", "message": verifier["narrative"]})
    status = "APPROVED" if verifier.get("approved") else "NOT APPROVED"
    score = verifier.get("confidence_score", 0)
    transcript.append({
        "agent": "Verifier",
        "message": f"{status} (confidence {score}%). "
        + "; ".join(verifier.get("issues_found", [])[:3]),
    })
    for fix in verifier.get("corrections", [])[:3]:
        transcript.append({"agent": "Verifier", "message": f"Correction: {fix}"})

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


def _situation_step(situation: Dict[str, Any], latency_ms: int) -> Dict[str, Any]:
    groq_live = situation.get("source") == "groq"
    step: Dict[str, Any] = {
        "agent": "Situation",
        "llm_used": groq_live,
        "model_used": groq_client.resolve_model() if groq_live else "offline",
        "latency_ms": latency_ms,
        "mode": "groq" if groq_live else "offline",
        "llm_error": situation.get("parse_error"),
    }
    key_used = situation.get("key_used") or groq_client.get_last_key_used()
    if groq_live and key_used is not None:
        step["key_used"] = key_used
    return step


def _collect_agent_errors(outputs: Dict[str, Any]) -> List[str]:
    """Surface per-agent failures that would otherwise be silent in the UI."""
    errors: List[str] = []
    for key, label in (
        ("plan", "Commander"),
        ("allocations", "Resource"),
        ("routes", "Routing"),
        ("comms", "Comms"),
        ("verifier", "Verifier"),
        ("report", "Reporter"),
    ):
        blob = outputs.get(key) or {}
        if blob.get("error"):
            errors.append(f"{label}: {blob['error']}")
    return errors


class SwarmManager:
    """Runs all agents in sequence with shared SwarmContext."""

    def run_full_scenario(self, scenario_text: str) -> Dict[str, Any]:
        partial = self.run_partial_scenario(scenario_text)
        if partial.get("error"):
            return partial
        return self.run_complete_scenario(partial, scenario_text)

    def run_partial_scenario(self, scenario_text: str) -> Dict[str, Any]:
        groq_client.reset_swarm_session()
        agent_steps: List[Dict[str, Any]] = []
        try:
            print("[Swarm] Parsing disaster situation...")
            t0 = time.perf_counter()
            situation = parse_situation(scenario_text)
            agent_steps.append(_situation_step(situation, int((time.perf_counter() - t0) * 1000)))

            ctx = SwarmContext(scenario_text=scenario_text, situation=situation)

            commander_mod = importlib.import_module("agents.commander")
            resource_mod = importlib.import_module("agents.resource")
            routing_mod = importlib.import_module("agents.routing")

            print("[Swarm] Commander + Triage...")
            commander = getattr(commander_mod, "Commander")()
            plan = commander.run_triage_then_plan(scenario_text, context=ctx)
            agent_steps.append(step_metadata(plan, "Commander"))
            triage = plan.get("triage") or {}
            if triage:
                agent_steps.append(step_metadata(triage, "Triage"))

            print("[Swarm] Resource...")
            allocations = resource_mod.allocate_resources(plan, context=ctx)
            agent_steps.append(step_metadata(allocations, "Resource"))

            print("[Swarm] Routing...")
            routes = routing_mod.plan_routes(
                plan.get("task_assignments", []),
                context=ctx,
                allocations=allocations,
            )
            agent_steps.append(step_metadata(routes, "Routing"))

            return {
                "situation": situation,
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "agent_steps": agent_steps,
            }
        except Exception:
            return {"error": "Partial Swarm failed", "trace": traceback.format_exc()}

    def run_complete_scenario(self, partial_out: Dict[str, Any], scenario_text: str) -> Dict[str, Any]:
        agent_steps = partial_out.get("agent_steps", [])
        situation = partial_out.get("situation", {})
        plan = partial_out.get("plan", {})
        allocations = partial_out.get("allocations", {})
        routes = partial_out.get("routes", {})

        try:
            ctx = SwarmContext(scenario_text=scenario_text, situation=situation)

            comms_mod = importlib.import_module("agents.comms")
            verifier_mod = importlib.import_module("agents.verifier")
            reporter_mod = importlib.import_module("agents.reporter")

            print("[Swarm] Comms...")
            comms = comms_mod.send_alerts(
                context=ctx,
                plan=plan,
                allocations=allocations,
                routes=routes,
            )
            agent_steps.append(step_metadata(comms, "Comms"))

            print("[Swarm] Verifier...")
            verifier = verifier_mod.verify_outputs(ctx, plan, allocations, routes, comms)
            agent_steps.append(step_metadata(verifier, "Verifier"))

            print("[Swarm] Final operational analysis...")
            analysis = build_analysis_payload(
                scenario_text, plan, allocations, routes, context=ctx, comms=comms
            )
            agent_steps.append(step_metadata(analysis, "Analysis"))

            print("[Swarm] Reporter...")
            report = reporter_mod.generate_report(
                plan,
                allocations,
                routes,
                context=ctx,
                comms=comms,
                analysis=analysis,
                verifier=verifier,
            )
            agent_steps.append(step_metadata(report, "Reporter"))

            outputs = {
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
                "verifier": verifier,
                "analysis": analysis,
                "report": report,
            }
            transcript = build_transcript(ctx, outputs)

            llm_agents = sum(1 for s in agent_steps if s.get("llm_used"))
            agent_errors = _collect_agent_errors(outputs)
            mode = "groq_multi_agent" if llm_agents >= 3 else (
                "groq_partial" if llm_agents > 0 else "offline_pipeline"
            )

            return {
                "mode": mode,
                "groq_live": llm_agents > 0,
                "groq_status": f"{llm_agents} of {len(agent_steps)} agents used Groq",
                "groq_model": groq_client.resolve_model() if groq_client.is_configured() else None,
                "situation": situation,
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
                "verifier": verifier,
                "report": report,
                "analysis": analysis,
                "transcript": transcript,
                "agent_steps": agent_steps,
                "agents_with_llm": llm_agents,
                "agent_errors": agent_errors,
            }
        except Exception:
            return {"error": "Complete Swarm failed", "trace": traceback.format_exc()}


def run_swarm(disaster_message: str) -> Dict[str, Any]:
    if groq_client.is_configured():
        ok, msg = groq_client.verify_connection(use_cache=True)
        if ok:
            print(f"[Swarm] Groq configured — {msg}")
        else:
            print(f"[Swarm] Groq ping failed (agents may use offline fallbacks): {msg}")
    else:
        print("[Swarm] OFFLINE MODE — set GROQ_API_KEY for AI agents.")

    return SwarmManager().run_full_scenario(disaster_message)


def run_swarm_partial(disaster_message: str) -> Dict[str, Any]:
    if groq_client.is_configured():
        ok, msg = groq_client.verify_connection(use_cache=True)
        if ok:
            print(f"[Swarm] Groq configured — {msg}")
        else:
            print(f"[Swarm] Groq ping failed (agents may use offline fallbacks): {msg}")
    else:
        print("[Swarm] OFFLINE MODE — set GROQ_API_KEY for AI agents.")

    return SwarmManager().run_partial_scenario(disaster_message)


def run_swarm_complete(partial_out: Dict[str, Any], disaster_message: str) -> Dict[str, Any]:
    return SwarmManager().run_complete_scenario(partial_out, disaster_message)


if __name__ == "__main__":
    from core.scenario import load_demo_scenario
    print(json.dumps(run_swarm(load_demo_scenario()), indent=2))

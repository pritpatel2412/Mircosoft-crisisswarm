"""Swarm orchestration — digital twin, arena strategies, Groq-powered agents."""
from typing import Dict, Any, List, Optional
import importlib
import traceback
import json

from core import groq_client
from core.context import SwarmContext
from core.situation import parse_situation
from core.analysis import build_analysis_payload
from core.digital_twin import DisasterWorld
from core.replay import CrisisReplay
from core.human_gate import build_approval_record
from core.debate import run_debate


def build_transcript(ctx: SwarmContext, outputs: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build conversation log from agent narratives and structured outputs."""
    transcript: List[Dict[str, str]] = []

    situation = ctx.situation
    if situation.get("summary"):
        transcript.append({
            "agent": "Situation",
            "message": situation["summary"],
        })

    forecast = outputs.get("forecast", {})
    if forecast.get("forecast_summary"):
        transcript.append({"agent": "Forecast", "message": forecast["forecast_summary"]})

    twin = outputs.get("digital_twin", {})
    if twin.get("zones"):
        transcript.append({
            "agent": "DigitalTwin",
            "message": f"World tick {twin.get('tick', 0)} — {len(twin.get('zones', []))} zones live.",
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

    trust = outputs.get("trust", {})
    for ex in trust.get("explanations", [])[:4]:
        transcript.append({
            "agent": "Trust",
            "message": f"{ex.get('decision')}: {', '.join(ex.get('because', [])[:2])}",
        })

    marketplace = outputs.get("marketplace", {})
    if marketplace.get("suggested_summary"):
        transcript.append({"agent": "Marketplace", "message": marketplace["suggested_summary"]})

    debate = outputs.get("debate", {})
    for rnd in debate.get("rounds", []):
        transcript.append({
            "agent": f"Debate:{rnd.get('speaker')}",
            "message": f"[{rnd.get('stance', '').upper()}] {rnd.get('message', '')[:120]}",
        })
    if debate.get("outcome_summary"):
        transcript.append({"agent": "Debate:Commander", "message": debate["outcome_summary"]})

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

    multilingual = outputs.get("multilingual", {})
    for ann in multilingual.get("announcements", [])[:3]:
        transcript.append({
            "agent": "Multilingual",
            "message": f"[{ann.get('language')}] {ann.get('text', '')[:80]}...",
        })

    verification = outputs.get("verification", {})
    if verification:
        status = verification.get("verification_status", "UNKNOWN")
        transcript.append({
            "agent": "Verifier",
            "message": (
                f"Verification {status} — confidence "
                f"{verification.get('confidence_score', 0):.2f}, "
                f"{len(verification.get('issues_found', []))} issue(s)."
            ),
        })
        for issue in verification.get("issues_found", []):
            transcript.append({
                "agent": "Verifier",
                "message": (
                    f"[{issue.get('severity')}] {issue.get('type')}: "
                    f"{issue.get('message')}"
                ),
            })

    whatif = outputs.get("whatif", {})
    if whatif.get("recommendation"):
        transcript.append({"agent": "WhatIf", "message": whatif["recommendation"]})

    report = outputs.get("report", {})
    if report.get("text_summary"):
        transcript.append({"agent": "Reporter", "message": report["text_summary"]})

    aar = outputs.get("after_action", {})
    if aar.get("summary"):
        transcript.append({"agent": "AfterAction", "message": aar["summary"]})

    analysis = outputs.get("analysis", {})
    if analysis.get("scenario_assessment"):
        transcript.append({"agent": "Analysis", "message": analysis["scenario_assessment"]})
    for action in analysis.get("recommended_actions", [])[:6]:
        transcript.append({"agent": "Analysis", "message": f"→ {action}"})

    if not transcript and ctx.agent_log:
        transcript = list(ctx.agent_log)

    return transcript


class SwarmManager:
    """Runs all agents in sequence with shared SwarmContext and Digital Twin."""

    def run_full_scenario(
        self,
        scenario_text: str,
        strategy: str = "default",
        world: Optional[DisasterWorld] = None,
        round_label: str = "initial",
        stop_before_finalize: bool = False,
        replay: Optional[CrisisReplay] = None,
    ) -> Dict[str, Any]:
        try:
            print(f"[Swarm] Parsing disaster situation (strategy={strategy})...")
            situation = parse_situation(scenario_text)
            ctx = SwarmContext(
                scenario_text=scenario_text,
                situation=situation,
                strategy=strategy,
                round_label=round_label,
            )

            if world is None:
                world = DisasterWorld.from_situation(situation)

            if replay is None:
                replay = CrisisReplay()
            replay.capture("situation_parsed", world.to_dict(), "Initial disaster world")

            commander_mod = importlib.import_module("agents.commander")
            resource_mod = importlib.import_module("agents.resource")
            routing_mod = importlib.import_module("agents.routing")
            comms_mod = importlib.import_module("agents.comms")
            verifier_mod = importlib.import_module("agents.verifier")
            reporter_mod = importlib.import_module("agents.reporter")
            forecast_mod = importlib.import_module("agents.forecast")
            trust_mod = importlib.import_module("agents.trust")
            marketplace_mod = importlib.import_module("agents.marketplace")
            multilingual_mod = importlib.import_module("agents.multilingual")
            after_action_mod = importlib.import_module("agents.after_action")
            whatif_mod = importlib.import_module("core.whatif")

            print("[Swarm] Forecast...")
            forecast = forecast_mod.forecast_disaster(situation, world=world, context=ctx)
            replay.capture("forecast", world.to_dict(), forecast.get("forecast_summary", ""))

            print("[Swarm] Commander + Triage...")
            commander = getattr(commander_mod, "Commander")()
            plan = commander.run_triage_then_plan(scenario_text, context=ctx)
            triage = plan.get("triage", {})
            if triage:
                world.apply_triage(triage)
            replay.capture("triage", world.to_dict(), "Casualty classification applied")

            print("[Swarm] Resource...")
            allocations = resource_mod.allocate_resources(plan, context=ctx)
            world.apply_resource(allocations, strategy=strategy)
            replay.capture("resource", world.to_dict(), allocations.get("narrative", ""))

            print("[Swarm] Agent debate chamber...")
            debate = run_debate(plan, situation, context=ctx)
            replay.capture("debate", world.to_dict(), debate.get("outcome_summary", ""))

            print("[Swarm] Resource marketplace...")
            marketplace = marketplace_mod.request_mutual_aid(
                allocations, world=world, context=ctx
            )

            print("[Swarm] Routing...")
            routes = routing_mod.plan_routes(
                plan.get("task_assignments", []),
                context=ctx,
                allocations=allocations,
            )
            world.apply_routing(routes)
            replay.capture("routing", world.to_dict(), routes.get("narrative", ""))

            trust = trust_mod.explain_decisions(
                plan, allocations, routes, world=world, context=ctx
            )

            print("[Swarm] Comms...")
            comms = comms_mod.send_alerts(
                context=ctx,
                plan=plan,
                allocations=allocations,
                routes=routes,
            )
            world.apply_comms(comms)
            replay.capture("comms", world.to_dict(), comms.get("narrative", ""))

            print("[Swarm] Multilingual alerts...")
            multilingual = multilingual_mod.generate_multilingual_alerts(
                plan, comms=comms, context=ctx
            )

            print("[Swarm] Verifier...")
            verification = verifier_mod.verify_response_plan(
                plan,
                allocations,
                routes,
                context=ctx,
            )

            print("[Swarm] What-if optimizer...")
            whatif = whatif_mod.optimize_strategy(
                world, plan, allocations, verification
            )
            replay.capture(
                "verification",
                world.to_dict(),
                f"Status {verification.get('verification_status')}",
                extra={"verification": verification},
            )

            print("[Swarm] Final operational analysis...")
            analysis = build_analysis_payload(
                scenario_text, plan, allocations, routes, context=ctx, comms=comms
            )

            metrics = world.compute_metrics(verification)

            outputs = {
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
                "forecast": forecast,
                "trust": trust,
                "debate": debate,
                "marketplace": marketplace,
                "multilingual": multilingual,
                "verification": verification,
                "whatif": whatif,
                "analysis": analysis,
            }

            if stop_before_finalize:
                transcript = build_transcript(ctx, {**outputs, "report": {}, "after_action": {}})
                groq_ok, groq_msg = groq_client.verify_connection()
                mode = "groq_multi_agent" if groq_ok else "offline_pipeline"
                return {
                    "mode": mode,
                    "strategy": strategy,
                    "round_label": round_label,
                    "status": "awaiting_human_approval",
                    "groq_live": groq_ok,
                    "groq_status": groq_msg,
                    "situation": situation,
                    "digital_twin": world.to_dict(),
                    "metrics": metrics,
                    "replay": replay.to_dict(),
                    "scenario_text": scenario_text,
                    "pending_outputs": outputs,
                    "transcript": transcript,
                    **outputs,
                }

            finalized = self._finalize_mission(
                scenario_text=scenario_text,
                ctx=ctx,
                world=world,
                outputs=outputs,
                replay=replay,
                reporter_mod=reporter_mod,
                after_action_mod=after_action_mod,
                human_approval=None,
            )
            report = finalized["report"]
            after_action = finalized["after_action"]
            human_approval = finalized.get("human_approval")

            transcript = build_transcript(ctx, {**outputs, "report": report, "after_action": after_action})

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
                "strategy": strategy,
                "round_label": round_label,
                "status": "completed",
                "groq_live": groq_ok,
                "groq_status": groq_msg,
                "groq_model": groq_client.resolve_model() if groq_client.is_configured() else None,
                "situation": situation,
                "digital_twin": world.to_dict(),
                "metrics": metrics,
                "replay": replay.to_dict(),
                "human_approval": human_approval,
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
                "forecast": forecast,
                "trust": trust,
                "debate": debate,
                "marketplace": marketplace,
                "multilingual": multilingual,
                "verification": verification,
                "whatif": whatif,
                "after_action": after_action,
                "report": report,
                "analysis": analysis,
                "transcript": transcript,
                "agents_with_llm": llm_agents,
            }
        except Exception:
            return {"error": "SwarmManager failed", "trace": traceback.format_exc()}

    def _finalize_mission(
        self,
        scenario_text: str,
        ctx: SwarmContext,
        world: DisasterWorld,
        outputs: Dict[str, Any],
        replay: CrisisReplay,
        reporter_mod: Any,
        after_action_mod: Any,
        human_approval: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        verification = outputs["verification"]
        plan = outputs["plan"]
        allocations = outputs["allocations"]
        routes = outputs["routes"]
        comms = outputs["comms"]
        analysis = outputs["analysis"]
        whatif = outputs["whatif"]

        print("[Swarm] Reporter...")
        report = reporter_mod.generate_report(
            plan,
            allocations,
            routes,
            context=ctx,
            comms=comms,
            analysis=analysis,
            verification=verification,
        )
        if human_approval:
            stamp = (
                f" [Human {human_approval['decision'].upper()} by "
                f"{human_approval['officer']} at {human_approval['timestamp']}]"
            )
            report["text_summary"] = (report.get("text_summary", "") + stamp)
            report["human_approval"] = human_approval

        replay.capture("report", world.to_dict(), "Situation report issued")

        full_outputs = {**outputs, "report": report}
        after_action = after_action_mod.generate_after_action_review(
            world, full_outputs, whatif=whatif, context=ctx
        )
        replay.capture("after_action", world.to_dict(), after_action.get("summary", ""))

        return {
            "report": report,
            "after_action": after_action,
            "human_approval": human_approval,
        }


def run_swarm(
    disaster_message: str,
    strategy: str = "default",
    await_human_approval: bool = True,
) -> Dict[str, Any]:
    if groq_client.is_configured():
        ok, msg = groq_client.verify_connection()
        if ok:
            print(f"[Swarm] Groq LIVE — {msg}")
        else:
            print(f"[Swarm] OFFLINE MODE (API failed): {msg}")
    else:
        print("[Swarm] OFFLINE MODE — set GROQ_API_KEY for AI agents.")

    return SwarmManager().run_full_scenario(
        disaster_message,
        strategy=strategy,
        stop_before_finalize=await_human_approval,
    )


def finalize_mission(
    pending: Dict[str, Any],
    decision: str,
    officer: str = "Incident Commander",
    notes: str = "",
) -> Dict[str, Any]:
    """
    Complete a paused mission after human approval or rejection.

    decision: 'approved' | 'rejected'
    """
    if pending.get("status") != "awaiting_human_approval":
        return {"error": "Mission is not awaiting approval"}

    try:
        from core.digital_twin import DisasterWorld

        outputs = pending.get("pending_outputs") or {}
        verification = outputs.get("verification", {})
        approval = build_approval_record(decision, officer, verification, notes)

        world_dict = pending.get("digital_twin", {})
        world = DisasterWorld(disaster_type=world_dict.get("disaster_type", "other"))
        world.tick = world_dict.get("tick", 0)
        world.global_resources = world_dict.get("global_resources", {})
        for z in world_dict.get("zones", []):
            if isinstance(z, dict):
                from core.digital_twin import ZoneState
                world.zones[z["name"]] = ZoneState.from_dict(z)

        replay_data = pending.get("replay", {})
        replay = CrisisReplay()
        replay.frames = list(replay_data.get("frames", []))

        ctx = SwarmContext(
            scenario_text=pending.get("scenario_text", ""),
            situation=pending.get("situation", {}),
            strategy=pending.get("strategy", "default"),
        )
        ctx.verification = verification

        reporter_mod = importlib.import_module("agents.reporter")
        after_action_mod = importlib.import_module("agents.after_action")
        manager = SwarmManager()

        if decision == "rejected":
            report = {
                "agent": "Reporter",
                "text_summary": (
                    "MISSION REJECTED by incident command. "
                    "Deployment plan not executed. Revise allocations/routes and re-submit."
                ),
                "human_approval": approval,
                "payload": {"status": "rejected", "verification": verification},
            }
            after_action = {
                "agent": "AfterActionReview",
                "mission_score": 0,
                "summary": "Mission halted — human rejected plan after verifier flags.",
                "mistakes": [i.get("message") for i in verification.get("issues_found", [])],
                "improvement": "Address verifier issues and re-run swarm.",
                "potential_lives_saved": "+0",
            }
            replay.capture("rejected", world.to_dict(), f"Rejected by {officer}")
        else:
            result = manager._finalize_mission(
                scenario_text=pending.get("scenario_text", ""),
                ctx=ctx,
                world=world,
                outputs=outputs,
                replay=replay,
                reporter_mod=reporter_mod,
                after_action_mod=after_action_mod,
                human_approval=approval,
            )
            report = result["report"]
            after_action = result["after_action"]

        metrics = world.compute_metrics(verification)
        full = {**pending, **outputs}
        full["report"] = report
        full["after_action"] = after_action
        full["human_approval"] = approval
        full["metrics"] = metrics
        full["digital_twin"] = world.to_dict()
        full["replay"] = replay.to_dict()
        full["status"] = "completed" if decision == "approved" else "rejected"
        full["transcript"] = build_transcript(ctx, full)
        return full
    except Exception:
        return {"error": "finalize_mission failed", "trace": traceback.format_exc()}


def run_aftershock_rerun(
    pending_or_completed: Dict[str, Any],
    event_name: str = "aftershock",
) -> Dict[str, Any]:
    """Apply judge aftershock to world and re-run swarm from updated scenario."""
    from core.events import get_event
    from core.digital_twin import DisasterWorld, ZoneState

    scenario = pending_or_completed.get("scenario_text", "")
    event = get_event(event_name)
    world_dict = pending_or_completed.get("digital_twin", {})
    world = DisasterWorld(disaster_type=world_dict.get("disaster_type", "other"))
    for z in world_dict.get("zones", []):
        if isinstance(z, dict):
            world.zones[z["name"]] = ZoneState.from_dict(z)
    world.apply_aftershock(event)
    new_scenario = (
        f"{scenario}\n\n[JUDGE EVENT] {event['label']}. "
        "Casualties increased — re-coordinate immediately."
    )
    strategy = pending_or_completed.get("strategy", "default")
    return SwarmManager().run_full_scenario(
        new_scenario,
        strategy=strategy,
        world=world,
        round_label="after_aftershock",
        stop_before_finalize=True,
    )


if __name__ == "__main__":
    from core.scenario import load_demo_scenario
    print(json.dumps(run_swarm(load_demo_scenario()), indent=2))

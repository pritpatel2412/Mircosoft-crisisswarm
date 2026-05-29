"""Verifier Agent — reviews swarm outputs for consistency and safety."""
from __future__ import annotations

from typing import Any, Dict, Optional
import json
import traceback

from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "Verifier"

SYSTEM_MESSAGE = (
    "Verifier Agent: Double-check Commander, Triage, Resource, Routing, and Comms "
    "outputs for internal consistency, safety, and operational feasibility."
)

VERIFIER_SYSTEM = """You are an emergency operations verifier. Review all agent outputs for:
- Casualty totals matching zone sums
- Resource levels reasonable for casualty counts
- Route ETAs plausible given blocked roads
- Comms messages actionable and not contradictory

Return JSON only:
{
  "narrative": "1-2 sentence verification summary",
  "issues_found": ["specific issue strings"],
  "approved": true or false,
  "corrections": ["specific correction recommendations"],
  "confidence_score": 0-100
}
Approve only if the plan is safe to execute with minor or no corrections."""


def _offline_verify(outputs: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    corrections = []
    plan = outputs.get("plan", {})
    triage = plan.get("triage", {})
    zones = triage.get("zones", {})
    total = sum(z.get("estimated_total", 0) for z in zones.values())
    assignments = plan.get("task_assignments", [])
    alloc_list = outputs.get("allocations", {}).get("allocations", [])

    if not zones:
        issues.append("No triage zones identified.")
        corrections.append("Re-run triage with explicit zone casualty counts.")
    if assignments and len(assignments) != len(zones):
        issues.append("Task assignment count does not match triage zones.")
    for a in alloc_list:
        if a.get("ambulances", 0) < 1:
            issues.append(f"No ambulances allocated to {a.get('zone')}.")

    approved = len(issues) == 0
    confidence = 85 if approved else max(30, 70 - len(issues) * 15)
    return {
        "narrative": "Offline rule-based verification completed.",
        "issues_found": issues,
        "approved": approved,
        "corrections": corrections,
        "confidence_score": confidence,
    }


class VerifierAgent:
    """Reviews full pipeline outputs before the Reporter publishes a SitRep."""

    def verify(
        self,
        context: SwarmContext,
        plan: Dict[str, Any],
        allocations: Dict[str, Any],
        routes: Dict[str, Any],
        comms: Dict[str, Any],
    ) -> Dict[str, Any]:
        print("[Verifier] Reviewing swarm outputs")
        try:
            payload = {
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms,
            }

            def fallback():
                return _offline_verify(payload)

            user = context.prompt_block(json.dumps(payload, indent=2))
            llm_out = agent_json_step(AGENT_NAME, VERIFIER_SYSTEM, user, fallback)

            output = {
                "agent": AGENT_NAME,
                "system_message": SYSTEM_MESSAGE,
                "narrative": llm_out.get("narrative", ""),
                "issues_found": llm_out.get("issues_found", []),
                "approved": bool(llm_out.get("approved", False)),
                "corrections": llm_out.get("corrections", []),
                "confidence_score": int(llm_out.get("confidence_score", 0)),
                "llm_used": llm_out.get("llm_used", False),
                "model_used": llm_out.get("model_used", "offline"),
                "latency_ms": llm_out.get("latency_ms", 0),
            }
            if llm_out.get("llm_error"):
                output["llm_error"] = llm_out["llm_error"]
            print(f"[Verifier] Output:", json.dumps(output, indent=2))
            return output
        except Exception as e:
            print(f"[Verifier] Error: {e}\n{traceback.format_exc()}")
            return {"agent": AGENT_NAME, "error": str(e)}


def verify_outputs(
    context: SwarmContext,
    plan: Dict[str, Any],
    allocations: Dict[str, Any],
    routes: Dict[str, Any],
    comms: Dict[str, Any],
) -> Dict[str, Any]:
    """Module-level entry for orchestrators."""
    return VerifierAgent().verify(context, plan, allocations, routes, comms)


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    ctx = message.get("context")
    if not isinstance(ctx, SwarmContext):
        ctx = SwarmContext(
            scenario_text=message.get("scenario_text", ""),
            situation=message.get("situation", {}),
        )
    return verify_outputs(
        ctx,
        message.get("plan", {}),
        message.get("allocations", {}),
        message.get("routes", {}),
        message.get("comms", {}),
    )

"""Swarm Arena — two strategies compete on the same digital twin."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.digital_twin import DisasterWorld
from core.events import get_event
from core.situation import parse_situation
from core.swarm import SwarmManager


STRATEGIES = {
    "medical_first": {
        "id": "medical_first",
        "label": "Swarm A — Medical First",
        "description": "Prioritize critical victims; surge ambulances to highest-acuity zones.",
    },
    "resource_balanced": {
        "id": "resource_balanced",
        "label": "Swarm B — Resource Balanced",
        "description": "Even distribution of ambulances and supplies across all zones.",
    },
}


def _rank_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(
        results,
        key=lambda r: (
            r.get("metrics", {}).get("lives_saved", 0),
            r.get("metrics", {}).get("mission_score", 0),
            -r.get("metrics", {}).get("response_time_min", 999),
        ),
        reverse=True,
    )
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
        r["winner"] = i == 0
    return ranked


def run_arena(
    scenario_text: str,
    strategies: Optional[List[str]] = None,
    inject_aftershock: bool = False,
    aftershock_round: bool = True,
) -> Dict[str, Any]:
    """
    Run multiple swarms on cloned digital twins and build a leaderboard.

    Round 1: initial response. Optional aftershock, then round 2 re-plan.
    """
    strategies = strategies or ["medical_first", "resource_balanced"]
    manager = SwarmManager()
    situation = parse_situation(scenario_text)
    base_world = DisasterWorld.from_situation(situation)
    round_results: List[Dict[str, Any]] = []
    current_scenario = scenario_text

    for round_num in (1, 2):
        if round_num == 2 and not (inject_aftershock and aftershock_round):
            break

        round_label = "initial" if round_num == 1 else "after_aftershock"
        swarm_results: List[Dict[str, Any]] = []

        for strategy in strategies:
            meta = STRATEGIES.get(strategy, {"label": strategy, "description": ""})
            world = base_world.clone()

            out = manager.run_full_scenario(
                current_scenario,
                strategy=strategy,
                world=world,
                round_label=round_label,
                stop_before_finalize=False,
            )
            if out.get("error"):
                swarm_results.append({
                    "strategy": strategy,
                    "label": meta.get("label", strategy),
                    "error": out.get("error"),
                })
                continue

            metrics = out.get("metrics", {})
            swarm_results.append({
                "strategy": strategy,
                "label": meta.get("label", strategy),
                "description": meta.get("description", ""),
                "round": round_num,
                "metrics": metrics,
                "verification_status": out.get("verification", {}).get("verification_status"),
                "world_snapshot": out.get("digital_twin"),
                "mission_score": metrics.get("mission_score", 0),
            })

        ranked = _rank_results([r for r in swarm_results if "metrics" in r])
        round_results.append({
            "round": round_num,
            "label": round_label,
            "results": ranked,
            "winner": ranked[0] if ranked else None,
        })

        if round_num == 1 and inject_aftershock:
            event = get_event("aftershock")
            base_world.apply_aftershock(event)
            current_scenario = (
                f"{scenario_text}\n\n[EVENT] {event['label']}. "
                "Casualties increased; re-coordinate response."
            )

    all_flat = []
    for rnd in round_results:
        for r in rnd.get("results", []):
            all_flat.append(r)

    leaderboard = _rank_results(all_flat)

    return {
        "mode": "swarm_arena",
        "strategies": [STRATEGIES.get(s, {"id": s}) for s in strategies],
        "rounds": round_results,
        "leaderboard": leaderboard,
        "winner": leaderboard[0] if leaderboard else None,
        "aftershock_injected": inject_aftershock,
        "comparison": _build_comparison(leaderboard),
    }


def _build_comparison(leaderboard: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(leaderboard) < 2:
        return {}
    a, b = leaderboard[0], leaderboard[1]
    ma, mb = a.get("metrics", {}), b.get("metrics", {})
    return {
        "lives_saved": {
            "leader": a.get("label"),
            "values": {
                a.get("label"): ma.get("lives_saved"),
                b.get("label"): mb.get("lives_saved"),
            },
        },
        "response_time_min": {
            "leader": (
                a.get("label")
                if ma.get("response_time_min", 999) <= mb.get("response_time_min", 999)
                else b.get("label")
            ),
            "values": {
                a.get("label"): ma.get("response_time_min"),
                b.get("label"): mb.get("response_time_min"),
            },
        },
        "mission_score": {
            "leader": a.get("label"),
            "values": {
                a.get("label"): ma.get("mission_score"),
                b.get("label"): mb.get("mission_score"),
            },
        },
    }

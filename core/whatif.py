"""What-if optimizer — compare alternative resource strategies on the digital twin."""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from core.digital_twin import DisasterWorld


def optimize_strategy(
    world: DisasterWorld,
    plan: Dict[str, Any],
    current_allocations: Dict[str, Any],
    verification: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Rule-based what-if: simulate medical-first vs balanced vs current on cloned worlds.
    """
    scenarios: List[Dict[str, Any]] = []
    strategies = ["medical_first", "resource_balanced", "default"]

    for strategy in strategies:
        sim = world.clone()
        alloc = _build_allocations_for_strategy(plan, strategy)
        sim.apply_resource(alloc, strategy=strategy)
        metrics = sim.compute_metrics(verification)
        scenarios.append({
            "strategy": strategy,
            "metrics": metrics,
            "allocations_summary": _summarize_alloc(alloc),
        })

    best = max(scenarios, key=lambda s: s["metrics"].get("lives_saved", 0))
    current_metrics = world.compute_metrics(verification)

    return {
        "agent": "WhatIfOptimizer",
        "current_strategy_metrics": current_metrics,
        "scenarios": scenarios,
        "recommended_strategy": best["strategy"],
        "potential_lives_saved_delta": (
            best["metrics"].get("lives_saved", 0)
            - current_metrics.get("lives_saved", 0)
        ),
        "recommendation": (
            f"Switch to '{best['strategy']}' for up to "
            f"+{max(0, best['metrics'].get('lives_saved', 0) - current_metrics.get('lives_saved', 0))} "
            "additional lives saved (simulated)."
        ),
        "llm_used": False,
    }


def _summarize_alloc(allocations: Dict[str, Any]) -> List[Dict[str, int]]:
    return [
        {"zone": a.get("zone"), "ambulances": a.get("ambulances", 0)}
        for a in allocations.get("allocations", [])
        if isinstance(a, dict)
    ]


def _build_allocations_for_strategy(plan: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """Build allocation payload tuned to strategy (offline simulation)."""
    zones = plan.get("triage", {}).get("zones", {})
    items = []
    total_amb = 22

    if strategy == "medical_first":
        ranked = sorted(
            zones.items(),
            key=lambda x: (x[1].get("breakdown") or {}).get("Critical", 0),
            reverse=True,
        )
        weights = [0.5, 0.3, 0.2] if len(ranked) >= 3 else [1.0 / len(ranked)] * len(ranked)
        for i, (name, info) in enumerate(ranked):
            share = weights[i] if i < len(weights) else 0.1
            amb = max(1, int(total_amb * share))
            items.append({
                "zone": name,
                "ambulances": amb,
                "medical_teams": max(1, int(amb * 1.5)),
                "shelters": 1,
            })
    elif strategy == "resource_balanced":
        n = max(1, len(zones))
        per = max(1, total_amb // n)
        for name in zones:
            items.append({
                "zone": name,
                "ambulances": per,
                "medical_teams": per,
                "shelters": 1,
            })
    else:
        for name, info in zones.items():
            est = info.get("estimated_total", 50) if isinstance(info, dict) else 50
            items.append({
                "zone": name,
                "ambulances": max(1, est // 25),
                "medical_teams": max(1, est // 20),
                "shelters": 1,
            })

    return {"allocations": items}

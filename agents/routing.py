"""Routing Agent — routes and ETAs with situation-aware Groq prioritization."""
from typing import List, Dict, Any, Tuple, Optional
import json
import math
import traceback

from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "Routing"

SYSTEM_MESSAGE = (
    "Routing Agent: Plan responder routes considering blocked roads, "
    "operational corridors, and zone priority."
)

ROUTING_SYSTEM = """You are an emergency route planner. Given situation (blocked/operational routes),
allocations, and task assignments, return JSON:
{
  "narrative": "1-2 sentences on routing strategy",
  "route_order": ["zone names in deployment order"],
  "routes": [
    {
      "zone": "name",
      "eta_minutes": <int>,
      "status": "ok|delayed|blocked",
      "rationale": "why this ETA/status considering road conditions"
    }
  ]
}
Shorter ETA for higher-priority zones. Increase ETA if zone access is blocked or routes are obstructed."""

_KNOWN_COORDS = {
    "Dharavi": (19.0033, 72.8446),
    "Kurla": (19.0666, 72.8562),
    "Andheri": (19.1190, 72.8465),
    "Downtown": (25.7617, -80.1918),
    "South Beach": (25.7826, -80.1341),
    "Little Havana": (25.7681, -80.2223),
    "Coral Gables": (25.7215, -80.2684),
}


def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    R = 6371.0
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _heuristic_routes(
    task_assignments: List[Dict[str, Any]],
    origin: Tuple[float, float] = None,
) -> Dict[str, Any]:
    if not origin:
        origin = (19.0760, 72.8777)
    routes = []
    for a in task_assignments:
        zone = a.get("zone")
        coords = _KNOWN_COORDS.get(zone)
        if coords:
            distance_km = _haversine_km(origin, coords)
            eta_min = max(5, int((distance_km / 30.0) * 60))
            route = {
                "zone": zone,
                "from": {"lat": origin[0], "lon": origin[1]},
                "to": {"lat": coords[0], "lon": coords[1]},
                "distance_km": round(distance_km, 2),
                "eta_minutes": eta_min,
                "status": "ok",
                "rationale": "Haversine heuristic at 30 km/h average.",
            }
        else:
            route = {
                "zone": zone,
                "from": {"lat": origin[0], "lon": origin[1]},
                "to": None,
                "distance_km": 10.0,
                "eta_minutes": 20,
                "status": "unknown_zone_fallback",
                "rationale": "Unknown zone coordinates; generic ETA.",
            }
        routes.append(route)
    return {
        "narrative": "Routes computed with distance heuristic.",
        "route_order": [r["zone"] for r in routes],
        "routes": routes,
    }


def _merge_llm_routes(base: Dict[str, Any], llm: Dict[str, Any]) -> Dict[str, Any]:
    llm_by_zone = {r["zone"]: r for r in llm.get("routes", []) if r.get("zone")}
    for route in base.get("routes", []):
        zone = route.get("zone")
        if zone in llm_by_zone:
            patch = llm_by_zone[zone]
            route["eta_minutes"] = int(patch.get("eta_minutes", route["eta_minutes"]))
            route["status"] = patch.get("status", route.get("status", "ok"))
            route["rationale"] = patch.get("rationale", route.get("rationale", ""))
    base["narrative"] = llm.get("narrative", base.get("narrative", ""))
    base["route_order"] = llm.get("route_order", base.get("route_order", []))
    return base


def plan_routes(
    task_assignments: List[Dict[str, Any]],
    context: Optional[SwarmContext] = None,
    allocations: Optional[Dict[str, Any]] = None,
    origin: Tuple[float, float] = None,
) -> Dict[str, Any]:
    print("[Routing] Planning routes with situation awareness")
    try:
        base = _heuristic_routes(task_assignments, origin)

        def fallback():
            return base

        payload = {"task_assignments": task_assignments, "base_routes": base}
        if allocations:
            payload["allocations"] = allocations
        user = json.dumps(payload, indent=2)
        if context:
            user = context.prompt_block(user)

        llm_out = agent_json_step(AGENT_NAME, ROUTING_SYSTEM, user, fallback)
        merged = _merge_llm_routes(base, llm_out)

        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "narrative": merged.get("narrative", ""),
            "route_order": merged.get("route_order", []),
            "routes": merged.get("routes", []),
            "llm_used": llm_out.get("llm_used", False),
        }
        print(f"[Routing] Output:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Routing] Error: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return plan_routes(message.get("task_assignments", []))

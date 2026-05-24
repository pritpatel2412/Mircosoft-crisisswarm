"""Routing Agent for CrisisSwarm.

Plans routes for responders and ambulances. If `AZURE_MAPS_KEY` is set
the agent is expected to call Azure Maps APIs (not implemented here).
For the hackathon demo we use a haversine-based heuristic to compute
distance and ETA estimates so the system works offline.
"""
from typing import List, Dict, Any, Tuple
import json
import math
import traceback

from config import settings

AGENT_NAME = "Routing"

SYSTEM_MESSAGE = (
    "Routing Agent (Route Planner): Compute safe routes and ETA estimates "
    "for responder units. If `AZURE_MAPS_KEY` is available, prefer Azure Maps "
    "routing data; otherwise use a conservative speed heuristic.\n"
    "Output format: {agent, system_message, routes: [...] }"
)

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
    """Compute great-circle distance (kilometers) between two lat/lon pairs."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    R = 6371.0
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def plan_routes(task_assignments: List[Dict[str, Any]], origin: Tuple[float, float] = None) -> Dict[str, Any]:
    """Plan routes from an origin to each task zone.

    Args:
        task_assignments: list of dicts containing `zone` keys.
        origin: lat/lon pair for responder staging area.

    Returns:
        dict with `agent`, `system_message`, and `routes`.
    """
    print("[Routing] Planning routes for task assignments")
    try:
        if not origin:
            origin = (19.0760, 72.8777) # Default Mumbai
            for a in task_assignments:
                zone = a.get("zone")
                if zone in _KNOWN_COORDS:
                    origin = (_KNOWN_COORDS[zone][0] + 0.05, _KNOWN_COORDS[zone][1] + 0.05)
                    break
        
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
                    "rationale": "Computed from known coordinates with a safe-speed heuristic",
                }
            else:
                route = {
                    "zone": zone,
                    "from": {"lat": origin[0], "lon": origin[1]},
                    "to": None,
                    "distance_km": 10.0,
                    "eta_minutes": 20,
                    "status": "unknown_zone_fallback",
                    "rationale": "No coordinates known for zone; using generic fallback of 10km/20min",
                }
            routes.append(route)

        output = {"agent": AGENT_NAME, "system_message": SYSTEM_MESSAGE, "routes": routes}
        print(f"[Routing] Routes computed for {AGENT_NAME}:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Routing] Error planning routes: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for orchestrators; expects `message` with `task_assignments`."""
    tasks = message.get("task_assignments", [])
    return plan_routes(tasks)


if __name__ == "__main__":
    sample_tasks = [{"zone": "Dharavi", "est_total": 200}, {"zone": "Kurla", "est_total": 150}]
    plan_routes(sample_tasks)

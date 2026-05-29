"""Routing Agent — Azure Maps or haversine with Groq prioritization."""
from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
import json
import math
import traceback
import urllib.parse
import urllib.request

from config import settings
from core.context import SwarmContext
from core.agent_llm import agent_json_step
from core.scenario import (
    MUMBAI_ZONE_COORDS,
    FLORIDA_ZONE_COORDS,
    MUMBAI_ORIGIN,
    FLORIDA_ORIGIN,
    origin_for_scenario,
)

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

_KNOWN_COORDS = {**MUMBAI_ZONE_COORDS, **FLORIDA_ZONE_COORDS}


def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    R = 6371.0
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _azure_maps_route(
    origin: Tuple[float, float],
    dest: Tuple[float, float],
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """Call Azure Maps Route Directions API. Returns distance_km and eta_minutes or None."""
    query = f"{origin[0]},{origin[1]}:{dest[0]},{dest[1]}"
    params = urllib.parse.urlencode({
        "api-version": "1.0",
        "subscription-key": api_key,
        "query": query,
    })
    url = f"https://atlas.microsoft.com/route/directions/json?{params}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        routes = data.get("routes") or []
        if not routes:
            return None
        summary = routes[0].get("summary") or {}
        length_m = summary.get("lengthInMeters", 0)
        travel_s = summary.get("travelTimeInSeconds", 0)
        return {
            "distance_km": round(length_m / 1000.0, 2),
            "eta_minutes": max(1, int(travel_s / 60)),
        }
    except Exception as exc:
        print(f"[Routing] Azure Maps request failed: {exc}")
        return None


def _heuristic_routes(
    task_assignments: List[Dict[str, Any]],
    origin: Tuple[float, float],
    scenario_text: str = "",
) -> Dict[str, Any]:
    api_key = (settings.AZURE_MAPS_KEY or "").strip()
    use_azure = bool(api_key and api_key not in ("your_azure_maps_subscription_key_here", "<placeholder>"))
    routing_engine = "haversine"

    routes = []
    for a in task_assignments:
        zone = a.get("zone")
        coords = _KNOWN_COORDS.get(zone)
        if coords:
            azure_result = None
            if use_azure:
                azure_result = _azure_maps_route(origin, coords, api_key)
                if azure_result:
                    routing_engine = "azure_maps"

            if azure_result:
                distance_km = azure_result["distance_km"]
                eta_min = azure_result["eta_minutes"]
                rationale = "Azure Maps Route API (live road network)."
            else:
                distance_km = round(_haversine_km(origin, coords), 2)
                eta_min = max(5, int((distance_km / 30.0) * 60))
                rationale = "Haversine fallback at 30 km/h average."

            route = {
                "zone": zone,
                "from": {"lat": origin[0], "lon": origin[1]},
                "to": {"lat": coords[0], "lon": coords[1]},
                "distance_km": distance_km,
                "eta_minutes": eta_min,
                "status": "ok",
                "rationale": rationale,
                "routing_engine": routing_engine if azure_result else "haversine",
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
                "routing_engine": "haversine",
            }
        routes.append(route)

    return {
        "narrative": f"Routes computed via {routing_engine}.",
        "route_order": [r["zone"] for r in routes],
        "routes": routes,
        "routing_engine": routing_engine,
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
        if not origin and context:
            origin = origin_for_scenario(context.scenario_text)
        if not origin:
            origin = MUMBAI_ORIGIN

        scenario_text = context.scenario_text if context else ""
        base = _heuristic_routes(task_assignments, origin, scenario_text)

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
            "routing_engine": merged.get("routing_engine", "haversine"),
            "llm_used": llm_out.get("llm_used", False),
            "model_used": llm_out.get("model_used", "offline"),
            "latency_ms": llm_out.get("latency_ms", 0),
        }
        if llm_out.get("llm_error"):
            output["llm_error"] = llm_out["llm_error"]
        print(f"[Routing] Output:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Routing] Error: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    return plan_routes(message.get("task_assignments", []))

"""Live command map — Pydeck visualization of digital-twin zones."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Mumbai demo zones (shared with routing agent)
ZONE_COORDS: Dict[str, Tuple[float, float]] = {
    "Dharavi": (19.0033, 72.8446),
    "Kurla": (19.0666, 72.8562),
    "Andheri": (19.1190, 72.8465),
    "Downtown": (25.7617, -80.1918),
    "South Beach": (25.7826, -80.1341),
    "Little Havana": (25.7681, -80.2223),
    "Coral Gables": (25.7215, -80.2684),
}

COMMAND_CENTER = (19.0760, 72.8777)


def _zone_rows(world: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for z in world.get("zones", []):
        if not isinstance(z, dict):
            continue
        name = z.get("name", "unknown")
        lat, lon = ZONE_COORDS.get(name, COMMAND_CENTER)
        critical = int(z.get("critical", 0))
        rows.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "casualties": int(z.get("casualties", 0)),
            "critical": critical,
            "serious": int(z.get("serious", 0)),
            "ambulances": int(z.get("ambulances_deployed", 0)),
            "delay_min": int(z.get("response_delay_min", 0)),
            "shelter": bool(z.get("shelter", False)),
            "access": str(z.get("access", "open")),
            "risk_color": min(255, 50 + critical * 8),
        })
    return rows


def build_pydeck_map(
    world: Dict[str, Any],
    routes: Optional[Dict[str, Any]] = None,
    height: int = 480,
) -> "pydeck.Deck":
    """Build an interactive map layer for Streamlit st.pydeck_chart."""
    import pydeck as pdk

    rows = _zone_rows(world)
    if not rows:
        rows = [{
            "name": "Command",
            "lat": COMMAND_CENTER[0],
            "lon": COMMAND_CENTER[1],
            "casualties": 0,
            "critical": 0,
            "serious": 0,
            "ambulances": 0,
            "delay_min": 0,
            "shelter": False,
            "access": "open",
            "risk_color": 100,
        }]

    df = pd.DataFrame(rows)
    center_lat = float(df["lat"].mean())
    center_lon = float(df["lon"].mean())

    zone_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_fill_color=["risk_color", 90, 54, 180],
        get_radius=1800,
        pickable=True,
        auto_highlight=True,
    )

    hub_df = pd.DataFrame([{
        "name": "Command Center",
        "lat": COMMAND_CENTER[0],
        "lon": COMMAND_CENTER[1],
    }])
    hub_layer = pdk.Layer(
        "ScatterplotLayer",
        data=hub_df,
        get_position=["lon", "lat"],
        get_fill_color=[17, 17, 17, 240],
        get_radius=1200,
        pickable=False,
    )

    layers: List[Any] = [zone_layer, hub_layer]

    route_paths: List[List[List[float]]] = []
    if routes:
        for r in routes.get("routes", []):
            if not isinstance(r, dict):
                continue
            zone = r.get("zone")
            if zone in ZONE_COORDS:
                lat, lon = ZONE_COORDS[zone]
                route_paths.append([
                    [COMMAND_CENTER[1], COMMAND_CENTER[0]],
                    [lon, lat],
                ])

    if route_paths:
        path_data = pd.DataFrame({"path": route_paths})
        layers.append(
            pdk.Layer(
                "PathLayer",
                data=path_data,
                get_path="path",
                get_color=[255, 90, 54, 200],
                get_width=4,
                width_min_pixels=2,
            )
        )

    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=10.5,
            pitch=40,
        ),
        tooltip={
            "html": (
                "<b>{name}</b><br/>"
                "Casualties: {casualties}<br/>"
                "Critical: {critical}<br/>"
                "Ambulances: {ambulances}<br/>"
                "ETA/delay: {delay_min} min<br/>"
                "Access: {access}"
            ),
            "style": {"backgroundColor": "#1a1a2e", "color": "white"},
        },
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    )

"""Streamlit dashboard for CrisisSwarm."""
import os
import sys
import streamlit as st
import json
import time
from typing import List, Dict, Any, Optional

import pandas as pd
import pydeck as pdk

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.scenario import (
    load_demo_scenario,
    load_florida_scenario,
    zone_coords_for_scenario,
)
from core.swarm import run_swarm
from core import groq_client

st.set_page_config(page_title="CrisisSwarm Dashboard", layout="wide")

st.title("CrisisSwarm — Multi-Agent Disaster Response")
st.caption("Microsoft Build AI Hackathon 2026 · Theme 05 — Agent Swarms")

if groq_client.is_configured():
    ok, msg = groq_client.verify_connection()
    if ok:
        st.success(f"Groq live — {msg}")
    else:
        st.error(
            "**Groq key is in `.env` but the API is NOT working.** "
            "The app runs on offline heuristics until fixed.\n\n"
            f"Error: {msg}"
        )
else:
    st.warning("No Groq API key. Set `GROQ_API_KEY` in `.env` for live AI agents.")

AGENT_COLORS = {
    "Situation": "#636efa",
    "Commander": "#1f77b4",
    "Triage": "#ff7f0e",
    "Resource": "#2ca02c",
    "Routing": "#d62728",
    "Comms": "#9467bd",
    "Verifier": "#e377c2",
    "Reporter": "#8c564b",
    "Analysis": "#17becf",
}


def _zone_rgb(breakdown: Dict[str, Any]) -> List[int]:
    critical = breakdown.get("Critical", 0)
    serious = breakdown.get("Serious", 0)
    if critical >= serious and critical > 0:
        return [220, 50, 50]
    if serious > 0:
        return [255, 140, 0]
    return [50, 200, 80]


def render_message(msg: Dict[str, str]) -> None:
    agent = msg.get("agent", "unknown")
    text = msg.get("message", "")
    color = AGENT_COLORS.get(agent, "#444444")
    html = f"""
    <div style='border-radius:8px;padding:8px;margin:6px 0;background-color:{color};color:white;'>
      <strong>{agent}</strong><div style='font-size:90%'>{text}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_agent_trace(agent_steps: List[Dict[str, Any]]) -> None:
    st.subheader("Agent execution trace")
    st.caption("Proves each step used live Groq or an offline fallback.")
    for step in agent_steps:
        mode = step.get("mode", "offline")
        llm = step.get("llm_used", False)
        badge = "🟢 Groq" if llm else "⚪ Offline"
        st.markdown(
            f"**{step.get('agent')}** — {badge} · model `{step.get('model_used', '—')}` · "
            f"**{step.get('latency_ms', 0)} ms**"
        )
        if step.get("llm_error"):
            st.caption(f"Fallback reason: {step['llm_error']}")


def build_map_df(
    scenario_text: str,
    plan: Dict[str, Any],
    routes: Dict[str, Any],
) -> pd.DataFrame:
    coords = zone_coords_for_scenario(scenario_text)
    triage_zones = plan.get("triage", {}).get("zones", {})
    route_by_zone = {r.get("zone"): r for r in routes.get("routes", [])}

    rows = []
    for zone, info in triage_zones.items():
        if zone not in coords:
            continue
        lat, lon = coords[zone]
        br = info.get("breakdown", {})
        r = route_by_zone.get(zone, {})
        rgb = _zone_rgb(br)
        rows.append({
            "zone": zone,
            "lat": lat,
            "lon": lon,
            "casualties": info.get("estimated_total", 0),
            "critical": br.get("Critical", 0),
            "serious": br.get("Serious", 0),
            "minor": br.get("Minor", 0),
            "eta_minutes": r.get("eta_minutes", "—"),
            "distance_km": r.get("distance_km", "—"),
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2],
        })
    return pd.DataFrame(rows)


def render_map(scenario_text: str, plan: Dict[str, Any], routes: Dict[str, Any]) -> None:
    df = build_map_df(scenario_text, plan, routes)
    if df.empty:
        st.info("No mappable zones in the last run.")
        return

    st.markdown(
        "**Legend:** 🔴 Critical-dominant · 🟠 Serious-dominant · 🟢 Minor-dominant"
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lon, lat]",
        get_fill_color="[r, g, b, 200]",
        get_radius=1800,
        pickable=True,
    )
    view = pdk.ViewState(
        latitude=float(df["lat"].mean()),
        longitude=float(df["lon"].mean()),
        zoom=10,
        pitch=30,
    )
    tooltip = {
        "html": "<b>{zone}</b><br/>"
        "Casualties: {casualties}<br/>"
        "C:{critical} S:{serious} M:{minor}<br/>"
        "ETA: {eta_minutes} min<br/>"
        "Distance: {distance_km} km",
        "style": {"backgroundColor": "#1a1a2e", "color": "white"},
    }
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip))


if "scenario_text" not in st.session_state:
    st.session_state.scenario_text = load_demo_scenario()
if "swarm_out" not in st.session_state:
    st.session_state.swarm_out = None
if "last_scenario_text" not in st.session_state:
    st.session_state.last_scenario_text = st.session_state.scenario_text

st.subheader("Disaster Scenario")
sc1, sc2, sc3 = st.columns([1, 1, 2])
with sc1:
    if st.button("Mumbai Earthquake", use_container_width=True):
        st.session_state.scenario_text = load_demo_scenario()
        st.rerun()
with sc2:
    if st.button("Florida Hurricane", use_container_width=True):
        st.session_state.scenario_text = load_florida_scenario()
        st.rerun()

scenario_text = st.text_area(
    "Scenario text",
    value=st.session_state.scenario_text,
    height=140,
    key="scenario_input",
)
st.session_state.scenario_text = scenario_text

if st.button("ACTIVATE SWARM", type="primary"):
    with st.spinner("Running multi-agent pipeline (Groq + verifier)..."):
        st.session_state.swarm_out = run_swarm(scenario_text)
        st.session_state.last_scenario_text = scenario_text

out: Optional[Dict[str, Any]] = st.session_state.swarm_out

if not out:
    st.info("Select a scenario and click **ACTIVATE SWARM**.")
    st.stop()

if out.get("error"):
    st.error(out.get("error"))
    if out.get("trace"):
        st.code(out["trace"])
    st.stop()

plan = out.get("plan", {})
situation = out.get("situation", {})
analysis = out.get("analysis", {})
verifier = out.get("verifier", {})
transcript = out.get("transcript", [])
agent_steps = out.get("agent_steps", [])
scenario_for_map = st.session_state.last_scenario_text

total_casualties = sum(
    z.get("estimated_total", 0) for z in plan.get("triage", {}).get("zones", {}).values()
)
allocations = out.get("allocations", {}).get("allocations", [])
total_ambulances = sum(a.get("ambulances", 0) for a in allocations)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Active Agents", len({s.get("agent") for s in agent_steps}))
m2.metric("Casualties Triaged", total_casualties)
m3.metric("Ambulances", total_ambulances)
m4.metric(
    "Verifier",
    "Approved" if verifier.get("approved") else "Review",
    delta=f"{verifier.get('confidence_score', 0)}% confidence",
)

tab_ops, tab_map, tab_trace = st.tabs(["Operations", "Map View", "Agent Trace"])

with tab_ops:
    if situation.get("summary"):
        st.subheader("Situation Understanding")
        st.write(situation.get("summary"))
        c1, c2, c3, c4 = st.columns(4)
        c1.caption(f"Type: {situation.get('disaster_type', '—')}")
        c2.caption(f"Location: {situation.get('location', '—')}")
        c3.caption(f"Severity: {situation.get('severity', '—')}")
        c4.caption(f"Source: {situation.get('source', '—')}")

    st.subheader("Operational Analysis")
    st.write(analysis.get("scenario_assessment", "No analysis available."))
    if analysis.get("coordination_notes"):
        st.info(analysis["coordination_notes"])
    if analysis.get("priority_zones"):
        st.markdown("**Priority zones:** " + ", ".join(analysis["priority_zones"]))
    if analysis.get("key_risks"):
        st.markdown("**Key risks**")
        for risk in analysis["key_risks"]:
            st.markdown(f"- {risk}")
    if analysis.get("recommended_actions"):
        st.markdown("**Recommended actions**")
        for action in analysis["recommended_actions"]:
            st.markdown(f"- {action}")

    if verifier:
        st.subheader("Verifier")
        vcol1, vcol2 = st.columns(2)
        vcol1.metric("Approved", str(verifier.get("approved", False)))
        vcol2.metric("Confidence", f"{verifier.get('confidence_score', 0)}%")
        if verifier.get("issues_found"):
            st.markdown("**Issues**")
            for issue in verifier["issues_found"]:
                st.markdown(f"- {issue}")
        if verifier.get("corrections"):
            st.markdown("**Corrections**")
            for fix in verifier["corrections"]:
                st.markdown(f"- {fix}")

    st.subheader("Live Conversation Log")
    for msg in transcript:
        render_message(msg)

    st.header("Reporter Summary")
    report = out.get("report", {})
    st.write(report.get("text_summary", "No report available."))
    st.download_button(
        "Download full report JSON",
        data=json.dumps({**report, "analysis": analysis, "verifier": verifier}, indent=2),
        file_name="report.json",
    )

    with st.expander("Raw Outputs"):
        st.json({
            "situation": situation,
            "plan": plan,
            "allocations": out.get("allocations"),
            "routes": out.get("routes"),
            "comms": out.get("comms"),
            "verifier": verifier,
            "analysis": analysis,
        })

with tab_map:
    st.subheader("Zone map")
    render_map(scenario_for_map, plan, out.get("routes", {}))

with tab_trace:
    render_agent_trace(agent_steps)

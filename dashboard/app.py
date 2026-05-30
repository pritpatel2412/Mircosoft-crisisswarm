"""Streamlit dashboard for CrisisSwarm."""
import os
import sys
import streamlit as st
import json
from typing import List, Dict, Any, Optional

import pandas as pd
import pydeck as pdk

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.scenario import (
    SCENARIOS,
    load_demo_scenario,
    zone_coords_for_scenario,
    is_approximate_map,
)
from core.swarm import run_swarm
from core import groq_client

st.set_page_config(page_title="CrisisSwarm Dashboard", layout="wide")

st.title("CrisisSwarm — Multi-Agent Disaster Response")
st.caption("Microsoft Build AI Hackathon 2026 · Theme 05 — Agent Swarms")

if groq_client.is_configured():
    blocked, block_reason = groq_client.is_temporarily_unavailable()
    if blocked:
        st.warning(
            "**Groq quota reached** during the last swarm run on this server. "
            "Further agents will use offline heuristics until you start a new run "
            "after limits reset.\n\n"
            f"{block_reason}"
        )
    else:
        ok, msg = groq_client.verify_connection(use_cache=True)
        key_info = groq_client.get_active_key_info()
        if ok:
            if key_info["keys_available"] >= 2:
                st.success(
                    f"Groq live — dual key rotation enabled "
                    f"(Key {key_info['active_key']} active). {msg}"
                )
            else:
                st.success(f"Groq live — {msg}")
            st.caption(
                "Tip: two keys on the **same** Groq account share one daily token limit. "
                "Use a second account for `GROQ_API_KEY_2`, or `GROQ_MODEL=llama-3.1-8b-instant`."
            )
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

SCENARIO_BUTTON_LABELS = {
    "Mumbai Earthquake": "🌏 Mumbai Earthquake",
    "Florida Hurricane": "🌀 Florida Hurricane",
    "Tokyo Flood": "🌊 Tokyo Flood",
    "Turkey Earthquake": "🏔️ Turkey Earthquake",
    "Chennai Cyclone": "🌪️ Chennai Cyclone",
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
        llm = step.get("llm_used", False)
        badge = "🟢 Groq" if llm else "⚪ Offline"
        key_line = ""
        if step.get("key_used"):
            key_line = f" · Groq key **{step['key_used']}**"
        st.markdown(
            f"**{step.get('agent')}** — {badge} · "
            f"model `{step.get('model_used', '—')}` · "
            f"**{step.get('latency_ms', 0)} ms**{key_line}"
        )
        if step.get("llm_error"):
            st.caption(f"Fallback reason: {step['llm_error']}")
        if step.get("error"):
            st.error(f"Agent error: {step['error']}")


def _match_coord_key(zone: str, coords: Dict[str, tuple]) -> Optional[str]:
    if zone in coords:
        return zone
    zl = zone.lower()
    for key in coords:
        kl = key.lower()
        if kl in zl or zl in kl:
            return key
    return None


def build_map_df(
    scenario_text: str,
    plan: Dict[str, Any],
    routes: Dict[str, Any],
) -> pd.DataFrame:
    coords = zone_coords_for_scenario(scenario_text)
    triage_zones = plan.get("triage", {}).get("zones", {})
    route_by_zone = {r.get("zone"): r for r in routes.get("routes", [])}
    approximate = is_approximate_map(scenario_text, coords)

    rows: List[Dict[str, Any]] = []

    for zone, info in triage_zones.items():
        key = _match_coord_key(zone, coords)
        if key is None and approximate:
            key = list(coords.keys())[len(rows) % len(coords)]
        if key is None:
            continue
        lat, lon = coords[key]
        br = info.get("breakdown", {})
        r = route_by_zone.get(zone, route_by_zone.get(key, {}))
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
            "approximate": "yes" if approximate else "no",
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2],
        })

    if not rows:
        for zone, (lat, lon) in coords.items():
            r = route_by_zone.get(zone, {})
            rows.append({
                "zone": zone,
                "lat": lat,
                "lon": lon,
                "casualties": 0,
                "critical": 0,
                "serious": 0,
                "minor": 0,
                "eta_minutes": r.get("eta_minutes", "—"),
                "distance_km": r.get("distance_km", "—"),
                "approximate": "yes" if approximate else "no",
                "r": 100,
                "g": 180,
                "b": 255,
            })

    return pd.DataFrame(rows)


def render_map(
    scenario_text: str,
    plan: Dict[str, Any],
    routes: Dict[str, Any],
) -> None:
    coords = zone_coords_for_scenario(scenario_text)
    approximate = is_approximate_map(scenario_text, coords)

    if approximate:
        st.info(
            "**Approximate zone locations** — no exact map data for this scenario. "
            "Markers are placed near the closest recognised city from your text."
        )

    df = build_map_df(scenario_text, plan, routes)
    if df.empty:
        centre = zone_coords_for_scenario(scenario_text)
        lat = sum(c[0] for c in centre.values()) / len(centre)
        lon = sum(c[1] for c in centre.values()) / len(centre)
        df = pd.DataFrame([{
            "zone": "Centre",
            "lat": lat,
            "lon": lon,
            "casualties": 0,
            "critical": 0,
            "serious": 0,
            "minor": 0,
            "eta_minutes": "—",
            "distance_km": "—",
            "approximate": "yes",
            "r": 100,
            "g": 180,
            "b": 255,
        }])

    st.markdown(
        "**Legend:** 🔴 Critical-dominant · 🟠 Serious-dominant · "
        "🟢 Minor-dominant · 🔵 Approximate / unknown"
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
        "html": (
            "<b>{zone}</b><br/>"
            "Casualties: {casualties}<br/>"
            "C:{critical} S:{serious} M:{minor}<br/>"
            "ETA: {eta_minutes} min<br/>"
            "Distance: {distance_km} km<br/>"
            "Approximate: {approximate}"
        ),
        "style": {"backgroundColor": "#1a1a2e", "color": "white"},
    }
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip))


def _render_swarm_results(out: Dict[str, Any]) -> None:
    plan = out.get("plan", {})
    situation = out.get("situation", {})
    analysis = out.get("analysis", {})
    verifier = out.get("verifier", {})
    transcript = out.get("transcript", [])
    agent_steps = out.get("agent_steps", [])
    agent_errors = out.get("agent_errors", [])
    scenario_for_map = st.session_state["last_scenario_text"]

    if agent_errors:
        st.error("**Agent errors during this run:**")
        for err in agent_errors:
            st.markdown(f"- {err}")

    llm_count = out.get("agents_with_llm", 0)
    total_steps = len(agent_steps)
    if llm_count == 0:
        st.warning("This run used **offline heuristics only** — see Agent Trace for details.")
    elif llm_count < total_steps:
        st.info(
            f"**Partial Groq run:** {llm_count} of {total_steps} steps used live AI. "
            "Check the Agent Trace tab for offline fallbacks."
        )

    total_casualties = sum(
        z.get("estimated_total", 0)
        for z in plan.get("triage", {}).get("zones", {}).values()
    )
    allocations = out.get("allocations", {}).get("allocations", [])
    total_ambulances = sum(a.get("ambulances", 0) for a in allocations)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Agents", len({s.get("agent") for s in agent_steps}))
    m2.metric("Casualties Triaged", total_casualties)
    m3.metric("Ambulances", total_ambulances)
    m4.metric(
        "Verifier",
        "✅ Approved" if verifier.get("approved") else "⚠️ Review",
        delta=f"{verifier.get('confidence_score', 0)}% confidence",
    )

    tab_ops, tab_map, tab_trace = st.tabs(["📋 Operations", "🗺️ Map View", "🔍 Agent Trace"])

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
            "⬇️ Download full report JSON",
            data=json.dumps(
                {**report, "analysis": analysis, "verifier": verifier},
                indent=2,
            ),
            file_name="crisis_report.json",
            mime="application/json",
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


# ---------------------------------------------------------------------------
# Session state — single key for text_area (fixes button / widget conflict)
# ---------------------------------------------------------------------------
if "scenario_input" not in st.session_state:
    st.session_state["scenario_input"] = load_demo_scenario()
if "swarm_out" not in st.session_state:
    st.session_state["swarm_out"] = None
if "last_scenario_text" not in st.session_state:
    st.session_state["last_scenario_text"] = st.session_state["scenario_input"]

# ---------------------------------------------------------------------------
# Scenario selector — 5 buttons
# ---------------------------------------------------------------------------
st.subheader("Disaster Scenario")

scenario_names = list(SCENARIOS.keys())
btn_cols = st.columns(5)
for i, name in enumerate(scenario_names):
    with btn_cols[i]:
        if st.button(
            SCENARIO_BUTTON_LABELS[name],
            use_container_width=True,
            key=f"scenario_btn_{i}",
        ):
            st.session_state["scenario_input"] = SCENARIOS[name]
            st.session_state["swarm_out"] = None
            st.rerun()

st.text_area(
    "Scenario text",
    key="scenario_input",
    height=140,
    help=(
        "Type a custom disaster scenario or use a preset button. "
        "Unknown locations use approximate map pins; built-in cities use exact zone coordinates."
    ),
)

# ---------------------------------------------------------------------------
# ACTIVATE SWARM
# ---------------------------------------------------------------------------
if st.button("🚨 ACTIVATE SWARM", type="primary", use_container_width=True):
    with st.spinner("Running multi-agent pipeline (Groq + verifier)..."):
        st.session_state["swarm_out"] = run_swarm(st.session_state["scenario_input"])
        st.session_state["last_scenario_text"] = st.session_state["scenario_input"]

out: Optional[Dict[str, Any]] = st.session_state.get("swarm_out")

if not out:
    st.info("Pick a scenario (or write your own) and click **🚨 ACTIVATE SWARM**.")
else:
    if out.get("error"):
        st.error(out.get("error"))
        if out.get("trace"):
            st.code(out["trace"])
    else:
        _render_swarm_results(out)

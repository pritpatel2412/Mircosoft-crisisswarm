"""Streamlit dashboard for CrisisSwarm.

Provides a simple UI to run the full demo and view agent logs and JSON
outputs. This lightweight dashboard is intended for local demo and can be
deployed to Azure App Service once keys and production settings are added.
"""
import os
import sys
import streamlit as st
import json
import time
from typing import List, Dict

# Ensure the repo root is on sys.path when Streamlit runs from the dashboard folder.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.scenario import load_demo_scenario
from core.swarm import run_swarm


st.set_page_config(page_title="CrisisSwarm Dashboard", layout="wide")

st.title("CrisisSwarm — Multi-Agent Disaster Response")

# Scenario input at the top
st.subheader("Disaster Scenario Input")
default_scenario = load_demo_scenario()
scenario_text = st.text_area("Scenario text", value=default_scenario, height=140)

# Metrics panel and Activate button
col1, col2 = st.columns([3, 1])

with col2:
    st.markdown("### \n")
    # Large red activation banner (visual) — primary action below
    st.markdown(
        "<div style='background-color:#d9534f;color:white;padding:12px;border-radius:8px;text-align:center;font-weight:700'>ACTIVATE SWARM</div>",
        unsafe_allow_html=True,
    )

with col1:
    st.markdown("**Metrics**")
    metrics_cols = st.columns(3)
    active_agents_card = metrics_cols[0].metric("Active Agents", 0)
    casualties_card = metrics_cols[1].metric("Casualties Triaged", 0)
    resources_card = metrics_cols[2].metric("Resources Deployed", 0)

# Color map for agents
AGENT_COLORS = {
    "Commander": "#1f77b4",
    "Triage": "#ff7f0e",
    "Resource": "#2ca02c",
    "Routing": "#d62728",
    "Comms": "#9467bd",
    "Reporter": "#8c564b",
}


def render_message(msg: Dict[str, str]):
    """Render a single chat message with color based on agent name."""
    agent = msg.get("agent", "unknown")
    text = msg.get("message", "")
    color = AGENT_COLORS.get(agent, "#444444")
    # Simple styled box using markdown
    html = f"""
    <div style='border-radius:8px;padding:8px;margin:6px 0;background-color:{color};color:white;'>
      <strong>{agent}</strong><div style='font-size:90%'>{text}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def build_transcript_from_fallback(out: Dict) -> List[Dict[str, str]]:
    """Construct a message transcript from the fallback SwarmManager output."""
    transcript: List[Dict[str, str]] = []
    plan = out.get("plan", {})
    triage = plan.get("triage", {})
    transcript.append({"agent": "Commander", "message": "Commander: initial operational plan created."})

    # Add triage details
    zones = triage.get("zones", {})
    for z, info in zones.items():
        transcript.append({"agent": "Triage", "message": f"{z}: estimated {info.get('estimated_total')} casualties."})

    # Resource allocations
    allocations = out.get("allocations", {}).get("allocations", [])
    for a in allocations:
        transcript.append({"agent": "Resource", "message": f"Allocating {a.get('ambulances')} ambulances to {a.get('zone')}"})

    # Routes
    routes = out.get("routes", {}).get("routes", [])
    for r in routes:
        transcript.append({"agent": "Routing", "message": f"Route to {r.get('zone')}: ETA {r.get('eta_minutes')} minutes"})

    # Comms
    deliveries = out.get("comms", {}).get("delivery_log", [])
    for d in deliveries:
        transcript.append({"agent": "Comms", "message": d.get("message", "")})

    # Reporter summary
    report = out.get("report", {})
    transcript.append({"agent": "Reporter", "message": report.get("text_summary", "Report generated.")})

    return transcript


log_container = st.container()

# ACTIVATE handler: primary button here
if st.button("ACTIVATE SWARM", key="start_swarm"):
    with st.spinner("Activating swarm..."):
        out = run_swarm(scenario_text)

    # If AutoGen transcript returned, use it; otherwise build from fallback outputs
    transcript = []
    if out.get("agent") == "autogen_groupchat":
        # transcript is already normalized by core.swarm
        transcript = out.get("transcript", [])
    else:
        transcript = build_transcript_from_fallback(out)

    # Update metrics
    active_agents = len({m.get("agent") for m in transcript})
    total_casualties = 0
    allocations = out.get("allocations", {}).get("allocations", [])
    for a in out.get("plan", {}).get("triage", {}).get("zones", {}).values():
        total_casualties += a.get("estimated_total", 0)
    total_ambulances = sum([a.get("ambulances", 0) for a in allocations])

    # Render metrics
    metrics_cols = st.columns(3)
    metrics_cols[0].metric("Active Agents", active_agents)
    metrics_cols[1].metric("Casualties Triaged", total_casualties)
    metrics_cols[2].metric("Resources Deployed (ambulances)", total_ambulances)

    # Live conversation log (playback)
    with log_container:
        st.subheader("Live Conversation Log")
        for msg in transcript:
            render_message(msg)
            time.sleep(0.4)

    # Reporter card at bottom
    st.header("Reporter Summary")
    report = out.get("report", {})
    st.write(report.get("text_summary", "No report available."))
    st.download_button("Download full report JSON", data=json.dumps(report, indent=2), file_name="report.json")

    # Also show raw outputs for debugging
    with st.expander("Raw Outputs"):
        st.subheader("Plan")
        st.json(out.get("plan"))
        st.subheader("Allocations")
        st.json(out.get("allocations"))
        st.subheader("Routes")
        st.json(out.get("routes"))
        st.subheader("Comms")
        st.json(out.get("comms"))

else:
    st.write("Click 'Start Swarm Run' to activate the agents for the provided scenario.")

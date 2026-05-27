"""Streamlit dashboard for CrisisSwarm."""
import os
import sys
import streamlit as st
import json
import time
from typing import List, Dict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.scenario import load_demo_scenario
from core.swarm import run_swarm
from core import groq_client

st.set_page_config(page_title="CrisisSwarm Dashboard", layout="wide")

st.title("CrisisSwarm — Multi-Agent Disaster Response")

if groq_client.is_configured():
    ok, msg = groq_client.verify_connection()
    if ok:
        st.success(f"Groq live — {msg}")
    else:
        st.error(
            "**Groq key is in `.env` but the API is NOT working** — your console will show "
            "**0 API calls** until this is fixed. The app still runs using **offline rules** "
            "(regex + math), not AI.\n\n"
            f"Error: {msg}\n\n"
            "Fix: In [Groq API Keys](https://console.groq.com/keys), click **Create API Key**, "
            "copy the full `gsk_...` secret immediately, replace `GROQ_API_KEY` in `.env`, save, "
            "then restart Streamlit."
        )
else:
    st.warning(
        "No Groq API key. Set `GROQ_API_KEY` in `.env`. "
        "Until then the swarm uses **offline heuristics only** (no AI)."
    )

st.subheader("Disaster Scenario Input")
default_scenario = load_demo_scenario()
scenario_text = st.text_area("Scenario text", value=default_scenario, height=140)

col1, col2 = st.columns([3, 1])

with col2:
    st.markdown("### \n")
    st.markdown(
        "<div style='background-color:#d9534f;color:white;padding:12px;border-radius:8px;text-align:center;font-weight:700'>ACTIVATE SWARM</div>",
        unsafe_allow_html=True,
    )

with col1:
    st.markdown("**Metrics**")
    metrics_cols = st.columns(3)
    metrics_cols[0].metric("Active Agents", 0)
    metrics_cols[1].metric("Casualties Triaged", 0)
    metrics_cols[2].metric("Resources Deployed", 0)
    live_render = st.checkbox("Live render transcript", value=True)

AGENT_COLORS = {
    "Situation": "#636efa",
    "Commander": "#1f77b4",
    "Triage": "#ff7f0e",
    "Resource": "#2ca02c",
    "Routing": "#d62728",
    "Comms": "#9467bd",
    "Reporter": "#8c564b",
    "Analysis": "#17becf",
    "Verifier": "#e377c2",
}


def render_message(msg: Dict[str, str]):
    agent = msg.get("agent", "unknown")
    text = msg.get("message", "")
    color = AGENT_COLORS.get(agent, "#444444")
    html = f"""
    <div style='border-radius:8px;padding:8px;margin:6px 0;background-color:{color};color:white;'>
      <strong>{agent}</strong><div style='font-size:90%'>{text}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_transcript(transcript: List[Dict[str, str]], live: bool) -> None:
    if not transcript:
        st.write("No transcript available.")
        return
    if not live:
        for msg in transcript:
            render_message(msg)
        return

    placeholder = st.empty()
    rendered: List[Dict[str, str]] = []
    batch_size = 4
    delay_seconds = 0.06
    for idx in range(0, len(transcript), batch_size):
        rendered.extend(transcript[idx:idx + batch_size])
        with placeholder.container():
            for msg in rendered:
                render_message(msg)
        time.sleep(delay_seconds)


log_container = st.container()

if st.button("ACTIVATE SWARM", key="start_swarm"):
    with st.spinner("Running multi-agent analysis..."):
        out = run_swarm(scenario_text)

    if out.get("error"):
        st.error(out.get("error"))
        if out.get("trace"):
            st.code(out["trace"])
        st.stop()

    plan = out.get("plan", {})
    for label, blob in [
        ("Commander", plan),
        ("Triage", plan.get("triage", {})),
        ("Resource", out.get("allocations", {})),
        ("Routing", out.get("routes", {})),
        ("Comms", out.get("comms", {})),
        ("Reporter", out.get("report", {})),
    ]:
        if isinstance(blob, dict) and blob.get("llm_error"):
            st.warning(f"{label} fell back to heuristics: {blob['llm_error']}")

    transcript = out.get("transcript", [])
    situation = out.get("situation", {})
    analysis = out.get("analysis", {})

    total_casualties = 0
    for info in plan.get("triage", {}).get("zones", {}).values():
        total_casualties += info.get("estimated_total", 0)

    allocations = out.get("allocations", {}).get("allocations", [])
    total_ambulances = sum(a.get("ambulances", 0) for a in allocations)
    active_agents = len({m.get("agent") for m in transcript})

    metrics_cols = st.columns(3)
    metrics_cols[0].metric("Active Agents", active_agents)
    metrics_cols[1].metric("Casualties Triaged", total_casualties)
    metrics_cols[2].metric("Resources Deployed (ambulances)", total_ambulances)

    if situation.get("summary"):
        st.subheader("Situation Understanding")
        st.write(situation.get("summary"))
        cols = st.columns(4)
        cols[0].caption(f"Type: {situation.get('disaster_type', '—')}")
        cols[1].caption(f"Location: {situation.get('location', '—')}")
        cols[2].caption(f"Severity: {situation.get('severity', '—')}")
        cols[3].caption(f"Source: {situation.get('source', '—')}")

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

    verification = out.get("verification", {})
    st.subheader("Verification Layer")
    v_status = verification.get("verification_status", "UNKNOWN")
    if v_status == "PASSED":
        st.success(
            f"Verification **PASSED** — confidence "
            f"{verification.get('confidence_score', 0):.2f}"
        )
    elif v_status == "FAILED":
        st.error(
            f"Verification **FAILED** — confidence "
            f"{verification.get('confidence_score', 0):.2f}"
        )
    else:
        st.warning(f"Verification status: {v_status}")

    v_cols = st.columns(2)
    v_cols[0].metric("Confidence Score", verification.get("confidence_score", 0))
    approval = verification.get("requires_human_approval", False)
    v_cols[1].metric(
        "Human Approval",
        "Required" if approval else "Not required",
    )

    issues = verification.get("issues_found", [])
    if issues:
        st.markdown("**Issues found**")
        for issue in issues:
            st.markdown(
                f"- **[{issue.get('severity', '?')}] {issue.get('type', 'ISSUE')}**: "
                f"{issue.get('message', '')}"
            )
            if issue.get("recommended_fix"):
                st.caption(f"Fix: {issue['recommended_fix']}")

    missing = verification.get("missing_data", [])
    if missing:
        st.markdown("**Missing data**")
        for item in missing:
            st.markdown(f"- {item}")

    if verification.get("recommendations"):
        st.markdown("**Verifier recommendations**")
        for rec in verification["recommendations"]:
            st.markdown(f"- {rec}")

    with log_container:
        st.subheader("Live Conversation Log")
        render_transcript(transcript, live_render)

    st.header("Reporter Summary")
    report = out.get("report", {})
    st.write(report.get("text_summary", "No report available."))
    st.download_button(
        "Download full report JSON",
        data=json.dumps({**report, "analysis": analysis}, indent=2),
        file_name="report.json",
    )

    with st.expander("Raw Outputs"):
        st.subheader("Situation")
        st.json(situation)
        st.subheader("Plan")
        st.json(plan)
        st.subheader("Allocations")
        st.json(out.get("allocations"))
        st.subheader("Routes")
        st.json(out.get("routes"))
        st.subheader("Comms")
        st.json(out.get("comms"))
        st.subheader("Analysis")
        st.json(analysis)
        st.subheader("Verification")
        st.json(verification)

else:
    st.write("Click 'ACTIVATE SWARM' to run Groq-backed triage and operational analysis.")

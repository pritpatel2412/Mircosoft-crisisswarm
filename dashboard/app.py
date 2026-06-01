"""CrisisSwarm Command Center — map · replay · debate · human gate · arena."""
import os
import sys
import json
from typing import List, Dict, Any, Optional

import streamlit as st
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
    zoom_for_scenario,
    detect_scenario_name,
)
from core.swarm import run_swarm, finalize_mission, run_aftershock_rerun, run_swarm_partial, run_swarm_complete
from core.arena import run_arena, STRATEGIES, _rank_results, _build_comparison
from core.human_gate import needs_human_gate
from core.sitrep import build_sitrep_text, build_responsible_ai_scorecard
from core import groq_client
from dashboard.ui_helpers import (
    render_command_map,
    render_replay_controls,
    render_human_gate,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CrisisSwarm Command Center",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CrisisSwarm Premium stylesheet
css_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Render Promo Banner and Top Navigation Bar
st.markdown("""
<div class="promo-banner">
    Frontier AI in Emergency Logistics &mdash; Powered by <strong>Groq (Llama 3.3 70B)</strong>
    <a href="https://console.groq.com/" target="_blank">Explore Groq Console &rarr;</a>
</div>
<div class="top-nav">
    <a class="top-nav-logo" href="#">CRISIS SWARM_ <span style="font-family:'Inter'; font-weight:400; font-size:14px; color:var(--colors-primary);">COMMAND_CENTER</span></a>
    <div class="top-nav-links">
        <a href="#active-command-center">Command Center</a>
        <a href="#verification-results">AI Scorecard</a>
        <a href="#agent-debate-chamber">Debate Chamber</a>
        <a href="#live-agent-transcript">Agent Log</a>
    </div>
    <a class="top-nav-cta" href="https://github.com/pritpatel2412/Mircosoft-crisisswarm" target="_blank">View Repository</a>
</div>
""", unsafe_allow_html=True)

if "mission" not in st.session_state:
    st.session_state.mission = None
if "officer_name" not in st.session_state:
    st.session_state.officer_name = "Incident Commander"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## CrisisSwarm")
    st.caption("Digital Twin Command Center")
    st.divider()

    officer = st.text_input("Incident Commander", st.session_state.officer_name)
    st.session_state.officer_name = officer

    run_mode = st.radio("Run mode", ["Single Swarm", "Swarm Arena (A vs B)"])

    st.divider()
    st.markdown("**Safety settings**")
    strict_gate = st.checkbox("Strict human gate (always require approval)", value=False)
    conflict_demo = st.checkbox(
        "Conflict demo (trigger verifier failure)",
        value=False,
        help="Forces 'only 5 ambulances available' — verifier will catch it.",
    )
    inject_aftershock = st.checkbox("Arena: inject aftershock between rounds", value=True)

    st.divider()
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
            else:
                st.error(
                    "**Groq key is in `.env` but the API is NOT working.** "
                    "The app runs on offline heuristics until fixed.\n\n"
                    f"Error: {msg}"
                )
    else:
        st.warning("No Groq API key. Set `GROQ_API_KEY` in `.env` for live AI agents.")

# ── Agent colour map ──────────────────────────────────────────────────────────
AGENT_COLORS: Dict[str, str] = {
    "Situation": "#636efa", "Commander": "#1f77b4", "Triage": "#ff7f0e",
    "Resource": "#2ca02c", "Routing": "#d62728", "Comms": "#9467bd",
    "Reporter": "#8c564b", "Analysis": "#17becf", "Verifier": "#e377c2",
    "DigitalTwin": "#bcbd22", "Forecast": "#7f7f7f", "Trust": "#3a7ebf",
    "Marketplace": "#e07b39", "WhatIf": "#5a9e6f", "AfterAction": "#8b6bad",
    "Multilingual": "#c45c8a", "Debate:Resource": "#c55a11",
    "Debate:Routing": "#c00000", "Debate:Commander": "#1a5276",
}

SCENARIO_BUTTON_LABELS = {
    "Mumbai Earthquake": "🌏 Mumbai Earthquake",
    "Florida Hurricane": "🌀 Florida Hurricane",
    "Tokyo Flood": "🌊 Tokyo Flood",
    "Turkey Earthquake": "🏔️ Turkey Earthquake",
    "Chennai Cyclone": "🌪️ Chennai Cyclone",
}


def _render_msg(msg: Dict[str, str]) -> None:
    agent = msg.get("agent", "?")
    color = AGENT_COLORS.get(agent, "var(--colors-steel)")
    st.markdown(
        f"<div style='border-radius: 8px; padding: 12px 16px; margin: 8px 0;"
        f"background: var(--colors-cream-soft); border: 1px solid var(--colors-beige-deep);"
        f"border-left: 4px solid {color}; color: var(--colors-ink);'>"
        f"<strong style='color:{color}; font-size: 14px;'>{agent}</strong>"
        f"<div style='font-size:13px; margin-top: 4px; line-height: 1.5;'>{msg.get('message','')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _scenario_text(base: str, conflict: bool) -> str:
    if conflict:
        return (
            f"{base}\n\nFleet status: only 5 ambulances available in Mumbai. "
            "Do not over-allocate."
        )
    return base


def _maybe_auto_approve(mission: Dict[str, Any], strict: bool, off: str) -> Dict[str, Any]:
    if mission.get("status") != "awaiting_human_approval":
        return mission
    if needs_human_gate(mission.get("verification", {}), strict=strict):
        return mission
    return finalize_mission(mission, "approved", officer=off, notes="Auto-approved — verifier passed")


# ── Debate chamber renderer ───────────────────────────────────────────────────
def render_debate(debate: Dict[str, Any]) -> None:
    if not debate or not debate.get("rounds"):
        return
    st.subheader("Agent Debate Chamber")
    st.caption(
        "Agents publish conflicting proposals before the plan is finalised. "
        "Commander mediates and issues the binding decision."
    )
    round_colors = {"Resource": "var(--colors-primary)", "Routing": "var(--colors-sunset-500)", "Commander": "var(--colors-ink)"}
    for rnd in debate.get("rounds", []):
        speaker = rnd.get("speaker", "?")
        color = round_colors.get(speaker, "#555")
        stance = rnd.get("stance", "").replace("_", " ").title()
        st.markdown(
            f"<div style='border-left:4px solid {color}; padding: 12px 16px;"
            f"margin:12px 0; background: var(--colors-cream-soft); border-radius: 8px;"
            f"border-top: 1px solid var(--colors-beige-deep); border-right: 1px solid var(--colors-beige-deep); border-bottom: 1px solid var(--colors-beige-deep);'>"
            f"<strong style='color:{color}; font-size:15px;'>Round {rnd.get('round')} &mdash; {speaker}</strong>"
            f"&nbsp;<span style='color: var(--colors-slate); font-size:85%'>[{stance}]</span>"
            f"<div style='margin-top:6px; font-size: 14px; line-height: 1.5;'>{rnd.get('message','')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        # Show zone-level proposals / counter-proposals compactly
        props = rnd.get("proposals") or rnd.get("counter_proposals") or rnd.get("final_allocations") or []
        if props:
            rows = []
            for p in props:
                rows.append({
                    "Zone": p.get("zone", "?"),
                    "Ambulances": p.get("ambulances", "—"),
                    "Rationale": p.get("rationale", p.get("basis", "—"))[:60],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.info(debate.get("outcome_summary", ""))


# ── Responsible AI panel ──────────────────────────────────────────────────────
def render_responsible_ai_panel(mission: Dict[str, Any]) -> None:
    scorecard = build_responsible_ai_scorecard(mission)
    grade = scorecard["grade"]
    score = scorecard["score"]

    st.subheader("Responsible AI Scorecard")
    col_score, col_detail = st.columns([1, 3])
    with col_score:
        st.markdown(
            f"<div style='text-align:center;padding:24px 16px;"
            f"background: linear-gradient(135deg, var(--colors-primary) 0%, var(--colors-primary-deep) 100%);"
            f"color:white;border-radius:12px;box-shadow: rgba(0,0,0,0.08) 0px 4px 12px;'>"
            f"<div style='font-family: \"Playfair Display\", serif; font-size:64px;font-weight:700;line-height:1;'>{grade}</div>"
            f"<div style='font-size:20px;font-weight:600;margin-top:8px;'>{score}/100</div>"
            f"<div style='font-size:12px;opacity:0.85;margin-top:4px;'>{scorecard['passed']}/{scorecard['total']} checks passed</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_detail:
        for c in scorecard["checks"]:
            icon = "✅" if c["status"] == "pass" else ("⚠️" if c["status"] == "warn" else "❌")
            st.markdown(f"""
            <div style="border-bottom: 1px solid var(--colors-hairline-soft); padding: 8px 0; font-size: 14px;">
                {icon} <strong>{c['check']}</strong> &mdash; <span style="color: var(--colors-slate);">{c['detail']}</span>
            </div>
            """, unsafe_allow_html=True)


# ── Arena renderer ────────────────────────────────────────────────────────────
def render_arena(arena: Dict[str, Any]) -> None:
    st.header("Swarm Arena — Battle Results")

    comparison = arena.get("comparison", {})
    winner = arena.get("winner")

    # Top KPI row
    if winner:
        m = winner.get("metrics", {})
        st.markdown(f"""
        <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; width: 100%;">
            <div class="metric-container" style="flex: 1; min-width: 180px; background-color: var(--colors-cream); border-color: var(--colors-beige-deep);">
                <span class="metric-label">Arena Winner</span>
                <span class="metric-value" style="color: var(--colors-primary-deep); font-size: 26px; font-weight: 700;">{winner.get('label', '?')}</span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 180px;">
                <span class="metric-label">Lives Saved (Winner)</span>
                <span class="metric-value" style="color: var(--colors-primary);">{m.get('lives_saved', 0)}</span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 180px;">
                <span class="metric-label">Response Time</span>
                <span class="metric-value">{m.get('response_time_min', 0)} <span style="font-size: 16px; color: var(--colors-steel);">min</span></span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 180px;">
                <span class="metric-label">Mission Score</span>
                <span class="metric-value">{m.get('mission_score', 0)}<span style="font-size: 16px; color: var(--colors-steel);">/100</span></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Bar charts side by side
    if comparison:
        chart_cols = st.columns(3)
        for i, (key, title) in enumerate([
            ("lives_saved", "Lives Saved"),
            ("response_time_min", "Response Time (min)"),
            ("mission_score", "Mission Score"),
        ]):
            data = comparison.get(key, {}).get("values", {})
            if data:
                import pandas as pd
                df = pd.DataFrame({
                    "Strategy": list(data.keys()),
                    title: list(data.values())
                })
                with chart_cols[i]:
                    st.subheader(title)
                    st.bar_chart(df.set_index("Strategy"), use_container_width=True)

    with st.expander("Full arena JSON"):
        st.json(arena)


# ── Single-mission renderer ───────────────────────────────────────────────────
def render_mission(mission: Dict[str, Any], off: str) -> None:
    if mission.get("error"):
        st.error(mission["error"])
        if mission.get("trace"):
            st.code(mission["trace"])
        return

    verification = mission.get("verification", {})
    replay       = mission.get("replay", {})
    routes       = mission.get("routes", {})
    human_approval = mission.get("human_approval")
    trust        = mission.get("trust", {})
    debate       = mission.get("debate", {})
    status       = mission.get("status", "completed")

    # Human gate blocks further rendering
    if status == "awaiting_human_approval":
        render_human_gate(mission, off)
        st.stop()

    # ── Metrics ──────────────────────────────────────────────────────────────
    metrics = mission.get("metrics", {})
    if metrics:
        st.markdown(f"""
        <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; width: 100%;">
            <div class="metric-container" style="flex: 1; min-width: 160px;">
                <span class="metric-label">Lives Saved</span>
                <span class="metric-value" style="color: var(--colors-primary);">{metrics.get('lives_saved', 0)}</span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 160px;">
                <span class="metric-label">Response Time</span>
                <span class="metric-value">{metrics.get('response_time_min', 0)} <span style="font-size: 16px; font-weight: 400; color: var(--colors-steel);">min</span></span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 160px;">
                <span class="metric-label">Zone Coverage</span>
                <span class="metric-value">{metrics.get('coverage_pct', 0)}<span style="font-size: 16px; font-weight: 400; color: var(--colors-steel);">%</span></span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 160px;">
                <span class="metric-label">Risk Level</span>
                <span class="metric-value">{metrics.get('risk_score', 0)}<span style="font-size: 16px; font-weight: 400; color: var(--colors-steel);">%</span></span>
            </div>
            <div class="metric-container" style="flex: 1; min-width: 160px; background-color: var(--colors-cream); border-color: var(--colors-beige-deep);">
                <span class="metric-label" style="color: var(--colors-ink);">Mission Score</span>
                <span class="metric-value" style="color: var(--colors-primary-deep); font-weight: 700;">{metrics.get('mission_score', 0)}<span style="font-size: 16px; font-weight: 400; color: var(--colors-steel);">/100</span></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Map + replay ──────────────────────────────────────────────────────────
    st.subheader("Live Command Map")
    frames = replay.get("frames", [])
    world  = mission.get("digital_twin", {})
    if frames:
        idx   = render_replay_controls(replay)
        world = frames[idx].get("world", world)
    render_command_map(world, routes=routes)

    # ── Action row ────────────────────────────────────────────────────────────
    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        if st.button("Judge: Inject Aftershock & Re-plan", use_container_width=True):
            with st.spinner("Applying aftershock..."):
                st.session_state.mission = run_aftershock_rerun(mission)
            st.rerun()
    with ac2:
        sitrep_text = build_sitrep_text(mission)
        st.download_button(
            "Download SitRep (txt)",
            data=sitrep_text,
            file_name="crisisswarm_sitrep.txt",
            use_container_width=True,
        )
    with ac3:
        audit = {
            "verification": verification,
            "human_approval": human_approval,
            "metrics": metrics,
            "debate_summary": debate.get("outcome_summary"),
            "responsible_ai": build_responsible_ai_scorecard(mission),
            "replay_steps": [f.get("step") for f in frames],
        }
        st.download_button(
            "Download Audit Log (JSON)",
            data=json.dumps(audit, indent=2),
            file_name="crisisswarm_audit.json",
            use_container_width=True,
        )

    # ── Verification ──────────────────────────────────────────────────────────
    v_status = verification.get("verification_status", "UNKNOWN")
    if v_status == "PASSED":
        st.success(f"Verification PASSED (confidence {verification.get('confidence_score', 0)})")
    elif v_status == "FAILED":
        st.error(f"Verification FAILED (confidence {verification.get('confidence_score', 0)})")
        for issue in verification.get("issues_found", []):
            if isinstance(issue, dict):
                st.warning(f"[{issue.get('severity')}] {issue.get('type')}: {issue.get('message')}")
            else:
                st.warning(str(issue))

    # ── Responsible AI panel ──────────────────────────────────────────────────
    render_responsible_ai_panel(mission)

    # ── Agent Debate Chamber ──────────────────────────────────────────────────
    render_debate(debate)

    # ── Trust explanations ────────────────────────────────────────────────────
    if trust.get("explanations"):
        with st.expander("Human Trust — Why these decisions?", expanded=False):
            for ex in trust["explanations"]:
                st.markdown(f"**{ex.get('decision')}**")
                for r in ex.get("because", []):
                    st.markdown(f"  - {r}")

    # ── Forecast ─────────────────────────────────────────────────────────────
    forecast = mission.get("forecast", {})
    if forecast.get("timeline"):
        with st.expander("Disaster Forecast", expanded=False):
            st.write(forecast.get("forecast_summary", ""))
            for block in forecast["timeline"]:
                st.markdown(f"**+{block.get('horizon_hours')}h**")
                for p in block.get("predictions", []):
                    st.markdown(f"- {p}")

    # ── What-if ───────────────────────────────────────────────────────────────
    whatif = mission.get("whatif", {})
    if whatif.get("recommendation"):
        st.info(f"What-if Optimizer: {whatif['recommendation']}")

    # ── Marketplace ───────────────────────────────────────────────────────────
    marketplace = mission.get("marketplace", {})
    if marketplace.get("transfer_plan"):
        with st.expander("Resource Marketplace — Mutual Aid", expanded=False):
            st.write(marketplace.get("suggested_summary", ""))

    # ── After Action Review ───────────────────────────────────────────────────
    aar = mission.get("after_action", {})
    if aar.get("summary"):
        with st.expander("After Action Review", expanded=False):
            st.write(aar["summary"])
            for mistake in aar.get("mistakes", []):
                st.error(f"⚠ {mistake}")
            st.info(f"Improvement: {aar.get('improvement', '')}")
            st.metric("Potential additional lives saved", aar.get("potential_lives_saved", "+0"))

    # ── Live transcript ───────────────────────────────────────────────────────
    with st.expander("Live agent transcript", expanded=False):
        for msg in mission.get("transcript", []):
            _render_msg(msg)

    # ── Situation Report ──────────────────────────────────────────────────────
    report = mission.get("report", {})
    if report.get("text_summary"):
        st.header("Situation Report")
        st.write(report["text_summary"])


# ══════════════════════════════════════════════════════════════════════════════
# Main UI
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero-band-sunset" id="active-command-center">
    <div class="hero-left">
        <div class="hero-display-text">Frontier AI.<br/>In your hands.</div>
        <div class="hero-subtitle-text">
            CrisisSwarm coordinates 13 specialist agents across one situation brief, 
            triaging casualties, deploying ambulances, planning routes, and broadcasting multilingual alerts.
        </div>
    </div>
    <div class="hero-right" style="position: relative;">
        <!-- Natural sunset photography illustration in HSL canvas -->
        <div style="width: 260px; height: 260px; border-radius: 12px; background: linear-gradient(135deg, #FF9E2C 0%, #FF5A36 50%, #FF3E1B 100%); box-shadow: rgba(0,0,0,0.15) 0 8px 24px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 20px; box-sizing: border-box; border: 1px solid rgba(255,255,255,0.2);">
            <div style="font-family: 'Playfair Display', serif; font-size: 80px; font-weight: 700; color: white; line-height: 1;">CS</div>
            <div style="font-family: 'Inter', sans-serif; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 2px; color: white; margin-top: 10px;">CRISIS SWARM</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Preset scenarios
st.subheader("Preset Presets")
scenario_names = list(SCENARIOS.keys())
btn_cols = st.columns(5)
for i, name in enumerate(scenario_names):
    with btn_cols[i]:
        if st.button(
            SCENARIO_BUTTON_LABELS[name],
            use_container_width=True,
            key=f"scenario_btn_{i}",
        ):
            st.session_state.mission = None
            # Update the text area below by setting the value in session state
            st.session_state["scenario_input_value"] = SCENARIOS[name]

if "scenario_input_value" not in st.session_state:
    st.session_state["scenario_input_value"] = default_scenario

scenario_text = st.text_area("Disaster scenario", value=st.session_state["scenario_input_value"], height=120)

if st.button("ACTIVATE SWARM", type="primary"):
    text = _scenario_text(scenario_text, conflict_demo)

    if run_mode.startswith("Swarm Arena"):
        # ── Arena: step-by-step with live progress ────────────────────────────
        status_box = st.empty()
        progress   = st.progress(0, text="Arena starting…")
        strategies = ["medical_first", "resource_balanced"]
        total_steps = (2 if inject_aftershock else 1) * len(strategies)
        step = 0

        from core.digital_twin import DisasterWorld
        from core.situation import parse_situation
        from core.events import get_event
        from core.swarm import SwarmManager

        situation    = parse_situation(text)
        base_world   = DisasterWorld.from_situation(situation)
        manager      = SwarmManager()
        round_results: List[Dict[str, Any]] = []
        current_text = text

        for round_num in (1, 2):
            if round_num == 2 and not inject_aftershock:
                break
            round_label  = "initial" if round_num == 1 else "after_aftershock"
            swarm_results: List[Dict[str, Any]] = []

            for strategy in strategies:
                meta = STRATEGIES.get(strategy, {"label": strategy})
                status_box.info(
                    f"Round {round_num}/{'2' if inject_aftershock else '1'} — "
                    f"running **{meta.get('label', strategy)}**…"
                )
                world = base_world.clone()
                out = manager.run_full_scenario(
                    current_text,
                    strategy=strategy,
                    world=world,
                    round_label=round_label,
                    stop_before_finalize=False,
                )
                step += 1
                progress.progress(step / total_steps, text=f"Done: {meta.get('label', strategy)}")

                if out.get("error"):
                    swarm_results.append({
                        "strategy": strategy,
                        "label": meta.get("label", strategy),
                        "error": out.get("error"),
                    })
                    continue

                m = out.get("metrics", {})
                swarm_results.append({
                    "strategy": strategy,
                    "label": meta.get("label", strategy),
                    "description": meta.get("description", ""),
                    "round": round_num,
                    "metrics": m,
                    "verification_status": out.get("verification", {}).get("verification_status"),
                    "world_snapshot": out.get("digital_twin"),
                    "mission_score": m.get("mission_score", 0),
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
                current_text = (
                    f"{text}\n\n[EVENT] {event['label']}. "
                    "Casualties increased; re-coordinate response."
                )

        all_flat  = [r for rnd in round_results for r in rnd.get("results", [])]
        leaderboard = _rank_results(all_flat)
        st.session_state.mission = {
            "mode": "swarm_arena",
            "strategies": [STRATEGIES.get(s, {"id": s}) for s in strategies],
            "rounds": round_results,
            "leaderboard": leaderboard,
            "winner": leaderboard[0] if leaderboard else None,
            "aftershock_injected": inject_aftershock,
            "comparison": _build_comparison(leaderboard),
        }
        status_box.empty()
        progress.empty()

    else:
        # ── Single swarm ──────────────────────────────────────────────────────
        with st.spinner("Running digital-twin simulation…"):
            st.session_state.mission = run_swarm(text, await_human_approval=True)
            st.session_state.mission = _maybe_auto_approve(
                st.session_state.mission, strict_gate, officer
            )

# ── Render results ────────────────────────────────────────────────────────────
mission: Optional[Dict[str, Any]] = st.session_state.mission

if mission and mission.get("mode") == "swarm_arena":
    render_arena(mission)
elif mission:
    render_mission(mission, officer)
else:
    st.markdown("""
    <div class="card-cream" style="padding: 32px; text-align: center; margin-bottom: 24px;">
        <h3 class="serif-font" style="margin-top:0; font-size: 26px;">Swarm Pipeline Ready</h3>
        <p style="font-size:15px; color: var(--colors-slate); max-width: 600px; margin: 8px auto 24px;">
            Click <strong>ACTIVATE SWARM</strong> above to run. You will see the live map, crisis replay, agent debate, verifier, human approval gate, and Responsible AI scorecard.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ── Sunset Stripe & Footer ───────────────────────────────────────────────────
st.markdown("""
<div class="sunset-stripe-band"></div>
<div class="footer-region">
    <div class="footer-col">
        <div class="footer-col-title">CrisisSwarm</div>
        <p style="font-size: 13px; line-height: 1.5; color: var(--colors-slate); margin-top: 0;">
            Frontier AI-driven multi-agent coordination for emergency logistics and casualty triage. Made for Microsoft Build AI Hackathon 2026.
        </p>
    </div>
    <div class="footer-col">
        <div class="footer-col-title">Explore</div>
        <a href="#active-command-center">Command Center</a>
        <a href="#verification-results">AI Scorecard</a>
        <a href="#agent-debate-chamber">Debate Chamber</a>
    </div>
    <div class="footer-col">
        <div class="footer-col-title">Build</div>
        <a href="https://console.groq.com/" target="_blank">Groq API</a>
        <a href="https://streamlit.io/" target="_blank">Streamlit</a>
        <a href="https://deck.gl/pydeck" target="_blank">Pydeck</a>
    </div>
    <div class="footer-col">
        <div class="footer-col-title">Legal</div>
        <a href="#">Responsible AI License</a>
        <a href="#">Privacy Policy</a>
        <a href="#">Terms of Use</a>
    </div>
    <div class="footer-col">
        <div class="footer-col-title">Team</div>
        <span style="font-size: 13px; color: var(--colors-slate);">Tejas & Team</span>
    </div>
    <div class="footer-bottom">
        <span>&copy; 2026 CrisisSwarm. All rights reserved.</span>
        <span>Frontier AI. In your hands.</span>
    </div>
</div>
""", unsafe_allow_html=True)

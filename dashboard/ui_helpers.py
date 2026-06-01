"""Dashboard UI helpers — map, replay, responsible-AI badge."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from core.command_map import build_pydeck_map


def render_command_map(
    world: Dict[str, Any],
    routes: Optional[Dict[str, Any]] = None,
    height: int = 480,
) -> None:
    try:
        deck = build_pydeck_map(world, routes=routes, height=height)
        st.pydeck_chart(deck, use_container_width=True)
    except Exception as exc:
        st.warning(f"Map unavailable ({exc}). Showing zone table.")
        for z in world.get("zones", []):
            st.write(z)


def render_replay_controls(replay: Dict[str, Any]) -> int:
    frames = replay.get("frames", [])
    if not frames:
        st.caption("No replay frames recorded.")
        return 0
    labels = [f"{i}: {f.get('step', '?')}" for i, f in enumerate(frames)]
    idx = st.select_slider(
        "Crisis Replay Timeline",
        options=list(range(len(frames))),
        format_func=lambda i: labels[i],
        key="replay_frame_idx",
    )
    frame = frames[idx]
    st.caption(frame.get("detail", ""))
    return idx


def render_responsible_ai_badge(
    verification: Dict[str, Any],
    human_approval: Optional[Dict[str, Any]],
    trust: Optional[Dict[str, Any]],
) -> None:
    cols = st.columns(5)
    v_ok = verification.get("verification_status") == "PASSED"
    cols[0].metric("Rules Verified", "Yes" if v_ok else "Flagged")
    cols[1].metric(
        "Human Gate",
        human_approval.get("decision", "pending").title()
        if human_approval
        else ("Required" if verification.get("requires_human_approval") else "Clear"),
    )
    cols[2].metric(
        "Explainability",
        f"{len((trust or {}).get('explanations', []))} decisions",
    )
    cols[3].metric("Audit Log", "Ready")
    cols[4].metric("Offline Safe", "Yes")


def render_human_gate(
    mission: Dict[str, Any],
    officer: str,
) -> None:
    verification = mission.get("verification", {})
    st.markdown("""
    <div class="card-cream" style="margin-bottom: 24px; padding: 24px;">
        <h3 class="serif-font" style="margin-top: 0; color: var(--colors-primary-deep); font-size: 28px;">Human Command Gate</h3>
        <p style="font-size: 15px; margin-bottom: 0;">
            <strong>Verification Alert:</strong> Verifier flagged this plan. 
            <em>AI proposes &mdash; humans authorize.</em> Approve to release the situation report and execute in simulation.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    for issue in verification.get("issues_found", []):
        st.markdown(f"""
        <div style="background-color: #FFF4F2; border-left: 4px solid var(--colors-primary-deep); padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; color: var(--colors-ink);">
            <strong style="color: var(--colors-primary-deep);">[{issue.get('severity')}]</strong> {issue.get('message')}
        </div>
        """, unsafe_allow_html=True)

    notes = st.text_area("Commander notes (optional)", key="approval_notes")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Approve Plan", type="primary", use_container_width=True):
            from core.swarm import finalize_mission
            st.session_state.mission = finalize_mission(
                mission, "approved", officer=officer, notes=notes
            )
            st.rerun()
    with c2:
        if st.button("Reject Plan", use_container_width=True):
            from core.swarm import finalize_mission
            st.session_state.mission = finalize_mission(
                mission, "rejected", officer=officer, notes=notes
            )
            st.rerun()
    with c3:
        if st.button("Auto-fix & Re-run", use_container_width=True):
            st.session_state.force_rerun = True
            st.rerun()

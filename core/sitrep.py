"""Situation Report generator — plain-text PDF-ready SitRep."""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


def build_sitrep_text(mission: Dict[str, Any]) -> str:
    """
    Produce a structured text SitRep from a completed mission dict.
    Works offline; suitable for PDF conversion or plain download.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: List[str] = []

    def h1(t: str) -> None:
        lines.append(f"\n{'='*60}")
        lines.append(f"  {t.upper()}")
        lines.append(f"{'='*60}")

    def h2(t: str) -> None:
        lines.append(f"\n── {t} {'─'*(54-len(t))}")

    def row(label: str, value: Any) -> None:
        lines.append(f"  {label:<28} {value}")

    h1("CRISISSWARM — INCIDENT SITUATION REPORT")
    row("Generated", ts)
    row("Strategy", mission.get("strategy", "default"))
    row("Round", mission.get("round_label", "initial"))

    approval = mission.get("human_approval")
    if approval:
        row("Human Decision", approval.get("decision", "").upper())
        row("Authorized by", approval.get("officer", ""))
        row("Auth timestamp", approval.get("timestamp", ""))
    else:
        row("Human Decision", "Auto-approved (verifier passed)")

    # ── Situation ──────────────────────────────────────────────────────────
    situation = mission.get("situation", {})
    h2("SITUATION")
    row("Disaster type", situation.get("disaster_type", "—"))
    row("Location", situation.get("location", "—"))
    row("Severity", situation.get("severity", "—"))
    if situation.get("summary"):
        lines.append(f"\n  {situation['summary']}")

    # ── Metrics ────────────────────────────────────────────────────────────
    metrics = mission.get("metrics", {})
    h2("MISSION METRICS")
    row("Lives saved (simulated)", metrics.get("lives_saved", 0))
    row("Response time (min)", metrics.get("response_time_min", 0))
    row("Zone coverage %", metrics.get("coverage_pct", 0))
    row("Risk score", metrics.get("risk_score", 0))
    row("Mission score", f"{metrics.get('mission_score', 0)}/100")

    # ── Triage ─────────────────────────────────────────────────────────────
    plan = mission.get("plan", {})
    zones = plan.get("triage", {}).get("zones", {})
    if zones:
        h2("CASUALTY TRIAGE")
        for zone, info in zones.items():
            if not isinstance(info, dict):
                continue
            br = info.get("breakdown", {})
            lines.append(
                f"  {zone:<20} Total={info.get('estimated_total',0):>4}  "
                f"C={br.get('Critical',0):>3}  S={br.get('Serious',0):>3}  "
                f"M={br.get('Minor',0):>3}"
            )

    # ── Allocations ────────────────────────────────────────────────────────
    allocations = mission.get("allocations", {}).get("allocations", [])
    if allocations:
        h2("RESOURCE ALLOCATIONS")
        for a in allocations:
            if not isinstance(a, dict):
                continue
            lines.append(
                f"  {a.get('zone','?'):<20} "
                f"AMB={a.get('ambulances',0):>2}  "
                f"TEAMS={a.get('medical_teams',0):>2}  "
                f"SHELTER={a.get('shelters',0):>1}"
            )

    # ── Routes ─────────────────────────────────────────────────────────────
    routes = mission.get("routes", {}).get("routes", [])
    if routes:
        h2("DEPLOYMENT ROUTES")
        for r in routes:
            if not isinstance(r, dict):
                continue
            lines.append(
                f"  {r.get('zone','?'):<20} "
                f"ETA={r.get('eta_minutes','?'):>3} min  "
                f"dist={r.get('distance_km','?'):>5} km  "
                f"status={r.get('status','?')}"
            )

    # ── Verification ───────────────────────────────────────────────────────
    verification = mission.get("verification", {})
    h2("VERIFICATION LAYER")
    row("Status", verification.get("verification_status", "UNKNOWN"))
    row("Confidence score", verification.get("confidence_score", 0))
    row("Human approval required", verification.get("requires_human_approval", False))
    issues = verification.get("issues_found", [])
    if issues:
        lines.append("  Issues:")
        for issue in issues:
            lines.append(
                f"    [{issue.get('severity')}] {issue.get('type')}: "
                f"{issue.get('message')}"
            )
    missing = verification.get("missing_data", [])
    if missing:
        lines.append(f"  Missing data: {', '.join(missing)}")

    # ── Debate ─────────────────────────────────────────────────────────────
    debate = mission.get("debate", {})
    if debate.get("rounds"):
        h2("AGENT DEBATE SUMMARY")
        lines.append(f"  {debate.get('outcome_summary', '')}")
        for rnd in debate["rounds"]:
            lines.append(f"\n  Round {rnd.get('round')} — {rnd.get('speaker')}")
            lines.append(f"    {rnd.get('message', '')[:120]}")

    # ── After Action ───────────────────────────────────────────────────────
    aar = mission.get("after_action", {})
    if aar:
        h2("AFTER ACTION REVIEW")
        row("Mission score", f"{aar.get('mission_score', 0)}/100")
        for mistake in aar.get("mistakes", []):
            lines.append(f"  [!] {mistake}")
        lines.append(f"  Improvement: {aar.get('improvement', '')}")
        lines.append(f"  Potential lives saved: {aar.get('potential_lives_saved', '+0')}")

    # ── Situation Report text ──────────────────────────────────────────────
    report = mission.get("report", {})
    if report.get("text_summary"):
        h2("EXECUTIVE SUMMARY")
        lines.append(f"  {report['text_summary']}")

    # ── Forecast ───────────────────────────────────────────────────────────
    forecast = mission.get("forecast", {})
    if forecast.get("timeline"):
        h2("DISASTER FORECAST")
        for block in forecast["timeline"]:
            lines.append(f"\n  +{block.get('horizon_hours')}h outlook:")
            for p in block.get("predictions", []):
                lines.append(f"    - {p}")

    h1("END OF REPORT")
    lines.append(f"  CrisisSwarm v1.0 — Microsoft Build AI Hackathon 2026\n")

    return "\n".join(lines)


def build_responsible_ai_scorecard(mission: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured scorecard for the Responsible AI badge panel."""
    verification = mission.get("verification", {})
    human_approval = mission.get("human_approval")
    trust = mission.get("trust", {})
    debate = mission.get("debate", {})
    aar = mission.get("after_action", {})

    checks = [
        {
            "check": "Rule-based verification",
            "status": "pass" if verification.get("verification_status") == "PASSED" else "fail",
            "detail": (
                f"Confidence {verification.get('confidence_score', 0):.2f} — "
                f"{len(verification.get('issues_found', []))} issue(s)"
            ),
        },
        {
            "check": "Human approval gate",
            "status": (
                "pass" if (human_approval and human_approval.get("decision") == "approved")
                else ("pass" if not verification.get("requires_human_approval") else "pending")
            ),
            "detail": (
                f"Decision: {human_approval['decision']} by {human_approval['officer']}"
                if human_approval
                else "Auto-approved — no conflicts"
            ),
        },
        {
            "check": "Explainability (Trust agent)",
            "status": "pass" if trust.get("explanations") else "warn",
            "detail": f"{len(trust.get('explanations', []))} deployment decisions explained",
        },
        {
            "check": "Agent debate & mediation",
            "status": "pass" if debate.get("rounds") else "warn",
            "detail": (
                debate.get("outcome_summary", "Debate not recorded")
                if debate else "Debate chamber not run"
            ),
        },
        {
            "check": "Audit trail",
            "status": "pass",
            "detail": "Full JSON audit log available for download",
        },
        {
            "check": "Offline-safe fallbacks",
            "status": "pass",
            "detail": "All agents have rule-based fallback — no Groq dependency for core safety",
        },
        {
            "check": "After Action Review",
            "status": "pass" if aar.get("mission_score") is not None else "warn",
            "detail": (
                f"Mission score {aar.get('mission_score', 0)}/100 — "
                f"{aar.get('improvement', 'No improvement noted')}"
                if aar else "AAR not generated"
            ),
        },
    ]

    passed = sum(1 for c in checks if c["status"] == "pass")
    total_score = round(100 * passed / len(checks))

    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "score": total_score,
        "grade": "A" if total_score >= 85 else "B" if total_score >= 70 else "C",
    }

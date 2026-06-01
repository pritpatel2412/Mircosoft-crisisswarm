"""End-to-end demo: swarm -> human gate -> approve -> aftershock rerun."""
import json

from core.scenario import load_demo_scenario
from core.swarm import run_swarm, finalize_mission, run_aftershock_rerun


def main():
    scenario = load_demo_scenario()
    conflict = (
        f"{scenario}\n\nFleet status: only 5 ambulances available in Mumbai."
    )

    print("\n=== 1) Run swarm (await approval) ===")
    pending = run_swarm(conflict, await_human_approval=True)
    print("Status:", pending.get("status"))
    print("Verification:", pending.get("verification", {}).get("verification_status"))
    print("Issues:", len(pending.get("verification", {}).get("issues_found", [])))
    print("Replay frames:", pending.get("replay", {}).get("frame_count"))

    print("\n=== 2) Human approves ===")
    approved = finalize_mission(pending, "approved", officer="Demo Commander")
    print("Status:", approved.get("status"))
    print("Report snippet:", (approved.get("report", {}).get("text_summary") or "")[:120])

    print("\n=== 3) Judge aftershock + re-plan ===")
    rerun = run_aftershock_rerun(approved)
    print("Status:", rerun.get("status"))
    print("Metrics:", rerun.get("metrics"))
    print("\nDone — open dashboard: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()

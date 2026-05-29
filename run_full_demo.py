"""Full demo script: chains Commander -> Resource -> Routing -> Comms -> Reporter."""
from agents.commander import Commander
from agents.resource import allocate_resources
from agents.routing import plan_routes
from agents.comms import send_alerts
from agents.reporter import generate_report
from core.context import SwarmContext
from core.situation import parse_situation
import json

SCENARIO = (
    "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
    "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100)."
)


def main():
    print("\n=== CrisisSwarm Full Demo ===")
    situation = parse_situation(SCENARIO)
    ctx = SwarmContext(scenario_text=SCENARIO, situation=situation)

    commander = Commander()
    plan = commander.run_triage_then_plan(SCENARIO, context=ctx)
    allocations = allocate_resources(plan, context=ctx)
    routes = plan_routes(
        plan.get("task_assignments", []),
        context=ctx,
        allocations=allocations,
    )
    comms_out = send_alerts(context=ctx, plan=plan, allocations=allocations, routes=routes)
    from agents.verifier import verify_outputs
    verifier_out = verify_outputs(ctx, plan, allocations, routes, comms_out)
    report = generate_report(
        plan, allocations, routes, context=ctx, comms=comms_out, verifier=verifier_out
    )

    print("\n=== Demo Summary ===")
    print(
        json.dumps(
            {
                "situation": situation,
                "plan": plan,
                "allocations": allocations,
                "routes": routes,
                "comms": comms_out,
                "report": report,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

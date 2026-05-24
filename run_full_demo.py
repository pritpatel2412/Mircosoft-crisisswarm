"""Full demo script: chains Commander -> Resource -> Routing -> Comms -> Reporter."""
from agents.commander import Commander
from agents.resource import allocate_resources
from agents.routing import plan_routes
from agents.comms import send_alerts
from agents.reporter import generate_report
import json

SCENARIO = (
    "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
    "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100)."
)


def main():
    print('\n=== CrisisSwarm Full Demo ===')
    commander = Commander()
    plan = commander.run_triage_then_plan(SCENARIO)

    allocations = allocate_resources(plan)
    routes = plan_routes(plan.get('task_assignments', []))

    # Prepare simple alert items for comms
    alerts = []
    for alloc in allocations.get('allocations', []):
        zone = alloc.get('zone')
        alerts.append({
            'recipient_type': 'responder',
            'contact': None,
            'message': f"Deploy {alloc.get('ambulances')} ambulances and {alloc.get('medical_teams')} medical teams to {zone}.",
        })

    comms_out = send_alerts(alerts)
    report = generate_report(plan, allocations, routes)

    print('\n=== Demo Summary ===')
    print(json.dumps({'plan': plan, 'allocations': allocations, 'routes': routes, 'comms': comms_out, 'report': report}, indent=2))


if __name__ == '__main__':
    main()

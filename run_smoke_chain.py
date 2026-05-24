"""Smoke test script: run Commander -> Resource -> Routing chain."""
from agents.commander import Commander
from agents.resource import allocate_resources
from agents.routing import plan_routes
import json

scenario = (
    "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
    "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100)."
)

def main():
    print('\n--- Running Commander to get plan ---')
    commander = Commander()
    plan = commander.run_triage_then_plan(scenario)

    print('\n--- Running Resource Agent ---')
    res_alloc = allocate_resources(plan)

    print('\n--- Running Routing Agent ---')
    routes = plan_routes(plan.get('task_assignments', []))

    print('\n--- Combined Summary ---')
    print(json.dumps({'plan': plan, 'allocations': res_alloc, 'routes': routes}, indent=2))


if __name__ == '__main__':
    main()

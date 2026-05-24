from core.swarm import run_swarm
from core.scenario import load_demo_scenario
import json

if __name__ == '__main__':
    out = run_swarm(load_demo_scenario())
    print(json.dumps(out, indent=2))

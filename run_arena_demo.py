"""Demo: Swarm Arena — Medical First vs Resource Balanced."""
import json

from core.arena import run_arena
from core.scenario import load_demo_scenario


def main():
    print("\n=== CrisisSwarm Arena Demo ===\n")
    result = run_arena(load_demo_scenario(), inject_aftershock=True)
    print(json.dumps(result, indent=2))
    winner = result.get("winner")
    if winner:
        print(f"\nWinner: {winner.get('label')} (mission score {winner.get('mission_score')})")


if __name__ == "__main__":
    main()

"""Tests for crisis replay and command map."""
import unittest

from core.replay import CrisisReplay
from core.command_map import build_pydeck_map, _zone_rows
from core.digital_twin import DisasterWorld, ZoneState


class TestReplayMap(unittest.TestCase):
    def test_replay_capture_frames(self):
        replay = CrisisReplay()
        world = DisasterWorld()
        world.zones["Dharavi"] = ZoneState(name="Dharavi", casualties=100, critical=10)
        world._initial_critical = 10
        replay.capture("start", world.to_dict(), "init")
        world.apply_resource(
            {"allocations": [{"zone": "Dharavi", "ambulances": 3, "medical_teams": 1}]}
        )
        replay.capture("resource", world.to_dict(), "deploy")
        self.assertEqual(len(replay.frames), 2)

    def test_map_builds(self):
        world = {
            "zones": [
                {"name": "Dharavi", "casualties": 200, "critical": 20, "ambulances_deployed": 5},
                {"name": "Kurla", "casualties": 150, "critical": 15, "ambulances_deployed": 3},
            ]
        }
        rows = _zone_rows(world)
        self.assertEqual(len(rows), 2)
        deck = build_pydeck_map(world)
        self.assertIsNotNone(deck)


if __name__ == "__main__":
    unittest.main()

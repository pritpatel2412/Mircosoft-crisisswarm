"""Tests for Disaster Digital Twin."""
import unittest

from core.digital_twin import DisasterWorld, ZoneState
from core.events import get_event


class TestDigitalTwin(unittest.TestCase):
    def test_resource_reduces_critical(self):
        world = DisasterWorld()
        world.zones["Dharavi"] = ZoneState(name="Dharavi", casualties=200, critical=40)
        world._initial_critical = 40
        world.apply_resource(
            {
                "allocations": [
                    {
                        "zone": "Dharavi",
                        "ambulances": 10,
                        "medical_teams": 5,
                        "shelters": 1,
                    }
                ]
            },
            strategy="medical_first",
        )
        self.assertLess(world.zones["Dharavi"].critical, 40)

    def test_aftershock_increases_casualties(self):
        world = DisasterWorld()
        world.zones["A"] = ZoneState(name="A", casualties=100, critical=10)
        before = world.zones["A"].casualties
        world.apply_aftershock(get_event("aftershock"))
        self.assertGreater(world.zones["A"].casualties, before)

    def test_metrics_lives_saved(self):
        world = DisasterWorld()
        world.zones["A"] = ZoneState(name="A", casualties=100, critical=20)
        world._initial_critical = 20
        world.apply_resource(
            {"allocations": [{"zone": "A", "ambulances": 8, "medical_teams": 4}]},
            strategy="medical_first",
        )
        m = world.compute_metrics()
        self.assertGreater(m["lives_saved"], 0)


if __name__ == "__main__":
    unittest.main()

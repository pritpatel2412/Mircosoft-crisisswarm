"""Smoke tests for the main swarm pipeline."""
import unittest
from unittest.mock import patch

from core.scenario import load_demo_scenario
from core.swarm import run_swarm


class TestSwarmSmoke(unittest.TestCase):
    @patch("core.groq_client.verify_connection", return_value=(False, "GROQ_API_KEY is not set in .env"))
    @patch("core.groq_client.is_configured", return_value=False)
    def test_run_swarm_offline(self, _is_configured, _verify_connection):
        result = run_swarm(load_demo_scenario())
        self.assertNotIn("error", result)
        for key in (
            "mode",
            "situation",
            "plan",
            "allocations",
            "routes",
            "comms",
            "verification",
            "report",
            "analysis",
            "transcript",
            "agents_with_llm",
        ):
            self.assertIn(key, result)
        self.assertEqual(result["mode"], "offline_pipeline")


if __name__ == "__main__":
    unittest.main()

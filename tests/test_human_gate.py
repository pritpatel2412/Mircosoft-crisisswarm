"""Tests for human approval gate and finalize flow."""
import unittest
from unittest.mock import patch

from core.human_gate import needs_human_gate, build_approval_record
from core.swarm import run_swarm, finalize_mission
from core.scenario import load_demo_scenario


class TestHumanGate(unittest.TestCase):
    def test_needs_gate_on_failed_verification(self):
        v = {"verification_status": "FAILED", "requires_human_approval": True}
        self.assertTrue(needs_human_gate(v, strict=False))

    def test_strict_always_needs_gate(self):
        v = {"verification_status": "PASSED", "requires_human_approval": False}
        self.assertTrue(needs_human_gate(v, strict=True))

    @patch("core.groq_client.verify_connection", return_value=(False, "offline"))
    @patch("core.groq_client.is_configured", return_value=False)
    def test_finalize_after_pending(self, *_mocks):
        pending = run_swarm(load_demo_scenario(), await_human_approval=True)
        self.assertEqual(pending.get("status"), "awaiting_human_approval")
        done = finalize_mission(pending, "approved", officer="Test Officer")
        self.assertIn(done.get("status"), ("completed", "rejected"))
        self.assertIsNotNone(done.get("human_approval"))
        self.assertEqual(done["human_approval"]["decision"], "approved")


if __name__ == "__main__":
    unittest.main()

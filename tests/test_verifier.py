"""Unit tests for VerifierAgent rule-based feasibility checks."""
import unittest

from agents.verifier import verify_response_plan
from core.context import SwarmContext


def _base_plan(critical: int = 10) -> dict:
    return {
        "triage": {
            "zones": {
                "Dharavi": {
                    "estimated_total": 100,
                    "breakdown": {
                        "Critical": critical,
                        "Serious": 30,
                        "Minor": 70 - critical,
                    },
                },
            },
        },
        "task_assignments": [{"zone": "Dharavi", "est_total": 100}],
    }


def _base_allocations(ambulances: int = 2) -> dict:
    return {
        "allocations": [
            {
                "zone": "Dharavi",
                "ambulances": ambulances,
                "medical_teams": 1,
            },
        ],
    }


def _base_routes(status: str = "ok") -> dict:
    return {
        "routes": [
            {
                "zone": "Dharavi",
                "eta_minutes": 15,
                "status": status,
                "rationale": "Primary corridor.",
            },
        ],
    }


class TestVerifierAgent(unittest.TestCase):
    def _context(self, **situation_overrides) -> SwarmContext:
        situation = {
            "blocked_routes": ["Western Express Highway"],
            "operational_routes": ["Bandra-Worli Sea Link"],
            "infrastructure": {"hospitals_on_alert": 12},
            "resources": {"available_ambulances": 18},
        }
        situation.update(situation_overrides)
        return SwarmContext(
            scenario_text="12 hospitals on alert. 18 ambulances available.",
            situation=situation,
        )

    def test_resource_conflict_fails(self):
        ctx = self._context()
        result = verify_response_plan(
            _base_plan(),
            _base_allocations(ambulances=25),
            _base_routes(),
            context=ctx,
        )
        self.assertEqual(result["verification_status"], "FAILED")
        types = [i["type"] for i in result["issues_found"]]
        self.assertIn("RESOURCE_CONFLICT", types)
        self.assertTrue(result["requires_human_approval"])

    def test_blocked_route_fails(self):
        ctx = self._context()
        result = verify_response_plan(
            _base_plan(),
            _base_allocations(ambulances=2),
            _base_routes(status="blocked"),
            context=ctx,
        )
        self.assertEqual(result["verification_status"], "FAILED")
        types = [i["type"] for i in result["issues_found"]]
        self.assertIn("ROUTE_CONFLICT", types)

    def test_critical_without_ambulances_fails(self):
        ctx = self._context()
        result = verify_response_plan(
            _base_plan(critical=20),
            _base_allocations(ambulances=0),
            _base_routes(),
            context=ctx,
        )
        self.assertEqual(result["verification_status"], "FAILED")
        types = [i["type"] for i in result["issues_found"]]
        self.assertIn("PRIORITY_FAILURE", types)

    def test_valid_plan_passes(self):
        ctx = self._context()
        result = verify_response_plan(
            _base_plan(critical=5),
            _base_allocations(ambulances=3),
            _base_routes(status="ok"),
            context=ctx,
        )
        self.assertEqual(result["verification_status"], "PASSED")
        self.assertEqual(result["issues_found"], [])
        self.assertFalse(result["requires_human_approval"])
        self.assertEqual(result["agent"], "VerifierAgent")
        self.assertFalse(result["llm_used"])


if __name__ == "__main__":
    unittest.main()

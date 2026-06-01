"""Tests for Agent Debate Chamber and Responsible AI SitRep."""
import unittest

from core.debate import run_debate
from core.sitrep import build_sitrep_text, build_responsible_ai_scorecard


def _base_plan(critical: int = 20) -> dict:
    return {
        "triage": {
            "zones": {
                "Dharavi": {
                    "estimated_total": 200,
                    "breakdown": {"Critical": critical, "Serious": 60, "Minor": 80},
                },
                "Kurla": {
                    "estimated_total": 150,
                    "breakdown": {"Critical": 15, "Serious": 50, "Minor": 85},
                },
            }
        },
        "task_assignments": [],
    }


def _base_situation() -> dict:
    return {
        "blocked_routes": ["Western Express Highway"],
        "resources": {"available_ambulances": 18},
        "infrastructure": {"hospitals_on_alert": 12},
    }


class TestDebateChamber(unittest.TestCase):
    def test_debate_has_three_rounds(self):
        debate = run_debate(_base_plan(), _base_situation())
        self.assertEqual(len(debate["rounds"]), 3)

    def test_speakers_in_order(self):
        debate = run_debate(_base_plan(), _base_situation())
        speakers = [r["speaker"] for r in debate["rounds"]]
        self.assertEqual(speakers, ["Resource", "Routing", "Commander"])

    def test_commander_mediates_within_fleet(self):
        debate = run_debate(_base_plan(), _base_situation())
        decision = debate["mediated_decision"]
        fleet = _base_situation()["resources"]["available_ambulances"]
        self.assertLessEqual(decision["fleet_used"], fleet)

    def test_outcome_summary_present(self):
        debate = run_debate(_base_plan(), _base_situation())
        self.assertIn("ambulances", debate["outcome_summary"])

    def test_llm_used_false(self):
        debate = run_debate(_base_plan(), _base_situation())
        self.assertFalse(debate["llm_used"])


class TestSitRep(unittest.TestCase):
    def _mission(self) -> dict:
        return {
            "situation": {"disaster_type": "earthquake", "location": "Mumbai", "severity": "critical"},
            "metrics": {"lives_saved": 10, "response_time_min": 15, "coverage_pct": 66.0,
                        "risk_score": 12.0, "mission_score": 82},
            "plan": {
                "triage": {
                    "zones": {
                        "Dharavi": {"estimated_total": 200,
                                    "breakdown": {"Critical": 20, "Serious": 60, "Minor": 120}},
                    }
                }
            },
            "allocations": {"allocations": [{"zone": "Dharavi", "ambulances": 5,
                                              "medical_teams": 3, "shelters": 1}]},
            "routes": {"routes": [{"zone": "Dharavi", "eta_minutes": 17,
                                   "distance_km": 8.8, "status": "ok"}]},
            "verification": {"verification_status": "PASSED", "confidence_score": 0.95,
                             "requires_human_approval": False, "issues_found": []},
            "debate": {"rounds": [], "outcome_summary": ""},
            "after_action": {"mission_score": 82, "mistakes": [], "improvement": "Maintain strategy",
                             "potential_lives_saved": "+0"},
            "report": {"text_summary": "Situation under control."},
            "forecast": {"timeline": []},
            "trust": {"explanations": [{"decision": "Deploy 5 ambulances to Dharavi",
                                        "because": ["20 critical victims"]}]},
            "human_approval": None,
        }

    def test_sitrep_contains_key_sections(self):
        text = build_sitrep_text(self._mission())
        for section in ("CASUALTY TRIAGE", "RESOURCE ALLOCATIONS",
                        "VERIFICATION LAYER", "MISSION METRICS"):
            self.assertIn(section, text)

    def test_scorecard_grade_a(self):
        sc = build_responsible_ai_scorecard(self._mission())
        self.assertGreaterEqual(sc["score"], 70)
        self.assertIn(sc["grade"], ("A", "B", "C"))


if __name__ == "__main__":
    unittest.main()

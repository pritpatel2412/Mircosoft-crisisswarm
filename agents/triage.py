"""Triage Agent for CrisisSwarm.

Extracts per-zone casualty estimates from free-form disaster text and
applies a deterministic heuristic to classify victims into Critical,
Serious, and Minor categories. This offline implementation ensures the
demo works without Azure credentials; replace with an LLM pipeline later
for improved accuracy.
"""
from typing import Dict, Any
import re
import json
import traceback

AGENT_NAME = "Triage"

SYSTEM_MESSAGE = (
    "Triage Agent (Medical Triage Specialist): Given a disaster scenario, "
    "extract explicit zones and casualty counts, then produce a JSON with "
    "per-zone `estimated_total` and a `breakdown` into Critical/Serious/Minor.\n"
    "Output format: {agent, system_message, input_summary, zones: {zone: {estimated_total, breakdown}}}."
)


def _parse_zones(text: str) -> Dict[str, int]:
    """Parse zone casualty estimates from free text.

    This looks for patterns like 'Dharavi (200)'. If none are found it
    attempts a fallback search for an overall `Estimated N casualties`.
    """
    zones: Dict[str, int] = {}
    matches = re.findall(r"([A-Za-z\- ]+)\s*\((\d{1,5})\)", text)
    for name, num in matches:
        clean_name = name.strip()
        if clean_name.lower().startswith("and "):
            clean_name = clean_name[4:].strip()
        zones[clean_name] = int(num)
    if not zones:
        m = re.search(r"Estimated\s+(\d{2,6})\s+casualties", text, re.IGNORECASE)
        if m:
            zones["unknown"] = int(m.group(1))
    return zones


def _classify_counts(count: int) -> Dict[str, int]:
    """Heuristic: split counts into Critical (10%), Serious (30%), Minor (rest)."""
    critical = max(1, int(count * 0.1))
    serious = int(count * 0.3)
    minor = count - critical - serious
    return {"Critical": critical, "Serious": serious, "Minor": minor}


def triage_victims(scenario_text: str) -> Dict[str, Any]:
    """Process scenario text and return structured triage results.

    Args:
        scenario_text: free-form disaster description

    Returns:
        dict with `agent`, `system_message`, `input_summary`, and `zones`.
    """
    print("[Triage] Processing scenario text for casualty extraction")
    try:
        zones = _parse_zones(scenario_text)
        results: Dict[str, Any] = {}
        for zone, count in zones.items():
            split = _classify_counts(count)
            results[zone] = {"estimated_total": count, "breakdown": split}

        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "input_summary": scenario_text[:200],
            "zones": results,
        }
        print(f"[Triage] Output for agent {AGENT_NAME}:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Triage] Error during triage: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point expected by orchestration layers.

    Expects `message` to contain a `text` key with scenario content.
    """
    text = message.get("text", "")
    return triage_victims(text)


if __name__ == "__main__":
    demo = (
        "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
        "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100)."
    )
    triage_victims(demo)

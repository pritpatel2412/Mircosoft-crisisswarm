"""Triage Agent — casualty extraction and medical classification via Groq."""
from typing import Dict, Any, Tuple, Optional
import re
import json
import traceback

from core import groq_client
from core.context import SwarmContext
from core.agent_llm import agent_json_step

AGENT_NAME = "Triage"

SYSTEM_MESSAGE = (
    "Triage Agent (Medical Triage Specialist): Extract zones, classify casualties "
    "into Critical/Serious/Minor based on disaster severity and zone hazards."
)

_ZONE_REGEX = re.compile(r"([A-Za-z\- ]+)\s*\((\d{1,5})\)")

TRIAGE_SYSTEM = """You are a medical triage specialist. Using the scenario and situation brief,
return JSON:
{
  "narrative": "1-2 sentences on triage approach",
  "zones": {
    "ZoneName": {
      "estimated_total": <int>,
      "breakdown": {"Critical": <int>, "Serious": <int>, "Minor": <int>},
      "notes": "brief clinical/operational note"
    }
  }
}
Breakdown must sum to estimated_total. Prioritize higher Critical % in zones with blocked access or worse hazards."""


def _parse_zones_regex(text: str) -> Dict[str, int]:
    zones: Dict[str, int] = {}
    for name, num in _ZONE_REGEX.findall(text):
        zones[name.strip()] = int(num)
    return zones or {"unknown": 100}


def _classify_counts(count: int) -> Dict[str, int]:
    critical = max(1, int(count * 0.1))
    serious = int(count * 0.3)
    minor = count - critical - serious
    return {"Critical": critical, "Serious": serious, "Minor": minor}


def _offline_triage(scenario_text: str, situation: Dict[str, Any]) -> Dict[str, Any]:
    zone_counts: Dict[str, int] = {}
    for z in situation.get("zones", []):
        if isinstance(z, dict) and z.get("name"):
            zone_counts[z["name"]] = int(z.get("casualties", 0))
    if not zone_counts:
        zone_counts = _parse_zones_regex(scenario_text)

    results = {}
    for zone, count in zone_counts.items():
        results[zone] = {
            "estimated_total": count,
            "breakdown": _classify_counts(count),
            "notes": "",
        }
    return {
        "narrative": "Heuristic triage applied (offline).",
        "zones": results,
    }


def triage_victims(
    scenario_text: str,
    context: Optional[SwarmContext] = None,
) -> Dict[str, Any]:
    print("[Triage] Processing scenario with full situation context")
    situation = context.situation if context else {}
    try:

        def fallback():
            return _offline_triage(scenario_text, situation)

        if context:
            llm_out = agent_json_step(
                AGENT_NAME,
                TRIAGE_SYSTEM,
                context.prompt_block(),
                fallback,
            )
        elif groq_client.is_configured():
            llm_out = agent_json_step(
                AGENT_NAME,
                TRIAGE_SYSTEM,
                scenario_text,
                fallback,
            )
        else:
            llm_out = fallback()
            llm_out["llm_used"] = False

        zones_raw = llm_out.get("zones", {})
        results: Dict[str, Any] = {}
        for zone, info in zones_raw.items():
            if not isinstance(info, dict):
                continue
            total = int(info.get("estimated_total", 0))
            breakdown = info.get("breakdown") or _classify_counts(total)
            results[zone] = {
                "estimated_total": total,
                "breakdown": breakdown,
                "notes": info.get("notes", ""),
            }

        narrative = llm_out.get("narrative", "Triage complete.")
        output = {
            "agent": AGENT_NAME,
            "system_message": SYSTEM_MESSAGE,
            "input_summary": scenario_text[:200],
            "zones": results,
            "narrative": narrative,
            "llm_used": llm_out.get("llm_used", False),
        }
        print(f"[Triage] Output:", json.dumps(output, indent=2))
        return output
    except Exception as e:
        print(f"[Triage] Error: {e}\n{traceback.format_exc()}")
        return {"agent": AGENT_NAME, "error": str(e)}


def agent_entry(message: Dict[str, Any]) -> Dict[str, Any]:
    text = message.get("text", "")
    return triage_victims(text)

"""Initial disaster situation parsing via Groq."""
from __future__ import annotations

import re
from typing import Any, Dict

from core import groq_client

SITUATION_SYSTEM = """You are an emergency management analyst. Read the disaster alert and return JSON only:
{
  "disaster_type": "earthquake|flood|fire|hurricane|other",
  "location": "city/region string",
  "severity": "low|medium|high|critical",
  "summary": "2-3 sentence overview",
  "zones": [
    {"name": "ZoneName", "casualties": 0, "hazards": ["..."], "access": "open|limited|blocked"}
  ],
  "blocked_routes": ["road or area names"],
  "operational_routes": ["usable corridors"],
  "infrastructure": {"collapsed_buildings": 0, "hospitals_on_alert": 0, "notes": "..."},
  "immediate_priorities": ["short priority strings"]
}
Use integers for counts. Extract only what the text states or clearly implies."""


def _parse_situation_offline(scenario_text: str) -> Dict[str, Any]:
    zones = []
    for name, num in re.findall(r"([A-Za-z\- ]+)\s*\((\d{1,5})\)", scenario_text):
        zones.append({
            "name": name.strip(),
            "casualties": int(num),
            "hazards": [],
            "access": "unknown",
        })
    blocked = []
    if "blocked" in scenario_text.lower():
        m = re.search(r"([^.]*blocked[^.]*)", scenario_text, re.I)
        if m:
            blocked.append(m.group(1).strip())
    hospitals = 0
    hm = re.search(r"(\d+)\s+hospitals", scenario_text, re.I)
    if hm:
        hospitals = int(hm.group(1))
    buildings = 0
    bm = re.search(r"(\d+)\s+buildings?\s+collapsed", scenario_text, re.I)
    if bm:
        buildings = int(bm.group(1))
    return {
        "disaster_type": "other",
        "location": "unknown",
        "severity": "high",
        "summary": scenario_text[:300],
        "zones": zones,
        "blocked_routes": blocked,
        "operational_routes": [],
        "infrastructure": {
            "collapsed_buildings": buildings,
            "hospitals_on_alert": hospitals,
            "notes": "",
        },
        "immediate_priorities": ["Triage casualties", "Deploy medical teams"],
        "source": "offline",
    }


def parse_situation(scenario_text: str) -> Dict[str, Any]:
    """Build a structured situation model all agents share."""
    if not groq_client.is_configured():
        return _parse_situation_offline(scenario_text)

    try:
        result = groq_client.chat_json(SITUATION_SYSTEM, scenario_text)
        result["source"] = "groq"
        if "zones" not in result or not isinstance(result["zones"], list):
            result["zones"] = []
        for key in (
            "blocked_routes",
            "operational_routes",
            "immediate_priorities",
        ):
            if key not in result or not isinstance(result[key], list):
                result[key] = result.get(key, []) if result.get(key) else []
        if "infrastructure" not in result:
            result["infrastructure"] = {}
        return result
    except Exception as exc:
        offline = _parse_situation_offline(scenario_text)
        offline["parse_error"] = str(exc)
        return offline

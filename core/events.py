"""Disaster event injection (aftershocks, floods, etc.)."""
from __future__ import annotations

from typing import Any, Dict


AFTERSHOCK_EVENT: Dict[str, Any] = {
    "type": "aftershock",
    "label": "M5.2 aftershock — structural damage worsens",
    "casualty_multiplier": 1.12,
    "extra_critical_per_zone": 8,
    "access_override": "limited",
}

FLOOD_SURGE_EVENT: Dict[str, Any] = {
    "type": "flood_surge",
    "label": "Flood surge — low-lying zones isolated",
    "casualty_multiplier": 1.2,
    "extra_critical_per_zone": 5,
    "access_override": "blocked",
}


def get_event(name: str = "aftershock") -> Dict[str, Any]:
    """Return a predefined injectable disaster event."""
    events = {
        "aftershock": AFTERSHOCK_EVENT,
        "flood_surge": FLOOD_SURGE_EVENT,
    }
    return dict(events.get(name, AFTERSHOCK_EVENT))

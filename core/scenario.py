"""Scenario loader for CrisisSwarm.

Provides functions to load test scenarios. Extend to load from files,
APIs, or user input later.
"""
from typing import Dict


DEMO_SCENARIO = (
    "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
    "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100). "
    "8 buildings collapsed. Western Express Highway blocked. Bandra-Worli Sea Link operational. "
    "12 hospitals on alert. Coordinate full emergency response immediately."
)


def load_demo_scenario() -> str:
    """Return the built-in demo scenario string.

    Returns:
        The demo scenario text used for local testing and demos.
    """
    return DEMO_SCENARIO


def load_from_file(path: str) -> str:
    """Load a scenario text from a UTF-8 file.

    Args:
        path: path to a text file containing the scenario.

    Returns:
        The file contents as a string.
    """
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()

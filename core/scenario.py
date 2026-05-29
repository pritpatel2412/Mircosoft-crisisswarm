"""Scenario loader for CrisisSwarm."""

MUMBAI_SCENARIO = (
    "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. "
    "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100). "
    "8 buildings collapsed. Western Express Highway blocked. Bandra-Worli Sea Link operational. "
    "12 hospitals on alert. Coordinate full emergency response immediately."
)

FLORIDA_SCENARIO = (
    "HURRICANE ALERT: Category 4 hurricane made landfall near Miami at 06:15 EST. "
    "Estimated 380 casualties across 4 zones: Downtown (120), South Beach (100), "
    "Little Havana (90), Coral Gables (70). Storm surge flooding on Biscayne Blvd. "
    "I-95 northbound blocked. MacArthur Causeway operational. 9 hospitals on alert. "
    "Coordinate full emergency response immediately."
)

# Mumbai zone coordinates (lat, lon)
MUMBAI_ZONE_COORDS = {
    "Dharavi": (19.0033, 72.8446),
    "Kurla": (19.0666, 72.8562),
    "Andheri": (19.1190, 72.8465),
}

# Miami-area zone coordinates (lat, lon)
FLORIDA_ZONE_COORDS = {
    "Downtown": (25.7617, -80.1918),
    "South Beach": (25.7826, -80.1341),
    "Little Havana": (25.7681, -80.2223),
    "Coral Gables": (25.7215, -80.2684),
}

MUMBAI_ORIGIN = (19.0760, 72.8777)
FLORIDA_ORIGIN = (25.7743, -80.1937)


def load_demo_scenario() -> str:
    """Default Mumbai earthquake scenario."""
    return MUMBAI_SCENARIO


def load_florida_scenario() -> str:
    """Florida hurricane scenario for Miami-area zones."""
    return FLORIDA_SCENARIO


def zone_coords_for_scenario(scenario_text: str) -> dict:
    """Return zone coordinate map based on scenario keywords."""
    lower = scenario_text.lower()
    if "miami" in lower or "hurricane" in lower or "florida" in lower:
        return FLORIDA_ZONE_COORDS
    return MUMBAI_ZONE_COORDS


def origin_for_scenario(scenario_text: str) -> tuple:
    """Return staging origin coordinates for routing."""
    lower = scenario_text.lower()
    if "miami" in lower or "hurricane" in lower or "florida" in lower:
        return FLORIDA_ORIGIN
    return MUMBAI_ORIGIN


def load_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()

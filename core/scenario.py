"""Scenario loader for CrisisSwarm — 5 built-in scenarios + smart coord detection."""

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

TOKYO_SCENARIO = (
    "FLOOD EMERGENCY: Typhoon-driven flash flooding across Tokyo at 09:45 JST. "
    "Estimated 310 casualties across 3 zones: Koto (130), Edogawa (110), Sumida (70). "
    "Arakawa River levee breached. Shuto Expressway partially submerged. "
    "Metro lines suspended. 14 hospitals on alert. "
    "Coordinate full emergency response immediately."
)

TURKEY_SCENARIO = (
    "EARTHQUAKE EMERGENCY: 7.4 magnitude earthquake struck Kahramanmaras, Turkey at 04:17 local time. "
    "Estimated 520 casualties across 4 zones: City Centre (220), Dulkadiroglu (140), "
    "Onikisibat (100), Pazarcik (60). 15 buildings collapsed, multiple trapped under rubble. "
    "D400 highway blocked. Airport operational. 10 hospitals overwhelmed. "
    "Coordinate full emergency response immediately."
)

CHENNAI_SCENARIO = (
    "CYCLONE ALERT: Severe cyclonic storm 'Vayu' made landfall near Chennai at 11:00 IST. "
    "Estimated 290 casualties across 3 zones: Marina (120), Adyar (100), Tambaram (70). "
    "Adyar River flooding. ECR road blocked. NH-48 operational. "
    "11 hospitals on alert. Power outage across 40% of the city. "
    "Coordinate full emergency response immediately."
)

# Defined early so imports always succeed (dashboard buttons use this dict).
SCENARIOS = {
    "Mumbai Earthquake": MUMBAI_SCENARIO,
    "Florida Hurricane": FLORIDA_SCENARIO,
    "Tokyo Flood": TOKYO_SCENARIO,
    "Turkey Earthquake": TURKEY_SCENARIO,
    "Chennai Cyclone": CHENNAI_SCENARIO,
}

MUMBAI_ZONE_COORDS = {
    "Dharavi": (19.0033, 72.8446),
    "Kurla": (19.0666, 72.8562),
    "Andheri": (19.1190, 72.8465),
}

FLORIDA_ZONE_COORDS = {
    "Downtown": (25.7617, -80.1918),
    "South Beach": (25.7826, -80.1341),
    "Little Havana": (25.7681, -80.2223),
    "Coral Gables": (25.7215, -80.2684),
}

TOKYO_ZONE_COORDS = {
    "Koto": (35.6731, 139.8170),
    "Edogawa": (35.7068, 139.8680),
    "Sumida": (35.7101, 139.8017),
}

TURKEY_ZONE_COORDS = {
    "City Centre": (37.5858, 36.9371),
    "Dulkadiroglu": (37.6050, 36.9600),
    "Onikisibat": (37.5400, 36.8900),
    "Pazarcik": (37.4900, 37.3100),
}

CHENNAI_ZONE_COORDS = {
    "Marina": (13.0612, 80.2852),
    "Adyar": (13.0012, 80.2565),
    "Tambaram": (12.9249, 80.1000),
}

_CITY_FALLBACK = {
    "mumbai": (19.0760, 72.8777),
    "miami": (25.7743, -80.1937),
    "florida": (25.7743, -80.1937),
    "tokyo": (35.6762, 139.6503),
    "kahramanmaras": (37.5858, 36.9371),
    "turkey": (37.5858, 36.9371),
    "chennai": (13.0827, 80.2707),
    "delhi": (28.6139, 77.2090),
    "kolkata": (22.5726, 88.3639),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "paris": (48.8566, 2.3522),
    "sydney": (-33.8688, 151.2093),
    "jakarta": (-6.2088, 106.8456),
    "beijing": (39.9042, 116.4074),
    "shanghai": (31.2304, 121.4737),
    "nairobi": (-1.2921, 36.8219),
    "cairo": (30.0444, 31.2357),
    "tehran": (35.6892, 51.3890),
    "karachi": (24.8607, 67.0011),
    "dhaka": (23.8103, 90.4125),
    "manila": (14.5995, 120.9842),
    "bangkok": (13.7563, 100.5018),
}

DEFAULT_CENTRE = (20.0, 78.0)

MUMBAI_ORIGIN = (19.0760, 72.8777)
FLORIDA_ORIGIN = (25.7743, -80.1937)
TOKYO_ORIGIN = (35.6762, 139.6503)
TURKEY_ORIGIN = (37.5858, 36.9371)
CHENNAI_ORIGIN = (13.0827, 80.2707)

_SCENARIO_COORDS = {
    "Mumbai Earthquake": MUMBAI_ZONE_COORDS,
    "Florida Hurricane": FLORIDA_ZONE_COORDS,
    "Tokyo Flood": TOKYO_ZONE_COORDS,
    "Turkey Earthquake": TURKEY_ZONE_COORDS,
    "Chennai Cyclone": CHENNAI_ZONE_COORDS,
}

_SCENARIO_ORIGINS = {
    "Mumbai Earthquake": MUMBAI_ORIGIN,
    "Florida Hurricane": FLORIDA_ORIGIN,
    "Tokyo Flood": TOKYO_ORIGIN,
    "Turkey Earthquake": TURKEY_ORIGIN,
    "Chennai Cyclone": CHENNAI_ORIGIN,
}

_KEYWORD_MAP = [
    (["dharavi", "kurla", "andheri", "mumbai"], "Mumbai Earthquake"),
    (["miami", "south beach", "little havana", "coral gables", "biscayne"], "Florida Hurricane"),
    (["koto", "edogawa", "sumida", "tokyo", "arakawa"], "Tokyo Flood"),
    (["kahramanmaras", "dulkadiroglu", "onikisibat", "pazarcik", "türkiye"], "Turkey Earthquake"),
    (["chennai", "adyar", "tambaram", "vayu", "marina beach"], "Chennai Cyclone"),
]

# Single strong token is enough to match a built-in scenario.
_STRONG_SCENARIO_TOKENS: dict[str, str] = {
    "mumbai": "Mumbai Earthquake",
    "miami": "Florida Hurricane",
    "tokyo": "Tokyo Flood",
    "chennai": "Chennai Cyclone",
    "kahramanmaras": "Turkey Earthquake",
    "turkey": "Turkey Earthquake",
    "türkiye": "Turkey Earthquake",
}

SYNTHETIC_ZONE_NAMES = ("Zone A", "Zone B", "Zone C")


def load_demo_scenario() -> str:
    return MUMBAI_SCENARIO


def load_florida_scenario() -> str:
    return FLORIDA_SCENARIO


def load_scenario(name: str) -> str:
    return SCENARIOS.get(name, MUMBAI_SCENARIO)


def detect_scenario_name(scenario_text: str) -> str | None:
    """Match built-in scenarios by exact text, strong city token, or 2+ zone keywords."""
    stripped = scenario_text.strip()
    for name, text in SCENARIOS.items():
        if text.strip() == stripped:
            return name

    lower = scenario_text.lower()
    for token, name in _STRONG_SCENARIO_TOKENS.items():
        if token in lower:
            return name

    scores: dict[str, int] = {}
    for keywords, name in _KEYWORD_MAP:
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            scores[name] = scores.get(name, 0) + hits

    if not scores:
        return None

    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return None


def zoom_for_scenario(scenario_text: str) -> int:
    name = detect_scenario_name(scenario_text)
    if name == "Mumbai Earthquake":
        return 11
    elif name == "Florida Hurricane":
        return 10
    elif name == "Tokyo Flood":
        return 11
    elif name == "Turkey Earthquake":
        return 8
    elif name == "Chennai Cyclone":
        return 10
    else:
        return 9


def _closest_city_centre(scenario_text: str) -> tuple[float, float]:
    lower = scenario_text.lower()
    for city, coords in _CITY_FALLBACK.items():
        if city in lower:
            return coords
    return DEFAULT_CENTRE


def _synthetic_zones(centre: tuple[float, float]) -> dict[str, tuple[float, float]]:
    lat, lon = centre
    return {
        "Zone A": (lat + 0.02, lon - 0.02),
        "Zone B": (lat - 0.01, lon + 0.03),
        "Zone C": (lat + 0.03, lon + 0.01),
    }


def is_approximate_map(scenario_text: str, coords: dict) -> bool:
    """True when map uses synthetic placeholder zones."""
    if detect_scenario_name(scenario_text):
        return False
    return all(name in SYNTHETIC_ZONE_NAMES for name in coords.keys())


def zone_coords_for_scenario(scenario_text: str) -> dict:
    """
    Return zone -> (lat, lon).

    Built-in scenarios use exact zone coordinates.
    Unknown text: 3 placeholder zones near the closest recognised city,
    or (20.0, 78.0) if no city is found.
    """
    name = detect_scenario_name(scenario_text)
    if name:
        return dict(_SCENARIO_COORDS[name])

    centre = _closest_city_centre(scenario_text)
    return _synthetic_zones(centre)


def origin_for_scenario(scenario_text: str) -> tuple:
    name = detect_scenario_name(scenario_text)
    if name:
        return _SCENARIO_ORIGINS[name]
    coords = zone_coords_for_scenario(scenario_text)
    return next(iter(coords.values()))


def load_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


__all__ = [
    "SCENARIOS",
    "MUMBAI_SCENARIO",
    "FLORIDA_SCENARIO",
    "TOKYO_SCENARIO",
    "TURKEY_SCENARIO",
    "CHENNAI_SCENARIO",
    "load_demo_scenario",
    "load_florida_scenario",
    "load_scenario",
    "load_from_file",
    "zone_coords_for_scenario",
    "origin_for_scenario",
    "is_approximate_map",
    "detect_scenario_name",
    "zoom_for_scenario",
]

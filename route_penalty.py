"""
CargoSense | route_penalty.py
Purpose: turn the corridor itself (distance versus promised days, and terrain) into a rule-based
delay penalty, in percentage points. This is the India-specific part of the risk: the model was
trained on non-Indian orders and never sees distance, state or terrain.
Input: geodesic distance from the origin (km), scheduled transit days, destination state name.
Output: dict with slack, terrain and total points, plus the required km per day.
Notes: slack compares the speed the promise needs (geodesic km x ROAD_FACTOR / days) with a
realistic road speed (KM_PER_DAY). Terrain points are scaled down for short hops. All constants
are team-chosen heuristics, not learned or validated. Tune only the constants below.
Used by: the API, added on top of the model's base risk and the weather penalty.
"""

KM_PER_DAY = 450.0
ROAD_FACTOR = 1.25
SLACK_POINTS = [(0.6, 0.0), (1.0, 8.0), (1.5, 16.0), (2.0, 20.0)]  # (needed speed / KM_PER_DAY, points)
TERRAIN_FULL_AT_KM = 800.0
TERRAIN_POINTS = {"himalayan": 6.0, "ghats": 3.0, "coastal": 1.5, "plains": 0.0}
MAX_ROUTE_PENALTY = 25.0

HIMALAYAN = {
    "HIMACHAL PRADESH", "UTTARAKHAND", "JAMMU AND KASHMIR", "LADAKH", "SIKKIM",
    "ARUNACHAL PRADESH", "NAGALAND", "MANIPUR", "MIZORAM", "MEGHALAYA",
}
GHATS = {"KARNATAKA", "KERALA", "GOA", "MAHARASHTRA", "TELANGANA", "ANDHRA PRADESH"}
COASTAL = {"TAMIL NADU", "ODISHA", "WEST BENGAL", "GUJARAT"}


def terrain_class(state):
    name = (state or "").strip().upper()
    if name in HIMALAYAN:
        return "himalayan"
    if name in GHATS:
        return "ghats"
    if name in COASTAL:
        return "coastal"
    return "plains"


def interpolate(value, points):
    if value <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return points[-1][1]


def required_km_per_day(distance_km, days):
    return distance_km * ROAD_FACTOR / days


def compute_route_penalty(distance_km, days, state=None):
    if distance_km is None or distance_km < 0:
        raise ValueError("distance_km must be zero or more")
    if not isinstance(days, int) or days < 1:
        raise ValueError("days must be an integer of 1 or more")
    need = required_km_per_day(distance_km, days)
    slack = interpolate(need / KM_PER_DAY, SLACK_POINTS)
    terrain_kind = terrain_class(state)
    terrain = TERRAIN_POINTS[terrain_kind] * min(distance_km / TERRAIN_FULL_AT_KM, 1.0)
    total = min(slack + terrain, MAX_ROUTE_PENALTY)
    return {
        "slack": round(slack, 1),
        "terrain": round(terrain, 1),
        "total": round(total, 1),
        "required_km_per_day": round(need, 1),
        "terrain_class": terrain_kind,
    }
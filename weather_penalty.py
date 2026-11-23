"""
CargoSense | weather_penalty.py
Purpose: turn an arrival-day forecast into a rule-based delay penalty, in percentage points.
Input: daily precipitation (mm), max wind (km/h), optional max temperature (C),
optional precipitation probability (0 to 100).
Output: dict with rain, wind, heat and total points. Total is capped at MAX_PENALTY.
Notes: rain bands follow the IMD daily rainfall categories, wind bands follow the Beaufort
scale. The point values are team-chosen heuristics, not learned or validated. The model
never sees weather. Tune only the constants below.
Used by: the API, before the penalty is added to the model's base risk.
"""

RAIN_BANDS_MM = [(204.5, 20.0), (115.6, 15.0), (64.5, 10.0), (15.6, 5.0), (2.5, 2.0)]
WIND_BANDS_KMH = [(89.0, 10.0), (62.0, 6.0), (39.0, 3.0)]
HEAT_BANDS_C = [(45.0, 4.0), (40.0, 2.0)]
MAX_PENALTY = 25.0


def band_points(value, bands):
    for threshold, points in bands:
        if value >= threshold:
            return points
    return 0.0


def validate(precip_mm, wind_kmh, temp_c, precip_prob_pct):
    if precip_mm is None or precip_mm < 0:
        raise ValueError("precip_mm must be zero or more")
    if wind_kmh is None or wind_kmh < 0:
        raise ValueError("wind_kmh must be zero or more")
    if precip_prob_pct is not None and not 0 <= precip_prob_pct <= 100:
        raise ValueError("precip_prob_pct must be between 0 and 100")


def compute_weather_penalty(precip_mm, wind_kmh, temp_c=None, precip_prob_pct=None):
    validate(precip_mm, wind_kmh, temp_c, precip_prob_pct)
    rain = band_points(precip_mm, RAIN_BANDS_MM)
    if precip_prob_pct is not None:
        rain *= precip_prob_pct / 100
    wind = band_points(wind_kmh, WIND_BANDS_KMH)
    heat = band_points(temp_c, HEAT_BANDS_C) if temp_c is not None else 0.0
    total = min(rain + wind + heat, MAX_PENALTY)
    return {
        "rain": round(rain, 1),
        "wind": round(wind, 1),
        "heat": round(heat, 1),
        "total": round(total, 1),
    }
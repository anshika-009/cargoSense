"""
CargoSense | weather_utils.py
Purpose: fetch the arrival-day forecast from Open-Meteo and turn it into a weather penalty.
Input: destination latitude and longitude, and transit days (arrival date = today + days).
Output: dict with forecast values, condition label, penalty breakdown and an availability flag.
Notes: the forecast is for the arrival date, not current conditions. If Open-Meteo cannot be
reached or returns incomplete data, the penalty is 0 and available is False; nothing is invented.
Results are cached in memory for 30 minutes. No API key is needed.
Used by: the API, before the penalty is added to the model's base risk.
"""
import time
from datetime import date, timedelta

from weather_penalty import compute_weather_penalty

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = "precipitation_sum,precipitation_probability_max,wind_speed_10m_max,temperature_2m_max"
TIMEZONE = "Asia/Kolkata"
TIMEOUT_SECONDS = 6
MAX_FORECAST_DAYS = 16
CACHE_TTL_SECONDS = 1800
FETCH_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError)
NO_PENALTY = {"rain": 0.0, "wind": 0.0, "heat": 0.0, "total": 0.0}
_CACHE = {}


def default_http_get(url, params, timeout):
    import requests

    return requests.get(url, params=params, timeout=timeout)


def clear_cache():
    _CACHE.clear()


def condition_label(precip_mm, wind_kmh):
    if precip_mm >= 64.5:
        return "HEAVY RAIN"
    if precip_mm >= 15.6:
        return "MODERATE RAIN"
    if precip_mm >= 2.5:
        return "LIGHT RAIN"
    if wind_kmh >= 39:
        return "STRONG WIND"
    return "CLEAR"


def pick(daily, name, position):
    values = daily.get(name)
    if values is None or position >= len(values):
        return None
    return values[position]


def unavailable(arrival, reason):
    return {
        "available": False,
        "source": "unavailable",
        "reason": reason,
        "forecast_date": arrival,
        "precip_mm": None,
        "precip_prob_pct": None,
        "wind_kmh": None,
        "temp_c": None,
        "condition": "UNAVAILABLE",
        "penalty": dict(NO_PENALTY),
    }


def read_forecast(payload, arrival):
    daily = payload["daily"]
    position = daily["time"].index(arrival.isoformat())
    precip = pick(daily, "precipitation_sum", position)
    wind = pick(daily, "wind_speed_10m_max", position)
    if precip is None or wind is None:
        raise ValueError("incomplete forecast")
    temp = pick(daily, "temperature_2m_max", position)
    prob = pick(daily, "precipitation_probability_max", position)
    return {
        "available": True,
        "source": "open-meteo",
        "reason": None,
        "forecast_date": arrival,
        "precip_mm": precip,
        "precip_prob_pct": prob,
        "wind_kmh": wind,
        "temp_c": temp,
        "condition": condition_label(precip, wind),
        "penalty": compute_weather_penalty(precip, wind, temp_c=temp, precip_prob_pct=prob),
    }


def get_arrival_weather(latitude, longitude, transit_days, today=None, http_get=default_http_get):
    if not isinstance(transit_days, int) or not 1 <= transit_days <= MAX_FORECAST_DAYS:
        raise ValueError(f"transit_days must be an integer from 1 to {MAX_FORECAST_DAYS}")
    arrival = (today or date.today()) + timedelta(days=transit_days)
    key = (round(latitude, 3), round(longitude, 3), arrival)
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": DAILY_FIELDS,
        "start_date": arrival.isoformat(),
        "end_date": arrival.isoformat(),
        "timezone": TIMEZONE,
    }
    try:
        response = http_get(OPEN_METEO_URL, params, TIMEOUT_SECONDS)
        response.raise_for_status()
        result = read_forecast(response.json(), arrival)
    except FETCH_ERRORS as error:
        return unavailable(arrival, f"{error.__class__.__name__}: {error}")
    _CACHE[key] = (time.time(), result)
    return result
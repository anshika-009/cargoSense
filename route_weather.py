"""
CargoSense | route_weather.py
Purpose: estimate a weather delay penalty from conditions along the route, not only on arrival day.
Input: origin and destination as (latitude, longitude), transit days and an optional dispatch date.
Output: dict with the averaged penalty, rain/wind/heat split, weather averages, the worst point,
per-route detail and an availability flag.
Notes: routes come from OSRM (free, no key); if it fails, a straight geodesic line is used and
flagged. Points are sampled along each route and the shipment is assumed to move at constant
speed, so a point at fraction f of the route is reached on day dispatch + f * transit_days.
Dispatch defaults to today and must fall inside the Open-Meteo forecast window (15 days).
Each point-day goes through compute_weather_penalty(); points are averaged per route, then routes
are averaged. Raw rain and wind are never averaged, only penalties. Nothing is invented: any
failed forecast makes available False with a zero penalty.
Live requests are throttled (one every MIN_INTERVAL_SECONDS across threads) and cached: route
geometry for ROUTE_CACHE_SECONDS, forecasts for FORECAST_CACHE_SECONDS. Failures are never cached.
Caching and throttling apply only to the default HTTP client, so tests with fakes see neither.
Used by: the API and experiments/compare_weather.py.
"""
import math
import threading
import time
from datetime import date, timedelta

from weather_penalty import compute_weather_penalty

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = "precipitation_sum,precipitation_probability_max,wind_speed_10m_max,temperature_2m_max"
TIMEZONE = "Asia/Kolkata"
TIMEOUT_SECONDS = 8
SPACING_KM = 150.0
MIN_POINTS = 3
MAX_POINTS = 12
MAX_ROUTES = 3
FORECAST_HORIZON_DAYS = 15
EARTH_RADIUS_KM = 6371.0088
FETCH_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError)
MIN_INTERVAL_SECONDS = 0.25
ROUTE_CACHE_SECONDS = 24 * 3600
FORECAST_CACHE_SECONDS = 3600

_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST = [0.0]
_CACHE = {"routes": {}, "forecasts": {}}


def clear_cache():
    for store in _CACHE.values():
        store.clear()


def cache_get(name, key, ttl_seconds):
    entry = _CACHE[name].get(key)
    if entry is None or time.time() - entry[0] > ttl_seconds:
        return None
    return entry[1]


def cache_put(name, key, value):
    _CACHE[name][key] = (time.time(), value)


def throttle():
    with _THROTTLE_LOCK:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _LAST_REQUEST[0])
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST[0] = time.monotonic()


def default_http_get(url, params, timeout):
    import requests

    throttle()
    return requests.get(url, params=params, timeout=timeout)


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def straight_line(origin, destination, steps=40):
    return [
        (origin[0] + (destination[0] - origin[0]) * i / steps,
         origin[1] + (destination[1] - origin[1]) * i / steps)
        for i in range(steps + 1)
    ]


def fetch_routes(origin, destination, http_get=default_http_get):
    """Returns (routes, source). Each route is a list of (lat, lon)."""
    use_cache = http_get is default_http_get
    key = (round(origin[0], 3), round(origin[1], 3), round(destination[0], 3), round(destination[1], 3))
    if use_cache:
        cached = cache_get("routes", key, ROUTE_CACHE_SECONDS)
        if cached is not None:
            return cached, "osrm"
    url = OSRM_URL.format(lon1=origin[1], lat1=origin[0], lon2=destination[1], lat2=destination[0])
    params = {"alternatives": "true", "overview": "simplified", "geometries": "geojson"}
    try:
        response = http_get(url, params, TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        routes = [[(lat, lon) for lon, lat in r["geometry"]["coordinates"]] for r in payload["routes"]]
        if not routes:
            raise ValueError("no routes")
        routes = routes[:MAX_ROUTES]
        if use_cache:
            cache_put("routes", key, routes)
        return routes, "osrm"
    except FETCH_ERRORS:
        return [straight_line(origin, destination)], "geodesic"


def sample_route(route, spacing_km=SPACING_KM):
    """Points along the route with their fraction of total distance (0 to 1)."""
    cumulative = [0.0]
    for p, q in zip(route, route[1:]):
        cumulative.append(cumulative[-1] + haversine_km(p, q))
    total = cumulative[-1]
    if total == 0:
        return [(route[0], 1.0)]
    count = min(max(round(total / spacing_km), MIN_POINTS), MAX_POINTS)
    points = []
    for i in range(count):
        target = total * (i + 1) / count
        index = next(k for k, c in enumerate(cumulative) if c >= target - 1e-9)
        points.append((route[index], target / total))
    return points


def day_for_fraction(fraction, transit_days, dispatch):
    offset = min(max(math.ceil(fraction * transit_days), 1), transit_days)
    return dispatch + timedelta(days=offset)


def fetch_point_forecasts(points, start, end, http_get=default_http_get):
    """One request for all points. Returns a list of daily dicts, one per point."""
    use_cache = http_get is default_http_get
    key = (tuple((round(p[0], 3), round(p[1], 3)) for p in points), start, end)
    if use_cache:
        cached = cache_get("forecasts", key, FORECAST_CACHE_SECONDS)
        if cached is not None:
            return cached
    params = {
        "latitude": ",".join(str(round(p[0], 3)) for p in points),
        "longitude": ",".join(str(round(p[1], 3)) for p in points),
        "daily": DAILY_FIELDS,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": TIMEZONE,
    }
    response = http_get(OPEN_METEO_URL, params, TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    payload = payload if isinstance(payload, list) else [payload]
    if len(payload) != len(points):
        raise ValueError("forecast count does not match points")
    daily = [item["daily"] for item in payload]
    if use_cache:
        cache_put("forecasts", key, daily)
    return daily


def point_penalty(daily, day):
    position = daily["time"].index(day.isoformat())
    precip = daily["precipitation_sum"][position]
    wind = daily["wind_speed_10m_max"][position]
    if precip is None or wind is None:
        raise ValueError("incomplete forecast")
    temp = daily.get("temperature_2m_max", [None] * (position + 1))[position]
    prob = daily.get("precipitation_probability_max", [None] * (position + 1))[position]
    return compute_weather_penalty(precip, wind, temp_c=temp, precip_prob_pct=prob), (precip, wind, temp)


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def check_window(transit_days, dispatch, today):
    if not isinstance(transit_days, int) or transit_days < 1:
        raise ValueError("transit_days must be an integer of 1 or more")
    if dispatch < today:
        raise ValueError("dispatch_date cannot be in the past")
    arrival = dispatch + timedelta(days=transit_days)
    if (arrival - today).days > FORECAST_HORIZON_DAYS:
        raise ValueError(f"arrival date must be within {FORECAST_HORIZON_DAYS} days from today")
    return arrival


def unavailable(reason, routes_source="none"):
    return {
        "available": False, "reason": reason, "route_source": routes_source,
        "penalty_mean": 0.0, "penalty_split": {"rain": 0.0, "wind": 0.0, "heat": 0.0},
        "penalty_worst": 0.0, "worst_point": None, "routes": [],
        "averages": {"precip_mm": None, "wind_kmh": None, "temp_c": None},
    }


def summarise(route_results):
    points = [p for r in route_results for p in r["points"]]
    split = {
        key: round(sum(mean([p[key] for p in r["points"]]) for r in route_results) / len(route_results), 1)
        for key in ("rain", "wind", "heat")
    }
    return points, split


def get_route_weather(origin, destination, transit_days, dispatch_date=None, http_get=default_http_get, today=None):
    today = today or date.today()
    dispatch = dispatch_date or today
    arrival = check_window(transit_days, dispatch, today)
    routes, source = fetch_routes(origin, destination, http_get)
    route_results = []
    try:
        for route in routes:
            sampled = sample_route(route)
            daily_list = fetch_point_forecasts(
                [p for p, _ in sampled], dispatch + timedelta(days=1), arrival, http_get
            )
            scored = []
            for (point, fraction), daily in zip(sampled, daily_list):
                day = day_for_fraction(fraction, transit_days, dispatch)
                penalty, (precip, wind, temp) = point_penalty(daily, day)
                scored.append({
                    "lat": point[0], "lon": point[1], "date": day.isoformat(), "fraction": round(fraction, 2),
                    "precip_mm": precip, "wind_kmh": wind, "temp_c": temp, "penalty": penalty["total"],
                    "rain": penalty["rain"], "wind": penalty["wind"], "heat": penalty["heat"],
                })
            route_results.append({
                "mean": round(sum(s["penalty"] for s in scored) / len(scored), 1), "points": scored,
            })
    except FETCH_ERRORS as error:
        result = unavailable(f"{error.__class__.__name__}: {error}", source)
        result.update(dispatch_date=dispatch, arrival_date=arrival)
        return result
    points, split = summarise(route_results)
    worst = max(points, key=lambda s: s["penalty"])
    return {
        "available": True, "reason": None, "route_source": source,
        "dispatch_date": dispatch, "arrival_date": arrival,
        "penalty_mean": round(sum(r["mean"] for r in route_results) / len(route_results), 1),
        "penalty_split": split,
        "penalty_worst": worst["penalty"], "worst_point": worst, "routes": route_results,
        "averages": {
            "precip_mm": mean([p["precip_mm"] for p in points]),
            "wind_kmh": mean([p["wind_kmh"] for p in points]),
            "temp_c": mean([p["temp_c"] for p in points]),
        },
    }

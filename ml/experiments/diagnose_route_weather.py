"""
CargoSense | experiments/diagnose_route_weather.py
Purpose: show, for two or more destinations, the per-point weather and penalty so you can see
whether the penalty really is the same everywhere or just looks the same (clear weather, bands
that round to 0, averaging). Needs network (OSRM and Open-Meteo).
Run from the repo root: python -m experiments.diagnose_route_weather Chennai Srinagar Guwahati 4
The last argument is the transit days (default 4). City names must exist in states_cities.py.
"""
import sys

from core import geo_utils
from core import route_penalty
from core import route_weather
from core.states_cities import INDIA_STATES_CITIES


def find_city(name):
    for state, cities in INDIA_STATES_CITIES.items():
        for item in cities:
            if item["city"].lower() == name.lower():
                return state, item["city"], (item["coords"][1], item["coords"][0])
    raise SystemExit(f"city not found in states_cities.py: {name}")


def main(argv):
    days = int(argv[-1]) if argv and argv[-1].isdigit() else 4
    names = [a for a in argv if not a.isdigit()] or ["Chennai", "Srinagar", "Guwahati"]
    for name in names:
        state, city, coords = find_city(name)
        distance = geo_utils.distance_km(geo_utils.ORIGIN_COORDS, coords)
        route = route_penalty.compute_route_penalty(distance, days, state)
        print(f"\n=== {city}, {state} | {distance:.0f} km | {days} days | route penalty {route} ===")
        try:
            result = route_weather.get_route_weather(geo_utils.ORIGIN_COORDS, coords, days)
        except ValueError as error:
            print("rejected:", error)
            continue
        print(f"available={result['available']} source={result['route_source']} reason={result['reason']}")
        print(f"weather mean={result['penalty_mean']} worst={result['penalty_worst']} split={result['penalty_split']}")
        for i, r in enumerate(result["routes"]):
            print(f"  route {i}: mean {r['mean']}")
            for p in r["points"]:
                print(f"    f={p['fraction']:.2f} {p['date']} precip={p['precip_mm']} wind={p['wind_kmh']} "
                      f"temp={p['temp_c']} -> {p['penalty']} (rain {p['rain']}, wind {p['wind']}, heat {p['heat']})")


if __name__ == "__main__":
    main(sys.argv[1:])

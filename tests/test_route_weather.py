"""
CargoSense | tests/test_route_weather.py
Purpose: check route sampling, day mapping, averaging and failure handling with fake responses.
"""
import unittest
from datetime import date, timedelta

import route_weather as rw

TODAY = date(2026, 11, 23)
DELHI = (28.7041, 77.1025)
CHENNAI = (13.0827, 80.2707)


class Fake:
    def __init__(self, payload, fail=False):
        self.payload, self.fail = payload, fail

    def raise_for_status(self):
        if self.fail:
            raise OSError("boom")

    def json(self):
        return self.payload


def make_http(routes=None, precip=0.0, wind=0.0, osrm_fail=False, meteo_fail=False):
    def http_get(url, params, timeout):
        if "osrm" in url:
            if osrm_fail:
                return Fake(None, fail=True)
            coords = routes or [[[DELHI[1], DELHI[0]], [CHENNAI[1], CHENNAI[0]]]]
            return Fake({"routes": [{"geometry": {"coordinates": c}} for c in coords]})
        if meteo_fail:
            return Fake(None, fail=True)
        n = len(params["latitude"].split(","))
        start = date.fromisoformat(params["start_date"])
        end = date.fromisoformat(params["end_date"])
        days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
        p = precip if isinstance(precip, list) else [precip] * len(days)
        daily = {"time": days, "precipitation_sum": p, "wind_speed_10m_max": [wind] * len(days),
                 "temperature_2m_max": [30.0] * len(days), "precipitation_probability_max": [100] * len(days)}
        return Fake([{"daily": daily} for _ in range(n)])
    return http_get


class RouteWeatherTests(unittest.TestCase):
    def test_sample_count_and_fractions(self):
        pts = rw.sample_route(rw.straight_line(DELHI, CHENNAI))
        self.assertTrue(rw.MIN_POINTS <= len(pts) <= rw.MAX_POINTS)
        self.assertAlmostEqual(pts[-1][1], 1.0, places=2)
        self.assertEqual([f for _, f in pts], sorted(f for _, f in pts))

    def test_day_mapping_bounds(self):
        self.assertEqual(rw.day_for_fraction(0.01, 4, TODAY), TODAY + timedelta(days=1))
        self.assertEqual(rw.day_for_fraction(1.0, 4, TODAY), TODAY + timedelta(days=4))

    def test_clear_weather_gives_zero(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 4, None, make_http(), today=TODAY)
        self.assertTrue(r["available"])
        self.assertEqual(r["penalty_mean"], 0.0)

    def test_uniform_rain_gives_that_penalty(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 4, None, make_http(precip=70.0), today=TODAY)
        self.assertEqual(r["penalty_mean"], 10.0)

    def test_one_bad_day_is_diluted_in_mean_but_kept_in_worst(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 4, None, make_http(precip=[0.0, 0.0, 0.0, 120.0]), today=TODAY)
        self.assertLess(r["penalty_mean"], r["penalty_worst"])
        self.assertEqual(r["penalty_worst"], 15.0)
        self.assertGreater(r["penalty_mean"], 0.0)

    def test_osrm_failure_falls_back_to_geodesic(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 3, None, make_http(osrm_fail=True), today=TODAY)
        self.assertEqual(r["route_source"], "geodesic")
        self.assertTrue(r["available"])

    def test_forecast_failure_is_unavailable_with_zero_penalty(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 3, None, make_http(meteo_fail=True), today=TODAY)
        self.assertFalse(r["available"])
        self.assertEqual(r["penalty_mean"], 0.0)

    def test_routes_are_averaged(self):
        a = [[DELHI[1], DELHI[0]], [CHENNAI[1], CHENNAI[0]]]
        b = [[DELHI[1], DELHI[0]], [78.0, 20.0], [CHENNAI[1], CHENNAI[0]]]
        r = rw.get_route_weather(DELHI, CHENNAI, 4, None, make_http(routes=[a, b], precip=70.0), today=TODAY)
        self.assertEqual(len(r["routes"]), 2)

    def test_split_and_averages_present(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 4, None, make_http(precip=70.0, wind=40.0), today=TODAY)
        self.assertEqual(r["penalty_split"]["rain"], 10.0)
        self.assertEqual(r["penalty_split"]["wind"], 3.0)
        self.assertEqual(r["averages"]["precip_mm"], 70.0)

    def test_future_dispatch_shifts_dates(self):
        r = rw.get_route_weather(DELHI, CHENNAI, 4, TODAY + timedelta(days=3), make_http(), today=TODAY)
        self.assertEqual(r["arrival_date"], TODAY + timedelta(days=7))
        self.assertTrue(all(p["date"] > (TODAY + timedelta(days=3)).isoformat() for p in r["routes"][0]["points"]))

    def test_past_dispatch_rejected(self):
        with self.assertRaises(ValueError):
            rw.get_route_weather(DELHI, CHENNAI, 3, TODAY - timedelta(days=1), make_http(), today=TODAY)

    def test_arrival_beyond_forecast_rejected(self):
        with self.assertRaises(ValueError):
            rw.get_route_weather(DELHI, CHENNAI, 5, TODAY + timedelta(days=12), make_http(), today=TODAY)

    def test_invalid_days(self):
        for bad in (0, 2.5):
            with self.assertRaises(ValueError):
                rw.get_route_weather(DELHI, CHENNAI, bad, None, make_http(), today=TODAY)


if __name__ == "__main__":
    unittest.main()

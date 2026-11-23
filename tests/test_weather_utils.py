"""
CargoSense | test_weather_utils.py
Purpose: check the Open-Meteo wrapper with fake responses (no network needed).
Run: python -m unittest discover -s tests -t . -v
"""
import unittest
from datetime import date

import weather_utils

TODAY = date(2026, 11, 22)
ARRIVAL = "2026-11-25"


class FakeResponse:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def payload(precip=24.5, wind=42.0, temp=31.0, prob=80, day=ARRIVAL):
    return {
        "daily": {
            "time": [day],
            "precipitation_sum": [precip],
            "precipitation_probability_max": [prob],
            "wind_speed_10m_max": [wind],
            "temperature_2m_max": [temp],
        }
    }


def fetcher(response, calls=None):
    def http_get(url, params, timeout):
        if calls is not None:
            calls.append(params)
        if isinstance(response, Exception):
            raise response
        return response

    return http_get


class WeatherUtilsTests(unittest.TestCase):
    def setUp(self):
        weather_utils.clear_cache()

    def test_parses_forecast_and_applies_penalty(self):
        result = weather_utils.get_arrival_weather(
            13.08, 80.27, 3, today=TODAY, http_get=fetcher(FakeResponse(payload()))
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["forecast_date"], date(2026, 11, 25))
        self.assertEqual(result["condition"], "MODERATE RAIN")
        self.assertEqual(result["penalty"]["total"], 7.0)

    def test_requests_the_arrival_date_only(self):
        calls = []
        weather_utils.get_arrival_weather(
            13.08, 80.27, 3, today=TODAY, http_get=fetcher(FakeResponse(payload()), calls)
        )
        self.assertEqual(calls[0]["start_date"], ARRIVAL)
        self.assertEqual(calls[0]["end_date"], ARRIVAL)

    def test_network_failure_gives_zero_penalty(self):
        result = weather_utils.get_arrival_weather(
            13.08, 80.27, 3, today=TODAY, http_get=fetcher(OSError("timeout"))
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["penalty"]["total"], 0.0)
        self.assertEqual(result["condition"], "UNAVAILABLE")

    def test_http_error_gives_zero_penalty(self):
        response = FakeResponse(payload(), error=OSError("500"))
        result = weather_utils.get_arrival_weather(13.08, 80.27, 3, today=TODAY, http_get=fetcher(response))
        self.assertFalse(result["available"])

    def test_missing_precipitation_is_unavailable(self):
        result = weather_utils.get_arrival_weather(
            13.08, 80.27, 3, today=TODAY, http_get=fetcher(FakeResponse(payload(precip=None)))
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["penalty"]["total"], 0.0)

    def test_wrong_date_in_response_is_unavailable(self):
        response = FakeResponse(payload(day="2026-11-30"))
        result = weather_utils.get_arrival_weather(13.08, 80.27, 3, today=TODAY, http_get=fetcher(response))
        self.assertFalse(result["available"])

    def test_missing_temperature_and_probability_still_work(self):
        result = weather_utils.get_arrival_weather(
            13.08, 80.27, 3, today=TODAY, http_get=fetcher(FakeResponse(payload(temp=None, prob=None)))
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["penalty"]["total"], 8.0)

    def test_second_call_uses_cache(self):
        calls = []
        http_get = fetcher(FakeResponse(payload()), calls)
        weather_utils.get_arrival_weather(13.08, 80.27, 3, today=TODAY, http_get=http_get)
        weather_utils.get_arrival_weather(13.08, 80.27, 3, today=TODAY, http_get=http_get)
        self.assertEqual(len(calls), 1)

    def test_failures_are_not_cached(self):
        calls = []
        http_get = fetcher(OSError("down"), calls)
        weather_utils.get_arrival_weather(13.08, 80.27, 3, today=TODAY, http_get=http_get)
        weather_utils.get_arrival_weather(13.08, 80.27, 3, today=TODAY, http_get=http_get)
        self.assertEqual(len(calls), 2)

    def test_invalid_transit_days_rejected(self):
        for days in (0, -1, 17, 2.5, None):
            with self.assertRaises(ValueError):
                weather_utils.get_arrival_weather(13.08, 80.27, days, today=TODAY, http_get=fetcher(FakeResponse(payload())))


if __name__ == "__main__":
    unittest.main()
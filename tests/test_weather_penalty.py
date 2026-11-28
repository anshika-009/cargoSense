"""
CargoSense | test_weather_penalty.py
Purpose: check the weather penalty rules with fixed inputs (bands, boundaries, probability
weighting, cap, monotonicity, input validation).
Run: python -m unittest discover -s tests -t . -v
"""
import unittest

from core.weather_penalty import MAX_PENALTY, compute_weather_penalty


def total(**kwargs):
    return compute_weather_penalty(**kwargs)["total"]


class RainTests(unittest.TestCase):
    def test_clear_sky_has_no_penalty(self):
        self.assertEqual(total(precip_mm=0, wind_kmh=0), 0.0)

    def test_very_light_rain_has_no_penalty(self):
        self.assertEqual(total(precip_mm=2.4, wind_kmh=0), 0.0)

    def test_light_rain(self):
        self.assertEqual(total(precip_mm=5, wind_kmh=0), 2.0)

    def test_moderate_rain(self):
        self.assertEqual(total(precip_mm=24.5, wind_kmh=0), 5.0)

    def test_heavy_rain_boundary(self):
        self.assertEqual(total(precip_mm=64.4, wind_kmh=0), 5.0)
        self.assertEqual(total(precip_mm=64.5, wind_kmh=0), 10.0)

    def test_extreme_rain_reaches_top_band(self):
        self.assertEqual(total(precip_mm=250, wind_kmh=0), 20.0)

    def test_probability_scales_rain_points(self):
        self.assertEqual(total(precip_mm=24.5, wind_kmh=0, precip_prob_pct=40), 2.0)

    def test_zero_probability_removes_rain_points(self):
        self.assertEqual(total(precip_mm=100, wind_kmh=0, precip_prob_pct=0), 0.0)

    def test_probability_does_not_scale_wind(self):
        self.assertEqual(total(precip_mm=0, wind_kmh=70, precip_prob_pct=0), 6.0)


class WindAndHeatTests(unittest.TestCase):
    def test_wind_boundaries(self):
        self.assertEqual(total(precip_mm=0, wind_kmh=38.9), 0.0)
        self.assertEqual(total(precip_mm=0, wind_kmh=39), 3.0)
        self.assertEqual(total(precip_mm=0, wind_kmh=62), 6.0)
        self.assertEqual(total(precip_mm=0, wind_kmh=89), 10.0)

    def test_heat_boundaries(self):
        self.assertEqual(total(precip_mm=0, wind_kmh=0, temp_c=39.9), 0.0)
        self.assertEqual(total(precip_mm=0, wind_kmh=0, temp_c=40), 2.0)
        self.assertEqual(total(precip_mm=0, wind_kmh=0, temp_c=45), 4.0)

    def test_missing_temperature_adds_nothing(self):
        self.assertEqual(compute_weather_penalty(0, 0, temp_c=None)["heat"], 0.0)


class CombinationTests(unittest.TestCase):
    def test_components_sum_to_total_below_cap(self):
        result = compute_weather_penalty(24.5, 42.0, temp_c=41)
        self.assertEqual(result["total"], result["rain"] + result["wind"] + result["heat"])

    def test_chennai_example_from_dashboard(self):
        self.assertEqual(total(precip_mm=24.5, wind_kmh=42.0), 8.0)

    def test_total_is_capped(self):
        result = compute_weather_penalty(300, 120, temp_c=48)
        self.assertEqual(result["total"], MAX_PENALTY)
        self.assertGreater(result["rain"] + result["wind"] + result["heat"], MAX_PENALTY)

    def test_penalty_never_decreases_as_rain_grows(self):
        previous = 0.0
        for rain in range(0, 301, 5):
            current = total(precip_mm=rain, wind_kmh=20)
            self.assertGreaterEqual(current, previous)
            previous = current

    def test_penalty_never_decreases_as_wind_grows(self):
        previous = 0.0
        for wind in range(0, 131, 5):
            current = total(precip_mm=10, wind_kmh=wind)
            self.assertGreaterEqual(current, previous)
            previous = current

    def test_penalty_stays_within_bounds(self):
        for rain in (0, 10, 70, 130, 250):
            for wind in (0, 45, 70, 100):
                value = total(precip_mm=rain, wind_kmh=wind, temp_c=44)
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, MAX_PENALTY)


class ValidationTests(unittest.TestCase):
    def test_negative_rain_rejected(self):
        with self.assertRaises(ValueError):
            compute_weather_penalty(-1, 0)

    def test_negative_wind_rejected(self):
        with self.assertRaises(ValueError):
            compute_weather_penalty(0, -5)

    def test_missing_rain_or_wind_rejected(self):
        with self.assertRaises(ValueError):
            compute_weather_penalty(None, 0)
        with self.assertRaises(ValueError):
            compute_weather_penalty(0, None)

    def test_probability_out_of_range_rejected(self):
        with self.assertRaises(ValueError):
            compute_weather_penalty(10, 10, precip_prob_pct=101)
        with self.assertRaises(ValueError):
            compute_weather_penalty(10, 10, precip_prob_pct=-1)


if __name__ == "__main__":
    unittest.main()
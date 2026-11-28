"""
CargoSense | tests/test_route_penalty.py
Purpose: check the distance/slack and terrain penalty rules.
"""
import unittest

from core import route_penalty as rp


class RoutePenaltyTests(unittest.TestCase):
    def test_short_hop_has_no_penalty(self):
        self.assertEqual(rp.compute_route_penalty(240, 2, "Rajasthan")["total"], 0.0)

    def test_penalty_grows_as_window_shrinks(self):
        values = [rp.compute_route_penalty(1750, d, "Tamil Nadu")["total"] for d in (6, 5, 4, 3, 2)]
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[-1], values[0])

    def test_destinations_differ(self):
        near = rp.compute_route_penalty(240, 4, "Rajasthan")["total"]
        far = rp.compute_route_penalty(1900, 4, "Assam")["total"]
        self.assertGreater(far, near)

    def test_terrain_scales_with_distance(self):
        short = rp.compute_route_penalty(200, 6, "Uttarakhand")["terrain"]
        long = rp.compute_route_penalty(900, 6, "Uttarakhand")["terrain"]
        self.assertGreater(long, short)
        self.assertEqual(long, 6.0)

    def test_unknown_state_is_plains(self):
        self.assertEqual(rp.compute_route_penalty(900, 6, None)["terrain_class"], "plains")

    def test_cap(self):
        self.assertLessEqual(rp.compute_route_penalty(5000, 1, "Ladakh")["total"], rp.MAX_ROUTE_PENALTY)

    def test_recommended_days_grow_with_distance_and_keep_penalty_low(self):
        near, far = rp.recommended_days(280), rp.recommended_days(2234)
        self.assertEqual(near, 2)
        self.assertGreater(far, near)
        for km in (280, 1150, 1760, 2234):
            self.assertLess(rp.compute_route_penalty(km, rp.recommended_days(km), "Plains")["slack"], 8.0)

    def test_recommended_days_validation(self):
        with self.assertRaises(ValueError):
            rp.recommended_days(-1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            rp.compute_route_penalty(-1, 3)
        with self.assertRaises(ValueError):
            rp.compute_route_penalty(100, 0)


if __name__ == "__main__":
    unittest.main()

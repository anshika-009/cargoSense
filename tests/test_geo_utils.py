"""
CargoSense | tests/test_geo_utils.py
Purpose: check geocoding, caching, failure handling, distance and market mapping with a fake geocoder.
"""
import unittest

import geo_utils as gu


class FakeLocation:
    latitude, longitude = 13.0827, 80.2707
    raw = {"address": {"country_code": "in"}}


class FakeGeocoder:
    def __init__(self, result=FakeLocation(), error=None):
        self.result, self.error, self.calls = result, error, 0

    def geocode(self, query, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class GeoUtilsTests(unittest.TestCase):
    def setUp(self):
        gu.clear_cache()

    def test_geocode_and_cache(self):
        g = FakeGeocoder()
        first = gu.geocode_destination("Chennai", "Tamil Nadu", g)
        second = gu.geocode_destination("chennai", "tamil nadu", g)
        self.assertEqual(first, (13.0827, 80.2707, "in"))
        self.assertEqual(first, second)
        self.assertEqual(g.calls, 1)

    def test_unknown_city_raises(self):
        with self.assertRaises(gu.GeocodeError):
            gu.geocode_destination("Nowhereville", None, FakeGeocoder(result=None))

    def test_service_failure_raises_and_is_not_cached(self):
        with self.assertRaises(gu.GeocodeError):
            gu.geocode_destination("Chennai", None, FakeGeocoder(error=OSError("down")))
        self.assertEqual(gu.geocode_destination("Chennai", None, FakeGeocoder())[2], "in")

    def test_distance_delhi_chennai(self):
        km = gu.distance_km(gu.ORIGIN_COORDS, (13.0827, 80.2707))
        self.assertTrue(1700 < km < 1800)

    def test_market_mapping(self):
        self.assertEqual(gu.market_for_country("in"), "Pacific Asia")
        self.assertEqual(gu.market_for_country("US"), "USCA")
        self.assertEqual(gu.market_for_country("zz"), gu.DEFAULT_MARKET)
        self.assertEqual(gu.market_for_country(None), gu.DEFAULT_MARKET)


if __name__ == "__main__":
    unittest.main()

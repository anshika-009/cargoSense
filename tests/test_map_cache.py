"""
CargoSense | tests/test_map_cache.py
Purpose: check the border data is shrunk, and the map deck is reused when only unrelated inputs change.
"""
import unittest

from core.states_cities import get_all_city_records
from dashboard import map as map_module
from dashboard.theme import STATUS_STABLE, simplify_geojson


class GeojsonTests(unittest.TestCase):
    def test_simplify_keeps_geometry_rounds_and_drops_properties(self):
        raw = {"type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"NAME": "X", "big": "y" * 500},
            "geometry": {"type": "Polygon", "coordinates": [[[77.123456, 28.987654], [77.1234561, 28.9876541], [78.5, 29.5], [77.123456, 28.987654]]]},
        }, {"type": "Feature", "properties": {}, "geometry": None}]}
        light = simplify_geojson(raw)
        self.assertEqual(len(light["features"]), 1)
        self.assertEqual(light["features"][0]["properties"], {})
        ring = light["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(ring, [[77.12, 28.99], [78.5, 29.5], [77.12, 28.99]])


class CompactTests(unittest.TestCase):
    def test_thinning_keeps_rings_closed_and_drops_dense_points(self):
        dense = [[77.0 + i * 0.001, 28.0] for i in range(200)] + [[77.0, 28.0]]
        raw = {"features": [{"geometry": {"type": "Polygon", "coordinates": [dense]}}]}
        ring = simplify_geojson(raw)["features"][0]["geometry"]["coordinates"][0]
        self.assertLess(len(ring), 30)
        self.assertEqual(ring[0], ring[-1])

    def test_deck_json_is_compact_and_built_once(self):
        rec = get_all_city_records()[0]
        deck = map_module.cached_map_deck(rec["state"], rec["city"], STATUS_STABLE, False, False)
        text = deck.to_json()
        self.assertNotIn("\n", text)
        self.assertIs(text, deck.to_json())


class DeckCacheTests(unittest.TestCase):
    def test_same_inputs_reuse_the_same_deck(self):
        rec = get_all_city_records()[0]
        first = map_module.cached_map_deck(rec["state"], rec["city"], STATUS_STABLE, False, False)
        again = map_module.cached_map_deck(rec["state"], rec["city"], STATUS_STABLE, False, False)
        self.assertIs(first, again)

    def test_city_records_are_built_once_but_copies_are_safe(self):
        a, b = get_all_city_records(), get_all_city_records()
        self.assertEqual(len(a), 46)
        a.pop()
        self.assertEqual(len(b), 46)


if __name__ == "__main__":
    unittest.main()

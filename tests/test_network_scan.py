"""
CargoSense | tests/test_network_scan.py
Purpose: check the network scan client and the corridor page against the real batch endpoint with faked weather.
"""
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

import FastAPI as api
import api_client
import route_weather
from states_cities import get_all_city_records
from tests.test_api import fake_weather

API = TestClient(api.app)
TODAY = date.today()
APP = Path(__file__).resolve().parent.parent / "app.py"


def post_via_test_client(url, json=None, timeout=None):
    response = API.post(url.replace(api_client.API_URL, ""), json=json)
    response.ok = response.status_code < 400
    return response


class ScanClientTests(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(api_client.requests, "post", side_effect=post_via_test_client),
            mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather(penalty=3.0)),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_scan_covers_every_hub_in_chunks(self):
        records = get_all_city_records()
        seen = []
        scan, error = api_client.run_network_scan(
            records, 1, 50.0, 10.0, "Standard Class", 4, TODAY, progress=seen.append,
        )
        self.assertIsNone(error)
        self.assertEqual(len(scan["items"]), len(records))
        self.assertEqual(scan["failed"], 0)
        self.assertAlmostEqual(seen[-1], 1.0)
        self.assertEqual(len(seen), -(-len(records) // api_client.SCAN_CHUNK))
        self.assertEqual(scan["key"], api_client.scan_key(1, 50.0, 10.0, "Standard Class", 4, TODAY))

    def test_recommended_days_mode_gives_each_hub_its_own_days(self):
        scan, _ = api_client.run_network_scan(
            get_all_city_records()[:12], 1, 50.0, 10.0, "Standard Class", None, TODAY,
        )
        days = {item["scheduled_shipping_days"] for item in scan["items"].values()}
        self.assertGreater(len(days), 1)

    def test_invalid_inputs_are_reported_without_calling_the_api(self):
        with mock.patch.object(api_client, "post_batch") as post:
            scan, error = api_client.run_network_scan([], 0, 50.0, 10.0, "Standard Class", 4, TODAY)
        self.assertIsNone(scan)
        self.assertIn("quantity", error)
        post.assert_not_called()

    def test_unreachable_api_is_an_error(self):
        with mock.patch.object(api_client.requests, "post", side_effect=api_client.requests.ConnectionError()):
            scan, error = api_client.run_network_scan(
                get_all_city_records()[:2], 1, 50.0, 10.0, "Standard Class", 4, TODAY,
            )
        self.assertIsNone(scan)
        self.assertIn("not reachable", error)


class CorridorPageTests(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(api_client.requests, "post", side_effect=post_via_test_client),
            mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather(penalty=3.0)),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def open_page(self):
        at = AppTest.from_file(str(APP), default_timeout=60)
        at.session_state["workspace_view"] = "Network Corridor Intelligence"
        at.run()
        return at

    def test_page_renders_and_scan_fills_every_row(self):
        at = self.open_page()
        self.assertFalse(at.exception)
        before = " ".join(m.value for m in at.markdown)
        self.assertIn("Run an assessment or a network scan", before)
        next(b for b in at.button if b.label == "Run Network Scan").click().run()
        self.assertFalse(at.exception)
        after = " ".join(m.value for m in at.markdown)
        self.assertIn("Scanned at", after)
        self.assertNotIn("Run an assessment or scan", after)
        self.assertEqual(after.count("<tr>"), len(get_all_city_records()) + 1)

    def test_changing_inputs_marks_scan_stale(self):
        at = self.open_page()
        next(b for b in at.button if b.label == "Run Network Scan").click().run()
        at.slider[0].set_value(5).run()
        self.assertTrue(any("scan again" in c.value for c in at.caption))
        self.assertNotIn("Scanned at", " ".join(m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()

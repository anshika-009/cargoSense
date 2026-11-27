"""
CargoSense | tests/test_api.py
Purpose: check the /predict contract end to end with the real model and faked weather and geocoding.
"""
import unittest
from datetime import date, timedelta
from unittest import mock

from fastapi.testclient import TestClient

import FastAPI as api
import geo_utils
import route_weather

BODY = {
    "order_quantity": 1, "sales_per_customer": 50, "product_price": 10,
    "shipping_mode": "Standard Class", "scheduled_shipping_days": 3,
    "destination_city": "Chennai", "destination_lat": 13.0827, "destination_lon": 80.2707,
}


def fake_weather(available=True, penalty=8.0):
    point = {"date": "2026-11-25", "lat": 20.0, "lon": 78.0, "precip_mm": 30.0, "wind_kmh": 20.0}
    return {
        "available": available, "reason": None if available else "OSError: down", "route_source": "osrm",
        "dispatch_date": date(2026, 11, 23), "arrival_date": date(2026, 11, 26),
        "penalty_mean": penalty if available else 0.0,
        "penalty_split": {"rain": penalty, "wind": 0.0, "heat": 0.0},
        "penalty_worst": 10.0, "worst_point": point if available else None, "routes": [],
        "averages": {"precip_mm": 12.0, "wind_kmh": 18.0, "temp_c": 30.0} if available else
        {"precip_mm": None, "wind_kmh": None, "temp_c": None},
    }


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def post(self, **changes):
        return self.client.post("/predict", json=dict(BODY, **changes))

    def test_contract_and_root_cause_split(self):
        with mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather()):
            r = self.post()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["weather_available"])
        self.assertEqual(data["weather_delay_penalty_pct"], 8.0)
        self.assertAlmostEqual(data["late_delivery_risk_prob"] * 100, min(data["base_risk_pct"] + 8.0, 100.0), places=1)
        self.assertEqual(data["market"], "Pacific Asia")
        self.assertTrue(1700 < data["distance_km"] < 1800)

    def test_weather_unavailable_state(self):
        with mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather(available=False)):
            data = self.post().json()
        self.assertFalse(data["weather_available"])
        self.assertEqual(data["weather_delay_penalty_pct"], 0.0)
        self.assertAlmostEqual(data["late_delivery_risk_prob"] * 100, data["base_risk_pct"], places=1)

    def test_hour_does_not_change_other_modes(self):
        with mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather(penalty=0.0)):
            morning = self.post(shipping_mode="Standard Class", scheduled_shipping_days=4, dispatch_hour=9).json()
            evening = self.post(shipping_mode="Standard Class", scheduled_shipping_days=4, dispatch_hour=15).json()
        self.assertEqual(morning["base_risk_pct"], evening["base_risk_pct"])
        self.assertEqual(morning["dispatch_hour"], 9)

    def test_hour_out_of_range_rejected(self):
        self.assertEqual(self.post(dispatch_hour=24).status_code, 422)

    def test_old_client_request_still_accepted(self):
        old = {k: v for k, v in BODY.items() if k not in ("destination_lat", "destination_lon")}
        old["weather_delay_penalty_pct"] = 99.0
        with mock.patch.object(geo_utils, "geocode_destination", return_value=(13.0827, 80.2707, "in")), \
                mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather()):
            data = self.client.post("/predict", json=old).json()
        self.assertEqual(data["weather_delay_penalty_pct"], 8.0)

    def test_zero_day_rejected(self):
        self.assertEqual(self.post(scheduled_shipping_days=0).status_code, 422)

    def test_negative_money_rejected(self):
        self.assertEqual(self.post(sales_per_customer=-1).status_code, 422)

    def test_lat_without_lon_rejected(self):
        body = dict(BODY)
        del body["destination_lon"]
        self.assertEqual(self.client.post("/predict", json=body).status_code, 422)

    def test_past_dispatch_rejected(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(self.post(dispatch_date=past).status_code, 422)

    def test_geocode_failure_is_422(self):
        body = {k: v for k, v in BODY.items() if k not in ("destination_lat", "destination_lon")}
        with mock.patch.object(geo_utils, "geocode_destination", side_effect=geo_utils.GeocodeError("no")):
            self.assertEqual(self.client.post("/predict", json=body).status_code, 422)


if __name__ == "__main__":
    unittest.main()

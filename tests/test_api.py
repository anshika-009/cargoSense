"""
CargoSense | tests/test_api.py
Purpose: check the /predict contract end to end with the real model and faked weather and geocoding.
"""
import unittest
from datetime import date, timedelta
from unittest import mock

from fastapi.testclient import TestClient

from api import main as api
from core import geo_utils
from core import route_weather

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
        self.assertGreater(data["route_penalty_pct"], 0)
        self.assertAlmostEqual(
            data["late_delivery_risk_prob"] * 100,
            min(data["base_risk_pct"] + 8.0 + data["route_penalty_pct"], 100.0), places=1,
        )
        self.assertEqual(data["market"], "Pacific Asia")
        self.assertTrue(1700 < data["distance_km"] < 1800)

    def test_weather_unavailable_state(self):
        with mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather(available=False)):
            data = self.post().json()
        self.assertFalse(data["weather_available"])
        self.assertEqual(data["weather_delay_penalty_pct"], 0.0)
        self.assertAlmostEqual(
            data["late_delivery_risk_prob"] * 100,
            min(data["base_risk_pct"] + data["route_penalty_pct"], 100.0), places=1,
        )

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


HUBS = [
    {"city": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873},
    {"city": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    {"city": "Kochi", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
]
BATCH = {
    "order_quantity": 1, "sales_per_customer": 50, "product_price": 10,
    "shipping_mode": "Standard Class", "hubs": HUBS,
}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def post(self, **changes):
        return self.client.post("/predict/batch", json=dict(BATCH, **changes))

    def patched(self, **kwargs):
        return mock.patch.object(route_weather, "get_route_weather", return_value=fake_weather(**kwargs))

    def test_one_item_per_hub_in_order(self):
        with self.patched():
            data = self.post().json()
        self.assertEqual([i["city"] for i in data["items"]], ["Jaipur", "Chennai", "Kochi"])
        self.assertEqual((data["count"], data["failed"]), (3, 0))
        self.assertTrue(all(i["ok"] and i["result"] for i in data["items"]))

    def test_hubs_get_their_own_recommended_days_by_default(self):
        with self.patched() as weather:
            data = self.post().json()
        days = [i["scheduled_shipping_days"] for i in data["items"]]
        self.assertEqual(days, [i["recommended_days"] for i in data["items"]])
        self.assertLess(days[0], days[1])
        self.assertFalse(data["common_window"])
        self.assertEqual([c.args[2] for c in weather.call_args_list], days)

    def test_common_window_applies_to_every_hub(self):
        with self.patched():
            data = self.post(scheduled_shipping_days=4).json()
        self.assertTrue(data["common_window"])
        self.assertEqual({i["scheduled_shipping_days"] for i in data["items"]}, {4})
        penalties = [i["result"]["route_penalty_pct"] for i in data["items"]]
        self.assertEqual(penalties, sorted(penalties))
        self.assertGreater(penalties[-1], penalties[0])

    def test_batch_item_matches_single_predict(self):
        single_body = dict(BODY, scheduled_shipping_days=4, dispatch_hour=10, destination_state="Tamil Nadu")
        with self.patched():
            single = self.client.post("/predict", json=single_body).json()
            batch = self.post(scheduled_shipping_days=4, dispatch_hour=10).json()["items"][1]["result"]
        for key in ("late_delivery_risk_prob", "base_risk_pct", "route_penalty_pct", "status", "distance_km"):
            self.assertEqual(single[key], batch[key])

    def test_weather_unavailable_hub_is_flagged_not_faked(self):
        with self.patched(available=False):
            data = self.post().json()
        self.assertEqual(data["failed"], 0)
        for item in data["items"]:
            self.assertFalse(item["result"]["weather_available"])
            self.assertEqual(item["result"]["weather_delay_penalty_pct"], 0.0)

    def test_one_failing_hub_does_not_sink_the_batch(self):
        def flaky(origin, destination, days, dispatch):
            if destination[0] < 12:
                raise ValueError("boom")
            return fake_weather()

        with mock.patch.object(route_weather, "get_route_weather", side_effect=flaky):
            data = self.post().json()
        self.assertEqual(data["failed"], 1)
        failed = [i for i in data["items"] if not i["ok"]]
        self.assertEqual(failed[0]["city"], "Kochi")
        self.assertEqual(failed[0]["error"], "boom")
        self.assertIsNone(failed[0]["result"])

    def test_days_are_capped_by_the_forecast_horizon(self):
        far_dispatch = (date.today() + timedelta(days=12)).isoformat()
        with self.patched():
            data = self.post(dispatch_date=far_dispatch).json()
        kochi = data["items"][2]
        self.assertEqual(kochi["scheduled_shipping_days"], 3)
        self.assertTrue(kochi["days_capped"])
        self.assertFalse(data["items"][0]["days_capped"])

    def test_validation(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(self.post(dispatch_date=past).status_code, 422)
        self.assertEqual(self.post(hubs=[]).status_code, 422)
        self.assertEqual(self.post(hubs=HUBS * 30).status_code, 422)
        self.assertEqual(self.post(scheduled_shipping_days=0).status_code, 422)
        self.assertEqual(self.post(hubs=[{"city": "X", "lat": 10.0}]).status_code, 422)
        late = (date.today() + timedelta(days=13)).isoformat()
        self.assertEqual(self.post(dispatch_date=late, scheduled_shipping_days=5).status_code, 422)


if __name__ == "__main__":
    unittest.main()

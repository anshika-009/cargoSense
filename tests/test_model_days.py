"""
CargoSense | tests/test_model_days.py
Purpose: check the model only sees scheduled days it was trained on, so the transit window cannot move the base risk.
"""
import unittest

from ml import inference

ORDER = {
    "sales_per_customer": 50, "order_quantity": 1, "product_price": 10,
    "shipping_mode": "Standard Class", "scheduled_shipping_days": 4,
}


class ModelDaysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.columns, cls.defaults = inference.load_artifacts()

    def score(self, **changes):
        return inference.score_order(self.model, self.columns, self.defaults, dict(ORDER, **changes))

    def test_window_does_not_change_base_risk(self):
        risks = {self.score(scheduled_shipping_days=d)["base_risk_pct"] for d in range(1, 8)}
        self.assertEqual(len(risks), 1)

    def test_model_gets_the_trained_days_for_each_mode(self):
        expected = {"Same Day": 0, "First Class": 1, "Second Class": 2, "Standard Class": 4}
        for mode, days in expected.items():
            self.assertEqual(self.score(shipping_mode=mode, scheduled_shipping_days=3)["model_scheduled_days"], days)

    def test_penalties_still_add_on_top(self):
        base = self.score()["base_risk_pct"]
        total = self.score(weather_penalty_pct=0.0)["late_delivery_risk_prob"] * 100
        self.assertAlmostEqual(total, base, places=1)
        with_penalties = inference.score_order(
            self.model, self.columns, self.defaults, ORDER, weather_penalty_pct=5.0, route_penalty_pct=10.0
        )
        self.assertAlmostEqual(with_penalties["late_delivery_risk_prob"] * 100, min(base + 15.0, 100.0), places=1)


if __name__ == "__main__":
    unittest.main()
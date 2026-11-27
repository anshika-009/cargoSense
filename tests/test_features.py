"""
CargoSense | tests/test_features.py
Purpose: check the order-hour feature is derived only for Same Day orders and never from the shipping date.
"""
import unittest

import pandas as pd

import feature_data as fd
import inference

DEFAULTS = {
    "Days for shipment (scheduled)": 4.0, "Sales per customer": 100.0, "Order Item Quantity": 1.0,
    "Order Item Product Price": 50.0, "Order Item Discount": 0.0, "Type": "DEBIT",
    "Shipping Mode": "Standard Class", "Customer Segment": "Consumer", "Department Name": "Fan Shop",
    "Market": "LATAM", "same_day_order_hour": -1.0,
}


class FeatureTests(unittest.TestCase):
    def test_hour_only_for_same_day(self):
        df = pd.DataFrame({
            "Shipping Mode": ["Same Day", "Standard Class"],
            "order date (DateOrders)": ["7/14/2017 9:30", "7/14/2017 15:45"],
        })
        out = fd.add_time_features(df)
        self.assertEqual(out["same_day_order_hour"].tolist(), [9, fd.NO_HOUR])

    def test_row_to_features_uses_supplied_hour_for_same_day(self):
        row = fd.row_to_features({"Shipping Mode": "Same Day", "order_hour": 15}, DEFAULTS)
        self.assertEqual(row["same_day_order_hour"].iloc[0], 15)
        self.assertEqual(list(row.columns), fd.FEATURES)

    def test_row_to_features_ignores_hour_for_other_modes(self):
        row = fd.row_to_features({"Shipping Mode": "Second Class", "order_hour": 15}, DEFAULTS)
        self.assertEqual(row["same_day_order_hour"].iloc[0], fd.NO_HOUR)

    def test_same_day_cutoff_is_learned_by_the_model(self):
        model, columns, defaults = inference.load_artifacts()
        order = {
            "scheduled_shipping_days": 0, "sales_per_customer": 50, "order_quantity": 1,
            "product_price": 10, "shipping_mode": "Same Day",
        }
        morning = inference.score_order(model, columns, defaults, dict(order, dispatch_hour=9))
        afternoon = inference.score_order(model, columns, defaults, dict(order, dispatch_hour=15))
        self.assertLess(morning["base_risk_pct"], 10.0)
        self.assertGreater(afternoon["base_risk_pct"], 90.0)

    def test_no_leakage_columns_in_features(self):
        fd.assert_no_leakage(fd.FEATURES)
        self.assertNotIn("shipping date (DateOrders)", fd.FEATURES)


if __name__ == "__main__":
    unittest.main()

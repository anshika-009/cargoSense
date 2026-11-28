"""
CargoSense | inference.py
Purpose: load the trained model once and turn one order into a late-delivery risk.
Notes: the model is given each shipping mode's trained scheduled days (Same Day 0, First Class 1,
Second Class 2, Standard Class 4), the only pairs in the training data. The user's transit window
is used for the weather and the route penalty, not by the model.
Used by: FastAPI.py. Kept free of web code so it can be tested on its own.
"""
import json
from pathlib import Path

import joblib
from xgboost import XGBClassifier

import feature_data as fd

MODELS_DIR = Path(__file__).parent / "models"
CRITICAL_THRESHOLD = 65
MODERATE_THRESHOLD = 35
PRED_THRESHOLD_PCT = 50
DEFAULT_MARKET = "Pacific Asia"  # all deployed routes are Delhi to India
MODE_TRAINED_DAYS = {"Same Day": 0, "First Class": 1, "Second Class": 2, "Standard Class": 4}

STATUS_STABLE = "STABLE OPTIMAL ROUTE"
STATUS_MODERATE = "MODERATE CAUTION ZONE"
STATUS_CRITICAL = "CRITICAL SLA RISK"


def status_from_risk(total_pct):
    if total_pct >= CRITICAL_THRESHOLD:
        return STATUS_CRITICAL
    if total_pct >= MODERATE_THRESHOLD:
        return STATUS_MODERATE
    return STATUS_STABLE


def load_artifacts(models_dir=MODELS_DIR):
    json_path = models_dir / "final_xgb_model.json"
    if json_path.exists():
        model = XGBClassifier()
        model.load_model(json_path)
    else:
        model = joblib.load(models_dir / "final_xgb_model.pkl")
    columns = joblib.load(models_dir / "processed_data_pipeline.pkl")
    defaults = json.loads((models_dir / "defaults.json").read_text())
    return model, columns, defaults


def score_order(model, columns, defaults, order, weather_penalty_pct=0.0, route_penalty_pct=0.0):
    """order: dict with the API field names. Returns the PredictResponse fields."""
    model_days = MODE_TRAINED_DAYS[order["shipping_mode"]]
    values = {
        "Days for shipment (scheduled)": model_days,
        "Sales per customer": order["sales_per_customer"],
        "Order Item Quantity": order["order_quantity"],
        "Order Item Product Price": order["product_price"],
        "Shipping Mode": order["shipping_mode"],
        "Market": order.get("market") or DEFAULT_MARKET,
    }
    if order.get("dispatch_hour") is not None:
        values["order_hour"] = order["dispatch_hour"]
        values["same_day_order_hour"] = order["dispatch_hour"]
    X = fd.encode_inference(fd.row_to_features(values, defaults), columns)
    base_pct = round(float(model.predict_proba(X)[0][1]) * 100, 1)
    total_pct = min(round(base_pct + weather_penalty_pct + route_penalty_pct, 1), 100.0)
    return {
        "late_delivery_risk_prob": round(total_pct / 100, 4),
        "late_delivery_risk_pred": int(total_pct >= PRED_THRESHOLD_PCT),
        "base_risk_pct": base_pct,
        "model_scheduled_days": model_days,
        "weather_delay_penalty_pct": float(weather_penalty_pct),
        "route_penalty_pct": float(route_penalty_pct),
        "status": status_from_risk(total_pct),
    }
import os
from datetime import date, timedelta
import requests
import streamlit as st

from route_weather import FORECAST_HORIZON_DAYS
from states_cities import ORIGIN_HUB

API_URL = os.environ.get("CARGOSENSE_API", "http://127.0.0.1:8000")
SCAN_CHUNK = 6
SCAN_TIMEOUT_SECONDS = 120


def validate_inputs(order_quantity, scheduled_shipping_days, sales_per_customer, product_price, dispatch_date):
    errors = []
    today = date.today()
    if order_quantity < 1:
        errors.append("Order quantity must be at least 1.")
    if scheduled_shipping_days < 1:
        errors.append("Scheduled transit days must be at least 1.")
    if sales_per_customer < 0:
        errors.append("Sales per customer (USD) cannot be negative.")
    if product_price < 0:
        errors.append("Product price (USD) cannot be negative.")
    if dispatch_date < today:
        errors.append("Dispatch date cannot be in the past.")
    elif (dispatch_date + timedelta(days=scheduled_shipping_days) - today).days > FORECAST_HORIZON_DAYS:
        errors.append(f"Arrival date must be within {FORECAST_HORIZON_DAYS} days from today (forecast limit).")
    return errors


def build_payload(hub_rec, qty, sales, price, mode, days, dispatch):
    return {
        "order_quantity": int(qty),
        "sales_per_customer": float(sales),
        "product_price": float(price),
        "shipping_mode": mode,
        "scheduled_shipping_days": int(days),
        "destination_city": hub_rec["city"],
        "destination_state": hub_rec["state"],
        "destination_lat": hub_rec["coords"][1],
        "destination_lon": hub_rec["coords"][0],
        "origin_hub": ORIGIN_HUB,
        "dispatch_date": dispatch.isoformat(),
    }


def describe_api_error(response):
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):
        detail = "; ".join(str(item.get("msg", item)) for item in detail)
    if detail:
        return f"The API rejected this order: {detail}"
    return f"The prediction service returned HTTP {response.status_code}."


def get_prediction(payload):
    try:
        response = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
    except requests.RequestException:
        return None, "The prediction service is not reachable. Start it with: uvicorn FastAPI:app --reload"
    if not response.ok:
        return None, describe_api_error(response)
    return response.json(), None


def get_plus_one_day_what_if(payload, current_total_pct):
    if payload["scheduled_shipping_days"] >= 6:
        return None
    next_days = payload["scheduled_shipping_days"] + 1
    next_pred, error = get_prediction(dict(payload, scheduled_shipping_days=next_days))
    if error:
        return None
    next_total_pct = round(next_pred["late_delivery_risk_prob"] * 100.0, 1)
    return {
        "next_days": next_days,
        "next_total_pct": next_total_pct,
        "diff_pct": round(next_total_pct - current_total_pct, 1),
    }


def run_and_store_assessment(hub_rec, qty, sales, price, mode, days, dispatch):
    current_payload = build_payload(hub_rec, qty, sales, price, mode, days, dispatch)
    input_errors = validate_inputs(
        current_payload["order_quantity"],
        current_payload["scheduled_shipping_days"],
        current_payload["sales_per_customer"],
        current_payload["product_price"],
        dispatch,
    )
    if input_errors:
        for err_msg in input_errors:
            st.error(err_msg)
        return
    with st.spinner("Scoring order and fetching route weather"):
        pred_result, error = get_prediction(current_payload)
        if error:
            st.error(error)
            return
        total_pct_val = round(pred_result["late_delivery_risk_prob"] * 100.0, 1)
        what_if_result = get_plus_one_day_what_if(current_payload, total_pct_val)
    st.session_state["prediction"] = {
        "payload": current_payload,
        "result": pred_result,
        "what_if": what_if_result,
    }


def scan_key(qty, sales, price, mode, days, dispatch):
    return (int(qty), float(sales), float(price), mode, days, dispatch.isoformat())


def post_batch(payload):
    try:
        response = requests.post(f"{API_URL}/predict/batch", json=payload, timeout=SCAN_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None, "The prediction service is not reachable. Start it with: uvicorn FastAPI:app --reload"
    if not response.ok:
        return None, describe_api_error(response)
    return response.json(), None


def run_network_scan(hub_records, qty, sales, price, mode, days, dispatch, progress=None):
    """Score every hub through POST /predict/batch in small chunks. days=None uses each hub's recommended days."""
    errors = validate_inputs(qty, days or 1, sales, price, dispatch)
    if errors:
        return None, " ".join(errors)
    shared = {
        "order_quantity": int(qty),
        "sales_per_customer": float(sales),
        "product_price": float(price),
        "shipping_mode": mode,
        "origin_hub": ORIGIN_HUB,
        "dispatch_date": dispatch.isoformat(),
    }
    if days is not None:
        shared["scheduled_shipping_days"] = int(days)
    items, as_of = {}, None
    for start in range(0, len(hub_records), SCAN_CHUNK):
        chunk = hub_records[start:start + SCAN_CHUNK]
        hubs = [{"city": r["city"], "state": r["state"], "lat": r["coords"][1], "lon": r["coords"][0]} for r in chunk]
        data, error = post_batch(dict(shared, hubs=hubs))
        if error:
            return None, error
        as_of = data["as_of"]
        items.update({(i["state"], i["city"]): i for i in data["items"]})
        if progress:
            progress(min(start + len(chunk), len(hub_records)) / len(hub_records))
    return {
        "key": scan_key(qty, sales, price, mode, days, dispatch),
        "as_of": as_of,
        "items": items,
        "failed": sum(1 for i in items.values() if not i["ok"]),
    }, None

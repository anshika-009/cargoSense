"""
CargoSense | FastAPI.py
Purpose: serve POST /predict. The XGBoost model gives the base risk; the server computes a
rule-based route weather penalty (route_weather.py) and adds it on top.
Input: order fields, destination (city, optional state or coordinates), optional dispatch date.
Output: total risk, base risk, weather penalty and its split, route (slack and terrain) penalty, weather values, status, availability.
Notes: if weather cannot be fetched the penalty is 0 and weather_available is False.
dispatch_hour (0 to 23) feeds the order_hour feature; it defaults to the current hour in India.
The model sees the shipping mode's trained scheduled days (model_scheduled_days); scheduled_shipping_days
drives the weather window and the route penalty.
POST /predict/batch scores many destinations in one call (the network scan). Shipment fields are shared;
each hub is scored with the same pipeline as /predict. scheduled_shipping_days is optional there: when it is
sent it is the common window for every hub, otherwise each hub gets route_penalty.recommended_days().
Hubs are processed by a few worker threads; outbound requests are throttled and cached in route_weather.
Run: uvicorn FastAPI:app --reload
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

import geo_utils
import inference
import route_penalty
import route_weather

app = FastAPI(title="CargoSense API", version="2.0")
INDIA_TZ = ZoneInfo("Asia/Kolkata")
MODEL, COLUMNS, DEFAULTS = inference.load_artifacts()
MAX_BATCH_HUBS = 60
BATCH_WORKERS = 4


class PredictRequest(BaseModel):
    order_quantity: int = Field(ge=1)
    sales_per_customer: float = Field(ge=0, description="USD")
    product_price: float = Field(ge=0, description="USD")
    shipping_mode: Literal["Standard Class", "Second Class", "First Class", "Same Day"]
    scheduled_shipping_days: int = Field(
        ge=1, le=route_weather.FORECAST_HORIZON_DAYS, description="Zero-day transit is rejected"
    )
    destination_city: str = Field(min_length=1)
    destination_state: Optional[str] = None
    destination_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    destination_lon: Optional[float] = Field(default=None, ge=-180, le=180)
    origin_hub: str = "Delhi Hub (North HQ)"
    dispatch_date: Optional[date] = Field(default=None, description="Defaults to today")
    dispatch_hour: Optional[int] = Field(default=None, ge=0, le=23, description="Defaults to the current hour in India")

    @model_validator(mode="after")
    def coordinates_come_together(self):
        if (self.destination_lat is None) != (self.destination_lon is None):
            raise ValueError("destination_lat and destination_lon must be sent together")
        return self


class WeatherValues(BaseModel):
    precip_mm_avg: Optional[float]
    wind_kmh_avg: Optional[float]
    temp_c_avg: Optional[float]
    worst_date: Optional[str]
    worst_lat: Optional[float]
    worst_lon: Optional[float]
    worst_precip_mm: Optional[float]
    worst_wind_kmh: Optional[float]


class PredictResponse(BaseModel):
    late_delivery_risk_prob: float
    late_delivery_risk_pred: int
    base_risk_pct: float
    model_scheduled_days: int
    weather_delay_penalty_pct: float
    weather_rain_pct: float
    weather_wind_pct: float
    weather_heat_pct: float
    weather_worst_penalty_pct: float
    route_penalty_pct: float
    route_slack_pct: float
    route_terrain_pct: float
    required_km_per_day: float
    terrain_class: str
    weather_available: bool
    weather_reason: Optional[str]
    weather_source: str
    weather_dispatch_date: date
    weather_arrival_date: date
    weather: WeatherValues
    distance_km: float
    dispatch_hour: int
    market: str
    status: str


class Hub(BaseModel):
    city: str = Field(min_length=1)
    state: Optional[str] = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class BatchRequest(BaseModel):
    order_quantity: int = Field(ge=1)
    sales_per_customer: float = Field(ge=0, description="USD")
    product_price: float = Field(ge=0, description="USD")
    shipping_mode: Literal["Standard Class", "Second Class", "First Class", "Same Day"]
    scheduled_shipping_days: Optional[int] = Field(
        default=None, ge=1, le=route_weather.FORECAST_HORIZON_DAYS,
        description="Common window for every hub. Omit to use each hub's recommended days",
    )
    hubs: List[Hub] = Field(min_length=1, max_length=MAX_BATCH_HUBS)
    origin_hub: str = "Delhi Hub (North HQ)"
    dispatch_date: Optional[date] = Field(default=None, description="Defaults to today")
    dispatch_hour: Optional[int] = Field(default=None, ge=0, le=23, description="Defaults to the current hour in India")


class BatchItem(BaseModel):
    city: str
    state: Optional[str]
    ok: bool
    error: Optional[str]
    recommended_days: int
    scheduled_shipping_days: int
    days_capped: bool
    result: Optional[PredictResponse]


class BatchResponse(BaseModel):
    as_of: str
    dispatch_date: date
    common_window: bool
    count: int
    failed: int
    items: List[BatchItem]


def resolve_destination(req):
    if req.destination_lat is not None:
        return (req.destination_lat, req.destination_lon), "in"
    try:
        lat, lon, country = geo_utils.geocode_destination(req.destination_city, req.destination_state)
    except geo_utils.GeocodeError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return (lat, lon), country


def weather_values(result):
    worst = result["worst_point"] or {}
    averages = result["averages"]
    return WeatherValues(
        precip_mm_avg=averages["precip_mm"], wind_kmh_avg=averages["wind_kmh"], temp_c_avg=averages["temp_c"],
        worst_date=worst.get("date"), worst_lat=worst.get("lat"), worst_lon=worst.get("lon"),
        worst_precip_mm=worst.get("precip_mm"), worst_wind_kmh=worst.get("wind_kmh"),
    )


@app.get("/health")
def health():
    return {"status": "ok", "features": len(COLUMNS)}


def run_prediction(order, destination, country, state, days, dispatch_date, hour):
    market = geo_utils.market_for_country(country)
    weather = route_weather.get_route_weather(geo_utils.ORIGIN_COORDS, destination, days, dispatch_date)
    distance = geo_utils.distance_km(geo_utils.ORIGIN_COORDS, destination)
    route = route_penalty.compute_route_penalty(distance, days, state)
    scored = inference.score_order(
        MODEL, COLUMNS, DEFAULTS, dict(order, scheduled_shipping_days=days, market=market, dispatch_hour=hour),
        weather_penalty_pct=weather["penalty_mean"], route_penalty_pct=route["total"],
    )
    split = weather["penalty_split"]
    return dict(
        scored,
        weather_rain_pct=split["rain"], weather_wind_pct=split["wind"], weather_heat_pct=split["heat"],
        route_slack_pct=route["slack"], route_terrain_pct=route["terrain"],
        required_km_per_day=route["required_km_per_day"], terrain_class=route["terrain_class"],
        weather_worst_penalty_pct=weather["penalty_worst"],
        weather_available=weather["available"], weather_reason=weather["reason"],
        weather_source=weather["route_source"],
        weather_dispatch_date=weather["dispatch_date"], weather_arrival_date=weather["arrival_date"],
        weather=weather_values(weather),
        distance_km=distance,
        dispatch_hour=hour,
        market=market,
    )


def current_hour():
    return datetime.now(INDIA_TZ).hour


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    destination, country = resolve_destination(req)
    hour = req.dispatch_hour if req.dispatch_hour is not None else current_hour()
    try:
        return run_prediction(
            req.model_dump(), destination, country, req.destination_state,
            req.scheduled_shipping_days, req.dispatch_date, hour,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


def hub_days(distance, common_days, max_days):
    recommended = route_penalty.recommended_days(distance)
    if common_days is not None:
        return recommended, common_days, False
    return recommended, min(recommended, max_days), recommended > max_days


def score_hub(req, hub, dispatch, hour, max_days):
    destination = (hub.lat, hub.lon)
    distance = geo_utils.distance_km(geo_utils.ORIGIN_COORDS, destination)
    recommended, days, capped = hub_days(distance, req.scheduled_shipping_days, max_days)
    item = {
        "city": hub.city, "state": hub.state, "ok": False, "error": None,
        "recommended_days": recommended, "scheduled_shipping_days": days, "days_capped": capped, "result": None,
    }
    try:
        item["result"] = run_prediction(req.model_dump(), destination, "in", hub.state, days, dispatch, hour)
        item["ok"] = True
    except ValueError as error:
        item["error"] = str(error)
    return item


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(req: BatchRequest):
    today = date.today()
    dispatch = req.dispatch_date or today
    try:
        route_weather.check_window(req.scheduled_shipping_days or 1, dispatch, today)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    max_days = route_weather.FORECAST_HORIZON_DAYS - (dispatch - today).days
    hour = req.dispatch_hour if req.dispatch_hour is not None else current_hour()
    with ThreadPoolExecutor(max_workers=BATCH_WORKERS) as pool:
        items = list(pool.map(lambda hub: score_hub(req, hub, dispatch, hour, max_days), req.hubs))
    return {
        "as_of": datetime.now(INDIA_TZ).isoformat(timespec="seconds"),
        "dispatch_date": dispatch,
        "common_window": req.scheduled_shipping_days is not None,
        "count": len(items),
        "failed": sum(1 for item in items if not item["ok"]),
        "items": items,
    }

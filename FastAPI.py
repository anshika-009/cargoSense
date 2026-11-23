"""
CargoSense | FastAPI.py
Purpose: serve POST /predict. The XGBoost model gives the base risk; the server computes a
rule-based route weather penalty (route_weather.py) and adds it on top.
Input: order fields, destination (city, optional state or coordinates), optional dispatch date.
Output: total risk, base risk, weather penalty and its split, weather values, status, availability.
Notes: if weather cannot be fetched the penalty is 0 and weather_available is False.
Run: uvicorn FastAPI:app --reload
"""
from datetime import date
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

import geo_utils
import inference
import route_weather

app = FastAPI(title="CargoSense API", version="2.0")
MODEL, COLUMNS, DEFAULTS = inference.load_artifacts()


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
    weather_delay_penalty_pct: float
    weather_rain_pct: float
    weather_wind_pct: float
    weather_heat_pct: float
    weather_worst_penalty_pct: float
    weather_available: bool
    weather_reason: Optional[str]
    weather_source: str
    weather_dispatch_date: date
    weather_arrival_date: date
    weather: WeatherValues
    distance_km: float
    market: str
    status: str


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


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    destination, country = resolve_destination(req)
    market = geo_utils.market_for_country(country)
    try:
        weather = route_weather.get_route_weather(
            geo_utils.ORIGIN_COORDS, destination, req.scheduled_shipping_days, req.dispatch_date
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    scored = inference.score_order(
        MODEL, COLUMNS, DEFAULTS, dict(req.model_dump(), market=market),
        weather_penalty_pct=weather["penalty_mean"],
    )
    split = weather["penalty_split"]
    return dict(
        scored,
        weather_rain_pct=split["rain"], weather_wind_pct=split["wind"], weather_heat_pct=split["heat"],
        weather_worst_penalty_pct=weather["penalty_worst"],
        weather_available=weather["available"], weather_reason=weather["reason"],
        weather_source=weather["route_source"],
        weather_dispatch_date=weather["dispatch_date"], weather_arrival_date=weather["arrival_date"],
        weather=weather_values(weather),
        distance_km=geo_utils.distance_km(geo_utils.ORIGIN_COORDS, destination),
        market=market,
    )

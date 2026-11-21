"""
CargoSense | FastAPI.py
Purpose: serve POST /predict. The XGBoost model gives the base risk; the weather
penalty sent by the client is added on top (rule-based, not learned).
Run: uvicorn FastAPI:app --reload
"""
from typing import Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

import inference

app = FastAPI(title="CargoSense API", version="1.0")
MODEL, COLUMNS, DEFAULTS = inference.load_artifacts()


class PredictRequest(BaseModel):
    order_quantity: int = Field(ge=1)
    sales_per_customer: float = Field(ge=0)
    product_price: float = Field(ge=0)
    shipping_mode: Literal["Standard Class", "Second Class", "First Class", "Same Day"]
    scheduled_shipping_days: int = Field(ge=1, description="Zero-day intercity transit is rejected")
    destination_city: str
    origin_hub: str = "Delhi Hub (North HQ)"
    weather_delay_penalty_pct: float = Field(default=0.0, ge=0, le=100)
    market: Optional[str] = None


class PredictResponse(BaseModel):
    late_delivery_risk_prob: float
    late_delivery_risk_pred: int
    base_risk_pct: float
    weather_delay_penalty_pct: float
    status: str


@app.get("/health")
def health():
    return {"status": "ok", "features": len(COLUMNS)}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    return inference.score_order(
        MODEL, COLUMNS, DEFAULTS, req.model_dump(),
        weather_penalty_pct=req.weather_delay_penalty_pct,
    )

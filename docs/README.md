# CargoSense

**Predictive Supply Chain and Delay Risk Engine**

CargoSense scores each shipment's chance of arriving late _before dispatch_, so operators can act before an SLA breach occurs. Most logistics dashboards report a delay after the SLA is already missed. CargoSense moves that to proactive risk scoring.

An XGBoost model trained on the DataCo Smart Supply Chain dataset is served through a FastAPI endpoint and shown in a Streamlit dashboard. The scope is inter-state transfers of goods from the Delhi hub.

## Features

- **Decoupled architecture:** the FastAPI backend (`POST /predict`

Request:

```json
{
  "order_quantity": 1,
  "sales_per_customer": 50,
  "product_price": 10,
  "shipping_mode": "Standard Class",
  "scheduled_shipping_days": 3,
  "destination_city": "Chennai",
  "destination_state": "Tamil Nadu",
  "destination_lat": 13.0827,
  "destination_lon": 80.2707,
  "origin_hub": "Delhi Hub (North HQ)",
  "dispatch_date": "2026-11-24"
}
```

`destination_state`, `destination_lat`, `destination_lon` and `dispatch_date` are optional. Latitude and longitude must be sent together; if they are missing the city is geocoded. Money fields are in USD. `scheduled_shipping_days` is 1 to 15.

Response (shortened):

```json
{
  "late_delivery_risk_prob": 0.46,
  "late_delivery_risk_pred": 0,
  "base_risk_pct": 38.0,
  "weather_delay_penalty_pct": 8.0,
  "weather_rain_pct": 8.0,
  "weather_wind_pct": 0.0,
  "weather_heat_pct": 0.0,
  "weather_worst_penalty_pct": 10.0,
  "weather_available": true,
  "weather_reason": null,
  "weather_source": "osrm",
  "weather_dispatch_date": "2026-11-24",
  "weather_arrival_date": "2026-11-27",
  "weather": {
    "precip_mm_avg": 12.0, "wind_kmh_avg": 18.0, "temp_c_avg": 30.0,
    "worst_date": "2026-11-26", "worst_lat": 20.3, "worst_lon": 78.1,
    "worst_precip_mm": 30.0, "worst_wind_kmh": 20.0
  },
  "distance_km": 1757.2,
  "market": "Pacific Asia",
  "status": "MODERATE CAUTION ZONE"
}
```

The API computes the weather penalty itself. A client-supplied `weather_delay_penalty_pct` or `market` is ignored. `weather_source` is `osrm`, or `geodesic` when routing failed and a straight line was used. The values above are illustrative.

Invalid input returns HTTP 422. Interactive docs are available at `http://localhost:8000/docs` while the API is running.

## Data and Model

- **Dataset:** DataCo Smart Supply Chain (roughly 2015 to 2018, mostly US order regions).
- **Target:** `Late_delivery_risk` (1 = late, 0 = on time).
- **Features (11):** payment type, shipping mode, scheduled shipping days, sales per customer, item quantity, product price, item discount, customer segment, department, market. Benefit per order was dropped (no effect on validation AUC). `Market` is used instead of `Order Region`; the API sets it from the geocoded country.
- **Leakage prevention:** `Days for shipping (real)`, `Delivery Status` and any field known only after dispatch are excluded.

## Limitations

- Evaluation uses the same historical dataset, so performance on Indian routes is unmeasured.
- The weather penalty is rule-based, with team-chosen point values and a 25 point cap, and has no measured accuracy of its own.
- Route weather assumes the shipment covers the same share of the route each day of the scheduled window. There is no truck tracking, so a late truck meets different weather than scored.
- OSRM and Nominatim are public services that can be slow or rate limited. When routing fails a straight line is used, and the response says so.
- Geodesic distance is a lower bound on road distance, so transit estimates are approximate.
- All money is in USD, with no conversion.

## Roadmap

- Probability calibration check (reliability curve)
- Precision and recall at the dashboard threshold
- Retrain or test on Indian or Asian shipment data
- Log live predictions and compare them with actual outcomes

# CargoSense

**Predictive Supply Chain and Delay Risk Engine**

CargoSense scores each shipment's chance of arriving late _before dispatch_, so operators can act before an SLA breach occurs. Most logistics dashboards report a delay after the SLA is already missed. CargoSense moves that to proactive risk scoring.

An XGBoost model trained on the DataCo Smart Supply Chain dataset is served through a FastAPI endpoint and shown in a Streamlit dashboard.

## Features

- **Decoupled architecture:** the FastAPI backend (`POST /predict`) is independent of the Streamlit UI, with strict Pydantic request and response schemas.
- **Arrival-day weather:** weather is fetched from Open-Meteo for the expected arrival date (today + transit days), not current conditions.
- **Root-cause attribution:** risk is split into base operational risk and a weather delay penalty (shown as +X%).
- **Geospatial mapping:** destination cities are geocoded with Geopy, geodesic distance is computed from the Delhi HQ hub, and each destination is mapped to a market region (Pacific Asia, USCA, Europe, LATAM, Africa).
- **Physical feasibility checks:** impossible inputs, such as zero-day intercity transit, are rejected in both the UI and the API.
- **Operational dashboard:** two pages, a Risk Assessment Calculator and a 3D Route Telemetry Map, with status badges: `STABLE OPTIMAL ROUTE`, `MODERATE CAUTION ZONE`, `CRITICAL SLA RISK`.

## How It Works

```
Streamlit input -> Geopy (distance, region) -> Open-Meteo (arrival-day weather)
   -> POST /predict -> Pydantic validation -> encode + reindex -> XGBoost
   -> PredictResponse (base risk, weather penalty, status) -> dashboard
```

## Tech Stack

| Layer                  | Technology                           |
| ---------------------- | ------------------------------------ |
| Language               | Python 3.9+                          |
| Model                  | XGBoost (`XGBClassifier`)            |
| Data                   | pandas, NumPy, scikit-learn          |
| API                    | FastAPI, Pydantic                    |
| Dashboard              | Streamlit                            |
| Geocoding and distance | Geopy (Nominatim), geodesic distance |
| Weather                | Open-Meteo API                       |
| Model storage          | pickle (`.pkl`)                      |

## Project Structure

```
data/                 DataCoSupplyChainDataset.csv
models/               final_xgb_model.pkl, processed_data_pipeline.pkl
FastAPI.py            prediction API
app.py                Streamlit dashboard
EDA.py                exploratory analysis
feature_data.py       feature selection and encoding
model_training.py     training and evaluation
requirements.txt
```

## Getting Started

```bash
git clone https://github.com/priyankchaurasiya539/SmartFreight
cd SmartFreight
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Run the API and the dashboard in two separate terminals, API first:

```bash
uvicorn FastAPI:app --reload
streamlit run app.py
```

To retrain the model:

```bash
python model_training.py
```

No API keys are needed. Open-Meteo and Nominatim are free; Nominatim has usage limits, so avoid rapid repeated requests.

## API

`POST /predict`

Request (illustrative):

```json
{
  "order_quantity": 1,
  "sales_per_customer": 50,
  "product_price": 10,
  "shipping_mode": "Standard Class",
  "scheduled_shipping_days": 2,
  "destination_city": "Chennai",
  "origin_hub": "Delhi Hub (North HQ)"
}
```

Response (illustrative):

```json
{
  "late_delivery_risk_prob": 0.81,
  "late_delivery_risk_pred": 1,
  "weather_delay_penalty_pct": 12.5,
  "status": "CRITICAL SLA RISK"
}
```

Invalid input returns HTTP 422. Interactive docs are available at `http://localhost:8000/docs` while the API is running.

## Data and Model

- **Dataset:** DataCo Smart Supply Chain (roughly 2015 to 2018, mostly US order regions).
- **Target:** `Late_delivery_risk` (1 = late, 0 = on time).
- **Features:** payment type, shipping mode, scheduled shipping days, sales per customer, item quantity, product price, discount, benefit per order, customer segment, department, order region.
- **Leakage prevention:** `Days for shipping (real)`, `Delivery Status` and any field known only after dispatch are excluded.

## Limitations

- Evaluation uses the same historical dataset, so performance on Indian routes is unmeasured.
- The weather penalty is rule-based and has no measured accuracy of its own.
- Geodesic distance is a lower bound on road distance, so transit estimates are approximate.
- The dataset is in USD while the dashboard displays INR; the model does not convert values.

## Roadmap

- Probability calibration check (reliability curve)
- Precision and recall at the dashboard threshold
- Retrain or test on Indian or Asian shipment data
- Log live predictions and compare them with actual outcomes

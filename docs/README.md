# CargoSense

**Predictive Supply Chain and Delay Risk Engine**

CargoSense scores each shipment's chance of arriving late _before dispatch_, so operators can act before an SLA breach occurs. Most logistics dashboards report a delay after the SLA is already missed. CargoSense moves that to proactive risk scoring.

An XGBoost model trained on the DataCo Smart Supply Chain dataset is served through a FastAPI endpoint and shown in a Streamlit dashboard. The scope is inter-state transfers of goods from the Delhi hub.

## Features

- **Decoupled architecture:** the FastAPI backend (`POST /predict`) is independent of the Streamlit UI, with strict Pydantic request and response schemas.
- **Route weather:** the API fetches road routes (OSRM), samples points along each route, dates each point by spreading the route evenly over the scheduled transit days, and takes the Open-Meteo forecast for each point and day. Each point-day gets a rule-based penalty, averaged per route and then across routes. The worst point is reported too.
- **Dispatch date and time:** the weather window starts on a chosen dispatch date (default today) and must end within 15 days from today, the forecast range. The dispatch hour feeds the model's same-day order hour feature.
- **Root-cause attribution:** risk is split into the model's base risk and a weather delay penalty (shown as +X%), with the penalty split into rain, wind and heat.
- **Geospatial mapping:** the API geocodes the destination with Geopy (Nominatim) when coordinates are not sent, computes geodesic distance from the Delhi HQ hub, and maps the country to the model's `Market` value. `Market` is backend-only and never shown; every Indian destination maps to Pacific Asia.
- **Physical feasibility checks:** zero-day transit is rejected in both the UI and the API, as are dispatch dates in the past and arrivals beyond the forecast range.
- **Weather unavailable state:** if a forecast cannot be fetched, the penalty is 0, `weather_available` is `false` and the dashboard says so. No weather values are invented, and there is no offline fallback.
- **Operational dashboard:** two pages, a Pre-Dispatch Risk Simulator with a 3D route map, and Network Corridor Intelligence with the model's real test metrics. Status badges: `STABLE OPTIMAL ROUTE`, `MODERATE CAUTION ZONE`, `CRITICAL SLA RISK`.

## How It Works

```
Streamlit input -> POST /predict -> Pydantic validation
   -> Geopy (coordinates if missing, distance, Market)
   -> OSRM routes -> sampled points -> Open-Meteo forecast per point and day -> weather penalty
   -> encode + reindex -> XGBoost base risk
   -> PredictResponse (base risk, penalty split, weather values, status) -> dashboard
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
| Routing                | OSRM public server (free, no key)    |
| Weather                | Open-Meteo API                       |
| Model storage          | pickle (`.pkl`)                      |

## Project Structure

```
data/                 train.csv, test.csv (DataCo, not in the repo)
models/               final_xgb_model.pkl, processed_data_pipeline.pkl, defaults.json, metrics.json, experiments.json
tests/                unit and API tests (no network needed)
experiments/          improve_model.py (accuracy experiments)
docs/                 README.md, DEVLOG.md
FastAPI.py            prediction API
inference.py          model loading, scoring, status thresholds
geo_utils.py          geocoding, geodesic distance, Market mapping
route_weather.py      route-based weather penalty
weather_utils.py      single-point arrival-day forecast
weather_penalty.py    rain, wind and heat rules
states_cities.py      destination cities and coordinates for the dashboard
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

To retrain the model (needs `data/train.csv` and `data/test.csv`; `--cv` adds 5-fold grouped cross-validation):

```bash
python model_training.py --cv
```

To repeat the accuracy experiments:

```bash
python -m experiments.improve_model
```

To run the tests (they use fake responses, so no internet is needed; the API tests need `httpx`):

```bash
pip install httpx
python -m unittest discover -s tests -t . -v
```

No API keys are needed. Open-Meteo, OSRM and Nominatim are free public services with usage limits, so avoid rapid repeated requests. Geocoding results are cached in memory.

## API

`POST /predict`

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
  "dispatch_date": "2026-11-24",
  "dispatch_hour": 9
}
```

`destination_state`, `destination_lat`, `destination_lon`, `dispatch_date` and `dispatch_hour` (0 to 23, defaults to the current hour in India) are optional. Latitude and longitude must be sent together; if they are missing the city is geocoded. Money fields are in USD. `scheduled_shipping_days` is 1 to 15.

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
  "dispatch_hour": 9,
  "market": "Pacific Asia",
  "status": "MODERATE CAUTION ZONE"
}
```

The API computes the weather penalty itself. A client-supplied `weather_delay_penalty_pct` or `market` is ignored. `weather_source` is `osrm`, or `geodesic` when routing failed and a straight line was used. The values above are illustrative.

Invalid input returns HTTP 422. Interactive docs are available at `http://localhost:8000/docs` while the API is running.

## Data and Model

- **Dataset:** DataCo Smart Supply Chain (roughly 2015 to 2018, mostly US order regions).
- **Split:** the provided `train.csv` and `test.csv` share 23,645 `Order Id` values, because one order has several item rows. Using them as given would leak, so they are pooled and re-split grouped by `Order Id`: 120,346 train, 24,069 validation and 36,104 test rows. All test numbers below are from this re-split test part, not from the original `test.csv`.
- **Target:** `Late_delivery_risk` (1 = late, 0 = on time).
- **Features (11):** payment type, shipping mode, scheduled shipping days, sales per customer, item quantity, product price, item discount, customer segment, department, market, and the same-day order hour. Benefit per order was dropped (no effect on validation AUC). `Market` is used instead of `Order Region`; the API sets it from the geocoded country.
- **Same-day order hour:** the hour the order is placed (the dispatch hour when serving), used only for Same Day orders and set to -1 for every other mode. In this data Same Day orders placed before noon are never late and later ones are 95.6% late. A raw hour feature was tested and rejected because it adds an hour effect to modes that have none.
- **Leakage prevention:** `Days for shipping (real)`, `Delivery Status`, the shipping date and any field known only after dispatch are excluded, and a guard in `feature_data.py` enforces this.

### Test results (XGBoost, threshold 0.5)

| Metric    | Before (10 features) | Now (+ same-day order hour) |
| --------- | -------------------- | --------------------------- |
| ROC-AUC   | 0.7426               | **0.7718**                  |
| Accuracy  | 69.4%                | **71.7%**                   |
| F1        | 0.6578               | **0.6910**                  |
| Precision | 0.8500               | **0.8607**                  |
| Recall    | 0.5365               | **0.5773**                  |

Train ROC-AUC is 0.7813 against 0.7705 validation and 0.7718 test, so there is no sign of overfitting. 5-fold grouped cross-validation gives ROC-AUC 0.7719 (std 0.0010) and accuracy 71.9% (std 0.0022).

### Where the gain comes from

| Shipping mode  | Test rows | Late rate | Accuracy before | Accuracy now |
| -------------- | --------- | --------- | --------------- | ------------ |
| First Class    | 5,552     | 96.3%     | 96.3%           | 96.3%        |
| Same Day       | 1,845     | 46.7%     | 53.3%           | **98.3%**    |
| Second Class   | 6,832     | 76.4%     | 76.4%           | 76.4%        |
| Standard Class | 21,875    | 38.3%     | 61.7%           | 61.7%        |

The whole improvement is Same Day orders. For the other three modes the model already matches the best guess that the data allows (always predict the mode's majority outcome), and excluding Same Day the accuracy is unchanged at 70.3%. The best accuracy this dataset allows is about 71.9%, so the model is at its ceiling. In DataCo the real transit days within First, Second and Standard Class look randomly drawn (for example Standard Class takes 2 to 6 days with roughly equal chance), so no feature can predict them.

### Experiments

Each change was tested alone against the baseline with `python -m experiments.improve_model` (same split; results saved to `models/experiments.json`):

| Change                                           | Test ROC-AUC | Test accuracy | Kept          |
| ------------------------------------------------ | ------------ | ------------- | ------------- |
| Baseline (10 features)                           | 0.7426       | 69.4%         |               |
| + raw order hour                                 | 0.7692       | 71.7%         | no, see above |
| + raw hour, month, weekday                       | 0.7674       | 71.7%         | no            |
| + same-day order hour                            | 0.7718       | 71.7%         | **yes**       |
| + same-day hour, drop cancelled and fraud orders | 0.7587       | 71.7%         | no            |
| + same-day hour, product category                | 0.7714       | 71.7%         | no            |
| + same-day hour, order region                    | 0.7718       | 71.7%         | no            |
| + same-day hour, deeper trees                    | 0.7720       | 71.7%         | no            |

Month, weekday, product category, region and tree depth gave no gain. A logistic regression with the same features also reaches 0.7712 ROC-AUC, so the information in the data is the limit, not the model type. Cancelled and suspected-fraud orders always have a late rate of 0, which is label noise, but removing them from training did not help.

## Limitations

- Evaluation uses the same historical dataset, so performance on Indian routes is unmeasured.
- The accuracy gain comes only from Same Day orders, which have 0 scheduled days. The dashboard and API reject zero-day transit for inter-state transfers, so for the orders they can score the accuracy is unchanged (about 70.3%). The model is at the accuracy ceiling for this data, so more features will not raise it.
- In the training data each shipping mode has exactly one scheduled day count (Same Day 0, First Class 1, Second Class 2, Standard Class 4). The dashboard lets the user pick other combinations, which the model has never seen, so those risks are extrapolations.
- First Class shows about 0.998 late in this dataset. This is a dataset quirk, not a real-world fact.
- Recall is 0.58 at the 0.5 threshold, so about 42% of late orders are not flagged by the classification output.
- The weather penalty is rule-based, with team-chosen point values and a 25 point cap, and has no measured accuracy of its own.
- Route weather assumes the shipment covers the same share of the route each day of the scheduled window. There is no truck tracking, so a late truck meets different weather than scored.
- OSRM and Nominatim are public services that can be slow or rate limited. When routing fails a straight line is used, and the response says so.
- Geodesic distance is a lower bound on road distance, so transit estimates are approximate.
- All money is in USD, with no conversion.

## Roadmap

- Probability calibration check (reliability curve)
- Decide the dashboard classification threshold (recall is only 0.58 at 0.5)
- Retrain or test on Indian or Asian shipment data
- Log live predictions and compare them with actual outcomes

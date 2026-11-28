# CargoSense Dev Log

A record of what we built, why, and what we rejected, organised by feature. Within each section, log entries are newest first.

## How to Update

- Add a dated line to the feature's **Log** in the same commit or PR as the code (`docs:` commit if docs only).
- If a decision changes, update **Why** and **Alternatives considered**, and note the change in the Log.
- Use real numbers only, copied from script output. Never estimate.
- Log any API contract change (field names, status strings, units) and tell whoever consumes it.
- New feature: copy the section layout (Status, What, Why, Alternatives considered, Log, Open).

## Contents

1. Data and EDA
2. Model
3. Weather penalty (rules)
4. Weather forecast fetch
5. API
6. Dashboard
7. Geocoding and region
8. Evaluation and limitations
9. Testing
10. Repo, branches and docs
11. Project decisions
12. Open items

---

## 1. Data and EDA

**Status:** done.

**What:** `EDA.py` inspects the separate train and test files and writes `eda_output.txt`. Findings: 144,415 train and 36,104 test rows, late share 0.5483 in both, no unseen categories, 23,645 `Order Id` values in both files, `Market` late rate almost flat (0.543 to 0.554).

**Why:** Every later step depends on facts only the data shows: column names, leakage columns, target balance, categories, and whether train and test overlap. EDA verifies our assumptions and discovers what we must decide.

**Alternatives considered:**

- Skip EDA and train directly: rejected, because leakage or overlap would only show up after training, and a leaked model scores brilliantly then fails in real use.
- Auto-drop suspicious columns: rejected. Leakage candidates are listed for manual review instead, so nothing is dropped silently.

**Log:**

- 2026-11-21: Added `EDA.py` and `eda_output.txt`. Files read with `latin-1`.

**Open:** none.

---

## 2. Model

**Status:** done (XGBoost, trained and saved).

**What:** `feature_data.py` (11 features, leakage guard, one-hot encoding, defaults) and `model_training.py` (grouped split, logistic and random forest baselines, XGBoost with early stopping, train AUC, optional `--cv`, a second model without the order-hour feature for before and after, accuracy by shipping mode). Saves `final_xgb_model.pkl`, `processed_data_pipeline.pkl`, `defaults.json` and `metrics.json`. `experiments/improve_model.py` runs each accuracy experiment alone against the baseline and saves `models/experiments.json`.

**Why XGBoost:**

- The PS specifies an XGBoost classifier.
- The data is a table of mixed numeric and categorical columns, where boosted trees usually perform best.
- It outputs probabilities, which the dashboard needs for risk percentages and status badges.
- It captures interactions (shipping mode with scheduled days) without hand-written rules.
- It is fast and saves to a single file.

**Alternatives considered:**

- Logistic regression: simple and explainable. Trained as a baseline; ROC-AUC 0.7425.
- Random forest: strong and easy. Trained as a baseline; ROC-AUC 0.7412.
- LightGBM and CatBoost: very similar to XGBoost, a near coin flip. Not used because the PS names XGBoost.
- Neural networks: overkill for a few tabular columns, and they need more data and tuning.
- SVM and KNN: slow on this size and give weak probabilities.
- Honest note: XGBoost (0.7426) does not beat the simple baselines. Its value here is the PS choice and probability output, not extra accuracy.

**Feature and split decisions:**

- Leakage excluded: `Days for shipping (real)`, `Delivery Status` and anything known only after dispatch. A guard in `feature_data.py` enforces this.
- Pooled train and test, then re-split by `Order Id` (test 1/5, validation 1/6 of the rest). Using the files as given was rejected: 23,645 order ids were in both, which would inflate the test score. A plain random row split was rejected for the same reason.
- `Market` used instead of `Order Region`: the backend can derive it from a geocoded city (5 values) and the UI never shows it.
- `Benefit per order` dropped: validation AUC 0.73928 with it, 0.73927 without, and the API never sends it.
- `model_training.py` also trains with and without `Benefit per order` and logs both validation AUCs.
- Early stopping with logloss last in `eval_metric`, so the saved probabilities are usable (AUC alone stopped at 4 trees on synthetic data).
- Category values whitespace-cleaned (`South of  USA`) so inference cannot silently miss a column.

**Log:**

- 2026-11-28 (`fix/model-days`, anshika-009): Decoupled model scoring days from user transit window. Model now receives each shipping mode's trained scheduled days (`Same Day: 0`, `First: 1`, `Second: 2`, `Standard: 4`), while user transit window drives weather timing and route penalty only. Avoids scoring unseen `day/mode` pairs (e.g., `Standard Class` at 3 days) that inflated base risk.

- 2026-11-21: Added `feature_data.py`, `model_training.py` and the model files. Test results (threshold 0.5): ROC-AUC 0.7426, accuracy 0.6940, F1 0.6578, precision 0.8500, recall 0.5365.

- 2026-11-27: ACCURACY WORK. Added the same-day order hour feature (the hour of the order, used only for Same Day orders; -1 for other modes). Test ROC-AUC 0.7426 to 0.7718, accuracy 69.4% to 71.7%, F1 0.6578 to 0.6910, precision 0.8500 to 0.8607, recall 0.5365 to 0.5773. Train AUC 0.7813, validation 0.7705; 5-fold grouped CV ROC-AUC 0.7719 (std 0.0010), accuracy 71.9% (std 0.0022).
- 2026-11-27: How we found it. Late rate by mode and scheduled days showed each mode has one scheduled day count, and real transit days inside First, Second and Standard Class are spread evenly (Standard Class 2 to 6 days), so nothing can predict them. Same Day orders placed before noon were never late (0.000) and from noon on were late 95.6% of the time, and the original features ignored the order time.
- 2026-11-27: Where the gain is. All of it is Same Day orders (accuracy 53.3% to 98.3% on 1,845 test rows). First, Second and Standard Class were already equal to always guessing their majority outcome, and excluding Same Day the accuracy is 70.3% before and after. The best accuracy this dataset allows is about 71.9% and CV accuracy reaches it, so more features will not raise it.
- 2026-11-27: Experiments (test ROC-AUC / accuracy): baseline 0.7426 / 69.4%; raw order hour 0.7692 / 71.7%; raw hour, month, weekday 0.7674 / 71.7%; same-day hour 0.7718 / 71.7% (adopted); drop cancelled and fraud orders from training 0.7587 / 71.7%; product category 0.7714 / 71.7%; order region 0.7718 / 71.7%; deeper trees 0.7720 / 71.7%. Raw hour was rejected: with it, a Standard Class order's base risk changed with the hour (34% at 09:00 vs 40% at 15:00) although the data has no such effect. Month, weekday, category, region and depth gave nothing.
- 2026-11-27: A logistic regression with the new feature also reaches 0.7712 ROC-AUC, confirming that the information in the data, not the model type, is the limit. Cancelled and suspected-fraud orders always have late rate 0 (label noise); dropping them from training did not help, so they stay.
- 2026-11-27: Caveats. The inter-state dashboard rejects zero-day transit and Same Day has 0 scheduled days in the data, so the gain does not show up in what the dashboard can score. Each mode has exactly one scheduled day count in the data, so other combinations the slider allows are extrapolations. Training reads the order date column; serving sends `dispatch_hour`.

**Open:** run `python -m ml.experiments.improve_model` and `python -m ml.model_training --cv` after any data change; run tests against the real model; choose the dashboard classification threshold (recall is 0.5773 at 0.5; the validation sweep is in `metrics.json`); decide whether to remove or relabel Same Day for inter-state use, since it cannot be scored there; update README note on trained days; pin versions in `requirements.txt`; `training_output.txt` was saved as UTF-16, so re-save as UTF-8 or leave it out of the repo.

---

## 3. Weather penalty (rules)

**Status:** done (rules and tests); not yet wired into the API or dashboard.

**What:** `weather_penalty.py` turns arrival-day weather into a penalty in percentage points, added on top of the model's base risk. Rain bands (2.5, 15.6, 64.5, 115.6, 204.5 mm) give 2, 5, 10, 15, 20 points, optionally scaled by rain probability. Wind bands (39, 62, 89 km/h) give 3, 6, 10. Heat bands (40, 45 C) give 2, 4. The total is capped at 25. It returns rain, wind, heat and total.

**Why rule-based:**

- The DataCo dataset has no weather, so the model cannot learn it.
- We have no Indian delivery outcomes to fit or check a learned effect.
- The PS says the weather penalty is a rule applied on top of the model output.
- A rule is transparent: operators see the cause (rain +X, wind +Y), which supports the root-cause attribution feature.

**Alternatives considered:**

- Hand-picked thresholds: fastest, but arbitrary.
- Standard category bands (chosen for the band edges): rain edges follow the IMD daily rainfall categories and wind edges follow the Beaufort scale (from memory, to be checked against the published tables). This only makes the edges defensible; the point values are still our judgment and have no measured accuracy.
- Learn from data by joining historical weather to DataCo orders: rejected for now. The orders are US-heavy, the effect would not transfer to India, and the model already leans on shipping mode and scheduled days, so little signal is expected. Test later by comparing validation AUC with and without weather features.
- Calibrate from logged outcomes: the only route to a measured penalty. Future work; needs real Indian deliveries.
- Design choices: probability weighting reduces false alarms; the cap stops weather swamping the base risk; all constants sit in one block for easy review.

**Log:**

- 2026-11-23: Added `weather_penalty.py` and 22 tests. Chennai's earlier hardcoded +12.5 becomes +8.0 for the same inputs (24.5 mm, 42 km/h).

**Open:** team reviews the point values; if a model is ever trained on weather, remove the rule penalty to avoid counting it twice; log weather inputs with predictions so the points can be calibrated.

---

## 4. Weather forecast fetch

**Status:** single-point arrival forecast done; route-based weather added in `route_weather.py` and used by the API.

**What:** `weather_utils.py`: `get_arrival_weather(latitude, longitude, transit_days)` requests the Open-Meteo forecast for today plus transit days (rain total, rain probability, max wind, max temperature). Returns the values, a condition label (HEAVY RAIN, MODERATE RAIN, LIGHT RAIN, STRONG WIND, CLEAR, UNAVAILABLE), the penalty breakdown and an `available` flag.

**Why:**

- The PS requires weather for the arrival date, not current conditions.
- Open-Meteo is the PS choice and needs no API key.
- Transit days are limited to 1 to 16, the forecast range.

**Alternatives considered:**

- Current weather at dispatch: rejected, it is not what happens on the arrival day.
- On failure, fall back to the old hardcoded table: rejected, it would show made-up numbers as if they were a forecast.
- On failure, raise an error: rejected, it would break the whole prediction.
- Chosen: zero penalty with `available: False` and `UNAVAILABLE`, so the UI can say "weather unavailable".
- Successes are cached for 30 minutes so Streamlit reruns do not spam the API; failures are not cached, so they retry.

**Log:**

- 2026-11-23: Added `route_weather.py` (13 mocked tests): up to 3 OSRM routes, a point about every 150 km, each point dated by spreading the route evenly over the scheduled transit days from the dispatch date, one Open-Meteo request per route, each point-day scored by `compute_weather_penalty()`, then averaged per point, per route and across routes. Penalties are averaged, not raw rain or wind, and the worst point is reported. OSRM failure falls back to a straight line (`weather_source: geodesic`); a forecast failure gives penalty 0 and `weather_available: false`. Not yet run against the live services.
- 2026-11-23: Added `weather_utils.py` with mocked tests. Live call and tests confirmed working locally.

**Open:** wire into the API and dashboard, replacing the hardcoded `INDIAN_HUBS` weather; the arrival date uses the server clock.

---

## 5. API

**Status:** done; the API computes the weather penalty itself.

**What:** `FastAPI.py` serves `POST /predict` and `GET /health`. Request: `order_quantity` (1 or more), `sales_per_customer` and `product_price` (0 or more, USD), `shipping_mode`, `scheduled_shipping_days` (1 to 15, so zero-day transit is rejected with HTTP 422), `destination_city`, optional `destination_state`, optional `destination_lat` and `destination_lon` (sent together, else the city is geocoded), `origin_hub`, optional `dispatch_date` and optional `dispatch_hour` (0 to 23, default the current hour in India). The API geocodes if needed, maps the country to `Market`, calls `route_weather.get_route_weather()`, scores the order with the model, adds the averaged weather penalty to the base risk and maps the total to a status (65 and 35 thresholds). `late_delivery_risk_pred` uses `PRED_THRESHOLD_PCT` (50). Response fields are listed in the README.

**Why:**

- The PS asks for a decoupled backend with strict Pydantic schemas, so other clients can reuse the model.
- Validation lives in the API as well as the UI, as the PS requires.

**Alternatives considered:**

- Call the model directly from Streamlit: simpler to host, but breaks the decoupled design the PS emphasises.
- Other frameworks (for example Flask): not needed; FastAPI gives schemas and `/docs` for free.
- CORS: not needed, because Streamlit calls the API from Python, not from a browser. Add it only if a browser frontend ever calls the API directly.

**Log:**

- 2026-11-28: CONTRACT ADDITION. New `POST /predict/batch` for the network scan: shared shipment fields plus a list of hubs (`city`, `state`, `lat`, `lon`), optional common `scheduled_shipping_days` (otherwise each hub gets `route_penalty.recommended_days()`), returns one `/predict`-shaped result per hub with `ok`, `error`, `days_capped` and an `as_of` time. `/predict` is unchanged; both share `run_prediction()`. `route_weather.py` now throttles live requests (0.25 s apart) and caches route geometry (24 h) and forecasts (1 h); failures are never cached and fakes bypass both. Reason: the corridor table scored every non-live hub with one fixed base risk and no weather, so all hubs looked alike.

- 2026-11-28 (`fix/model-days`, anshika-009): CONTRACT ADDITION. `POST /predict` now returns `model_scheduled_days` (`inference.py`, `FastAPI.py`).

- 2026-11-27: CONTRACT ADDITION. Added optional request field `dispatch_hour` (0 to 23, default the current hour in India) and response field `dispatch_hour`. It feeds the same-day order hour feature; other modes ignore it. Older clients keep working.
- 2026-11-23: CONTRACT CHANGE (v2.0). The API now computes the weather penalty. The request field `weather_delay_penalty_pct` is no longer used (a client that still sends it is ignored) and `market` is derived from the geocoded country. Added optional request fields `destination_state`, `destination_lat`, `destination_lon` (sent together; if missing the city is geocoded) and `dispatch_date` (default today; past dates and arrivals beyond 15 days are rejected), and `scheduled_shipping_days` now has an upper limit of 15. Added response fields `weather_rain_pct`, `weather_wind_pct`, `weather_heat_pct`, `weather_worst_penalty_pct`, `weather_available`, `weather_reason`, `weather_source`, `weather_dispatch_date`, `weather_arrival_date`, `weather` (averages and worst point), `distance_km` and `market`. Existing response fields keep their names and units, so the current dashboard keeps working.
- 2026-11-21: API and `inference.py` in the repo (logged retroactively). The dashboard posts to it at `CARGOSENSE_API` (default `http://127.0.0.1:8000`, 8 second timeout) and falls back to the static hub table if it is unreachable, tagging results `model` or `fallback`.

**Open:** `inference.py` has an inline comment that breaks the header-only rule; log weather inputs with predictions so the points can be calibrated.

---

## 6. Dashboard

**Status:** in progress.

**What:** Streamlit `app.py` with two pages: Pre-Dispatch Risk Simulator and Network Corridor Intelligence. Single-order input in the sidebar with validation; results come from the API; 3D arc map; status badges (STABLE OPTIMAL ROUTE, MODERATE CAUTION ZONE, CRITICAL SLA RISK).

**Why:**

- The PS describes a Streamlit dashboard with a calculator page and a route map page.
- One shipment in, one prediction out matches the PS. The earlier CSV batch flow was removed.
- Operators need speed and clarity, so metrics are consolidated into one "Shipment risk summary" card (total, base, weather penalty, distance, status, conditions, precipitation, wind, temperature, arrival date, advisory) with the map full width below.

**Alternatives considered:**

- React frontend: considered, then dropped. It means rebuilding two pages and the 3D map, which costs time better spent on missing PS features, and Streamlit already meets the PS. Streamlit's slowness and styling are fixable.
- Deploying the frontend alone: rejected. Without the API it would show fallback numbers that look real but are not from the model.
- Batch CSV or Excel upload and "shorter route" suggestions: out of scope for now. The model never sees distance, so a shorter route would not change the risk, and real routing needs road data.

**Removed from the UI:** placeholder KPIs, "LIVE RADAR" label, duplicate weather labels, speed requirement, market and region chips, sidebar Facts panel, the non-functional "Authorize Dispatch Exception" button, emojis.

**Log:**

- 2026-11-28: Network Corridor Intelligence gets a "Run Network Scan" button (`corridor.py`, `api_client.py`). It posts hubs to `/predict/batch` in chunks of 6 with a progress bar, either with the console window or each hub's recommended days. The table gains Window and Weather columns, an "as of" note and a stale-scan caption when inputs change. Hubs whose forecast failed show "unavailable". 93 tests.

- 2026-11-23: Page 1 now uses the API for weather. Added a dispatch date picker; the request sends `dispatch_date`, destination coordinates and state. The summary card shows the penalty split, weather window, worst segment, route averages and arrival date from the response, and a "weather unavailable" warning when `weather_available` is false. Removed the dashboard's own live weather fetch and the static offline fallback (including the invented +1 day relief); if the API is down or rejects the order the dashboard shows the error and stores nothing. Removed the per-hub advisory text from the card.
- 2026-11-27: Added a Dispatch Time input (hourly) that is sent as `dispatch_hour`. Page 2 metrics card now shows each metric with its value before the order-hour feature ("was 69.4% before"), an Accuracy tile, and an Accuracy by shipping mode table showing before and after, so it is clear the gain is Same Day orders only.
- 2026-11-26: Page 2 rebuilt. It now shows the real test metrics card from `metrics.json` (ROC-AUC, precision, recall, F1, test rows), hub count and nearest and furthest distance, the scored shipment's order value and value at risk (order value x late probability), and a corridor reference table (distance, terrain, indicative friction, scored risk for the scored corridor only) with terrain filter and sort. Removed the invented 20% penalty rate, $45 expedite cost and ROI, the per-hub fake base risk and weather, and the severe-weather filter. `states_cities.py` no longer holds `base_risk`, `weather_penalty`, `weather`, `temp_c`, `precip`, `wind`, `sla_days` or `advisory`, and distance is now geodesic (Geopy) instead of straight line x 1.22, so distances are about 18% shorter than before and the terrain friction bands (which use distance) shift slightly. Removed `get_static_weather`.
- 2026-11-23: Prepared an updated `app.py`: consolidated summary card, title no longer hidden under the header (top padding 2.2rem to 4.5rem), emojis and clutter removed, solid accent on the Run button ("Run risk assessment"). Not yet confirmed applied to the repo.
- 2026-11-21: Replaced CSV input with the single-order flow (`validate_inputs`, `get_prediction`, session-state results), added `status_from_risk` and `get_arrival_weather`, removed fake metrics. Results are tied to the exact payload, so an input change needs a re-run. The Run button sits above the sidebar panels.

**Open:** add caption near the transit window slider; confirm the update was applied against the latest local `app.py`; check the map filter selector in the deployed Streamlit version; theme toggle looks broken (`.streamlit/config.toml` option suggested); slow loading (move the repo out of OneDrive, run with `--server.fileWatcherType none`, cache or localise the state borders).

---

## 7. Geocoding and region

**Status:** backend built in `geo_utils.py`; the dashboard still uses its fixed 28-state list.

**What (planned):** Geopy geocodes the destination, computes geodesic distance from the Delhi hub, and maps the city to a market region.

**Why:** the PS lists geospatial mapping as a key feature. Today only 5 hub cities work, with hardcoded coordinates and distances.

**Alternatives considered:**

- Keep the 5 fixed hubs: fine for a first demo, but typing another city will not work.
- Drop `Market` from the model: possible, since its late rate is almost flat (0.543 to 0.554) and the backend always uses Pacific Asia. Decide before building the mapping.
- Multiple origin hubs: out of scope; Delhi is the single origin for now.

**Log:**

- 2026-11-23: Added `geo_utils.py` (5 tests): Nominatim geocoding restricted to India with in-memory caching, geodesic distance from Delhi, and a country to `Market` map. Decision: keep `Market` as a backend-only feature because the model was trained with it; every Indian destination maps to Pacific Asia. A failed lookup is an HTTP 422, not a guess.

**Open:** a live Nominatim check; Nominatim has rate limits.

---

## 8. Evaluation and limitations

**Status:** numbers recorded; PS figures replaced.

**What:** Test results (XGBoost, threshold 0.5, 36,104 test rows): ROC-AUC 0.7718, accuracy 71.7%, F1 0.6910, precision 0.8607, recall 0.5773. Before the order-hour feature (2026-11-27): ROC-AUC 0.7426, accuracy 69.4%, F1 0.6578, precision 0.8500, recall 0.5365. The PS reported 0.91 ROC-AUC and 89.4% accuracy; these are not our results and must not appear in the docs.

**Overfitting check:** train ROC-AUC 0.7813, validation 0.7705, test 0.7718, and 5-fold grouped CV 0.7719 (std 0.0010), so the gap is small. Test calibration is close and a logistic regression matches XGBoost, so the limit is the information in the data, not overfitting or the model type.

**Limitations to state openly:**

- Trained on DataCo (US-heavy) and not validated on Indian routes. We do not add synthetic Indian data, since invented outcomes would make the model look India-ready when it is not.
- First Class shows about 0.998 late in this dataset, which is a dataset quirk.
- The accuracy gain is Same Day only; the dashboard cannot score Same Day (zero-day rejected), so for inter-state orders accuracy is about 70.3% and at the dataset's ceiling.
- Each shipping mode has one scheduled day count in the training data; other combinations are extrapolations.
- The weather penalty is rule-based with no measured accuracy.
- Geodesic distance underestimates road distance.
- All money is in USD, with no conversion.

**Log:**

- 2026-11-23: Overfitting check and India-data decision recorded.

**Open:** record train AUC and optionally 5-fold grouped cross-validation; calibration of risk percentages; log predictions with weather inputs to validate on real outcomes later.

---

## 9. Testing

**Status:** weather, geocoding, API contract (single and batch), caching and the order-hour feature covered.

**What:** 65 passing tests in `tests/`: 22 for `weather_penalty.py` (band boundaries, probability scaling, cap, monotonic growth, validation), 10 for `weather_utils.py` (parsing, wrong date, failure, caching, invalid days), 13 for `route_weather.py` (sampling, day mapping, averaging, failure, dispatch date), 5 for `geo_utils.py`, 10 for the `/predict` contract (real model, faked weather and geocoding) and 5 for the order-hour feature (derived only for Same Day, learned cut-off, no leakage columns). All use fake responses, so no network is needed. Run from the repo root: `python -m unittest discover -s tests -t . -v`.

**Why:** the weather work cannot be checked against real outcomes, so the tests lock in the rules and the failure behaviour.

**Alternatives considered:** pytest was not used, to avoid a new dependency; `unittest` is in the standard library.

**Log:**

- 2026-11-28: 87 tests. Added `/predict/batch` (8), cache and throttle (5) and `recommended_days` (2) tests.
- 2026-11-28 (`fix/model-days`, anshika-009): Added `tests/test_model_days.py` for model scheduled-day routing vs. transit window.

- 2026-11-23: Tests moved into `tests/` with `tests/__init__.py`. App modules stay in the repo root.

**Open:** direct tests for the status thresholds in `inference.py`; live checks are manual (`experiments/`).

---

## 10. Repo, branches and docs

**Status:** in place.

**What:** `main` is the base branch; each teammate works on a feature branch (`feature/model-api`, `feature/ui`) and merges through pull requests. Commits follow Conventional Commits (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`), one concern per commit. Docs: team doc, AGENTS.md (comment and naming rules), README, training plan, this log.

**Why:** separate branches and separate files keep merge conflicts rare. Header-only comments and fixed naming conventions keep the code consistent across people and AI agents.

**Log:**

- 2026-11-28: CONTRACT CHANGE (run commands and imports). Sorted the flat repo into packages: `api/` (`FastAPI.py` is now `api/main.py`), `core/` (geo, route and weather rules, `states_cities`), `dashboard/` (`api_client`, `corridor`, `simulator_view`, `map`, `theme`), `ml/` (`feature_data`, `inference`, `model_training`, `EDA`, `experiments/`), `reports/` (the two output text files). `Test_model_days.py` moved to `tests/test_model_days.py`. `app.py` stays in the root. New commands: `uvicorn api.main:app --reload`, `python -m ml.model_training --cv`, `python -m ml.experiments.improve_model`. `streamlit run app.py` is unchanged.
- 2026-11-21: Set `main` as the base; a commit pushed to the wrong branch was moved to `feature/model-api`. Added the README and this log.

**Open:** set `main` as the GitHub default branch; README must sit in the repo root (it is in `docs/`); replace 0.91 and 89.4% with the real numbers and fill F1 and the split; change the clone URL from SmartFreight to CargoSense; add the team doc, AGENTS.md and `docs/MODEL_TRAINING_PLAN.md` to the repo; update docs for `tests/`, the weather modules and the new API contract; pin `requirements.txt`; consider moving the project out of OneDrive.

---

## 11. Project decisions

- Stay on Streamlit.
- Live demo from a local run, with a recorded backup. No hosting.
- All money in USD end to end.
- Delhi is the single origin hub.
- Market and order region are backend-only and never shown in the UI.
- Out of scope for now: batch upload, route optimisation, "what-if" suggestions, multiple hubs, deployment.

---

## 12. Open items

1. Live checks locally: the dashboard against the live API, one Nominatim lookup.
2. Decide the classification threshold (50 or 40) and whether to move the 35 status cutoff: the base risk is bunched at 37 to 42% or above 70%, so STABLE is almost empty.
3. Decide what to do with Same Day for inter-state use (the dashboard cannot score it) and how to treat scheduled-days values the model never saw.
4. Repo cleanup: root README, rename SmartFreight, pin requirements, `.gitignore`, UTF-8 `training_output.txt`, theme toggle, emojis, comments, `AGENTS.md`.
5. Rehearse the demo and record a backup video.
# CargoSense Dev Log

A running record of what changed and why. Newest entry on top.

## How to Write an Entry

- Add the entry in the same commit or PR as the code, with a `docs:` commit if it is docs only.
- Use real numbers only (metrics, split, thresholds), copied from script output. Never estimate.
- Log any change to the API contract (field names, status strings, units) and tell the teammate who consumes it.
- Update the team doc open-items checklist when an item is resolved.
- Keep entries short: a few lines per field.

**Template**

```
## YYYY-MM-DD | branch-name | owner
Done: what was built or changed
Files: files touched
Decisions: choices made and why
Open: anything unresolved or to verify

## 2026-11-21 | feature/ui | AgentRob0
Done: Replaced CSV batch input with a single-order flow (sidebar inputs, `validate_inputs`, `get_prediction` stub, session-state results). Replaced map overlays with three cards below the map: arrival-day forecast, risk attribution, dispatch status. Added `status_from_risk` (65 and 35 thresholds) and `get_arrival_weather`. KPIs now computed from `INDIAN_HUBS`; fake metrics removed.
Files: app.py
Decisions: Results are tied to the exact payload, so any input change needs a re-run. Stub predicts late at 50% or more. Forecast date is today plus committed days. Run button moved above the sidebar panels.
Open: Replace `get_prediction` with `requests.post` to FastAPI `/predict` and `get_arrival_weather` with Open-Meteo. Load real model metrics into the performance card. Check the map filter selector in the deployed Streamlit version.
```

## 2026-11-21 | feature/model-api | anshika-009

Done: Added `EDA.py` to inspect the separate train and test files (shape, missing values, duplicates, target balance, categories, train vs test checks, leakage candidates) and saved the output to `eda_output.txt`.
Files: EDA.py, eda_output.txt
Decisions: Read with `latin-1`. Leakage columns are listed for manual review, not auto-dropped. Findings from the run: 144,415 train and 36,104 test rows, late share 0.5483 in both, no unseen categories, 23,645 shared `Order Id` values, `Market` late rate flat (0.543 to 0.554).
Open: Shared order ids are handled in `model_training.py` by re-splitting. Check whether `Order Region` is worth a country-to-region mapping.

## 2026-11-21 | feature/model-api | anshika-009

Done: Added `feature_data.py` (11 model features, leakage guard, one-hot encoding, defaults) and `model_training.py` (grouped split, logistic and random forest baselines, XGBoost with early stopping, saves the four model files).
Files: feature_data.py, model_training.py
Decisions (add): Dropped `Benefit per order`: validation AUC 0.73928 with it, 0.73927 without, and the API never sends it. Test results (XGBoost, threshold 0.5): ROC-AUC 0.7426, accuracy 0.6940, F1 0.6578, precision 0.8500, recall 0.5365. Logistic regression (0.7425) and random forest (0.7412) score the same, so the signal is mostly shipping mode.
Open (replace first sentence): Choose the dashboard threshold; recall at 0.5 is only 0.5365.
Pooled train and test and re-split by `Order Id` (test 1/5, validation 1/6 of the rest), because 23,645 order ids were in both files and a plain test score would be inflated. Used `Market` instead of `Order Region` since the backend can derive it from the geocoded city (5 mapped values) and the UI never shows it. Put logloss last in `eval_metric` so early stopping gives usable probabilities; AUC alone stopped at 4 trees on synthetic data. Category values are whitespace-cleaned (`South of  USA`) so inference cannot silently miss a column. Script also trains with and without `Benefit per order` and logs both validation AUCs.
Open: Not yet run on the real data, so no metrics are recorded. After the run: fill the Results table, decide `Benefit per order` (API never sends it) and the threshold, pin versions in `requirements.txt`, update the repo map (`train.csv`, `test.csv`) and Known Limitations, and give the UI owner the contract. API must map city to the exact `Market` strings.

---

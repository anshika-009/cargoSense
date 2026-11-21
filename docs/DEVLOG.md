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

---

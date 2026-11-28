"""CargoSense | corridor.py
Purpose: the Network Corridor Intelligence page and the model-validation sidebar.
Input: the scored /predict result for the active route, if there is one, plus the transit window.
Output: Streamlit cards and a corridor table covering every hub. The active route shows its live /predict score.
Every other hub shows an estimate: the ML base risk from the last scored run plus the rule-based route penalty
(distance and terrain versus the window), the same rule the API adds to the live score. Weather is not included in the estimate for other hubs.
Notes: the model itself does not see the destination, so hubs differ only by route penalty (and weather on the live
route). The SLA penalty rate and expedite cost are planning assumptions, not model outputs, and are labelled as such.
Used by: app.py.
"""

import json
from pathlib import Path
import streamlit as st

import route_penalty

from states_cities import ORIGIN_HUB, get_all_city_records
from theme import (
    ACCENT,
    CRIT_TEXT,
    STATUS_COLORS,
    STATUS_FILL,
    STATUS_TAG_CLASS,
    TEXT_SUB,
    format_weather_condition,
    metric_tile,
    status_from_risk,
)
from weather_utils import condition_label

METRICS_FILE = Path(__file__).parent / "models" / "metrics.json"
SLA_PENALTY_RATE = 0.20
EXPEDITE_COST_USD = 45.0


@st.cache_data(show_spinner=False)
def load_model_metrics():
    if not METRICS_FILE.exists():
        return None
    return json.loads(METRICS_FILE.read_text(encoding="utf-8"))


def render_model_sidebar():
    with st.sidebar:
        st.markdown("### Model Validation & Weights")
        metrics_data = load_model_metrics()
        if metrics_data:
            roc_auc = metrics_data.get("roc_auc", 0.0)
            precision = metrics_data.get("precision", 0.0)
            recall = metrics_data.get("recall", 0.0)
            f1 = metrics_data.get("f1", 0.0)
            best_iter = metrics_data.get("best_iteration", "N/A")
            top_features = metrics_data.get("top_importances", {})

            st.metric("ROC-AUC Score", f"{roc_auc:.3f}")
            st.metric("Precision", f"{precision * 100:.1f}%")
            st.metric("Recall", f"{recall * 100:.1f}%")
            st.metric("F1 Score", f"{f1:.3f}", delta=f"Trees: {best_iter}")

            if top_features:
                st.caption("Top Predictive Feature Weights")
                for feat, weight in list(top_features.items())[:5]:
                    st.write(f"**{feat}:** {weight * 100.0:.1f}%")
        else:
            st.caption("No local metrics.json found.")


TERRAIN_LABELS = {
    "himalayan": "Hill / Himalayan",
    "ghats": "Ghats / Plateau",
    "coastal": "Coastal",
    "plains": "Plains",
}


def render_corridor_intelligence(committed_days, hub_rec=None, scored_pred=None, qty=1, sales=50.0, shipping_mode=None):
    mode_text = f"{shipping_mode}, " if shipping_mode else ""
    active_key = (hub_rec.get("state"), hub_rec.get("city")) if (hub_rec and scored_pred) else None
    live_weather = (scored_pred.get("weather") or {}) if scored_pred else {}
    weather_available = bool(scored_pred.get("weather_available", True)) if scored_pred else False
    base_pct = float(scored_pred["base_risk_pct"]) if (scored_pred and scored_pred.get("base_risk_pct") is not None) else None

    rows = []
    for rec in get_all_city_records():
        is_live = active_key == (rec["state"], rec["city"])
        dist_km = float(scored_pred.get("distance_km", rec["dist"])) if is_live else float(rec["dist"])
        route = route_penalty.compute_route_penalty(dist_km, int(committed_days), rec["state"])
        row = {
            "state": rec["state"],
            "city": rec["city"],
            "dist": dist_km,
            "is_live": is_live,
            "terrain": route["terrain_class"],
            "speed": route["required_km_per_day"],
            "route_pts": route["total"],
            "slack_pts": route["slack"],
            "terrain_pts": route["terrain"],
            "total_pct": None,
            "status": None,
            "precip": 0.0,
            "wind": 0.0,
        }
        if is_live:
            row["total_pct"] = round(float(scored_pred["late_delivery_risk_prob"]) * 100.0, 1)
            row["precip"] = float(live_weather.get("worst_precip_mm") or 0.0)
            row["wind"] = float(live_weather.get("worst_wind_kmh") or 0.0)
        elif base_pct is not None:
            row["total_pct"] = round(min(base_pct + route["total"], 100.0), 1)
        if row["total_pct"] is not None:
            row["status"] = status_from_risk(row["total_pct"])
        rows.append(row)

    longest = max(rows, key=lambda r: r["dist"])
    live_row = next((r for r in rows if r["is_live"]), None)
    n_states = len({r["state"] for r in rows})
    strained = sum(1 for r in rows if r["route_pts"] > 0)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            metric_tile("Tracked Hubs", str(len(rows)), f"Destination cities across {n_states} states", ACCENT),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            metric_tile(
                "Hubs With Route Penalty",
                str(strained),
                f"{mode_text}{committed_days}-day window · longest: {longest['city']} ({longest['dist']:,.0f} km)",
                ACCENT,
            ),
            unsafe_allow_html=True,
        )
    with k3:
        if live_row:
            st.markdown(
                metric_tile(
                    "Live Route Risk",
                    f'<span style="color: {STATUS_COLORS[live_row["status"]]};">{live_row["total_pct"]:.1f}%</span>',
                    f'{live_row["city"]}: {live_row["status"]}',
                    STATUS_FILL[live_row["status"]],
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                metric_tile("Live Route Risk", "Not scored", "Run an assessment on the Pre-Dispatch Risk Simulator", ACCENT),
                unsafe_allow_html=True,
            )

    if live_row:
        total_order_value = float(sales) * int(qty)
        risk_prob = float(scored_pred["late_delivery_risk_prob"])
        est_exposure = total_order_value * risk_prob * SLA_PENALTY_RATE
        roi_pct = (est_exposure - EXPEDITE_COST_USD) / EXPEDITE_COST_USD * 100.0
        live_cond = (
            condition_label(live_row["precip"], live_row["wind"]) if weather_available else "Weather unavailable"
        )
        st.markdown(
            f'<div class="intel-card">'
            f'<div class="card-title">Live /predict Order Impact · {ORIGIN_HUB} → {hub_rec["city"]} ({hub_rec["state"]})</div>'
            f'<div style="display:flex; flex-wrap:wrap; gap:24px; font-size:13.5px;">'
            f'<div><strong>Live Total Risk:</strong> <span style="color:{STATUS_COLORS[status_from_risk(risk_prob * 100.0)]}; font-weight:700;">{risk_prob * 100.0:.1f}%</span></div>'
            f'<div><strong>Live Distance:</strong> {live_row["dist"]:,.0f} km</div>'
            f'<div><strong>Window:</strong> {committed_days} days</div>'
            f'<div><strong>Live Weather:</strong> {live_cond}</div>'
            f'<div><strong>Order Value:</strong> ${total_order_value:,.2f}</div>'
            f'<div><strong>SLA Penalty Exposure ({SLA_PENALTY_RATE:.0%}):</strong> <span style="color:{CRIT_TEXT}; font-weight:700;">${est_exposure:,.2f}</span></div>'
            f'<div><strong>Expedite Cost vs ROI:</strong> ${EXPEDITE_COST_USD:,.0f} ({roi_pct:+.0f}% ROI)</div>'
            f'</div>'
            f'<div style="font-size:12px; margin-top:8px; color:{TEXT_SUB};">The {SLA_PENALTY_RATE:.0%} penalty rate and ${EXPEDITE_COST_USD:,.0f} expedite cost are planning assumptions, not model outputs.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="intel-card">'
            f'<div class="card-title">Live /predict Order Impact</div>'
            f'<div style="font-size:13px; color:{TEXT_SUB};">'
            f"No active live /predict score for the current order/route. Run an assessment on <strong>Pre-Dispatch Risk Simulator</strong> to view live model risk and SLA exposure here."
            f"</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height: 6px;"></div>', unsafe_allow_html=True)
    f_col1, f_col2 = st.columns([3, 2])
    with f_col1:
        state_filter = st.selectbox(
            "State",
            ["All states"] + sorted({r["state"] for r in rows}),
            label_visibility="collapsed",
        )
    with f_col2:
        hub_sort = st.selectbox(
            "Sort Order",
            ["Highest Estimated Risk", "Highest Route Penalty", "Furthest Distance", "State / City (A-Z)"],
            label_visibility="collapsed",
        )

    filtered = [r for r in rows if state_filter == "All states" or r["state"] == state_filter]
    if hub_sort == "Highest Estimated Risk":
        filtered = sorted(filtered, key=lambda r: (-(r["total_pct"] if r["total_pct"] is not None else -1.0), -r["dist"]))
    elif hub_sort == "Highest Route Penalty":
        filtered = sorted(filtered, key=lambda r: (-r["route_pts"], -r["dist"]))
    elif hub_sort == "Furthest Distance":
        filtered = sorted(filtered, key=lambda r: -r["dist"])
    else:
        filtered = sorted(filtered, key=lambda r: (r["state"], r["city"]))

    rows_html = ""
    for row in filtered:
        terrain_cell = TERRAIN_LABELS[row["terrain"]]
        speed_cell = f"{row['speed']:,.0f} km/day"
        penalty_cell = (
            f"+{row['route_pts']:.1f} pts "
            f"<span style='color:{TEXT_SUB}; font-size:11px;'>(window {row['slack_pts']:.1f} + terrain {row['terrain_pts']:.1f})</span>"
            if row["route_pts"] > 0
            else "0.0 pts"
        )
        if row["total_pct"] is None:
            risk_cell = f"<span style='color:{TEXT_SUB};'>Run an assessment</span>"
            tag = f"<span style='color:{TEXT_SUB};'>—</span>"
        else:
            risk_cell = (
                f'<strong>{row["total_pct"]:.0f}%</strong>'
                f'<span class="mini-bar"><div style="width: {min(row["total_pct"], 100)}%; background: {STATUS_FILL[row["status"]]};"></div></span>'
            )
            tag = f'<span class="{STATUS_TAG_CLASS[row["status"]]}">{row["status"]}</span>'
        src_badge = (
            f' <span style="font-size:11px; color:{ACCENT}; font-weight:600;">(Live /predict)</span>'
            if row["is_live"]
            else ""
        )
        rows_html += (
            f"<tr>"
            f"<td><strong>Delhi HQ → {row['city']}</strong> <span style='color:{TEXT_SUB};'>({row['state']})</span>{src_badge}</td>"
            f"<td>{row['dist']:,.0f} KM</td>"
            f"<td>{terrain_cell}</td>"
            f"<td>{speed_cell}</td>"
            f"<td>{penalty_cell}</td>"
            f"<td>{risk_cell}</td>"
            f"<td>{tag}</td>"
            f"</tr>"
        )

    if not rows_html:
        rows_html = f"<tr><td colspan='7' style='text-align:center; color:{TEXT_SUB}; padding:18px;'>No corridors match the selected filter.</td></tr>"

    note = (
        f"Estimate = ML base risk from the last scored run ({base_pct:.1f}%) + route penalty. Weather is only included on the live route. "
        if base_pct is not None
        else "Run an assessment to add the ML base risk to each hub. "
    )
    st.markdown(
        f'<div class="intel-card">'
        f'<div class="card-title">Corridor Overview — {mode_text}{committed_days}-Day Window ({len(filtered)} of {len(rows)} Hubs)</div>'
        f'<table class="intel-table">'
        f"<thead><tr><th>Corridor</th><th>Distance</th><th>Terrain</th><th>Speed Needed</th>"
        f"<th>Route Penalty</th><th>Est. Risk</th><th>Status</th></tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table>"
        f'<div style="font-size:12px; margin-top:8px; color:{TEXT_SUB};">{note}'
        f"The model does not see the destination, so hubs differ only by route penalty (distance and terrain versus the window). "
        f"Route penalty is a rule-based heuristic, not learned, and does not depend on shipping mode.</div></div>",
        unsafe_allow_html=True,
    )
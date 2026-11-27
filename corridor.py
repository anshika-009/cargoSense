from datetime import datetime, timedelta
import json
from pathlib import Path
import streamlit as st

from states_cities import ORIGIN_HUB, get_all_city_records
from theme import (
    ACCENT,
    CRIT_TEXT,
    STATUS_COLORS,
    STATUS_CRITICAL,
    STATUS_FILL,
    STATUS_TAG_CLASS,
    TEXT_SUB,
    format_weather_condition,
    metric_tile,
    status_from_risk,
)
from weather_utils import condition_label

METRICS_FILE = Path(__file__).parent / "models" / "metrics.json"


@st.cache_data(show_spinner=False)
def load_model_metrics():
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text())
        except Exception:
            return None
    return None


def get_static_weather(hub_record, days):
    return {
        "precip": hub_record["precip"],
        "wind": hub_record["wind"],
        "temp_c": hub_record["temp_c"],
        "condition": hub_record["weather"],
        "forecast_date": datetime.now() + timedelta(days=days),
        "penalty_pct": hub_record["weather_penalty"],
    }


def render_model_sidebar():
    with st.sidebar:
        st.markdown("### Model Validation & Weights")
        show_model_sidebar = st.checkbox("Show ROC / Validation Metrics", value=False)
        if show_model_sidebar:
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


def render_corridor_intelligence(committed_days, hub_rec=None, scored_pred=None, qty=1, sales=50.0):
    st.markdown(
        '<div class="page2-sidebar-trigger">☰ Use the top-left sidebar toggle to view Model Validation &amp; Weights</div>',
        unsafe_allow_html=True,
    )

    all_corridor_stats = []
    for rec in get_all_city_records():
        city_weather = get_static_weather(rec, committed_days)
        city_total_pct = min(round(float(rec["base_risk"]) + float(city_weather["penalty_pct"]), 1), 100.0)
        all_corridor_stats.append(
            {
                "state": rec["state"],
                "city": rec["city"],
                "dist": float(rec["dist"]),
                "weather": city_weather,
                "total_pct": city_total_pct,
                "status": status_from_risk(city_total_pct),
            }
        )

    flagged_cities = [
        f"{row['city']} ({row['state']})"
        for row in all_corridor_stats
        if row["status"] == STATUS_CRITICAL
    ]
    avg_total_pct = sum(r["total_pct"] for r in all_corridor_stats) / max(len(all_corridor_stats), 1)
    avg_status = status_from_risk(avg_total_pct)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            metric_tile("Tracked Hubs", str(len(all_corridor_stats)), "Static hub baseline (28 states)", ACCENT),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            metric_tile(
                "Baseline Critical Hubs",
                f'<span style="color: {STATUS_COLORS[STATUS_CRITICAL]};">{len(flagged_cities)}</span>',
                f"{len(flagged_cities)} high-risk hubs (static)",
                STATUS_FILL[STATUS_CRITICAL],
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            metric_tile(
                "Baseline Avg Risk",
                f'<span style="color: {STATUS_COLORS[avg_status]};">{avg_total_pct:.1f}%</span>',
                "Static hub baseline (not live /predict)",
                STATUS_FILL[avg_status],
            ),
            unsafe_allow_html=True,
        )

    if hub_rec and scored_pred:
        total_order_value = float(sales) * int(qty)
        penalty_rate = 0.20
        risk_prob = float(scored_pred["late_delivery_risk_prob"])
        est_exposure = total_order_value * risk_prob * penalty_rate
        expedite_cost = 45.0
        roi_pct = ((est_exposure - expedite_cost) / expedite_cost) * 100.0 if expedite_cost > 0 else 0.0
        scored_km = float(scored_pred.get("distance_km", hub_rec["dist"]))
        live_cond = (
            condition_label(
                (scored_pred.get("weather") or {}).get("worst_precip_mm") or 0.0,
                (scored_pred.get("weather") or {}).get("worst_wind_kmh") or 0.0,
            )
            if scored_pred.get("weather_available", True)
            else "Weather unavailable"
        )

        st.markdown(
            f'<div class="intel-card">'
            f'<div class="card-title">Live /predict Order Impact · {ORIGIN_HUB} → {hub_rec["city"]} ({hub_rec["state"]})</div>'
            f'<div style="display:flex; flex-wrap:wrap; gap:24px; font-size:13.5px;">'
            f'<div><strong>Live Total Risk:</strong> <span style="color:{STATUS_COLORS[status_from_risk(risk_prob * 100.0)]}; font-weight:700;">{risk_prob * 100.0:.1f}%</span></div>'
            f'<div><strong>Live Distance:</strong> {scored_km:,.0f} km</div>'
            f'<div><strong>Live Weather:</strong> {live_cond}</div>'
            f'<div><strong>Order Value:</strong> ${total_order_value:,.2f}</div>'
            f'<div><strong>SLA Penalty Exposure (20%):</strong> <span style="color:{CRIT_TEXT}; font-weight:700;">${est_exposure:,.2f}</span></div>'
            f'<div><strong>Expedite Cost vs ROI:</strong> ${expedite_cost:,.0f} ({roi_pct:+.0f}% ROI)</div>'
            f'</div></div>',
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
        hub_filter = st.radio(
            "Filter Corridors",
            ["All Hubs", "Critical Risk Only", "Severe Weather"],
            horizontal=True,
            label_visibility="collapsed",
        )
    with f_col2:
        hub_sort = st.selectbox(
            "Sort Order",
            ["Highest Risk %", "Furthest Distance", "State / City (A-Z)"],
            label_visibility="collapsed",
        )

    filtered_hubs = all_corridor_stats
    if hub_filter == "Critical Risk Only":
        filtered_hubs = [h for h in filtered_hubs if h["status"] == STATUS_CRITICAL]
    elif hub_filter == "Severe Weather":
        filtered_hubs = [
            h for h in filtered_hubs
            if (h["weather"]["precip"] >= 15.0 or h["weather"]["wind"] >= 25.0)
        ]

    if hub_sort == "Highest Risk %":
        filtered_hubs = sorted(filtered_hubs, key=lambda x: x["total_pct"], reverse=True)
    elif hub_sort == "Furthest Distance":
        filtered_hubs = sorted(filtered_hubs, key=lambda x: x["dist"], reverse=True)
    else:
        filtered_hubs = sorted(filtered_hubs, key=lambda x: (x["state"], x["city"]))

    rows_html = ""
    for row in filtered_hubs[:25]:
        tag = f'<span class="{STATUS_TAG_CLASS[row["status"]]}">{row["status"]}</span>'
        risk_cell = (
            f'<strong>{row["total_pct"]:.0f}%</strong>'
            f'<span class="mini-bar"><div style="width: {min(row["total_pct"], 100)}%; background: {STATUS_FILL[row["status"]]};"></div></span>'
        )
        cond_label = format_weather_condition(
            row["weather"]["condition"], row["weather"]["precip"], row["weather"]["wind"]
        )
        rows_html += (
            f"<tr>"
            f"<td><strong>Delhi HQ → {row['city']}</strong> <span style='color:{TEXT_SUB};'>({row['state']})</span></td>"
            f"<td>{row['dist']:,.0f} KM</td>"
            f"<td>{cond_label}</td>"
            f"<td>{risk_cell}</td>"
            f"<td>{tag}</td>"
            f"</tr>"
        )

    if not rows_html:
        rows_html = f"<tr><td colspan='5' style='text-align:center; color:{TEXT_SUB}; padding:18px;'>No corridors match the selected filter.</td></tr>"

    st.markdown(
        f'<div class="intel-card">'
        f'<div class="card-title">Static Hub Reference Snapshot — Not Live /predict Output (Showing {len(filtered_hubs[:25])} of {len(filtered_hubs)} Matching Hubs)</div>'
        f'<table class="intel-table">'
        f"<thead><tr><th>Corridor</th><th>Distance</th><th>Condition</th><th>Risk</th><th>Status</th></tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )
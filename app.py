"""CargoSense Streamlit dashboard: pre-dispatch late-delivery risk simulation
and network corridor intelligence across all 28 Indian states.
"""

import base64
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

from states_cities import (
    DELHI_HQ_COORDS,
    INDIA_STATES_CITIES,
    ORIGIN_HUB,
    get_all_city_records,
    get_hub_record,
)

st.set_page_config(
    page_title="CargoSense — 3D Telemetry & Route Analysis",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def svg_to_data_uri(svg_text: str) -> str:
    encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{encoded}"


GREY_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 48 60">'
    '<path d="M24 3 C12.4 3 3 12.2 3 23.6 C3 39.2 24 57 24 57 C24 57 45 39.2 45 23.6 '
    'C45 12.2 35.6 3 24 3 Z" fill="#64748b" stroke="#e2e8f0" stroke-width="2.5"/>'
    '<circle cx="24" cy="23" r="8" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>'
    "</svg>"
)

GLASS_3D_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 56 70">'
    "<defs>"
    '<linearGradient id="glassGrad" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#a5f3fc" stop-opacity="0.98"/>'
    '<stop offset="55%" stop-color="#6366f1" stop-opacity="0.95"/>'
    '<stop offset="100%" stop-color="#3730a3" stop-opacity="0.98"/>'
    "</linearGradient>"
    "</defs>"
    '<path d="M28 4 C14.7 4 4 14.5 4 27.5 C4 45.5 28 66 28 66 C28 66 52 45.5 52 27.5 '
    'C52 14.5 41.3 4 28 4 Z" fill="url(#glassGrad)" stroke="#e0e7ff" stroke-width="2.8"/>'
    '<ellipse cx="21" cy="17" rx="6" ry="3.5" transform="rotate(-25 21 17)" fill="#ffffff" opacity="0.65"/>'
    '<circle cx="28" cy="27" r="8.5" fill="#eef2ff" stroke="#4338ca" stroke-width="2.2"/>'
    "</svg>"
)

CRITICAL_WARN_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 58 72">'
    "<defs>"
    '<linearGradient id="warnPinGrad" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#fda4af"/>'
    '<stop offset="55%" stop-color="#e11d48"/>'
    '<stop offset="100%" stop-color="#881337"/>'
    "</linearGradient>"
    "</defs>"
    '<path d="M29 4 C15.2 4 4 14.9 4 28.3 C4 46.8 29 68 29 68 C29 68 54 46.8 54 28.3 '
    'C54 14.9 42.8 4 29 4 Z" fill="url(#warnPinGrad)" stroke="#ffe4e6" stroke-width="2.8"/>'
    '<polygon points="29,15 41,36 17,36" fill="#fff7ed" stroke="#fed7aa" stroke-width="1.8" stroke-linejoin="round"/>'
    '<rect x="27.7" y="21" width="2.6" height="8" rx="1" fill="#be123c"/>'
    '<circle cx="29" cy="32.3" r="1.5" fill="#be123c"/>'
    "</svg>"
)

top_col1, top_col2 = st.columns([4, 1.3])

with top_col1:
    st.markdown(
        """
        <div class="hero">
            <div class="brand-mark">CS</div>
            <div>
                <div class="hero-title">Cargo<span class="accent">Sense</span></div>
                <div class="hero-sub">3D dynamic arc telemetry &amp; route analysis · Delhi HQ outbound</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top_col2:
    theme_mode = st.radio(
        "Display Theme",
        ["Dark Mode", "Light Mode"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )

if theme_mode == "Light Mode":
    bg_app = "#f2f4fb"
    bg_header = "#f2f4fb"
    bg_card = "#ffffff"
    bg_toolbar = "#e6e9f6"
    bg_input = "#ffffff"
    text_input = "#14172e"
    border_input = "#8b93c4"
    border_card = "#dde1f0"
    text_main = "#14172e"
    text_sub = "#5a6183"
    grid_line = "rgba(79, 70, 229, 0.05)"
    accent = "#5b5bf0"
    accent_soft = "rgba(91, 91, 240, 0.12)"
    ok_text = "#047857"
    mod_text = "#b45309"
    crit_text = "#be123c"
    tile_shadow = "0 8px 22px rgba(40, 50, 120, 0.10)"
    map_style_choice = pdk.map_styles.CARTO_LIGHT
    arc_inactive_color = [100, 116, 139, 95]
    pin_label_color = [20, 23, 46, 255]
    secondary_label_color = [71, 85, 105, 220]
    state_border_color = [91, 100, 150, 170]
else:
    bg_app = "#0a0f24"
    bg_header = "#0a0f24"
    bg_card = "#141b3b"
    bg_toolbar = "#1b2450"
    bg_input = "#0b1026"
    text_input = "#ffffff"
    border_input = "#4a5590"
    border_card = "#2a3566"
    text_main = "#eef1ff"
    text_sub = "#9aa6d1"
    grid_line = "rgba(129, 140, 248, 0.05)"
    accent = "#818cf8"
    accent_soft = "rgba(129, 140, 248, 0.16)"
    ok_text = "#34d399"
    mod_text = "#fbbf24"
    crit_text = "#fb7185"
    tile_shadow = "0 10px 26px rgba(0, 0, 0, 0.35)"
    map_style_choice = pdk.map_styles.CARTO_DARK
    arc_inactive_color = [148, 163, 184, 95]
    pin_label_color = [238, 241, 255, 255]
    secondary_label_color = [148, 163, 184, 215]
    state_border_color = [129, 140, 248, 140]

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, .stApp, .stApp * {{
    font-family: 'Inter', 'Segoe UI', sans-serif;
}}

.stApp {{
    background-color: {bg_app} !important;
    background-image:
        radial-gradient(circle at 85% 5%, {accent_soft}, transparent 40%),
        radial-gradient(circle at 5% 95%, rgba(6, 182, 212, 0.08), transparent 40%),
        linear-gradient(to right, {grid_line} 1px, transparent 1px),
        linear-gradient(to bottom, {grid_line} 1px, transparent 1px) !important;
    background-size: 100% 100%, 100% 100%, 32px 32px, 32px 32px !important;
    color: {text_main} !important;
}}

.block-container {{
    padding-top: 3.5rem !important;
    max-width: 1520px !important;
}}

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {{
    background-color: {bg_header} !important;
    color: {text_main} !important;
}}

[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span,
[data-testid="stWidgetLabel"] label,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"] span,
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] label span,
div[data-testid="stCheckbox"] label,
div[data-testid="stCheckbox"] label p,
div[data-testid="stCheckbox"] label span,
.stMarkdown p,
.stMarkdown span {{
    color: {text_main} !important;
}}

div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label {{
    font-weight: 600 !important;
    opacity: 1 !important;
}}

[data-testid="stElementToolbar"] {{
    background-color: {bg_toolbar} !important;
    border: 1px solid {border_card} !important;
    border-radius: 8px !important;
    opacity: 1 !important;
}}

.hero {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 8px;
}}

.brand-mark {{
    width: 48px;
    height: 48px;
    border-radius: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 800;
    color: #ffffff !important;
    background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
    box-shadow: 0 8px 20px rgba(99, 102, 241, 0.40);
}}

.hero-title {{
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.8px;
    line-height: 1.1;
    color: {text_main} !important;
}}

.hero-title .accent {{
    color: {accent} !important;
}}

.hero-sub {{
    font-size: 13px;
    font-weight: 600;
    color: {text_sub} !important;
    margin-top: 2px;
}}

.console-banner {{
    background: {bg_card} !important;
    border: 1px solid {border_card} !important;
    border-radius: 14px;
    padding: 14px 18px 10px;
    margin-bottom: 16px;
    box-shadow: {tile_shadow};
}}

.console-title {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {accent} !important;
    margin-bottom: 8px;
}}

.origin-pill {{
    background: {accent_soft} !important;
    border: 1px solid {border_card} !important;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 700;
    color: {text_main} !important;
    margin-top: 4px;
}}

div[data-baseweb="select"],
div[data-baseweb="select"] * {{
    background-color: {bg_input} !important;
    color: {text_input} !important;
    border-color: {border_input} !important;
}}

div[data-baseweb="select"] svg {{
    fill: {text_input} !important;
    color: {text_input} !important;
}}

div[data-baseweb="popover"],
div[data-baseweb="popover"] *,
div[data-baseweb="menu"],
div[data-baseweb="menu"] li {{
    background-color: {bg_input} !important;
    color: {text_input} !important;
}}

div[data-testid="stNumberInput"] div[data-baseweb="input"],
div[data-testid="stNumberInput"] input {{
    background-color: {bg_input} !important;
    color: {text_input} !important;
    border-color: {border_input} !important;
}}

div[data-testid="stNumberInput"] button,
div[data-testid="stNumberInput"] button svg {{
    color: {text_input} !important;
    fill: {text_input} !important;
}}

div[data-testid="stDeckGlJsonChart"] {{
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid {border_card};
    box-shadow: {tile_shadow};
}}

.left-summary-card {{
    background: {bg_card} !important;
    border: 1px solid {border_card} !important;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: {tile_shadow};
}}

.left-summary-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 10px;
    margin-bottom: 12px;
    border-bottom: 1px solid {border_card};
}}

.left-summary-title {{
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {text_sub} !important;
}}

.left-summary-route {{
    font-size: 12px;
    font-weight: 700;
    color: {accent} !important;
    margin-bottom: 10px;
}}

.left-stat-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid {border_card};
    font-size: 13px;
}}

.left-stat-label {{
    color: {text_sub} !important;
    font-weight: 600;
}}

.left-stat-val {{
    color: {text_main} !important;
    font-weight: 700;
}}

.left-advisory {{
    margin-top: 12px;
    padding-top: 10px;
    font-size: 12.5px;
    line-height: 1.45;
    color: {text_main} !important;
}}

.mitigation-box {{
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    font-size: 12px;
    line-height: 1.45;
    color: {text_main} !important;
}}

.metric-tile {{
    background-color: {bg_card} !important;
    border: 1px solid {border_card} !important;
    border-top: 4px solid {accent};
    border-radius: 14px;
    padding: 14px 16px;
    min-height: 122px;
    box-shadow: {tile_shadow};
    margin-bottom: 12px;
}}

.metric-label {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: {text_sub} !important;
}}

.metric-value {{
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.8px;
    line-height: 1.15;
    margin: 6px 0;
    color: {text_main} !important;
}}

.metric-sub {{
    font-size: 12px;
    font-weight: 600;
    color: {text_sub} !important;
}}

.card-title {{
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: {accent} !important;
    margin-bottom: 10px;
}}

.intel-card {{
    background-color: {bg_card} !important;
    border: 1px solid {border_card} !important;
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
    color: {text_main} !important;
    box-shadow: {tile_shadow};
}}

.intel-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}

.intel-table th {{
    text-align: left;
    padding: 9px 10px;
    color: {text_sub} !important;
    font-size: 11px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    border-bottom: 2px solid {border_card};
}}

.intel-table td {{
    padding: 10px 10px;
    border-bottom: 1px solid {border_card};
    color: {text_main} !important;
}}

.mini-bar {{
    display: inline-block;
    vertical-align: middle;
    width: 72px;
    height: 7px;
    border-radius: 999px;
    background: {border_card};
    margin-left: 8px;
    overflow: hidden;
}}

.mini-bar div {{
    height: 100%;
    border-radius: 999px;
}}

.tag-crit {{
    display: inline-block;
    background: rgba(244, 63, 94, 0.14);
    color: {crit_text} !important;
    border: 1px solid rgba(244, 63, 94, 0.50);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.tag-mod {{
    display: inline-block;
    background: rgba(245, 158, 11, 0.14);
    color: {mod_text} !important;
    border: 1px solid rgba(245, 158, 11, 0.50);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.tag-ok {{
    display: inline-block;
    background: rgba(16, 185, 129, 0.14);
    color: {ok_text} !important;
    border: 1px solid rgba(16, 185, 129, 0.50);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}
</style>
""",
    unsafe_allow_html=True,
)

CRITICAL_THRESHOLD = 65
MODERATE_THRESHOLD = 35

STATUS_STABLE = "STABLE OPTIMAL ROUTE"
STATUS_MODERATE = "MODERATE CAUTION ZONE"
STATUS_CRITICAL = "CRITICAL SLA RISK"

STATUS_COLORS = {
    STATUS_STABLE: ok_text,
    STATUS_MODERATE: mod_text,
    STATUS_CRITICAL: crit_text,
}

STATUS_FILL = {
    STATUS_STABLE: "#10b981",
    STATUS_MODERATE: "#f59e0b",
    STATUS_CRITICAL: "#f43f5e",
}

STATUS_FILL_RGB = {
    STATUS_STABLE: [16, 185, 129],
    STATUS_MODERATE: [245, 158, 11],
    STATUS_CRITICAL: [244, 63, 94],
}

STATUS_TAG_CLASS = {
    STATUS_STABLE: "tag-ok",
    STATUS_MODERATE: "tag-mod",
    STATUS_CRITICAL: "tag-crit",
}

ARC_SOURCE_RGB = [6, 182, 212]
API_URL = os.environ.get("CARGOSENSE_API", "http://127.0.0.1:8000")
METRICS_FILE = Path(__file__).parent / "models" / "metrics.json"


def format_weather_condition(condition_text, precip_mm=0.0, wind_kmh=0.0):
    upper_cond = (condition_text or "").upper()
    if "STORM" in upper_cond or "THUNDER" in upper_cond or (precip_mm >= 24.0 and wind_kmh >= 35.0):
        emoji = "⛈️"
    elif "RAIN" in upper_cond or precip_mm > 5.0:
        emoji = "🌧️"
    elif "CLOUD" in upper_cond or "OVERCAST" in upper_cond:
        emoji = "☁️"
    elif "CLEAR" in upper_cond or "SUN" in upper_cond:
        emoji = "☀️"
    else:
        emoji = "⛅"
    return f"{emoji} {(condition_text or 'Variable').title()}"


@st.cache_data(show_spinner=False)
def load_india_states_geojson():
    url = "https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson"
    try:
        res = requests.get(url, timeout=4.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


@st.cache_data(show_spinner=False)
def load_model_metrics():
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text())
        except Exception:
            return None
    return None


def status_from_risk(total_pct):
    if total_pct >= CRITICAL_THRESHOLD:
        return STATUS_CRITICAL
    if total_pct >= MODERATE_THRESHOLD:
        return STATUS_MODERATE
    return STATUS_STABLE


def validate_inputs(order_quantity, scheduled_shipping_days, sales_per_customer, product_price):
    errors = []
    if order_quantity < 1:
        errors.append("Order quantity must be at least 1.")
    if scheduled_shipping_days < 1:
        errors.append("Scheduled transit days must be at least 1.")
    if sales_per_customer < 0:
        errors.append("Sales per customer (USD) cannot be negative.")
    if product_price < 0:
        errors.append("Product price (USD) cannot be negative.")
    return errors


def get_arrival_weather(hub_record, days):
    return {
        "precip": hub_record["precip"],
        "wind": hub_record["wind"],
        "temp_c": hub_record["temp_c"],
        "condition": hub_record["weather"],
        "forecast_date": datetime.now() + timedelta(days=days),
        "penalty_pct": hub_record["weather_penalty"],
    }


def get_prediction(payload, hub_record):
    """Score via FastAPI /predict when reachable; otherwise fall back cleanly."""
    weather = get_arrival_weather(hub_record, payload["scheduled_shipping_days"])
    body = dict(payload, weather_delay_penalty_pct=weather["penalty_pct"])
    try:
        res = requests.post(f"{API_URL}/predict", json=body, timeout=8)
        res.raise_for_status()
        return dict(res.json(), scored_at=datetime.now().strftime("%H:%M:%S IST"), source="model")
    except requests.RequestException as exc:
        st.warning(f"FastAPI unreachable ({exc.__class__.__name__}); using corridor estimate.")
        total_pct = min(round(hub_record["base_risk"] + weather["penalty_pct"], 1), 100.0)
        return {
            "late_delivery_risk_prob": round(total_pct / 100.0, 4),
            "late_delivery_risk_pred": int(total_pct >= 50),
            "base_risk_pct": round(total_pct - weather["penalty_pct"], 1),
            "weather_delay_penalty_pct": weather["penalty_pct"],
            "status": status_from_risk(total_pct),
            "scored_at": datetime.now().strftime("%H:%M:%S IST"),
            "source": "fallback",
        }


def generate_mitigation_action(active_status, payload, weather_info, active_hub):
    """Generate context-aware dispatch mitigations based on risk level and order parameters."""
    if active_status == STATUS_CRITICAL:
        actions = []
        if payload["shipping_mode"] in ["Standard Class", "Second Class"]:
            actions.append(
                "Divert to <strong>First Class / Air Express</strong> to compress line-haul transit by 24–48 hours."
            )
        if weather_info["precip"] > 15.0 or weather_info["wind"] > 30.0:
            actions.append(
                f"Hold dispatch gate release for <strong>8–12 hours</strong> until severe weather ({format_weather_condition(weather_info['condition'], weather_info['precip'], weather_info['wind'])}) eases."
            )
        if payload["scheduled_shipping_days"] <= 2 and active_hub["dist"] > 1000:
            actions.append(
                f"Expand committed SLA window from {payload['scheduled_shipping_days']}d to <strong>{payload['scheduled_shipping_days'] + 1}d</strong> to absorb corridor friction."
            )
        if payload["sales_per_customer"] * payload["order_quantity"] >= 150:
            actions.append(
                "Flag as <strong>High-Value Priority</strong> for dedicated hub cross-dock bypass."
            )
        if not actions:
            actions.append("Trigger priority lane clearance and alert destination hub operations.")

        return (
            '<div class="mitigation-box" style="border-left: 4px solid #f43f5e; background: rgba(244, 63, 94, 0.12);">'
            '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #fb7185; margin-bottom: 6px;">'
            "🚨 Automated Risk Mitigation Protocol"
            "</div>"
            '<ul style="margin: 0; padding-left: 18px; line-height: 1.5; font-size: 12.5px;">'
            + "".join([f"<li>{action}</li>" for action in actions])
            + "</ul></div>"
        )

    if active_status == STATUS_MODERATE:
        note = "Monitor corridor transit checkpoints. "
        if payload["shipping_mode"] == "Standard Class":
            note += "Evaluate optional upgrade to <strong>Second Class</strong> to protect tight SLA windows."
        else:
            note += "Verify hub loading cutoff times to avoid overnight holdover."

        return (
            '<div class="mitigation-box" style="border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.12);">'
            '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #fbbf24; margin-bottom: 4px;">'
            "⚠️ Cautionary Dispatch Advisory"
            "</div>"
            f'<div style="font-size: 12.5px; line-height: 1.45;">{note}</div>'
            "</div>"
        )

    return (
        '<div class="mitigation-box" style="border-left: 4px solid #10b981; background: rgba(16, 185, 129, 0.10);">'
        '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #34d399; margin-bottom: 4px;">'
        "✅ Clear for Dispatch"
        "</div>"
        '<div style="font-size: 12.5px; line-height: 1.45;">Nominal risk footprint across corridor. Proceed with standard carrier allocation.</div>'
        "</div>"
    )


def metric_tile(label, value_html, sub_html, accent_color):
    return (
        f'<div class="metric-tile" style="border-top-color: {accent_color};">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value_html}</div>'
        f'<div class="metric-sub">{sub_html}</div>'
        "</div>"
    )


# --- HORIZONTAL CARGOSENSE CONSOLE (TOP) ---
state_list = sorted(INDIA_STATES_CITIES.keys())

st.markdown(
    '<div class="console-banner"><div class="console-title">CargoSense Console — Route &amp; Order Controls</div>',
    unsafe_allow_html=True,
)

c_origin, c_state, c_city, c_mode, c_days = st.columns([1.3, 1.4, 1.4, 1.3, 1.3])
with c_origin:
    st.caption("Origin Hub (Default)")
    st.markdown(f'<div class="origin-pill">{ORIGIN_HUB}</div>', unsafe_allow_html=True)

with c_state:
    selected_state = st.selectbox(
        "Destination State",
        options=state_list,
        index=None,
        placeholder="Select destination state",
    )

with c_city:
    if selected_state:
        city_options = [item["city"] for item in INDIA_STATES_CITIES[selected_state]]
        selected_city = st.selectbox(
            "Destination City",
            options=city_options,
            index=None,
            placeholder="Select destination city",
        )
    else:
        selected_city = st.selectbox(
            "Destination City",
            options=[],
            index=None,
            placeholder="Select state first",
            disabled=True,
        )

with c_mode:
    shipping_mode = st.selectbox(
        "Shipping Mode",
        ["Standard Class", "First Class", "Second Class", "Same Day"],
    )

with c_days:
    committed_days = st.slider("Transit Window (Days)", 1, 6, 3)

c_qty, c_sales, c_price, c_arcs, c_view, c_run = st.columns([1.0, 1.2, 1.2, 1.2, 1.5, 1.4])
with c_qty:
    order_quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
with c_sales:
    sales_per_customer = st.number_input("Sales (USD)", min_value=0.0, value=50.0, step=1.0)
with c_price:
    product_price = st.number_input("Price (USD)", min_value=0.0, value=10.0, step=1.0)
with c_arcs:
    st.write("")
    show_secondary = st.checkbox("All Corridor Arcs", value=False)
with c_view:
    nav_choice = st.selectbox(
        "Workspace View",
        ["Pre-Dispatch Risk Simulator", "Network Corridor Intelligence"],
    )
with c_run:
    st.write("")
    run_clicked = st.button("Run Risk Assessment", type="primary", use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

active_hub = (
    get_hub_record(selected_state, selected_city)
    if (selected_state and selected_city)
    else None
)

if run_clicked:
    if not selected_state or not selected_city or not active_hub:
        st.warning("Please choose both a Destination State and Destination City first.")
    else:
        current_payload = {
            "order_quantity": int(order_quantity),
            "sales_per_customer": float(sales_per_customer),
            "product_price": float(product_price),
            "shipping_mode": shipping_mode,
            "scheduled_shipping_days": int(committed_days),
            "destination_city": active_hub["city"],
            "origin_hub": ORIGIN_HUB,
        }
        input_errors = validate_inputs(
            current_payload["order_quantity"],
            current_payload["scheduled_shipping_days"],
            current_payload["sales_per_customer"],
            current_payload["product_price"],
        )
        if input_errors:
            for err_msg in input_errors:
                st.error(err_msg)
        else:
            st.session_state["prediction"] = {
                "payload": current_payload,
                "result": get_prediction(current_payload, active_hub),
            }


def build_clean_map_deck(all_records, active_hub=None, active_status=None, is_scored=False):
    arc_data = []
    if active_hub is not None:
        for rec in all_records:
            is_active = (
                rec["state"] == active_hub["state"] and rec["city"] == active_hub["city"]
            )
            if not is_active and not show_secondary:
                continue
            if is_active:
                status_rgb = STATUS_FILL_RGB[active_status]
                core_source = ARC_SOURCE_RGB + [255]
                core_target = status_rgb + [255]
                glow_source = ARC_SOURCE_RGB + [70]
                glow_target = status_rgb + [70]
                core_w = 5.0
                glow_w = 13.0
            else:
                core_source = arc_inactive_color
                core_target = arc_inactive_color
                glow_source = [0, 0, 0, 0]
                glow_target = [0, 0, 0, 0]
                core_w = 1.1
                glow_w = 1.1

            arc_data.append(
                {
                    "from_lon": DELHI_HQ_COORDS[0],
                    "from_lat": DELHI_HQ_COORDS[1],
                    "to_lon": rec["coords"][0],
                    "to_lat": rec["coords"][1],
                    "core_source": core_source,
                    "core_target": core_target,
                    "glow_source": glow_source,
                    "glow_target": glow_target,
                    "core_width": core_w,
                    "glow_width": glow_w,
                }
            )
    df_arcs = pd.DataFrame(arc_data)

    pins_data = []
    primary_labels = []
    secondary_labels = []

    for rec in all_records:
        is_active = (
            active_hub is not None
            and rec["state"] == active_hub["state"]
            and rec["city"] == active_hub["city"]
        )
        is_crit = is_active and is_scored and (active_status == STATUS_CRITICAL)
        if is_crit:
            icon_url = CRITICAL_WARN_PIN_URI
            icon_size = 44
        elif is_active:
            icon_url = GLASS_3D_PIN_URI
            icon_size = 42
        else:
            icon_url = GREY_PIN_URI
            icon_size = 24

        pins_data.append(
            {
                "name": f"{rec['city']} ({rec['state']})",
                "lon": rec["coords"][0],
                "lat": rec["coords"][1],
                "icon_url": icon_url,
                "icon_size": icon_size,
            }
        )

        if is_active:
            primary_labels.append(
                {
                    "text": f"{rec['city']}, {rec['state']}",
                    "lon": rec["coords"][0],
                    "lat": rec["coords"][1],
                    "offset": rec.get("label_pos", [0, -28]),
                }
            )
        elif show_secondary:
            secondary_labels.append(
                {
                    "text": rec["city"],
                    "lon": rec["coords"][0],
                    "lat": rec["coords"][1],
                    "offset": [0, 14],
                }
            )

    pins_data.append(
        {
            "name": ORIGIN_HUB,
            "lon": DELHI_HQ_COORDS[0],
            "lat": DELHI_HQ_COORDS[1],
            "icon_url": GLASS_3D_PIN_URI,
            "icon_size": 38,
        }
    )
    primary_labels.append(
        {
            "text": "Delhi HQ",
            "lon": DELHI_HQ_COORDS[0],
            "lat": DELHI_HQ_COORDS[1],
            "offset": [0, -28],
        }
    )

    layers = []
    states_geojson = load_india_states_geojson()
    if states_geojson:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=states_geojson,
                filled=False,
                stroked=True,
                get_line_color=state_border_color,
                line_width_min_pixels=1.3,
            )
        )

    if not df_arcs.empty:
        layers.append(
            pdk.Layer(
                "ArcLayer",
                data=df_arcs,
                get_source_position=["from_lon", "from_lat"],
                get_target_position=["to_lon", "to_lat"],
                get_source_color="glow_source",
                get_target_color="glow_target",
                get_width="glow_width",
            )
        )
        layers.append(
            pdk.Layer(
                "ArcLayer",
                data=df_arcs,
                get_source_position=["from_lon", "from_lat"],
                get_target_position=["to_lon", "to_lat"],
                get_source_color="core_source",
                get_target_color="core_target",
                get_width="core_width",
                auto_highlight=True,
            )
        )

    layers.append(
        pdk.Layer(
            "IconLayer",
            data=pd.DataFrame(pins_data),
            get_icon={
                "url": "icon_url",
                "width": 58,
                "height": 72,
                "anchorY": 72,
            },
            get_position=["lon", "lat"],
            get_size="icon_size",
            size_units="pixels",
            pickable=True,
        )
    )

    if active_hub is not None and is_scored and active_status == STATUS_CRITICAL:
        sonar_data = pd.DataFrame(
            [
                {
                    "lon": active_hub["coords"][0],
                    "lat": active_hub["coords"][1],
                    "radius": 68000,
                    "color": [244, 63, 94, 235],
                },
                {
                    "lon": active_hub["coords"][0],
                    "lat": active_hub["coords"][1],
                    "radius": 108000,
                    "color": [244, 63, 94, 120],
                },
            ]
        )
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=sonar_data,
                get_position=["lon", "lat"],
                get_color="color",
                get_radius="radius",
                stroked=True,
                filled=False,
                line_width_min_pixels=2.5,
            )
        )

    if secondary_labels:
        layers.append(
            pdk.Layer(
                "TextLayer",
                data=pd.DataFrame(secondary_labels),
                get_position=["lon", "lat"],
                get_text="text",
                get_color=secondary_label_color,
                get_size=10,
                get_pixel_offset="offset",
                background=True,
                get_background_color=[20, 27, 59, 175] if theme_mode != "Light Mode" else [255, 255, 255, 200],
                get_border_color=[0, 0, 0, 0],
            )
        )

    layers.append(
        pdk.Layer(
            "TextLayer",
            data=pd.DataFrame(primary_labels),
            get_position=["lon", "lat"],
            get_text="text",
            get_color=pin_label_color,
            get_size=13,
            get_pixel_offset="offset",
            background=True,
            get_background_color=[20, 27, 59, 215] if theme_mode != "Light Mode" else [255, 255, 255, 230],
            get_border_color=state_border_color,
            get_border_width=1,
        )
    )

    view_state = pdk.ViewState(
        latitude=21.5,
        longitude=80.0,
        zoom=4.25,
        pitch=34,
        bearing=0,
    )

    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style=map_style_choice,
        tooltip={"text": "{name}"},
    )


def render_corridor_intelligence(committed_days):
    corridor_stats = []
    for rec in get_all_city_records():
        city_weather = get_arrival_weather(rec, committed_days)
        city_total_pct = min(round(rec["base_risk"] + city_weather["penalty_pct"], 1), 100.0)
        corridor_stats.append(
            {
                "state": rec["state"],
                "city": rec["city"],
                "dist": rec["dist"],
                "weather": city_weather,
                "total_pct": city_total_pct,
                "status": status_from_risk(city_total_pct),
            }
        )

    flagged_cities = [
        f"{row['city']} ({row['state']})"
        for row in corridor_stats
        if row["status"] == STATUS_CRITICAL
    ]
    avg_total_pct = sum(r["total_pct"] for r in corridor_stats) / max(len(corridor_stats), 1)
    avg_status = status_from_risk(avg_total_pct)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            metric_tile("Tracked Hubs", str(len(corridor_stats)), "Across all 28 Indian states", accent),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            metric_tile(
                "Critical Bottlenecks",
                f'<span style="color: {STATUS_COLORS[STATUS_CRITICAL]};">{len(flagged_cities)}</span>',
                f"{len(flagged_cities)} high-risk hubs",
                STATUS_FILL[STATUS_CRITICAL],
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            metric_tile(
                "Avg Corridor Risk",
                f'<span style="color: {STATUS_COLORS[avg_status]};">{avg_total_pct:.1f}%</span>',
                "Base risk + weather penalty",
                STATUS_FILL[avg_status],
            ),
            unsafe_allow_html=True,
        )

    rows_html = ""
    for row in corridor_stats[:20]:
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
            f"<td><strong>Delhi HQ → {row['city']}</strong> <span style='color:{text_sub};'>({row['state']})</span></td>"
            f"<td>{row['dist']:,.0f} KM</td>"
            f"<td>{cond_label}</td>"
            f"<td>{risk_cell}</td>"
            f"<td>{tag}</td>"
            f"</tr>"
        )

    st.markdown(
        f'<div class="intel-card">'
        f'<div class="card-title">28-State Corridor Telemetry Snapshot (Top 20 Hubs)</div>'
        f'<table class="intel-table">'
        f"<thead><tr><th>Corridor</th><th>Distance</th><th>Condition</th><th>Risk</th><th>Status</th></tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )

    metrics_data = load_model_metrics()
    if metrics_data:
        roc_auc = metrics_data.get("roc_auc", 0.0)
        precision = metrics_data.get("precision", 0.0)
        recall = metrics_data.get("recall", 0.0)
        f1 = metrics_data.get("f1", 0.0)
        best_iter = metrics_data.get("best_iteration", "N/A")
        top_features = metrics_data.get("top_importances", {})

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.markdown(
                metric_tile("ROC-AUC Score", f"{roc_auc:.3f}", "Test split cross-validated", accent),
                unsafe_allow_html=True,
            )
        with m_col2:
            st.markdown(
                metric_tile("Precision", f"{precision * 100:.1f}%", "Flagged breach accuracy", ok_text),
                unsafe_allow_html=True,
            )
        with m_col3:
            st.markdown(
                metric_tile("Recall", f"{recall * 100:.1f}%", "Late risk capture rate", mod_text),
                unsafe_allow_html=True,
            )
        with m_col4:
            st.markdown(
                metric_tile("F1 Score", f"{f1:.3f}", f"Optimal trees: {best_iter}", crit_text),
                unsafe_allow_html=True,
            )

        if top_features:
            feature_rows = ""
            for feat, weight in list(top_features.items())[:5]:
                pct = weight * 100.0
                feature_rows += (
                    f"<tr>"
                    f"<td><strong>{feat}</strong></td>"
                    f"<td>{pct:.1f}%</td>"
                    f"<td><span class='mini-bar' style='width:160px;'>"
                    f"<div style='width:{min(pct, 100.0)}%; background:{accent};'></div>"
                    f"</span></td>"
                    f"</tr>"
                )

            st.markdown(
                f'<div class="intel-card">'
                f'<div class="card-title">XGBoost Top Predictive Feature Weights</div>'
                f'<table class="intel-table">'
                f"<thead><tr><th>Feature</th><th>Weight</th><th>Relative Influence</th></tr></thead>"
                f"<tbody>{feature_rows}</tbody>"
                f"</table></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("XGBoost classifier artifacts loaded via FastAPI /predict endpoint.")


# --- LEFT COLUMN (SUMMARY) + RIGHT COLUMN (MAP / CORRIDOR INTEL) ---
left_col, right_col = st.columns([1.15, 2.35], gap="medium")

if not active_hub:
    with left_col:
        st.markdown(
            f"""
            <div class="left-summary-card">
                <div class="left-summary-head">
                    <span class="left-summary-title">Shipment Risk Summary</span>
                    <span class="tag-mod">Awaiting Corridor</span>
                </div>
                <div class="left-summary-route" style="color: {text_sub};">
                    From {ORIGIN_HUB} → Select Destination
                </div>
                <p style="font-size: 13px; color: {text_sub}; line-height: 1.6; margin-top: 10px;">
                    Select a <strong>Destination State</strong> and <strong>Destination City</strong> from the console above to inspect route distance and weather conditions, then click <strong>Run Risk Assessment</strong> to score the order.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        if nav_choice == "Pre-Dispatch Risk Simulator":
            deck = build_clean_map_deck(get_all_city_records())
            st.pydeck_chart(deck, width="stretch", height=540)
        else:
            render_corridor_intelligence(committed_days)

else:
    active_weather = get_arrival_weather(active_hub, committed_days)

    expected_payload = {
        "order_quantity": int(order_quantity),
        "sales_per_customer": float(sales_per_customer),
        "product_price": float(product_price),
        "shipping_mode": shipping_mode,
        "scheduled_shipping_days": int(committed_days),
        "destination_city": active_hub["city"],
        "origin_hub": ORIGIN_HUB,
    }

    stored_prediction = st.session_state.get("prediction")
    prediction = (
        stored_prediction["result"]
        if (stored_prediction and stored_prediction.get("payload") == expected_payload)
        else None
    )

    weather_pct = (
        prediction["weather_delay_penalty_pct"]
        if prediction
        else active_weather["penalty_pct"]
    )

    if prediction:
        active_total_pct = round(prediction["late_delivery_risk_prob"] * 100.0, 1)
        base_pct_val = round(prediction["base_risk_pct"], 1)
        active_status = status_from_risk(active_total_pct)
        total_display = f"{active_total_pct:.1f}%"
        base_display = f"{base_pct_val:.1f}%"
        total_color = STATUS_COLORS[active_status]
        status_badge = f'<span class="{STATUS_TAG_CLASS[active_status]}">{active_status}</span>'
        score_note = f"Scored via API at {prediction.get('scored_at', 'now')}"
    else:
        active_status = status_from_risk(
            min(round(active_hub["base_risk"] + weather_pct, 1), 100.0)
        )
        total_display = "Pending"
        base_display = "Pending"
        total_color = text_sub
        status_badge = '<span class="tag-mod">READY TO SCORE</span>'
        score_note = "Corridor preview loaded — click Run Risk Assessment to score"

    forecast_date_text = active_weather["forecast_date"].strftime("%d %b %Y")
    weather_display = format_weather_condition(
        active_weather["condition"], active_weather["precip"], active_weather["wind"]
    )

    mitigation_html = (
        generate_mitigation_action(active_status, expected_payload, active_weather, active_hub)
        if prediction
        else (
            f'<div class="mitigation-box" style="border-left: 4px solid {accent}; background: {accent_soft};">'
            f'<div style="font-size: 12px; color: {text_main};">'
            "💡 <em>Click <strong>Run Risk Assessment</strong> to generate dynamic mitigation suggestions.</em>"
            "</div></div>"
        )
    )

    with left_col:
        st.markdown(
            f"""
            <div class="left-summary-card">
                <div class="left-summary-head">
                    <span class="left-summary-title">Shipment Risk Summary</span>
                    {status_badge}
                </div>
                <div class="left-summary-route">
                    Delhi HQ → {active_hub["city"]}, {active_hub["state"]} · {committed_days}d window
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">ML Total Risk</span>
                    <span class="left-stat-val" style="color: {total_color};">{total_display}</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">ML Base Risk</span>
                    <span class="left-stat-val">{base_display}</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Weather Penalty</span>
                    <span class="left-stat-val" style="color: {crit_text if weather_pct > 0 else text_main};">+{weather_pct:.1f}%</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Route Distance</span>
                    <span class="left-stat-val">{active_hub["dist"]:,.0f} km</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Shipping Mode</span>
                    <span class="left-stat-val">{shipping_mode}</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Conditions</span>
                    <span class="left-stat-val">{weather_display}</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Rainfall / Wind</span>
                    <span class="left-stat-val">{active_weather["precip"]} mm · {active_weather["wind"]} km/h</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Temperature</span>
                    <span class="left-stat-val">{active_weather["temp_c"]} °C</span>
                </div>
                <div class="left-stat-row">
                    <span class="left-stat-label">Est. Arrival</span>
                    <span class="left-stat-val">{forecast_date_text}</span>
                </div>
                <div class="left-advisory">
                    <strong>{score_note}:</strong><br/>
                    {active_hub["advisory"]}
                </div>
                {mitigation_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        if nav_choice == "Pre-Dispatch Risk Simulator":
            deck = build_clean_map_deck(
                get_all_city_records(),
                active_hub=active_hub,
                active_status=active_status,
                is_scored=prediction is not None,
            )
            st.pydeck_chart(deck, width="stretch", height=540)
        else:
            render_corridor_intelligence(committed_days)
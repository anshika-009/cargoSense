"""CargoSense Streamlit dashboard: pre-dispatch late-delivery risk simulation and network corridor intelligence."""

import base64
import os
from datetime import datetime, timedelta

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(
    page_title="CargoSense — 3D Telemetry & Route Analysis",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


def svg_to_data_uri(svg_text: str) -> str:
    encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{encoded}"


GREY_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 48 60">'
    '<path d="M24 3 C12.4 3 3 12.2 3 23.6 C3 39.2 24 57 24 57 C24 57 45 39.2 45 23.6 '
    'C45 12.2 35.6 3 24 3 Z" fill="#64748b" stroke="#e2e8f0" stroke-width="2.5"/>'
    '<circle cx="24" cy="23" r="8" fill="#f1f5f9" stroke="#475569" stroke-width="2"/>'
    '</svg>'
)

GLASS_3D_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 56 70">'
    '<defs>'
    '<linearGradient id="glassGrad" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#a5f3fc" stop-opacity="0.98"/>'
    '<stop offset="55%" stop-color="#6366f1" stop-opacity="0.95"/>'
    '<stop offset="100%" stop-color="#3730a3" stop-opacity="0.98"/>'
    '</linearGradient>'
    '</defs>'
    '<path d="M28 4 C14.7 4 4 14.5 4 27.5 C4 45.5 28 66 28 66 C28 66 52 45.5 52 27.5 '
    'C52 14.5 41.3 4 28 4 Z" fill="url(#glassGrad)" stroke="#e0e7ff" stroke-width="2.8"/>'
    '<ellipse cx="21" cy="17" rx="6" ry="3.5" transform="rotate(-25 21 17)" fill="#ffffff" opacity="0.65"/>'
    '<circle cx="28" cy="27" r="8.5" fill="#eef2ff" stroke="#4338ca" stroke-width="2.2"/>'
    '</svg>'
)

CRITICAL_WARN_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 58 72">'
    '<defs>'
    '<linearGradient id="warnPinGrad" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#fda4af"/>'
    '<stop offset="55%" stop-color="#e11d48"/>'
    '<stop offset="100%" stop-color="#881337"/>'
    '</linearGradient>'
    '</defs>'
    '<path d="M29 4 C15.2 4 4 14.9 4 28.3 C4 46.8 29 68 29 68 C29 68 54 46.8 54 28.3 '
    'C54 14.9 42.8 4 29 4 Z" fill="url(#warnPinGrad)" stroke="#ffe4e6" stroke-width="2.8"/>'
    '<polygon points="29,15 41,36 17,36" fill="#fff7ed" stroke="#fed7aa" stroke-width="1.8" stroke-linejoin="round"/>'
    '<rect x="27.7" y="21" width="2.6" height="8" rx="1" fill="#be123c"/>'
    '<circle cx="29" cy="32.3" r="1.5" fill="#be123c"/>'
    '</svg>'
)

top_col1, top_col2 = st.columns([4, 1.3])

with top_col1:
    st.markdown(
        """
        <div class="hero">
            <div class="brand-mark">⚡</div>
            <div>
                <div class="hero-title">Cargo<span class="accent">Sense</span></div>
                <div class="hero-sub">3D dynamic arc telemetry &amp; route analysis</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with top_col2:
    theme_mode = st.radio(
        "Display Theme",
        ["Dark Mode", "Light Mode"],
        index=1,
        horizontal=True,
        label_visibility="collapsed"
    )

sidebar_text = "#e8ebff"
sidebar_sub = "#a9b3e0"

if theme_mode == "Light Mode":
    bg_app = "#f2f4fb"
    bg_header = "#f2f4fb"
    bg_sidebar = "#171b45"
    bg_card = "#ffffff"
    bg_toolbar = "#e6e9f6"
    bg_input = "#ffffff"
    text_input = "#000000"
    border_input = "#8b93c4"
    border_card = "#dde1f0"
    text_main = "#14172e"
    text_sub = "#5a6183"
    chip_bg = "rgba(255, 255, 255, 0.10)"
    chip_color = "#c7d2fe"
    grid_line = "rgba(79, 70, 229, 0.05)"
    accent = "#5b5bf0"
    accent_soft = "rgba(91, 91, 240, 0.12)"
    ok_text = "#047857"
    mod_text = "#b45309"
    crit_text = "#be123c"
    tile_shadow = "0 8px 22px rgba(40, 50, 120, 0.10)"
    map_style_choice = pdk.map_styles.CARTO_LIGHT
    arc_inactive_color = [100, 116, 139, 110]
    pin_label_color = [20, 23, 46, 255]
    state_border_color = [91, 100, 150, 170]
else:
    bg_app = "#0a0f24"
    bg_header = "#0a0f24"
    bg_sidebar = "#0d1330"
    bg_card = "#141b3b"
    bg_toolbar = "#1b2450"
    bg_input = "#000000"
    text_input = "#ffffff"
    border_input = "#4a5590"
    border_card = "#2a3566"
    text_main = "#eef1ff"
    text_sub = "#9aa6d1"
    chip_bg = "rgba(255, 255, 255, 0.08)"
    chip_color = "#a5b4fc"
    grid_line = "rgba(129, 140, 248, 0.05)"
    accent = "#818cf8"
    accent_soft = "rgba(129, 140, 248, 0.16)"
    ok_text = "#34d399"
    mod_text = "#fbbf24"
    crit_text = "#fb7185"
    tile_shadow = "0 10px 26px rgba(0, 0, 0, 0.35)"
    map_style_choice = pdk.map_styles.CARTO_DARK
    arc_inactive_color = [148, 163, 184, 110]
    pin_label_color = [238, 241, 255, 255]
    state_border_color = [129, 140, 248, 140]

st.markdown(f"""
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
padding-top: 2.2rem !important;
max-width: 1500px !important;
}}

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {{
background-color: {bg_header} !important;
color: {text_main} !important;
}}

header[data-testid="stHeader"] a,
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] span,
[data-testid="stToolbar"] button,
[data-testid="stToolbar"] span {{
color: {text_main} !important;
}}

[data-testid="stElementToolbar"] {{
background-color: {bg_toolbar} !important;
border: 1px solid {border_card} !important;
border-radius: 8px !important;
opacity: 1 !important;
}}

[data-testid="stElementToolbar"] button,
[data-testid="stElementToolbar"] svg {{
color: {text_main} !important;
fill: {text_main} !important;
}}

.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label, .stApp span {{
color: {text_main};
}}

div[data-testid="stRadio"] label,
div[data-testid="stRadio"] span,
div[data-testid="stRadio"] p {{
color: {text_main} !important;
font-weight: 600 !important;
}}

.hero {{
display: flex;
align-items: center;
gap: 16px;
}}

.brand-mark {{
width: 52px;
height: 52px;
border-radius: 14px;
display: flex;
align-items: center;
justify-content: center;
font-size: 26px;
background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
box-shadow: 0 8px 20px rgba(99, 102, 241, 0.40);
}}

.hero-title {{
font-size: 32px;
font-weight: 800;
letter-spacing: -0.8px;
line-height: 1.1;
color: {text_main};
}}

.hero-title .accent {{
color: {accent} !important;
}}

.hero-sub {{
font-size: 14px;
font-weight: 600;
color: {text_sub};
margin-top: 2px;
}}

section[data-testid="stSidebar"] {{
background-color: {bg_sidebar} !important;
border-right: 1px solid {border_card} !important;
padding-top: 1rem;
}}

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] li {{
color: {sidebar_text} !important;
}}

section[data-testid="stSidebar"] hr {{
border-color: rgba(255, 255, 255, 0.14) !important;
}}

section[data-testid="stSidebar"] [role="slider"] {{
background-color: {accent} !important;
box-shadow: 0 0 0 4px {accent_soft} !important;
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
background-color: {bg_input} !important;
color: {text_input} !important;
fill: {text_input} !important;
border-color: {border_input} !important;
}}

.sidebar-panel {{
background-color: rgba(255, 255, 255, 0.07) !important;
border: 1px solid rgba(255, 255, 255, 0.16) !important;
border-radius: 14px;
padding: 14px 16px;
margin-bottom: 12px;
color: {sidebar_text} !important;
}}

.chip-tag {{
background-color: {chip_bg} !important;
border: 1px solid rgba(255, 255, 255, 0.22) !important;
color: {chip_color} !important;
padding: 3px 9px;
border-radius: 999px;
font-size: 12px;
font-weight: 700;
}}

section[data-testid="stSidebar"] div.stButton > button,
section[data-testid="stSidebar"] div.stButton > button * {{
background: transparent !important;
color: #ffffff !important;
}}

section[data-testid="stSidebar"] div.stButton > button {{
background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%) !important;
color: #ffffff !important;
font-weight: 800 !important;
font-size: 15px !important;
border: 0 !important;
border-radius: 12px !important;
padding: 13px 18px !important;
width: 100% !important;
box-shadow: 0 10px 24px rgba(99, 102, 241, 0.45), inset 0 1px 2px rgba(255, 255, 255, 0.45) !important;
transition: all 0.16s ease-in-out !important;
}}

section[data-testid="stSidebar"] div.stButton > button:hover {{
transform: translateY(-2px);
box-shadow: 0 14px 30px rgba(99, 102, 241, 0.60), inset 0 1px 2px rgba(255, 255, 255, 0.55) !important;
}}

div[data-testid="stDeckGlJsonChart"] {{
border-radius: 18px;
overflow: hidden;
border: 1px solid {border_card};
box-shadow: {tile_shadow};
margin-bottom: 12px;
}}

.metric-tile {{
background-color: {bg_card};
border: 1px solid {border_card};
border-top: 4px solid {accent};
border-radius: 16px;
padding: 16px 18px;
min-height: 140px;
box-shadow: {tile_shadow};
margin-bottom: 14px;
}}

.metric-label {{
font-size: 11px;
font-weight: 800;
letter-spacing: 1.2px;
text-transform: uppercase;
color: {text_sub} !important;
}}

.metric-value {{
font-size: 36px;
font-weight: 800;
letter-spacing: -1px;
line-height: 1.15;
margin: 6px 0 6px 0;
color: {text_main};
}}

.metric-sub {{
font-size: 12px;
font-weight: 600;
color: {text_sub} !important;
line-height: 1.4;
}}

.split-bar {{
display: flex;
height: 8px;
width: 100%;
border-radius: 999px;
overflow: hidden;
background: {border_card};
margin-bottom: 6px;
}}

.legend-dot {{
display: inline-block;
width: 8px;
height: 8px;
border-radius: 50%;
margin: 0 4px 0 0;
}}

.overlay-sub {{
font-size: 11px;
color: {text_sub} !important;
font-weight: 600;
}}

.overlay-val {{
font-size: 18px;
font-weight: 800;
color: {text_main} !important;
margin-top: 2px;
}}

.card-title {{
font-size: 12px;
font-weight: 800;
letter-spacing: 1.2px;
text-transform: uppercase;
color: {accent} !important;
margin-bottom: 10px;
}}

.hazard-stripe-bar {{
height: 10px;
width: 100%;
background: repeating-linear-gradient(
-55deg,
#f43f5e 0px,
#f43f5e 10px,
#1e1b4b 10px,
#1e1b4b 20px
);
border-radius: 5px;
margin-bottom: 12px;
}}

.btn-3d-red {{
display: block;
width: 100%;
text-align: center;
background: linear-gradient(135deg, #fb7185 0%, #e11d48 100%);
color: #ffffff !important;
font-weight: 800;
font-size: 14px;
padding: 11px 14px;
border-radius: 10px;
box-shadow: 0 8px 18px rgba(225, 29, 72, 0.40), inset 0 1px 2px rgba(255, 255, 255, 0.45);
cursor: pointer;
text-decoration: none;
margin-top: 12px;
}}

.storm-badge {{
display: flex;
align-items: center;
gap: 10px;
background: {accent_soft};
padding: 7px 12px;
border-radius: 12px;
border: 1px solid {border_card};
margin-bottom: 4px;
}}

.intel-card {{
background-color: {bg_card} !important;
border: 1px solid {border_card} !important;
border-radius: 16px;
padding: 18px 20px;
margin-bottom: 14px;
color: {text_main} !important;
box-shadow: {tile_shadow};
}}

.intel-table {{
width: 100%;
border-collapse: collapse;
font-size: 14px;
}}

.intel-table th {{
text-align: left;
padding: 10px 12px;
color: {text_sub};
font-size: 11px;
letter-spacing: 1px;
text-transform: uppercase;
border-bottom: 2px solid {border_card};
}}

.intel-table td {{
padding: 13px 12px;
border-bottom: 1px solid {border_card};
color: {text_main};
}}

.intel-table tbody tr:nth-child(even) {{
background-color: {accent_soft};
}}

.mini-bar {{
display: inline-block;
vertical-align: middle;
width: 90px;
height: 8px;
border-radius: 999px;
background: {border_card};
margin-left: 10px;
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
padding: 3px 11px;
border-radius: 999px;
font-size: 11px;
font-weight: 800;
}}

.tag-mod {{
display: inline-block;
background: rgba(245, 158, 11, 0.14);
color: {mod_text} !important;
border: 1px solid rgba(245, 158, 11, 0.50);
padding: 3px 11px;
border-radius: 999px;
font-size: 11px;
font-weight: 800;
}}

.tag-ok {{
display: inline-block;
background: rgba(16, 185, 129, 0.14);
color: {ok_text} !important;
border: 1px solid rgba(16, 185, 129, 0.50);
padding: 3px 11px;
border-radius: 999px;
font-size: 11px;
font-weight: 800;
}}
</style>
""", unsafe_allow_html=True)

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

WEATHER_FILL = "#f59e0b"
ROUTE_FILL = "#06b6d4"
ARC_SOURCE_RGB = [6, 182, 212]

ORIGIN_HUB = "Delhi Hub (North HQ)"
RUN_PROMPT = "Press Run Multi-Factor Risk Simulation to score this order."
DELHI_HQ = [77.1025, 28.7041]

INDIAN_HUBS = {
    "Chennai": {
        "coords": [80.2707, 13.0827],
        "state": "Tamil Nadu",
        "dist": 1760.0,
        "base_risk": 75.5,
        "weather_penalty": 12.5,
        "weather": "HEAVY RAIN",
        "temp_c": 26.5,
        "precip": 24.5,
        "wind": 42.0,
        "label_pos": [54, 4],
        "advisory": "Heavy precipitation on ETA window over the Eastern corridor. Divert to First Class or delay gate departure by 12 hours."
    },
    "Mumbai": {
        "coords": [72.8777, 19.0760],
        "state": "Maharashtra",
        "dist": 1150.0,
        "base_risk": 12.0,
        "weather_penalty": 0.0,
        "weather": "CLEAR SKY",
        "temp_c": 31.0,
        "precip": 0.0,
        "wind": 14.0,
        "label_pos": [-74, -8],
        "advisory": "Standard clearance verified. Transit window compliant with minimal atmospheric friction."
    },
    "Bengaluru": {
        "coords": [77.5946, 12.9716],
        "state": "Karnataka",
        "dist": 1740.0,
        "base_risk": 30.0,
        "weather_penalty": 5.0,
        "weather": "SCATTERED RAIN",
        "temp_c": 23.0,
        "precip": 6.2,
        "wind": 21.0,
        "label_pos": [-66, 4],
        "advisory": "Scattered showers along corridor. Priority lane clearance advised."
    },
    "Kolkata": {
        "coords": [88.3639, 22.5726],
        "state": "West Bengal",
        "dist": 1305.0,
        "base_risk": 15.5,
        "weather_penalty": 2.5,
        "weather": "LIGHT OVERCAST",
        "temp_c": 28.0,
        "precip": 1.0,
        "wind": 11.0,
        "label_pos": [52, 0],
        "advisory": "Standard flight transit cleared. Minimal humidity impediment."
    },
    "Jaipur": {
        "coords": [75.7873, 26.9124],
        "state": "Rajasthan",
        "dist": 280.0,
        "base_risk": 8.0,
        "weather_penalty": 0.0,
        "weather": "CLEAR & DRY",
        "temp_c": 27.5,
        "precip": 0.0,
        "wind": 8.0,
        "label_pos": [-50, -6],
        "advisory": "Optimal transit parameters confirmed."
    }
}


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


def get_arrival_weather(city, days):
    hub = INDIAN_HUBS[city]
    return {
        "precip": hub["precip"],
        "wind": hub["wind"],
        "temp_c": hub["temp_c"],
        "condition": hub["weather"],
        "forecast_date": datetime.now() + timedelta(days=days),
        "penalty_pct": hub["weather_penalty"],
    }


API_URL = os.environ.get("CARGOSENSE_API", "http://127.0.0.1:8000")


def get_prediction(payload):
    """Score through the FastAPI model service; fall back to the hub table if it is down."""
    city = payload["destination_city"]
    weather = get_arrival_weather(city, payload["scheduled_shipping_days"])
    body = dict(payload, weather_delay_penalty_pct=weather["penalty_pct"])
    try:
        res = requests.post(f"{API_URL}/predict", json=body, timeout=8)
        res.raise_for_status()
        return dict(res.json(), source="model")
    except requests.RequestException as exc:
        st.warning(f"Model API unreachable ({exc.__class__.__name__}). Showing the static corridor estimate instead.")
        total_pct = min(round(INDIAN_HUBS[city]["base_risk"] + weather["penalty_pct"], 1), 100.0)
        return {
            "late_delivery_risk_prob": round(total_pct / 100, 4),
            "late_delivery_risk_pred": int(total_pct >= 50),
            "base_risk_pct": round(total_pct - weather["penalty_pct"], 1),
            "weather_delay_penalty_pct": weather["penalty_pct"],
            "status": status_from_risk(total_pct),
            "source": "fallback",
        }


def metric_tile(label, value_html, sub_html, accent_color):
    return (
        f'<div class="metric-tile" style="border-top-color: {accent_color};">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value_html}</div>'
        f'<div class="metric-sub">{sub_html}</div>'
        '</div>'
    )


st.sidebar.markdown("### 🧭 CargoSense Console")
nav_choice = st.sidebar.radio(
    "Navigation View",
    ["Pre-Dispatch Risk Simulator", "Network Corridor Intelligence"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown("#### 3D CORRIDOR INSPECTOR")
destination = st.sidebar.selectbox("Inspect Active Corridor", list(INDIAN_HUBS.keys()), index=0)
shipping_mode = st.sidebar.selectbox("Shipping Mode", ["Standard Class", "First Class", "Second Class", "Same Day"])
committed_days = st.sidebar.slider("Committed Transit Window (Days)", 1, 6, 3)

st.sidebar.markdown("#### ORDER DETAILS")
order_quantity = st.sidebar.number_input("Order Quantity", min_value=1, value=1, step=1)
sales_per_customer = st.sidebar.number_input("Sales per Customer (USD)", min_value=0.0, value=50.0, step=1.0)
product_price = st.sidebar.number_input("Product Price (USD)", min_value=0.0, value=10.0, step=1.0)

show_secondary = st.sidebar.checkbox("Show Secondary Route Arcs", value=True)
run_clicked = st.sidebar.button("⚡ Run Multi-Factor Risk Simulation")

active_hub = INDIAN_HUBS[destination]
active_weather = get_arrival_weather(destination, committed_days)

current_payload = {
    "order_quantity": int(order_quantity),
    "sales_per_customer": float(sales_per_customer),
    "product_price": float(product_price),
    "shipping_mode": shipping_mode,
    "scheduled_shipping_days": int(committed_days),
    "destination_city": destination,
    "origin_hub": ORIGIN_HUB,
}

if run_clicked:
    input_errors = validate_inputs(
        current_payload["order_quantity"],
        current_payload["scheduled_shipping_days"],
        current_payload["sales_per_customer"],
        current_payload["product_price"],
    )
    if input_errors:
        for error_message in input_errors:
            st.error(error_message)
    else:
        st.session_state["prediction"] = {
            "payload": current_payload,
            "result": get_prediction(current_payload),
        }

stored_prediction = st.session_state.get("prediction")
prediction = stored_prediction["result"] if stored_prediction and stored_prediction["payload"] == current_payload else None

if prediction:
    active_total_pct = round(prediction["late_delivery_risk_prob"] * 100, 1)
else:
    active_total_pct = round(active_hub["base_risk"] + active_weather["penalty_pct"], 1)
active_status = status_from_risk(active_total_pct)

st.sidebar.markdown(
    f"""
    <div class="sidebar-panel">
        <div style="font-size: 13px; font-weight: 800; margin-bottom: 8px; color: {sidebar_text};">Global Schema Mapping</div>
        <div style="margin-bottom: 6px;"><span class="chip-tag">Market: PACIFIC ASIA</span></div>
        <div><span class="chip-tag">Order Region: SOUTH ASIA</span></div>
        <div style="font-size: 11px; color: {sidebar_sub}; margin-top: 8px;">*Auto-resolved DataCo feature encoders</div>
    </div>
    """,
    unsafe_allow_html=True
)

speed_req = int(active_hub["dist"] / max(committed_days, 1))
sla_badge_html = f'<span class="{STATUS_TAG_CLASS[active_status]}">{active_status}</span>'

st.sidebar.markdown(
    f"""
    <div class="sidebar-panel">
        <div style="font-size: 13px; font-weight: 800; margin-bottom: 8px; color: {sidebar_text};">Facts</div>
        <div style="font-size: 13px; line-height: 2; color: {sidebar_text};">
            <div>• <strong>Geodesic Distance:</strong> {active_hub['dist']:,.0f} KM</div>
            <div>• <strong>Route SLA Status:</strong> {sla_badge_html}</div>
            <div>• <strong>Estimated Speed Req:</strong> {speed_req} KM/day</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if nav_choice == "Pre-Dispatch Risk Simulator":
    penalty_pct = active_weather["penalty_pct"]

    if prediction:
        weather_pct = prediction["weather_delay_penalty_pct"]
        base_pct = round(active_total_pct - weather_pct, 1)
        total_tile = metric_tile(
            "Total risk",
            f'<span style="color: {STATUS_COLORS[active_status]};">{active_total_pct:.1f}%</span>',
            (
                f'<div class="split-bar"><div style="width: {base_pct}%; background: {accent};"></div>'
                f'<div style="width: {weather_pct}%; background: {WEATHER_FILL};"></div></div>'
                f'<span class="legend-dot" style="background: {accent};"></span>Base '
                f'<span class="legend-dot" style="background: {WEATHER_FILL}; margin-left: 8px;"></span>Weather'
            ),
            STATUS_FILL[active_status]
        )
        base_tile = metric_tile("Base risk", f"{base_pct:.1f}%", "Operational transit risk before weather", accent)
        weather_tile = metric_tile(
            "Weather penalty",
            f'<span style="color: {crit_text if weather_pct > 0 else text_main};">+{weather_pct:.1f}%</span>',
            f'{active_weather["condition"]} on arrival day',
            WEATHER_FILL
        )
    else:
        total_tile = metric_tile("Total risk", "—", RUN_PROMPT, accent)
        base_tile = metric_tile("Base risk", "—", "Awaiting simulation", accent)
        weather_tile = metric_tile("Weather penalty", "—", f'{active_weather["condition"]} on arrival day', WEATHER_FILL)

    route_tile = metric_tile(
        "Route",
        f'{active_hub["dist"]:,.0f}<span style="font-size: 16px; font-weight: 700;"> km</span>',
        f'Delhi (HQ) to {destination} · {speed_req} km/day over {committed_days} days',
        ROUTE_FILL
    )

    tile_col1, tile_col2, tile_col3, tile_col4 = st.columns(4)
    with tile_col1:
        st.markdown(total_tile, unsafe_allow_html=True)
    with tile_col2:
        st.markdown(base_tile, unsafe_allow_html=True)
    with tile_col3:
        st.markdown(weather_tile, unsafe_allow_html=True)
    with tile_col4:
        st.markdown(route_tile, unsafe_allow_html=True)

    arc_data = []
    for name, hub in INDIAN_HUBS.items():
        is_active = (name == destination)
        if not is_active and not show_secondary:
            continue
        if is_active:
            status_rgb = STATUS_FILL_RGB[active_status]
            core_source = ARC_SOURCE_RGB + [255]
            core_target = status_rgb + [255]
            glow_source = ARC_SOURCE_RGB + [70]
            glow_target = status_rgb + [70]
        else:
            core_source = arc_inactive_color
            core_target = arc_inactive_color
            glow_source = [0, 0, 0, 0]
            glow_target = [0, 0, 0, 0]
        arc_data.append({
            "from_lon": DELHI_HQ[0],
            "from_lat": DELHI_HQ[1],
            "to_lon": hub["coords"][0],
            "to_lat": hub["coords"][1],
            "core_source": core_source,
            "core_target": core_target,
            "glow_source": glow_source,
            "glow_target": glow_target,
            "core_width": 5.0 if is_active else 1.5,
            "glow_width": 13.0 if is_active else 1.5
        })
    df_arcs = pd.DataFrame(arc_data)

    pins_data = []
    for name, hub in INDIAN_HUBS.items():
        is_active = (name == destination)
        is_crit = (active_status == STATUS_CRITICAL)
        if is_active and is_crit:
            icon_url = CRITICAL_WARN_PIN_URI
            icon_size = 46
        elif is_active:
            icon_url = GLASS_3D_PIN_URI
            icon_size = 44
        else:
            icon_url = GREY_PIN_URI
            icon_size = 32

        pins_data.append({
            "name": name,
            "lon": hub["coords"][0],
            "lat": hub["coords"][1],
            "icon_url": icon_url,
            "icon_size": icon_size,
            "label_pos": hub["label_pos"]
        })

    pins_data.append({
        "name": "Delhi HQ",
        "lon": DELHI_HQ[0],
        "lat": DELHI_HQ[1],
        "icon_url": GLASS_3D_PIN_URI,
        "icon_size": 40,
        "label_pos": [0, -34]
    })
    df_pins = pd.DataFrame(pins_data)

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
                line_width_min_pixels=1.4,
            )
        )

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
            data=df_pins,
            get_icon={
                "url": "icon_url",
                "width": 58,
                "height": 72,
                "anchorY": 72
            },
            get_position=["lon", "lat"],
            get_size="icon_size",
            size_units="pixels",
            pickable=True,
        )
    )

    if active_status == STATUS_CRITICAL:
        sonar_data = pd.DataFrame([
            {"lon": active_hub["coords"][0], "lat": active_hub["coords"][1], "radius": 72000, "color": [244, 63, 94, 235]},
            {"lon": active_hub["coords"][0], "lat": active_hub["coords"][1], "radius": 115000, "color": [244, 63, 94, 120]}
        ])
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

    layers.append(
        pdk.Layer(
            "TextLayer",
            data=df_pins,
            get_position=["lon", "lat"],
            get_text="name",
            get_color=pin_label_color,
            get_size=13,
            get_pixel_offset="label_pos",
        )
    )

    view_state = pdk.ViewState(
        latitude=20.6,
        longitude=79.2,
        zoom=4.5,
        pitch=38,
        bearing=0
    )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style=map_style_choice,
        tooltip={"text": "{name}"}
    )

    forecast_date_text = active_weather["forecast_date"].strftime("%b %d, %Y")

    storm_badge_html = ""
    if penalty_pct > 0:
        storm_badge_html = (
            '<div class="storm-badge">'
            '<svg width="46" height="40" viewBox="0 0 64 54" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M18 32H46A11 11 0 0 0 47 11A15 15 0 0 0 18 14A9 9 0 0 0 18 32Z" fill="#94a3b8" stroke="#e2e8f0" stroke-width="2"/>'
            '<polygon points="30,26 22,38 29,38 25,50 39,34 32,34" fill="#facc15" stroke="#eab308" stroke-width="1.2"/>'
            '<line x1="20" y1="36" x2="16" y2="44" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>'
            '<line x1="42" y1="36" x2="38" y2="44" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>'
            '</svg>'
            '<div>'
            f'<div style="font-size: 13px; font-weight: 800; color: {crit_text};">Weather delay risk</div>'
            f'<div style="font-size: 11px; font-weight: 700; color: {text_main};">+{penalty_pct}% penalty on arrival day</div>'
            '</div>'
            '</div>'
        )

    forecast_card_html = (
        '<div class="intel-card">'
        f'<div class="card-title">Arrival-day forecast: {destination}</div>'
        f'<div class="overlay-sub" style="margin-bottom: 10px;">{active_weather["condition"]}</div>'
        f'{storm_badge_html}'
        '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-top: 10px;">'
        f'<div><div class="overlay-sub">Precipitation</div><div class="overlay-val">💧 {active_weather["precip"]} mm</div></div>'
        f'<div><div class="overlay-sub">Wind</div><div class="overlay-val">💨 {active_weather["wind"]} km/h</div></div>'
        f'<div><div class="overlay-sub">Forecast date</div><div class="overlay-val">{forecast_date_text}</div></div>'
        f'<div><div class="overlay-sub">Temperature</div><div class="overlay-val">🌡️ {active_weather["temp_c"]} °C</div></div>'
        '</div>'
        '</div>'
    )

    if prediction:
        status_body = ""
        if active_status == STATUS_CRITICAL:
            status_body += '<div class="hazard-stripe-bar"></div>'
        status_body += (
            f'<div style="margin-bottom: 10px;"><span class="{STATUS_TAG_CLASS[active_status]}">● {active_status}</span></div>'
            f'<div style="font-size: 13px; line-height: 1.5;">{active_hub["advisory"]}</div>'
        )
        if active_status == STATUS_CRITICAL:
            status_body += '<a href="#" class="btn-3d-red">Authorize Dispatch Exception</a>'
    else:
        status_body = f'<div class="overlay-sub">{RUN_PROMPT}</div>'

    status_card_html = (
        '<div class="intel-card">'
        '<div class="card-title">Dispatch status</div>'
        f'{status_body}'
        '</div>'
    )

    map_col, side_col = st.columns([2.1, 1])
    with map_col:
        st.pydeck_chart(deck, width="stretch", height=560)
    with side_col:
        st.markdown(status_card_html, unsafe_allow_html=True)
        st.markdown(forecast_card_html, unsafe_allow_html=True)

else:
    corridor_stats = []
    for city, hub in INDIAN_HUBS.items():
        city_weather = get_arrival_weather(city, committed_days)
        city_total_pct = round(hub["base_risk"] + city_weather["penalty_pct"], 1)
        corridor_stats.append({
            "city": city,
            "dist": hub["dist"],
            "weather": city_weather,
            "total_pct": city_total_pct,
            "status": status_from_risk(city_total_pct),
        })

    flagged_cities = [row["city"] for row in corridor_stats if row["status"] == STATUS_CRITICAL]
    average_total_pct = sum(row["total_pct"] for row in corridor_stats) / len(corridor_stats)
    average_status = status_from_risk(average_total_pct)

    flagged_note = ", ".join(flagged_cities) if flagged_cities else "No critical corridors"
    flagged_color = STATUS_COLORS[STATUS_CRITICAL] if flagged_cities else STATUS_COLORS[STATUS_STABLE]
    flagged_fill = STATUS_FILL[STATUS_CRITICAL] if flagged_cities else STATUS_FILL[STATUS_STABLE]

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            metric_tile("Active fleet corridors", str(len(corridor_stats)), "Origin: Delhi (HQ)", accent),
            unsafe_allow_html=True
        )
    with k2:
        st.markdown(
            metric_tile(
                "Flagged bottlenecks",
                f'<span style="color: {flagged_color};">{len(flagged_cities)}</span>',
                flagged_note,
                flagged_fill
            ),
            unsafe_allow_html=True
        )
    with k3:
        st.markdown(
            metric_tile(
                "Average total risk",
                f'<span style="color: {STATUS_COLORS[average_status]};">{average_total_pct:.1f}%</span>',
                "Base risk plus arrival-day weather penalty",
                STATUS_FILL[average_status]
            ),
            unsafe_allow_html=True
        )

    rows_html = ""
    for row in corridor_stats:
        tag = f'<span class="{STATUS_TAG_CLASS[row["status"]]}">● {row["status"]}</span>'
        risk_cell = (
            f'<strong>{row["total_pct"]:.0f}%</strong>'
            f'<span class="mini-bar"><div style="width: {min(row["total_pct"], 100)}%; background: {STATUS_FILL[row["status"]]};"></div></span>'
        )
        rows_html += (
            f'<tr>'
            f'<td><strong>Delhi (HQ) → {row["city"]}</strong></td>'
            f'<td>{row["dist"]:,.0f} KM</td>'
            f'<td>{row["weather"]["condition"]} ({row["weather"]["temp_c"]}°C)</td>'
            f'<td>{risk_cell}</td>'
            f'<td>{tag}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div class="intel-card">'
        f'<div class="card-title">Indian domestic corridors — telemetry &amp; schema mapping</div>'
        f'<table class="intel-table">'
        f'<thead><tr><th>Corridors</th><th>Distance</th><th>Condition</th><th>Risk</th><th>Status</th></tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="intel-card">'
        '<div class="card-title">XGBoost offline inference model performance</div>'
        '<div style="font-size:13px; line-height:1.7;">Model metrics are loaded from the training report</div>'
        '</div>',
        unsafe_allow_html=True
    )
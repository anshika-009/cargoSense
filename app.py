"""CargoSense Streamlit dashboard: pre-dispatch late-delivery risk simulation and network corridor intelligence."""

import base64
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
    '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="60" viewBox="0 0 48 60">'
    '<path d="M24 3 C12.4 3 3 12.2 3 23.6 C3 39.2 24 57 24 57 C24 57 45 39.2 45 23.6 '
    'C45 12.2 35.6 3 24 3 Z" fill="#64748b" stroke="#cbd5e1" stroke-width="2.5"/>'
    '<circle cx="24" cy="23" r="8" fill="#e2e8f0" stroke="#475569" stroke-width="2"/>'
    '</svg>'
)

GLASS_3D_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="56" height="70" viewBox="0 0 56 70">'
    '<defs>'
    '<linearGradient id="glassGrad" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#bae6fd" stop-opacity="0.95"/>'
    '<stop offset="55%" stop-color="#38bdf8" stop-opacity="0.88"/>'
    '<stop offset="100%" stop-color="#0369a1" stop-opacity="0.95"/>'
    '</linearGradient>'
    '</defs>'
    '<path d="M28 4 C14.7 4 4 14.5 4 27.5 C4 45.5 28 66 28 66 C28 66 52 45.5 52 27.5 '
    'C52 14.5 41.3 4 28 4 Z" fill="url(#glassGrad)" stroke="#e0f2fe" stroke-width="2.8"/>'
    '<ellipse cx="21" cy="17" rx="6" ry="3.5" transform="rotate(-25 21 17)" fill="#ffffff" opacity="0.65"/>'
    '<circle cx="28" cy="27" r="8.5" fill="#f0f9ff" stroke="#0284c7" stroke-width="2.2"/>'
    '</svg>'
)

CRITICAL_WARN_PIN_URI = svg_to_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="58" height="72" viewBox="0 0 58 72">'
    '<defs>'
    '<linearGradient id="warnPinGrad" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0%" stop-color="#7dd3fc"/>'
    '<stop offset="55%" stop-color="#0284c7"/>'
    '<stop offset="100%" stop-color="#0c4a6e"/>'
    '</linearGradient>'
    '</defs>'
    '<path d="M29 4 C15.2 4 4 14.9 4 28.3 C4 46.8 29 68 29 68 C29 68 54 46.8 54 28.3 '
    'C54 14.9 42.8 4 29 4 Z" fill="url(#warnPinGrad)" stroke="#bae6fd" stroke-width="2.8"/>'
    '<polygon points="29,15 41,36 17,36" fill="#ef4444" stroke="#fecaca" stroke-width="1.8" stroke-linejoin="round"/>'
    '<rect x="27.7" y="21" width="2.6" height="8" rx="1" fill="#ffffff"/>'
    '<circle cx="29" cy="32.3" r="1.5" fill="#ffffff"/>'
    '</svg>'
)

top_col1, top_col2 = st.columns([4, 1.3])

with top_col1:
    st.markdown(
        """
        <div style="padding-top: 4px;">
            <h2 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">
                CargoSense <span style="font-weight: 400; opacity: 0.78;">— 3D Dynamic Arc Telemetry & Route Analysis</span>
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )

with top_col2:
    theme_mode = st.radio(
        "Display Theme",
        ["Dark Mode", "Light Mode"],
        horizontal=True,
        label_visibility="collapsed"
    )

if theme_mode == "Dark Mode":
    bg_app = "#080d1a"
    bg_header = "#080d1a"
    bg_sidebar = "#101a2d"
    bg_card = "#142038"
    bg_toolbar = "#162238"
    border_card = "#283c5e"
    text_main = "#f8fafc"
    text_sub = "#94a3b8"
    chip_bg = "#0b1322"
    chip_color = "#38bdf8"
    grid_line = "rgba(56, 189, 248, 0.04)"
    map_style_choice = pdk.map_styles.CARTO_ROAD
    neon_core_color = [125, 249, 255, 255]
    neon_glow_color = [34, 211, 238, 95]
    arc_inactive_color = [103, 232, 249, 75]
    pin_label_color = [248, 250, 252, 255]
    state_border_color = [15, 23, 42, 220]
    map_filter_css = "filter: grayscale(100%) contrast(125%) brightness(58%);"
else:
    bg_app = "#dce6f2"
    bg_header = "#dce6f2"
    bg_sidebar = "#cedceb"
    bg_card = "#e7eff8"
    bg_toolbar = "#d8e4f2"
    border_card = "#7c98b6"
    text_main = "#0f172a"
    text_sub = "#334155"
    chip_bg = "#c7daf0"
    chip_color = "#1e3a8a"
    grid_line = "rgba(30, 58, 138, 0.06)"
    map_style_choice = pdk.map_styles.CARTO_ROAD
    neon_core_color = [0, 185, 245, 255]
    neon_glow_color = [2, 132, 199, 105]
    arc_inactive_color = [71, 85, 105, 95]
    pin_label_color = [15, 23, 42, 255]
    state_border_color = [71, 85, 105, 210]
    map_filter_css = "filter: grayscale(100%) contrast(108%) brightness(90%);"

st.markdown(f"""
<style>
.stApp {{
background-color: {bg_app} !important;
background-image:
radial-gradient(circle at 80% 10%, rgba(14, 165, 233, 0.10), transparent 45%),
linear-gradient(to right, {grid_line} 1px, transparent 1px),
linear-gradient(to bottom, {grid_line} 1px, transparent 1px) !important;
background-size: 100% 100%, 32px 32px, 32px 32px !important;
color: {text_main} !important;
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
section[data-testid="stSidebar"] h4 {{
color: {text_main} !important;
}}

.sidebar-panel {{
background-color: {bg_card} !important;
border: 1px solid {border_card} !important;
border-radius: 10px;
padding: 14px 16px;
margin-bottom: 12px;
color: {text_main} !important;
box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}}

.chip-tag {{
background-color: {chip_bg} !important;
border: 1px solid {border_card} !important;
color: {chip_color} !important;
padding: 3px 8px;
border-radius: 5px;
font-size: 12px;
font-weight: 700;
}}

section[data-testid="stSidebar"] div.stButton > button,
section[data-testid="stSidebar"] div.stButton > button * {{
background: transparent !important;
color: #ffffff !important;
}}

section[data-testid="stSidebar"] div.stButton > button {{
background: linear-gradient(180deg, #38bdf8 0%, #0284c7 52%, #0369a1 100%) !important;
color: #ffffff !important;
font-weight: 800 !important;
font-size: 15px !important;
border: 2px solid #7dd3fc !important;
border-radius: 10px !important;
padding: 12px 18px !important;
width: 100% !important;
box-shadow:
0 0 16px rgba(56, 189, 248, 0.65),
inset 0 2px 3px rgba(255, 255, 255, 0.75),
inset 0 -2px 4px rgba(0, 0, 0, 0.35) !important;
text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
transition: all 0.18s ease-in-out !important;
}}

section[data-testid="stSidebar"] div.stButton > button:hover {{
box-shadow:
0 0 24px rgba(56, 189, 248, 0.95),
inset 0 2px 4px rgba(255, 255, 255, 0.9) !important;
transform: translateY(-1px);
}}

div[data-testid="stDeckGlJsonChart"] {{
border-radius: 14px;
overflow: hidden;
border: 1px solid {border_card};
box-shadow: 0 12px 36px rgba(15, 23, 42, 0.18);
margin-bottom: 12px;
}}

div[data-testid="stDeckGlJsonChart"] iframe,
div[data-testid="stDeckGlJsonChart"] canvas {{
{map_filter_css}
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

.hazard-stripe-bar {{
height: 10px;
width: 100%;
background: repeating-linear-gradient(
-55deg,
#ef4444 0px,
#ef4444 10px,
#18181b 10px,
#18181b 20px
);
border-radius: 5px;
margin-bottom: 10px;
border: 1px solid rgba(251, 146, 60, 0.4);
}}

.btn-3d-red {{
display: block;
width: 100%;
text-align: center;
background: linear-gradient(180deg, #f87171 0%, #ef4444 50%, #b91c1c 100%);
color: #ffffff !important;
font-weight: 800;
font-size: 14px;
padding: 10px 14px;
border-radius: 8px;
border: 1px solid #fca5a5;
box-shadow:
0 4px 14px rgba(220, 38, 38, 0.45),
inset 0 1px 2px rgba(255, 255, 255, 0.7),
inset 0 -2px 3px rgba(0, 0, 0, 0.35);
cursor: pointer;
text-decoration: none;
margin-top: 10px;
}}

.storm-badge {{
display: flex;
align-items: center;
gap: 10px;
background: {chip_bg};
padding: 7px 12px;
border-radius: 10px;
border: 1px solid {border_card};
margin-bottom: 4px;
}}

.intel-card {{
background-color: {bg_card} !important;
border: 1px solid {border_card} !important;
border-radius: 12px;
padding: 16px 20px;
margin-bottom: 14px;
color: {text_main} !important;
box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
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
font-size: 12px;
text-transform: uppercase;
border-bottom: 1px solid {border_card};
}}

.intel-table td {{
padding: 11px 12px;
border-bottom: 1px solid {border_card};
color: {text_main};
}}

.tag-crit {{
background: rgba(239, 68, 68, 0.16);
color: #dc2626;
border: 1px solid rgba(239, 68, 68, 0.45);
padding: 3px 10px;
border-radius: 999px;
font-size: 11px;
font-weight: 700;
}}

.tag-mod {{
background: rgba(245, 158, 11, 0.16);
color: #d97706;
border: 1px solid rgba(245, 158, 11, 0.45);
padding: 3px 10px;
border-radius: 999px;
font-size: 11px;
font-weight: 700;
}}

.tag-ok {{
background: rgba(16, 185, 129, 0.16);
color: #059669;
border: 1px solid rgba(16, 185, 129, 0.45);
padding: 3px 10px;
border-radius: 999px;
font-size: 11px;
font-weight: 700;
}}
</style>
""", unsafe_allow_html=True)

CRITICAL_THRESHOLD = 65
MODERATE_THRESHOLD = 35

STATUS_STABLE = "STABLE OPTIMAL ROUTE"
STATUS_MODERATE = "MODERATE CAUTION ZONE"
STATUS_CRITICAL = "CRITICAL SLA RISK"

STATUS_COLORS = {
    STATUS_STABLE: "#059669",
    STATUS_MODERATE: "#d97706",
    STATUS_CRITICAL: "#dc2626",
}

STATUS_TAG_CLASS = {
    STATUS_STABLE: "tag-ok",
    STATUS_MODERATE: "tag-mod",
    STATUS_CRITICAL: "tag-crit",
}

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


def get_prediction(payload):
    city = payload["destination_city"]
    weather = get_arrival_weather(city, payload["scheduled_shipping_days"])
    total_pct = min(round(INDIAN_HUBS[city]["base_risk"] + weather["penalty_pct"], 1), 100.0)
    return {
        "late_delivery_risk_prob": round(total_pct / 100, 4),
        "late_delivery_risk_pred": int(total_pct >= 50),
        "weather_delay_penalty_pct": weather["penalty_pct"],
        "status": status_from_risk(total_pct),
    }


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
        <div style="font-size: 13px; font-weight: 700; margin-bottom: 6px; color: {text_main};">Global Schema Mapping</div>
        <div style="margin-bottom: 5px;"><span class="chip-tag">Market: PACIFIC ASIA</span></div>
        <div><span class="chip-tag">Order Region: SOUTH ASIA</span></div>
        <div style="font-size: 11px; color: {text_sub}; margin-top: 6px;">*Auto-resolved DataCo feature encoders</div>
    </div>
    """,
    unsafe_allow_html=True
)

speed_req = int(active_hub["dist"] / max(committed_days, 1))
status_color = STATUS_COLORS[active_status]

st.sidebar.markdown(
    f"""
    <div class="sidebar-panel">
        <div style="font-size: 13px; font-weight: 700; margin-bottom: 8px; color: {text_main};">Facts</div>
        <div style="font-size: 13px; line-height: 1.8; color: {text_main};">
            <div>• <strong>Geodesic Distance:</strong> {active_hub['dist']:,.0f} KM</div>
            <div>• <strong>Route SLA Status:</strong> <span style="background: rgba(239, 68, 68, 0.16); color: {status_color}; font-weight: 700; padding: 2px 8px; border-radius: 4px;">{active_status}</span></div>
            <div>• <strong>Estimated Speed Req:</strong> {speed_req} KM/day</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if nav_choice == "Pre-Dispatch Risk Simulator":
    arc_data = []
    for name, hub in INDIAN_HUBS.items():
        is_active = (name == destination)
        if not is_active and not show_secondary:
            continue
        arc_data.append({
            "from_lon": DELHI_HQ[0],
            "from_lat": DELHI_HQ[1],
            "to_lon": hub["coords"][0],
            "to_lat": hub["coords"][1],
            "core_color": neon_core_color if is_active else arc_inactive_color,
            "glow_color": neon_glow_color if is_active else [0, 0, 0, 0],
            "core_width": 4.5 if is_active else 1.5,
            "glow_width": 11.0 if is_active else 1.5
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
                line_width_min_pixels=1.6,
            )
        )

    layers.append(
        pdk.Layer(
            "ArcLayer",
            data=df_arcs,
            get_source_position=["from_lon", "from_lat"],
            get_target_position=["to_lon", "to_lat"],
            get_source_color="glow_color",
            get_target_color="glow_color",
            get_width="glow_width",
        )
    )
    layers.append(
        pdk.Layer(
            "ArcLayer",
            data=df_arcs,
            get_source_position=["from_lon", "from_lat"],
            get_target_position=["to_lon", "to_lat"],
            get_source_color="core_color",
            get_target_color="core_color",
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
            {"lon": active_hub["coords"][0], "lat": active_hub["coords"][1], "radius": 72000, "color": [239, 68, 68, 225]},
            {"lon": active_hub["coords"][0], "lat": active_hub["coords"][1], "radius": 115000, "color": [239, 68, 68, 115]}
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

    st.pydeck_chart(deck, use_container_width=True, height=520)

    forecast_date_text = active_weather["forecast_date"].strftime("%b %d, %Y")
    penalty_pct = active_weather["penalty_pct"]

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
            '<div style="font-size: 13px; font-weight: 800; color: #dc2626;">Weather delay risk</div>'
            f'<div style="font-size: 11px; font-weight: 700; color: {text_main};">+{penalty_pct}% penalty on arrival day</div>'
            '</div>'
            '</div>'
        )

    forecast_card_html = (
        '<div class="intel-card">'
        f'<div style="font-size: 13px; font-weight: 800; letter-spacing: 0.5px;">ARRIVAL-DAY FORECAST: {destination.upper()}</div>'
        f'<div class="overlay-sub" style="margin-bottom: 10px;">{active_weather["condition"]}</div>'
        f'{storm_badge_html}'
        '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 10px;">'
        f'<div><div class="overlay-sub">Precipitation</div><div class="overlay-val">💧 {active_weather["precip"]} mm</div></div>'
        f'<div><div class="overlay-sub">Wind</div><div class="overlay-val">💨 {active_weather["wind"]} km/h</div></div>'
        f'<div><div class="overlay-sub">Forecast date</div><div class="overlay-val">{forecast_date_text}</div></div>'
        f'<div><div class="overlay-sub">Temperature</div><div class="overlay-val">🌡️ {active_weather["temp_c"]} °C</div></div>'
        '</div>'
        '</div>'
    )

    if prediction:
        weather_pct = prediction["weather_delay_penalty_pct"]
        base_pct = round(active_total_pct - weather_pct, 1)
        penalty_color = "#dc2626" if weather_pct > 0 else text_main
        attribution_body = (
            '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">'
            f'<div><div class="overlay-sub">Base risk</div><div class="overlay-val">{base_pct:.1f}%</div></div>'
            f'<div><div class="overlay-sub">Weather penalty</div><div class="overlay-val" style="color: {penalty_color} !important;">+{weather_pct:.1f}%</div></div>'
            f'<div><div class="overlay-sub">Total risk</div><div class="overlay-val">{active_total_pct:.1f}%</div></div>'
            '</div>'
        )

        status_body = ""
        if active_status == STATUS_CRITICAL:
            status_body += '<div class="hazard-stripe-bar"></div>'
        status_body += (
            f'<div style="margin-bottom: 8px;"><span class="{STATUS_TAG_CLASS[active_status]}">● {active_status}</span></div>'
            f'<div style="font-size: 12px; line-height: 1.4;">{active_hub["advisory"]}</div>'
        )
        if active_status == STATUS_CRITICAL:
            status_body += '<a href="#" class="btn-3d-red">Authorize Dispatch Exception</a>'
    else:
        attribution_body = f'<div class="overlay-sub">{RUN_PROMPT}</div>'
        status_body = f'<div class="overlay-sub">{RUN_PROMPT}</div>'

    attribution_card_html = (
        '<div class="intel-card">'
        '<div style="font-size: 13px; font-weight: 800; letter-spacing: 0.5px; margin-bottom: 10px;">RISK ATTRIBUTION</div>'
        f'{attribution_body}'
        '</div>'
    )

    status_card_html = (
        '<div class="intel-card">'
        '<div style="font-size: 13px; font-weight: 800; letter-spacing: 0.5px; margin-bottom: 10px;">DISPATCH STATUS</div>'
        f'{status_body}'
        '</div>'
    )

    card_col1, card_col2, card_col3 = st.columns(3)
    with card_col1:
        st.markdown(forecast_card_html, unsafe_allow_html=True)
    with card_col2:
        st.markdown(attribution_card_html, unsafe_allow_html=True)
    with card_col3:
        st.markdown(status_card_html, unsafe_allow_html=True)

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

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            f'<div class="intel-card"><div class="overlay-sub">Active Fleet Corridors</div><div class="overlay-val" style="font-size:28px;">{len(corridor_stats)}</div><div class="overlay-sub">Origin: Delhi (HQ)</div></div>',
            unsafe_allow_html=True
        )
    with k2:
        flagged_color = "#dc2626" if flagged_cities else text_main
        flagged_note = ", ".join(flagged_cities) if flagged_cities else "No critical corridors"
        st.markdown(
            f'<div class="intel-card"><div class="overlay-sub">Flagged Bottlenecks</div><div class="overlay-val" style="font-size:28px; color:{flagged_color} !important;">{len(flagged_cities)}</div><div class="overlay-sub">{flagged_note}</div></div>',
            unsafe_allow_html=True
        )
    with k3:
        st.markdown(
            f'<div class="intel-card"><div class="overlay-sub">Average Total Risk</div><div class="overlay-val" style="font-size:28px;">{average_total_pct:.1f}%</div><div class="overlay-sub">Base risk plus arrival-day weather penalty</div></div>',
            unsafe_allow_html=True
        )

    rows_html = ""
    for row in corridor_stats:
        tag = f'<span class="{STATUS_TAG_CLASS[row["status"]]}">● {row["status"]}</span>'
        rows_html += (
            f'<tr>'
            f'<td><strong>Delhi (HQ) → {row["city"]}</strong></td>'
            f'<td>{row["dist"]:,.0f} KM</td>'
            f'<td>{row["weather"]["condition"]} ({row["weather"]["temp_c"]}°C)</td>'
            f'<td><strong>{row["total_pct"]:.0f}%</strong></td>'
            f'<td>{tag}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div class="intel-card">'
        f'<div class="overlay-sub" style="margin-bottom:10px;">Indian Domestic Corridors — Telemetry & Schema Mapping</div>'
        f'<table class="intel-table">'
        f'<thead><tr><th>Corridors</th><th>Distance</th><th>Condition</th><th>Risk</th><th>Status</th></tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="intel-card">'
        '<div style="font-weight:800; font-size:15px; margin-bottom:10px;">XGBoost Offline Inference Model Performance</div>'
        '<div style="font-size:13px; line-height:1.7;">Model metrics are loaded from the training report</div>'
        '</div>',
        unsafe_allow_html=True
    )
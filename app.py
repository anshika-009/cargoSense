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

if "pending_mode_update" in st.session_state:
    st.session_state["shipping_mode_input"] = st.session_state.pop("pending_mode_update")
if "pending_days_update" in st.session_state:
    st.session_state["committed_days_input"] = st.session_state.pop("pending_days_update")

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
        index=1,
        horizontal=True,
        label_visibility="collapsed",
    )

if theme_mode == "Light Mode":
    # Sunrise Haze: Soft Peach (#FDF6E3) + Sky Blue (#E0F6FF) mixed
    bg_app_mix = (
        "linear-gradient(125deg, #E0F6FF 0%, #EDF6F4 48%, #FDF6E3 100%), "
        "radial-gradient(circle at 15% 15%, rgba(224, 246, 255, 0.85), transparent 50%), "
        "radial-gradient(circle at 88% 85%, rgba(253, 246, 227, 0.90), transparent 50%)"
    )
    sidebar_bg = "linear-gradient(180deg, #E0F6FF 0%, #EEF6F5 52%, #FDF6E3 100%)"
    sidebar_text = "#0f172a"
    sidebar_sub = "#334155"
    sidebar_card_bg = "rgba(255, 255, 255, 0.72)"
    sidebar_border = "rgba(15, 23, 42, 0.14)"
    sidebar_delta_bg = "rgba(4, 120, 87, 0.14)"
    sidebar_delta_text = "#047857"
    bg_card = "rgba(255, 253, 248, 0.90)"
    bg_toolbar = "#E0F6FF"
    bg_input = "#ffffff"
    text_input = "#0f172a"
    border_input = "#7c98b3"
    border_card = "#c8dff0"
    text_main = "#0f172a"
    text_sub = "#475569"
    accent = "#0369a1"
    accent_soft = "rgba(3, 105, 161, 0.10)"
    btn_sec_bg = "#ffffff"
    btn_sec_text = "#0f172a"
    btn_sec_border = "#64748b"
    ok_text = "#047857"
    mod_text = "#b45309"
    crit_text = "#be123c"
    tile_shadow = "0 8px 22px rgba(15, 23, 42, 0.07)"
    map_style_choice = pdk.map_styles.CARTO_LIGHT
    arc_inactive_color = [100, 116, 139, 95]
    pin_label_color = [15, 23, 42, 255]
    secondary_label_color = [71, 85, 105, 220]
    state_border_color = [51, 92, 129, 165]
else:
    # Northern Lights: Deep Teal (#0C2B3C) + Soft Lavender (#6B5B95) mixed
    bg_app_mix = (
        "linear-gradient(125deg, #0C2B3C 0%, #243b5c 52%, #6B5B95 100%), "
        "radial-gradient(circle at 12% 18%, rgba(12, 43, 60, 0.85), transparent 52%), "
        "radial-gradient(circle at 88% 82%, rgba(107, 91, 149, 0.65), transparent 52%)"
    )
    sidebar_bg = "linear-gradient(180deg, #0C2B3C 0%, #243b5c 52%, #6B5B95 100%)"
    sidebar_text = "#f8fafc"
    sidebar_sub = "#ddd6fe"
    sidebar_card_bg = "rgba(8, 28, 40, 0.55)"
    sidebar_border = "rgba(221, 214, 254, 0.28)"
    sidebar_delta_bg = "rgba(52, 211, 153, 0.18)"
    sidebar_delta_text = "#6ee7b7"
    bg_card = "rgba(16, 44, 62, 0.86)"
    bg_toolbar = "#183c52"
    bg_input = "#081c28"
    text_input = "#f8fafc"
    border_input = "#8b7ec8"
    border_card = "rgba(180, 168, 224, 0.34)"
    text_main = "#f5f7ff"
    text_sub = "#c7d2fe"
    accent = "#c4b5fd"
    accent_soft = "rgba(196, 181, 253, 0.16)"
    btn_sec_bg = "#14374d"
    btn_sec_text = "#ffffff"
    btn_sec_border = "#a594f9"
    ok_text = "#34d399"
    mod_text = "#fbbf24"
    crit_text = "#fb7185"
    tile_shadow = "0 10px 26px rgba(4, 15, 24, 0.42)"
    map_style_choice = pdk.map_styles.CARTO_DARK
    arc_inactive_color = [165, 180, 252, 105]
    pin_label_color = [245, 247, 255, 255]
    secondary_label_color = [199, 210, 254, 220]
    state_border_color = [165, 180, 252, 155]

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, .stApp {{
    font-family: 'Inter', 'Segoe UI', sans-serif;
}}

.stApp *:not([data-testid="stIconMaterial"]):not([data-testid="stSidebarCollapseButton"] *):not([data-testid="stExpandSidebarButton"] *):not([class*="material-icons"]):not([class*="MaterialIcon"]) {{
    font-family: 'Inter', 'Segoe UI', sans-serif;
}}

[data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stExpandSidebarButton"] span {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}}

.stApp {{
    background: {bg_app_mix} !important;
    background-attachment: fixed !important;
    color: {text_main} !important;
}}

section[data-testid="stSidebar"] {{
    background: {sidebar_bg} !important;
    border-right: 1px solid {sidebar_border} !important;
}}

section[data-testid="stSidebar"] > div {{
    background: transparent !important;
}}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {{
    color: {sidebar_text} !important;
}}

section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{
    color: {sidebar_sub} !important;
    font-weight: 700 !important;
}}

section[data-testid="stSidebar"] [data-testid="stCheckbox"] > label {{
    background: {sidebar_card_bg} !important;
    border: 1px solid {sidebar_border} !important;
    border-radius: 10px !important;
    padding: 8px 10px !important;
    width: 100% !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetric"] {{
    background: {sidebar_card_bg} !important;
    border: 1px solid {sidebar_border} !important;
    border-radius: 12px !important;
    padding: 10px 12px !important;
    margin-bottom: 8px !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricLabel"],
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] * {{
    color: {sidebar_sub} !important;
    font-weight: 700 !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricValue"],
section[data-testid="stSidebar"] [data-testid="stMetricValue"] * {{
    color: {sidebar_text} !important;
    font-weight: 800 !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricDelta"] {{
    background: {sidebar_delta_bg} !important;
    border-radius: 999px !important;
    padding: 2px 8px !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricDelta"],
section[data-testid="stSidebar"] [data-testid="stMetricDelta"] * {{
    color: {sidebar_delta_text} !important;
    font-weight: 700 !important;
}}

[data-testid="stExpander"] summary {{
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}}

[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span:not([data-testid="stIconMaterial"]) {{
    margin: 0 !important;
    line-height: 1.35 !important;
}}

.block-container {{
    padding-top: 2.2rem !important;
    max-width: 1520px !important;
}}

header[data-testid="stHeader"] {{
    background: transparent !important;
    background-color: transparent !important;
    border-bottom: none !important;
    color: {text_main} !important;
}}

[data-testid="stToolbar"],
[data-testid="stDecoration"] {{
    background: transparent !important;
    background-color: transparent !important;
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
div[data-testid="stCheckbox"] label span {{
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

/* Action & CSV Download Buttons — High Contrast in Both Modes */
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {{
    background-color: {btn_sec_bg} !important;
    color: {btn_sec_text} !important;
    border: 1.5px solid {btn_sec_border} !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}}

div[data-testid="stButton"] > button *,
div[data-testid="stDownloadButton"] > button * {{
    color: {btn_sec_text} !important;
    fill: {btn_sec_text} !important;
    opacity: 1 !important;
}}

div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {{
    border-color: {accent} !important;
    filter: brightness(1.06);
}}

div[data-testid="stButton"] > button[kind="primary"] {{
    background: linear-gradient(135deg, #0284c7 0%, #6d5dfc 100%) !important;
    color: #ffffff !important;
    border: none !important;
}}

div[data-testid="stButton"] > button[kind="primary"] * {{
    color: #ffffff !important;
    fill: #ffffff !important;
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
    background: linear-gradient(135deg, #0c2b3c 0%, #6b5b95 100%);
    box-shadow: 0 8px 20px rgba(12, 43, 60, 0.28);
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
    backdrop-filter: blur(10px);
    border: 1px solid {border_card} !important;
    border-radius: 14px;
    padding: 14px 18px 12px;
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

/* Number Input Box & Plus/Minus Stepper Buttons — Always High Contrast */
div[data-testid="stNumberInput"] div[data-baseweb="input"],
div[data-testid="stNumberInput"] input,
div[data-testid="stNumberInput"] div[data-baseweb="input"] > div {{
    background-color: {bg_input} !important;
    color: {text_input} !important;
    border-color: {border_input} !important;
}}

div[data-testid="stNumberInput"] button {{
    background-color: #ffffff !important;
    color: #000000 !important;
    border-color: {border_input} !important;
    opacity: 1 !important;
}}

div[data-testid="stNumberInput"] button:hover {{
    background-color: #e2e8f0 !important;
}}

div[data-testid="stNumberInput"] button svg,
div[data-testid="stNumberInput"] button svg path {{
    color: #000000 !important;
    fill: #000000 !important;
    stroke: #000000 !important;
    opacity: 1 !important;
}}

div[data-testid="stDeckGlJsonChart"] {{
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid {border_card};
    box-shadow: {tile_shadow};
}}

.left-summary-card {{
    background: {bg_card} !important;
    backdrop-filter: blur(10px);
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

.whatif-box {{
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid {border_card};
    background: {accent_soft};
    font-size: 12px;
    line-height: 1.45;
    color: {text_main} !important;
}}

.terrain-box {{
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid {border_card};
    background: {accent_soft};
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
    background: rgba(244, 63, 94, 0.16);
    color: {crit_text} !important;
    border: 1px solid rgba(244, 63, 94, 0.55);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.tag-mod {{
    display: inline-block;
    background: rgba(245, 158, 11, 0.16);
    color: {mod_text} !important;
    border: 1px solid rgba(245, 158, 11, 0.55);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.tag-ok {{
    display: inline-block;
    background: rgba(16, 185, 129, 0.16);
    color: {ok_text} !important;
    border: 1px solid rgba(16, 185, 129, 0.55);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.page2-sidebar-trigger {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 14px;
    border-radius: 10px;
    background: {bg_card};
    border: 1.5px solid {btn_sec_border};
    color: {text_main};
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 12px;
    box-shadow: {tile_shadow};
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


def get_terrain_profile(state_name: str, dist_km: float):
    state_upper = (state_name or "").upper()
    himalayan = [
        "HIMACHAL PRADESH", "UTTARAKHAND", "JAMMU AND KASHMIR", "LADAKH",
        "SIKKIM", "ARUNACHAL PRADESH", "NAGALAND", "MANIPUR", "MIZORAM", "MEGHALAYA"
    ]
    ghats_plateau = ["KARNATAKA", "KERALA", "GOA", "MAHARASHTRA", "TELANGANA", "ANDHRA PRADESH"]
    coastal = ["TAMIL NADU", "ODISHA", "WEST BENGAL", "GUJARAT"]

    if any(h in state_upper for h in himalayan):
        return {
            "type": "Himalayan Ridge / Montane Pass",
            "friction_mult": 1.75,
            "gradient_desc": "High elevation gradient, tight switchbacks & landslide vulnerability.",
            "color": "#f43f5e",
        }
    if any(g in state_upper for g in ghats_plateau):
        return {
            "type": "Western Ghats / Deccan Plateau",
            "friction_mult": 1.40,
            "gradient_desc": "Rolling plateau & steep ghat passes; monsoon fog holdover zone.",
            "color": "#f59e0b",
        }
    if any(c in state_upper for c in coastal):
        return {
            "type": "Coastal Plain / Estuarine Belt",
            "friction_mult": 1.25,
            "gradient_desc": "Flat maritime line-haul; high humidity & storm waterlogging.",
            "color": "#0284c7",
        }
    return {
        "type": "Indo-Gangetic / Northern Plains",
        "friction_mult": 1.05,
        "gradient_desc": "Optimal flat multi-lane highway; seasonal winter fog friction.",
        "color": "#10b981",
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
    weather = get_arrival_weather(hub_record, payload["scheduled_shipping_days"])
    body = dict(payload, weather_delay_penalty_pct=weather["penalty_pct"])
    try:
        res = requests.post(f"{API_URL}/predict", json=body, timeout=8)
        res.raise_for_status()
        return dict(res.json(), source="model")
    except requests.RequestException:
        total_pct = min(round(hub_record["base_risk"] + weather["penalty_pct"], 1), 100.0)
        return {
            "late_delivery_risk_prob": round(total_pct / 100.0, 4),
            "late_delivery_risk_pred": int(total_pct >= 50),
            "base_risk_pct": round(total_pct - weather["penalty_pct"], 1),
            "weather_delay_penalty_pct": weather["penalty_pct"],
            "status": status_from_risk(total_pct),
            "source": "fallback",
        }


def get_plus_one_day_what_if(payload, hub_record, current_total_pct):
    if payload["scheduled_shipping_days"] >= 6:
        return None
    next_days = payload["scheduled_shipping_days"] + 1
    next_payload = dict(payload, scheduled_shipping_days=next_days)
    next_pred = get_prediction(next_payload, hub_record)
    next_total_pct = round(next_pred["late_delivery_risk_prob"] * 100.0, 1)

    if next_pred.get("source") == "fallback":
        relief = 0.0
        if hub_record.get("weather_penalty", 0.0) >= 7.5 or hub_record.get("dist", 0) >= 1500:
            relief = -3.5
        elif payload["scheduled_shipping_days"] <= 2:
            relief = -2.0
        next_total_pct = min(max(round(current_total_pct + relief, 1), 0.0), 100.0)

    diff_pct = round(next_total_pct - current_total_pct, 1)
    return {
        "next_days": next_days,
        "next_total_pct": next_total_pct,
        "diff_pct": diff_pct,
    }


def run_and_store_assessment(hub_rec, qty, sales, price, mode, days):
    current_payload = {
        "order_quantity": int(qty),
        "sales_per_customer": float(sales),
        "product_price": float(price),
        "shipping_mode": mode,
        "scheduled_shipping_days": int(days),
        "destination_city": hub_rec["city"],
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
        return
    pred_result = get_prediction(current_payload, hub_rec)
    total_pct_val = round(pred_result["late_delivery_risk_prob"] * 100.0, 1)
    what_if_result = get_plus_one_day_what_if(current_payload, hub_rec, total_pct_val)
    st.session_state["prediction"] = {
        "payload": current_payload,
        "result": pred_result,
        "what_if": what_if_result,
    }


def generate_mitigation_action(active_status, payload, weather_info, active_hub):
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
            '<div class="mitigation-box" style="border-left: 4px solid #f43f5e; background: rgba(244, 63, 94, 0.14);">'
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
            '<div class="mitigation-box" style="border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.14);">'
            '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #fbbf24; margin-bottom: 4px;">'
            "⚠️ Cautionary Dispatch Advisory"
            "</div>"
            f'<div style="font-size: 12.5px; line-height: 1.45;">{note}</div>'
            "</div>"
        )

    return (
        '<div class="mitigation-box" style="border-left: 4px solid #10b981; background: rgba(16, 185, 129, 0.14);">'
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
        key="shipping_mode_input",
    )

with c_days:
    committed_days = st.slider(
        "Transit Window (Days)",
        1,
        6,
        3,
        key="committed_days_input",
    )

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

# Page 1: Completely hide sidebar & toggle buttons
# Page 2: Show hamburger toggle button to open/close sidebar
if nav_choice != "Network Corridor Intelligence":
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"] {{
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            background: {bg_card} !important;
            color: {text_main} !important;
            border: 1.5px solid {btn_sec_border} !important;
            border-radius: 10px !important;
        }}
        [data-testid="stSidebarCollapseButton"] *,
        [data-testid="stExpandSidebarButton"] * {{
            color: {text_main} !important;
            fill: {text_main} !important;
            opacity: 1 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

active_hub = (
    get_hub_record(selected_state, selected_city)
    if (selected_state and selected_city)
    else None
)

if run_clicked:
    if not selected_state or not selected_city or not active_hub:
        st.warning("Please choose both a Destination State and Destination City first.")
    else:
        run_and_store_assessment(
            active_hub,
            order_quantity,
            sales_per_customer,
            product_price,
            shipping_mode,
            committed_days,
        )

expected_payload = (
    {
        "order_quantity": int(order_quantity),
        "sales_per_customer": float(sales_per_customer),
        "product_price": float(product_price),
        "shipping_mode": shipping_mode,
        "scheduled_shipping_days": int(committed_days),
        "destination_city": active_hub["city"],
        "origin_hub": ORIGIN_HUB,
    }
    if active_hub
    else None
)

stored_prediction = st.session_state.get("prediction")
prediction = (
    stored_prediction["result"]
    if (
        expected_payload
        and stored_prediction
        and stored_prediction.get("payload") == expected_payload
    )
    else None
)
what_if_data = (
    stored_prediction.get("what_if")
    if (
        expected_payload
        and stored_prediction
        and stored_prediction.get("payload") == expected_payload
    )
    else None
)

if nav_choice == "Network Corridor Intelligence":
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
                get_background_color=[16, 44, 62, 190] if theme_mode != "Light Mode" else [255, 253, 248, 210],
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
            get_background_color=[16, 44, 62, 225] if theme_mode != "Light Mode" else [255, 253, 248, 235],
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


def render_corridor_intelligence(committed_days, hub_rec=None, scored_pred=None, qty=1, sales=50.0):
    st.markdown(
        '<div class="page2-sidebar-trigger">☰ Use the top-left sidebar toggle to view Model Validation &amp; Weights</div>',
        unsafe_allow_html=True,
    )

    all_corridor_stats = []
    for rec in get_all_city_records():
        city_weather = get_arrival_weather(rec, committed_days)
        city_total_pct = min(round(rec["base_risk"] + city_weather["penalty_pct"], 1), 100.0)
        all_corridor_stats.append(
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
        for row in all_corridor_stats
        if row["status"] == STATUS_CRITICAL
    ]
    avg_total_pct = sum(r["total_pct"] for r in all_corridor_stats) / max(len(all_corridor_stats), 1)
    avg_status = status_from_risk(avg_total_pct)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            metric_tile("Tracked Hubs", str(len(all_corridor_stats)), "Across all 28 Indian states", accent),
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

    if hub_rec and scored_pred:
        total_order_value = float(sales) * int(qty)
        penalty_rate = 0.20
        risk_prob = float(scored_pred["late_delivery_risk_prob"])
        est_exposure = total_order_value * risk_prob * penalty_rate
        expedite_cost = 45.0
        roi_pct = ((est_exposure - expedite_cost) / expedite_cost) * 100.0 if expedite_cost > 0 else 0.0

        st.markdown(
            f'<div class="intel-card">'
            f'<div class="card-title">Executive SLA &amp; Cost Impact · {ORIGIN_HUB} → {hub_rec["city"]} ({hub_rec["state"]})</div>'
            f'<div style="display:flex; flex-wrap:wrap; gap:28px; font-size:13.5px;">'
            f'<div><strong>Order Value:</strong> ${total_order_value:,.2f}</div>'
            f'<div><strong>SLA Penalty Exposure (20%):</strong> <span style="color:{crit_text}; font-weight:700;">${est_exposure:,.2f}</span> ({risk_prob * 100.0:.1f}% risk)</div>'
            f'<div><strong>Expedite Cost vs ROI:</strong> ${expedite_cost:,.0f} ({roi_pct:+.0f}% ROI)</div>'
            f'</div></div>',
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
            f"<td><strong>Delhi HQ → {row['city']}</strong> <span style='color:{text_sub};'>({row['state']})</span></td>"
            f"<td>{row['dist']:,.0f} KM</td>"
            f"<td>{cond_label}</td>"
            f"<td>{risk_cell}</td>"
            f"<td>{tag}</td>"
            f"</tr>"
        )

    if not rows_html:
        rows_html = f"<tr><td colspan='5' style='text-align:center; color:{text_sub}; padding:18px;'>No corridors match the selected filter.</td></tr>"

    st.markdown(
        f'<div class="intel-card">'
        f'<div class="card-title">28-State Corridor Telemetry Snapshot (Showing {len(filtered_hubs[:25])} of {len(filtered_hubs)} Matching Hubs)</div>'
        f'<table class="intel-table">'
        f"<thead><tr><th>Corridor</th><th>Distance</th><th>Condition</th><th>Risk</th><th>Status</th></tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )


def render_shipment_summary_card(active_hub_rec, current_days, current_mode, current_pred, current_what_if):
    if not active_hub_rec:
        st.markdown(
            f"""
            <div class="left-summary-card">
                <div class="left-summary-head">
                    <span class="left-summary-title">Shipment Risk Summary</span>
                    <span class="tag-mod">Awaiting Selection</span>
                </div>
                <div class="left-summary-route" style="color: {text_sub};">
                    From {ORIGIN_HUB} → Select Destination
                </div>
                <div class="left-stat-row"><span class="left-stat-label">ML Total Risk</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">ML Base Risk</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Weather Penalty</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Route Distance</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Shipping Mode</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Conditions</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Rainfall / Wind</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Temperature</span><span class="left-stat-val">--</span></div>
                <div class="left-stat-row"><span class="left-stat-label">Est. Arrival</span><span class="left-stat-val">--</span></div>
                <div class="left-advisory">
                    Select a <strong>Destination State</strong> and <strong>Destination City</strong> above, then click <strong>Run Risk Assessment</strong>.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return STATUS_MODERATE

    weather_info = get_arrival_weather(active_hub_rec, current_days)
    weather_pct = (
        current_pred["weather_delay_penalty_pct"]
        if current_pred
        else weather_info["penalty_pct"]
    )

    if current_pred:
        active_total_pct = round(current_pred["late_delivery_risk_prob"] * 100.0, 1)
        base_pct_val = round(current_pred["base_risk_pct"], 1)
        active_status = status_from_risk(active_total_pct)
        total_display = f"{active_total_pct:.1f}%"
        base_display = f"{base_pct_val:.1f}%"
        total_color = STATUS_COLORS[active_status]
        status_badge = f'<span class="{STATUS_TAG_CLASS[active_status]}">{active_status}</span>'
    else:
        active_status = status_from_risk(
            min(round(active_hub_rec["base_risk"] + weather_pct, 1), 100.0)
        )
        total_display = "Pending"
        base_display = "Pending"
        total_color = text_sub
        status_badge = '<span class="tag-mod">READY TO SCORE</span>'

    forecast_date_text = weather_info["forecast_date"].strftime("%d %b %Y")
    weather_display = format_weather_condition(
        weather_info["condition"], weather_info["precip"], weather_info["wind"]
    )

    terrain_info = get_terrain_profile(active_hub_rec["state"], active_hub_rec["dist"])

    terrain_html = ""
    if current_pred:
        pct_width = int(min((terrain_info["friction_mult"] / 2.0) * 100.0, 100.0))
        terrain_html = (
            f'<div class="terrain-box">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
            f'<strong>Topology:</strong> <span>{terrain_info["type"]}</span>'
            f'</div>'
            f'<div style="font-size:11.5px; color:{text_sub}; margin-bottom:6px;">{terrain_info["gradient_desc"]}</div>'
            f'<div style="display:flex; align-items:center; font-size:11.5px;">'
            f'<span style="font-weight:700;">Corridor Friction: {terrain_info["friction_mult"]:.2f}×</span>'
            f'<span class="mini-bar" style="width:90px; margin-left:10px;"><div style="width:{pct_width}%; background:{terrain_info["color"]};"></div></span>'
            f'</div></div>'
        )

    what_if_html = ""
    if current_pred and current_what_if:
        delta_sign = "+" if current_what_if["diff_pct"] > 0 else ""
        what_if_html = (
            '<div class="whatif-box">'
            f'<strong>What-If (+1 Transit Day → {current_what_if["next_days"]}d):</strong> '
            f'Projected risk moves from <strong>{active_total_pct:.1f}%</strong> to '
            f'<strong>{current_what_if["next_total_pct"]:.1f}%</strong> '
            f'({delta_sign}{current_what_if["diff_pct"]:.1f}%).'
            "</div>"
        )

    mitigation_html = (
        generate_mitigation_action(active_status, expected_payload, weather_info, active_hub_rec)
        if current_pred
        else (
            f'<div class="mitigation-box" style="border-left: 4px solid {accent}; background: {accent_soft};">'
            f'<div style="font-size: 12px; color: {text_main};">'
            "💡 <em>Click <strong>Run Risk Assessment</strong> to generate risk scoring, what-if comparison, and mitigation advice.</em>"
            "</div></div>"
        )
    )

    st.markdown(
        f"""
        <div class="left-summary-card">
            <div class="left-summary-head">
                <span class="left-summary-title">Shipment Risk Summary</span>
                {status_badge}
            </div>
            <div class="left-summary-route">
                Delhi HQ → {active_hub_rec["city"]}, {active_hub_rec["state"]} · {current_days}d window
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
                <span class="left-stat-val">{active_hub_rec["dist"]:,.0f} km</span>
            </div>
            <div class="left-stat-row">
                <span class="left-stat-label">Shipping Mode</span>
                <span class="left-stat-val">{current_mode}</span>
            </div>
            <div class="left-stat-row">
                <span class="left-stat-label">Conditions</span>
                <span class="left-stat-val">{weather_display}</span>
            </div>
            <div class="left-stat-row">
                <span class="left-stat-label">Rainfall / Wind</span>
                <span class="left-stat-val">{weather_info["precip"]} mm · {weather_info["wind"]} km/h</span>
            </div>
            <div class="left-stat-row">
                <span class="left-stat-label">Temperature</span>
                <span class="left-stat-val">{weather_info["temp_c"]} °C</span>
            </div>
            <div class="left-stat-row">
                <span class="left-stat-label">Est. Arrival</span>
                <span class="left-stat-val">{forecast_date_text}</span>
            </div>
            {terrain_html}
            {what_if_html}
            <div class="left-advisory">
                {active_hub_rec["advisory"]}
            </div>
            {mitigation_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_pred and active_status != STATUS_STABLE:
        st.write("")
        if current_mode != "First Class":
            if st.button("⚡ Apply First Class Upgrade & Re-Score", use_container_width=True):
                st.session_state["pending_mode_update"] = "First Class"
                run_and_store_assessment(
                    active_hub_rec,
                    order_quantity,
                    sales_per_customer,
                    product_price,
                    "First Class",
                    current_days,
                )
                st.rerun()
        elif current_days < 6:
            if st.button("⏱️ Add +1 Transit Day & Re-Score", use_container_width=True):
                next_d = current_days + 1
                st.session_state["pending_days_update"] = next_d
                run_and_store_assessment(
                    active_hub_rec,
                    order_quantity,
                    sales_per_customer,
                    product_price,
                    current_mode,
                    next_d,
                )
                st.rerun()

    if current_pred:
        st.write("")
        manifest_record = {
            "dispatch_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "origin_hub": ORIGIN_HUB,
            "destination_city": active_hub_rec["city"],
            "destination_state": active_hub_rec["state"],
            "distance_km": active_hub_rec["dist"],
            "terrain_type": terrain_info["type"],
            "friction_multiplier": terrain_info["friction_mult"],
            "shipping_mode": current_mode,
            "scheduled_transit_days": current_days,
            "order_quantity": order_quantity,
            "sales_per_customer_usd": sales_per_customer,
            "total_order_value_usd": round(sales_per_customer * order_quantity, 2),
            "ml_base_risk_pct": base_pct_val,
            "weather_penalty_pct": weather_pct,
            "total_risk_pct": active_total_pct,
            "sla_risk_status": active_status,
            "gate_release_authorization": (
                "AUTHORIZED" if active_status == STATUS_STABLE else "PRIORITY CLEARANCE REQUIRED"
            ),
        }
        manifest_df = pd.DataFrame([manifest_record])
        manifest_csv = manifest_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Dispatch Manifest (CSV)",
            data=manifest_csv,
            file_name=f"cargosense_manifest_{active_hub_rec['city'].lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    return active_status


# --- ROUTE BY WORKSPACE VIEW (STRICTLY 2 OPERATIONAL PAGES) ---
if nav_choice == "Pre-Dispatch Risk Simulator":
    left_col, right_col = st.columns([1.15, 2.35], gap="medium")
    with left_col:
        current_status = render_shipment_summary_card(
            active_hub, committed_days, shipping_mode, prediction, what_if_data
        )
    with right_col:
        deck = build_clean_map_deck(
            get_all_city_records(),
            active_hub=active_hub,
            active_status=current_status if active_hub else None,
            is_scored=prediction is not None,
        )
        st.pydeck_chart(deck, width="stretch", height=540)
else:
    render_corridor_intelligence(
        committed_days,
        hub_rec=active_hub,
        scored_pred=prediction,
        qty=order_quantity,
        sales=sales_per_customer,
    )
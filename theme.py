import base64
import requests
import streamlit as st

CRITICAL_THRESHOLD = 75
MODERATE_THRESHOLD = 50

STATUS_STABLE = "STABLE OPTIMAL ROUTE"
STATUS_MODERATE = "MODERATE CAUTION ZONE"
STATUS_CRITICAL = "CRITICAL SLA RISK"

# Permanent Light Mode ("Sunrise Haze" Palette)
BG_APP_MIX = (
    "linear-gradient(125deg, #E0F6FF 0%, #EDF6F4 48%, #FDF6E3 100%), "
    "radial-gradient(circle at 15% 15%, rgba(224, 246, 255, 0.85), transparent 50%), "
    "radial-gradient(circle at 88% 85%, rgba(253, 246, 227, 0.90), transparent 50%)"
)
SIDEBAR_BG = "linear-gradient(180deg, #E0F6FF 0%, #EEF6F5 52%, #FDF6E3 100%)"
SIDEBAR_TEXT = "#0f172a"
SIDEBAR_SUB = "#334155"
SIDEBAR_CARD_BG = "rgba(255, 255, 255, 0.78)"
SIDEBAR_BORDER = "rgba(15, 23, 42, 0.16)"
SIDEBAR_DELTA_BG = "rgba(4, 120, 87, 0.14)"
SIDEBAR_DELTA_TEXT = "#047857"
BG_CARD = "rgba(255, 253, 248, 0.92)"
BG_TOOLBAR = "#E0F6FF"
BOX_BG = "#ffffff"
BOX_FG = "#000000"
BOX_BORDER = "#64748b"
BOX_HOVER = "#f1f5f9"
BOX_SELECTED = "#e2e8f0"
BORDER_CARD = "#c8dff0"
TEXT_MAIN = "#0f172a"
TEXT_SUB = "#475569"
ACCENT = "#0369a1"
ACCENT_SOFT = "rgba(3, 105, 161, 0.10)"
BTN_SEC_BG = "#ffffff"
BTN_SEC_TEXT = "#0f172a"
BTN_SEC_BORDER = "#64748b"
OK_TEXT = "#047857"
MOD_TEXT = "#b45309"
CRIT_TEXT = "#be123c"
TILE_SHADOW = "0 8px 22px rgba(15, 23, 42, 0.07)"
PIN_LABEL_COLOR = [15, 23, 42, 255]
STATE_BORDER_COLOR = [51, 92, 129, 165]
ARC_SOURCE_RGB = [6, 182, 212]

STATUS_COLORS = {
    STATUS_STABLE: OK_TEXT,
    STATUS_MODERATE: MOD_TEXT,
    STATUS_CRITICAL: CRIT_TEXT,
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


def svg_to_data_uri(svg_text: str) -> str:
    encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{encoded}"


def status_from_risk(total_pct: float) -> str:
    if total_pct >= CRITICAL_THRESHOLD:
        return STATUS_CRITICAL
    if total_pct >= MODERATE_THRESHOLD:
        return STATUS_MODERATE
    return STATUS_STABLE


def show_val(value, unit: str = "") -> str:
    return "n/a" if value is None else f"{value}{unit}"


def format_weather_condition(condition_text, precip_mm=0.0, wind_kmh=0.0) -> str:
    precip_mm = precip_mm or 0.0
    wind_kmh = wind_kmh or 0.0
    upper_cond = (condition_text or "").upper()
    if upper_cond == "UNAVAILABLE":
        return "Forecast unavailable"
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


def get_terrain_profile(state_name: str, dist_km: float) -> dict:
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


def generate_mitigation_action(active_status: str, payload: dict, weather_info: dict, active_hub: dict) -> str:
    precip_val = weather_info.get("precip") or 0.0
    wind_val = weather_info.get("wind") or 0.0
    if active_status == STATUS_CRITICAL:
        actions = []
        if payload["shipping_mode"] in ["Standard Class", "Second Class"]:
            actions.append(
                "Divert to <strong>First Class / Air Express</strong> to compress line-haul transit by 24–48 hours."
            )
        if precip_val > 15.0 or wind_val > 30.0:
            actions.append(
                f"Hold dispatch gate release for <strong>8–12 hours</strong> until severe weather ({format_weather_condition(weather_info.get('condition'), precip_val, wind_val)}) eases."
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

        items_html = "".join(f"<li>{action}</li>" for action in actions)
        return (
            '<div class="mitigation-box" style="border-left: 4px solid #f43f5e; background: rgba(244, 63, 94, 0.14);">'
            '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #be123c; margin-bottom: 6px;">'
            "Automated Risk Mitigation Protocol"
            "</div>"
            f'<ul style="margin: 0; padding-left: 18px; line-height: 1.5; font-size: 12.5px;">{items_html}</ul>'
            "</div>"
        )

    if active_status == STATUS_MODERATE:
        note = "Monitor corridor transit checkpoints. "
        if payload["shipping_mode"] == "Standard Class":
            note += "Evaluate optional upgrade to <strong>Second Class</strong> to protect tight SLA windows."
        else:
            note += "Verify hub loading cutoff times to avoid overnight holdover."

        return (
            '<div class="mitigation-box" style="border-left: 4px solid #f59e0b; background: rgba(245, 158, 11, 0.14);">'
            '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #b45309; margin-bottom: 4px;">'
            "Cautionary Dispatch Advisory"
            "</div>"
            f'<div style="font-size: 12.5px; line-height: 1.45;">{note}</div>'
            "</div>"
        )

    return (
        '<div class="mitigation-box" style="border-left: 4px solid #10b981; background: rgba(16, 185, 129, 0.14);">'
        '<div style="font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; font-size: 11px; color: #047857; margin-bottom: 4px;">'
        "Clear for Dispatch"
        "</div>"
        '<div style="font-size: 12.5px; line-height: 1.45;">Nominal risk footprint across corridor. Proceed with standard carrier allocation.</div>'
        "</div>"
    )


def metric_tile(label: str, value_html: str, sub_html: str, accent_color: str) -> str:
    return (
        f'<div class="metric-tile" style="border-top-color: {accent_color};">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value_html}</div>'
        f'<div class="metric-sub">{sub_html}</div>'
        "</div>"
    )


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


def apply_theme_and_header(nav_choice: str) -> None:
    st.markdown(
        '<div class="hero">'
        '<div class="brand-mark">CS</div>'
        "<div>"
        '<div class="hero-title">Cargo<span class="accent">Sense</span></div>'
        '<div class="hero-sub">3D dynamic arc telemetry &amp; route analysis · Delhi HQ outbound</div>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

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
    background: {BG_APP_MIX} !important;
    background-attachment: fixed !important;
    color: {TEXT_MAIN} !important;
}}

section[data-testid="stSidebar"] {{
    background: {SIDEBAR_BG} !important;
    border-right: 1px solid {SIDEBAR_BORDER} !important;
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
    color: {SIDEBAR_TEXT} !important;
}}

section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{
    color: {SIDEBAR_SUB} !important;
    font-weight: 700 !important;
}}

section[data-testid="stSidebar"] [data-testid="stCheckbox"] > label {{
    background: {SIDEBAR_CARD_BG} !important;
    border: 1px solid {SIDEBAR_BORDER} !important;
    border-radius: 10px !important;
    padding: 8px 10px !important;
    width: 100% !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetric"] {{
    background: {SIDEBAR_CARD_BG} !important;
    border: 1px solid {SIDEBAR_BORDER} !important;
    border-radius: 12px !important;
    padding: 10px 12px !important;
    margin-bottom: 8px !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricLabel"],
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] * {{
    color: {SIDEBAR_SUB} !important;
    font-weight: 700 !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricValue"],
section[data-testid="stSidebar"] [data-testid="stMetricValue"] * {{
    color: {SIDEBAR_TEXT} !important;
    font-weight: 800 !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricDelta"] {{
    background: {SIDEBAR_DELTA_BG} !important;
    border-radius: 999px !important;
    padding: 2px 8px !important;
}}

section[data-testid="stSidebar"] [data-testid="stMetricDelta"],
section[data-testid="stSidebar"] [data-testid="stMetricDelta"] * {{
    color: {SIDEBAR_DELTA_TEXT} !important;
    font-weight: 700 !important;
}}

.block-container {{
    padding-top: 2.2rem !important;
    max-width: 1520px !important;
}}

header[data-testid="stHeader"] {{
    background: transparent !important;
    background-color: transparent !important;
    border-bottom: none !important;
    color: {TEXT_MAIN} !important;
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
    color: {TEXT_MAIN} !important;
}}

div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label {{
    font-weight: 600 !important;
    opacity: 1 !important;
}}

[data-testid="stElementToolbar"] {{
    background-color: {BG_TOOLBAR} !important;
    border: 1px solid {BORDER_CARD} !important;
    border-radius: 8px !important;
    opacity: 1 !important;
}}

div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {{
    background-color: {BTN_SEC_BG} !important;
    color: {BTN_SEC_TEXT} !important;
    border: 1.5px solid {BTN_SEC_BORDER} !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}}

div[data-testid="stButton"] > button *,
div[data-testid="stDownloadButton"] > button * {{
    color: {BTN_SEC_TEXT} !important;
    fill: {BTN_SEC_TEXT} !important;
    opacity: 1 !important;
}}

div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {{
    border-color: {ACCENT} !important;
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
    margin-bottom: 12px;
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
    color: {TEXT_MAIN} !important;
}}

.hero-title .accent {{
    color: {ACCENT} !important;
}}

.hero-sub {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_SUB} !important;
    margin-top: 2px;
}}

.console-banner {{
    background: {BG_CARD} !important;
    backdrop-filter: blur(10px);
    border: 1px solid {BORDER_CARD} !important;
    border-radius: 14px;
    padding: 14px 18px 12px;
    margin-bottom: 16px;
    box-shadow: {TILE_SHADOW};
}}

.console-title {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {ACCENT} !important;
    margin-bottom: 8px;
}}

.origin-pill {{
    background: {BOX_BG} !important;
    border: 1.5px solid {BOX_BORDER} !important;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 700;
    color: {BOX_FG} !important;
    margin-top: 4px;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div[aria-disabled="true"],
div[data-testid="stNumberInput"] [data-baseweb="input"],
div[data-testid="stDateInput"] [data-baseweb="input"] {{
    background-color: {BOX_BG} !important;
    background: {BOX_BG} !important;
    border: 1.5px solid {BOX_BORDER} !important;
    border-radius: 8px !important;
    opacity: 1 !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] span,
div[data-testid="stSelectbox"] [data-baseweb="select"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] div,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input {{
    background-color: transparent !important;
    color: {BOX_FG} !important;
    -webkit-text-fill-color: {BOX_FG} !important;
    opacity: 1 !important;
}}

div[data-testid="stSelectbox"] [data-baseweb="select"] svg,
div[data-testid="stSelectbox"] [data-baseweb="select"] svg path {{
    fill: {BOX_FG} !important;
    stroke: {BOX_FG} !important;
    color: {BOX_FG} !important;
}}

div[data-testid="stDateInput"] [data-baseweb="input"],
div[data-testid="stDateInput"] [data-baseweb="input"] > div,
div[data-testid="stDateInput"] button {{
    background-color: #ffffff !important;
    background: #ffffff !important;
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
    border-color: #64748b !important;
    opacity: 1 !important;
}}

div[data-testid="stDateInput"] svg,
div[data-testid="stDateInput"] svg path,
div[data-testid="stDateInput"] button svg,
div[data-testid="stDateInput"] button svg path {{
    fill: none !important;
    stroke: #0f172a !important;
    stroke-width: 2 !important;
    color: #0f172a !important;
    background: transparent !important;
}}

div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
div[data-baseweb="menu"],
ul[role="listbox"] {{
    background-color: {BOX_BG} !important;
    background: {BOX_BG} !important;
    border: 1.5px solid {BOX_BORDER} !important;
    opacity: 1 !important;
}}

ul[role="listbox"] li,
ul[role="listbox"] li * {{
    background-color: {BOX_BG} !important;
    color: {BOX_FG} !important;
    -webkit-text-fill-color: {BOX_FG} !important;
    opacity: 1 !important;
}}

ul[role="listbox"] li:hover,
ul[role="listbox"] li:hover * {{
    background-color: {BOX_HOVER} !important;
    color: {BOX_FG} !important;
    -webkit-text-fill-color: {BOX_FG} !important;
}}

ul[role="listbox"] li[aria-selected="true"],
ul[role="listbox"] li[aria-selected="true"] * {{
    background-color: {BOX_SELECTED} !important;
    color: {BOX_FG} !important;
    -webkit-text-fill-color: {BOX_FG} !important;
    font-weight: 700 !important;
}}

div[data-testid="stNumberInput"] button {{
    background-color: {BOX_BG} !important;
    color: {BOX_FG} !important;
    border-color: {BOX_BORDER} !important;
    opacity: 1 !important;
}}

div[data-testid="stNumberInput"] button:hover {{
    background-color: {BOX_HOVER} !important;
}}

div[data-testid="stNumberInput"] button svg {{
    fill: {BOX_FG} !important;
    color: {BOX_FG} !important;
}}

div[data-testid="stDeckGlJsonChart"] {{
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid {BORDER_CARD};
    box-shadow: {TILE_SHADOW};
}}

.left-summary-card {{
    background: {BG_CARD} !important;
    backdrop-filter: blur(10px);
    border: 1px solid {BORDER_CARD} !important;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: {TILE_SHADOW};
}}

.left-summary-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 10px;
    margin-bottom: 12px;
    border-bottom: 1px solid {BORDER_CARD};
}}

.left-summary-title {{
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {TEXT_SUB} !important;
}}

.left-summary-route {{
    font-size: 12px;
    font-weight: 700;
    color: {ACCENT} !important;
    margin-bottom: 10px;
}}

.left-stat-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid {BORDER_CARD};
    font-size: 13px;
}}

.left-stat-label {{
    color: {TEXT_SUB} !important;
    font-weight: 600;
}}

.left-stat-val {{
    color: {TEXT_MAIN} !important;
    font-weight: 700;
}}

.mitigation-box {{
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    font-size: 12px;
    line-height: 1.45;
    color: {TEXT_MAIN} !important;
}}

.whatif-box, .terrain-box {{
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid {BORDER_CARD};
    background: {ACCENT_SOFT};
    font-size: 12px;
    line-height: 1.45;
    color: {TEXT_MAIN} !important;
}}

.metric-tile {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER_CARD} !important;
    border-top: 4px solid {ACCENT};
    border-radius: 14px;
    padding: 14px 16px;
    min-height: 122px;
    box-shadow: {TILE_SHADOW};
    margin-bottom: 12px;
}}

.metric-label {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: {TEXT_SUB} !important;
}}

.metric-value {{
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.8px;
    line-height: 1.15;
    margin: 6px 0;
    color: {TEXT_MAIN} !important;
}}

.metric-sub {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_SUB} !important;
}}

.card-title {{
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: {ACCENT} !important;
    margin-bottom: 10px;
}}

.intel-card {{
    background-color: {BG_CARD} !important;
    border: 1px solid {BORDER_CARD} !important;
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
    color: {TEXT_MAIN} !important;
    box-shadow: {TILE_SHADOW};
}}

.intel-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}

.intel-table th {{
    text-align: left;
    padding: 9px 10px;
    color: {TEXT_SUB} !important;
    font-size: 11px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    border-bottom: 2px solid {BORDER_CARD};
}}

.intel-table td {{
    padding: 10px 10px;
    border-bottom: 1px solid {BORDER_CARD};
    color: {TEXT_MAIN} !important;
}}

.mini-bar {{
    display: inline-block;
    vertical-align: middle;
    width: 72px;
    height: 7px;
    border-radius: 999px;
    background: {BORDER_CARD};
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
    color: {CRIT_TEXT} !important;
    border: 1px solid rgba(244, 63, 94, 0.55);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.tag-mod {{
    display: inline-block;
    background: rgba(245, 158, 11, 0.16);
    color: {MOD_TEXT} !important;
    border: 1px solid rgba(245, 158, 11, 0.55);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.tag-ok {{
    display: inline-block;
    background: rgba(16, 185, 129, 0.16);
    color: {OK_TEXT} !important;
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
    background: {BG_CARD};
    border: 1.5px solid {BTN_SEC_BORDER};
    color: {TEXT_MAIN};
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 12px;
    box-shadow: {TILE_SHADOW};
}}
</style>
""",
        unsafe_allow_html=True,
    )

    if nav_choice != "Network Corridor Intelligence":
        st.markdown(
            "<style>"
            'section[data-testid="stSidebar"],'
            '[data-testid="stSidebarCollapseButton"],'
            '[data-testid="stExpandSidebarButton"] {'
            "display: none !important;"
            "}"
            "</style>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<style>"
            '[data-testid="stSidebarCollapseButton"],'
            '[data-testid="stExpandSidebarButton"] {{'
            "display: flex !important;"
            "visibility: visible !important;"
            "opacity: 1 !important;"
            f"background: {BG_CARD} !important;"
            f"color: {TEXT_MAIN} !important;"
            f"border: 1.5px solid {BTN_SEC_BORDER} !important;"
            "border-radius: 10px !important;"
            "}}"
            '[data-testid="stSidebarCollapseButton"] *,'
            '[data-testid="stExpandSidebarButton"] * {{'
            f"color: {TEXT_MAIN} !important;"
            f"fill: {TEXT_MAIN} !important;"
            "opacity: 1 !important;"
            "}}"
            "</style>",
            unsafe_allow_html=True,
        )
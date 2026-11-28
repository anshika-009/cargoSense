"""CargoSense Streamlit entrypoint: route controls and workspace navigation."""

from datetime import date, timedelta
import streamlit as st

from dashboard.api_client import build_payload, run_and_store_assessment
from dashboard.corridor import render_corridor_intelligence, render_model_sidebar
from core.route_weather import FORECAST_HORIZON_DAYS
from dashboard.simulator_view import render_simulator_page
from core.states_cities import INDIA_STATES_CITIES, ORIGIN_HUB, get_hub_record
from dashboard.theme import apply_theme_and_header

st.set_page_config(
    page_title="CargoSense — 3D Telemetry & Route Analysis",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "pending_mode_update" in st.session_state:
    st.session_state["shipping_mode_input"] = st.session_state.pop("pending_mode_update")
if "pending_days_update" in st.session_state:
    st.session_state["committed_days_input"] = st.session_state.pop("pending_days_update")

# --- HEADER & BRANDING (TOP) ---
current_view = st.session_state.get("workspace_view", "Pre-Dispatch Risk Simulator")
apply_theme_and_header(current_view)

# --- HORIZONTAL CARGOSENSE CONSOLE ---
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

c_qty, c_sales, c_price, c_date, c_view, c_run = st.columns([1.0, 1.1, 1.1, 1.3, 1.6, 1.5])
with c_qty:
    order_quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
with c_sales:
    sales_per_customer = st.number_input("Sales (USD)", min_value=0.0, value=50.0, step=1.0)
with c_price:
    product_price = st.number_input("Price (USD)", min_value=0.0, value=10.0, step=1.0)
with c_date:
    dispatch_date = st.date_input(
        "Dispatch Date",
        value=date.today(),
        min_value=date.today(),
        max_value=date.today() + timedelta(days=FORECAST_HORIZON_DAYS - 1),
    )
with c_view:
    nav_choice = st.selectbox(
        "Workspace View",
        ["Pre-Dispatch Risk Simulator", "Network Corridor Intelligence"],
        key="workspace_view",
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
        run_and_store_assessment(
            active_hub,
            order_quantity,
            sales_per_customer,
            product_price,
            shipping_mode,
            committed_days,
            dispatch_date,
        )

expected_payload = (
    build_payload(
        active_hub, order_quantity, sales_per_customer, product_price,
        shipping_mode, committed_days, dispatch_date,
    )
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
    render_model_sidebar()

if nav_choice == "Pre-Dispatch Risk Simulator":
    render_simulator_page(
        active_hub=active_hub,
        committed_days=committed_days,
        shipping_mode=shipping_mode,
        prediction=prediction,
        what_if_data=what_if_data,
        dispatch_date=dispatch_date,
        order_quantity=order_quantity,
        sales_per_customer=sales_per_customer,
        product_price=product_price,
        expected_payload=expected_payload,
    )
else:
    render_corridor_intelligence(
        committed_days,
        hub_rec=active_hub,
        scored_pred=prediction,
        qty=order_quantity,
        sales=sales_per_customer,
        shipping_mode=shipping_mode,
        price=product_price,
        dispatch_date=dispatch_date,
    )
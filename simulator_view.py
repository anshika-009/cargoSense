from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st

from api_client import run_and_store_assessment
from map import build_clean_map_deck
from states_cities import ORIGIN_HUB, get_all_city_records
from theme import (
    ACCENT,
    ACCENT_SOFT,
    CRIT_TEXT,
    STATUS_COLORS,
    STATUS_MODERATE,
    STATUS_STABLE,
    STATUS_TAG_CLASS,
    TEXT_MAIN,
    TEXT_SUB,
    format_weather_condition,
    generate_mitigation_action,
    get_terrain_profile,
    show_val,
    status_from_risk,
)
from weather_utils import condition_label


def render_shipment_summary_card(
    active_hub_rec,
    current_days,
    current_mode,
    current_pred,
    current_what_if,
    dispatch,
    order_quantity,
    sales_per_customer,
    product_price,
    expected_payload,
):
    if not active_hub_rec:
        st.markdown(
            f'<div class="left-summary-card">'
            f'<div class="left-summary-head">'
            f'<span class="left-summary-title">Shipment Risk Summary</span>'
            f'<span class="tag-mod">Awaiting Selection</span>'
            f'</div>'
            f'<div class="left-summary-route" style="color: {TEXT_SUB};">From {ORIGIN_HUB} → Select Destination</div>'
            f'<div class="left-stat-row"><span class="left-stat-label">ML Total Risk</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">ML Base Risk</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Weather Penalty (route avg)</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Penalty Split</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Route Distance</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Shipping Mode</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Weather Window</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Worst Conditions</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Worst Segment</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Avg Rainfall / Wind</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Avg Temperature</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-stat-row"><span class="left-stat-label">Est. Arrival</span><span class="left-stat-val">--</span></div>'
            f'<div class="left-advisory">Select a <strong>Destination State</strong> and <strong>Destination City</strong> above, then click <strong>Run Risk Assessment</strong>.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return STATUS_MODERATE

    weather_info = {"available": False, "precip": None, "wind": None, "temp_c": None, "condition": "UNAVAILABLE"}
    weather_pct = 0.0
    weather_note = "n/a"
    if current_pred:
        route_values = current_pred["weather"]
        weather_info["available"] = current_pred["weather_available"]
        if weather_info["available"]:
            weather_pct = current_pred["weather_delay_penalty_pct"]
            weather_info.update(
                precip=route_values["worst_precip_mm"],
                wind=route_values["worst_wind_kmh"],
                temp_c=route_values["temp_c_avg"],
                condition=condition_label(route_values["worst_precip_mm"] or 0.0, route_values["worst_wind_kmh"] or 0.0),
            )
            weather_note = (
                f'rain {current_pred["weather_rain_pct"]:.1f} · wind {current_pred["weather_wind_pct"]:.1f}'
                f' · heat {current_pred["weather_heat_pct"]:.1f}'
            )
        else:
            st.warning(
                "Route weather is unavailable. No weather penalty is applied, so the risk shown is the model's base risk only."
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
        active_status = STATUS_MODERATE
        total_display = "Pending"
        base_display = "Pending"
        total_color = TEXT_SUB
        status_badge = '<span class="tag-mod">READY TO SCORE</span>'

    if current_pred:
        arrival_text = date.fromisoformat(str(current_pred["weather_arrival_date"])).strftime("%d %b %Y")
        window_text = f'{date.fromisoformat(str(current_pred["weather_dispatch_date"])).strftime("%d %b")} to {arrival_text}'
        route_km = current_pred["distance_km"]
    else:
        arrival_text = (dispatch + timedelta(days=int(current_days))).strftime("%d %b %Y")
        window_text = f'{dispatch.strftime("%d %b")} to {arrival_text}'
        route_km = active_hub_rec["dist"]

    weather_display = format_weather_condition(
        weather_info["condition"], weather_info["precip"], weather_info["wind"]
    )
    if current_pred and weather_info["available"]:
        worst_text = (
            f'{route_values["worst_date"]} near {route_values["worst_lat"]:.1f}, {route_values["worst_lon"]:.1f}'
            f' (+{current_pred["weather_worst_penalty_pct"]:.1f}%)'
        )
        avg_text = f'{show_val(route_values["precip_mm_avg"], " mm")} · {show_val(route_values["wind_kmh_avg"], " km/h")}'
        temp_text = show_val(route_values["temp_c_avg"], " °C")
    else:
        worst_text = avg_text = temp_text = "n/a"
    penalty_text = "Unavailable" if (current_pred and not weather_info["available"]) else f"+{weather_pct:.1f}%"
    route_penalty_text = (
        f"+{current_pred.get('route_penalty_pct', 0.0):.1f}% "
        f"(slack {current_pred.get('route_slack_pct', 0.0):.1f} · terrain {current_pred.get('route_terrain_pct', 0.0):.1f})"
        if current_pred else "--"
    )

    terrain_info = get_terrain_profile(active_hub_rec["state"], active_hub_rec["dist"])

    terrain_html = ""
    if current_pred:
        pct_width = int(min((terrain_info["friction_mult"] / 2.0) * 100.0, 100.0))
        terrain_html = (
            '<div class="terrain-box">'
            '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">'
            f'<strong>Topology:</strong> <span>{terrain_info["type"]}</span>'
            "</div>"
            f'<div style="font-size:11.5px; color:{TEXT_SUB}; margin-bottom:6px;">{terrain_info["gradient_desc"]}</div>'
            '<div style="display:flex; align-items:center; font-size:11.5px;">'
            f'<span style="font-weight:700;">Corridor Friction: {terrain_info["friction_mult"]:.2f}×</span>'
            f'<span class="mini-bar" style="width:90px; margin-left:10px;"><div style="width:{pct_width}%; background:{terrain_info["color"]};"></div></span>'
            "</div></div>"
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
            f'<div class="mitigation-box" style="border-left: 4px solid {ACCENT}; background: {ACCENT_SOFT};">'
            f'<div style="font-size: 12px; color: {TEXT_MAIN};">'
            "<em>Click <strong>Run Risk Assessment</strong> to generate risk scoring, what-if comparison, and mitigation advice.</em>"
            "</div></div>"
        )
    )

    st.markdown(
        f'<div class="left-summary-card">'
        f'<div class="left-summary-head">'
        f'<span class="left-summary-title">Shipment Risk Summary</span>'
        f'{status_badge}'
        f'</div>'
        f'<div class="left-summary-route">'
        f'Delhi HQ → {active_hub_rec["city"]}, {active_hub_rec["state"]} · {current_days}d window'
        f'</div>'
        f'<div class="left-stat-row"><span class="left-stat-label">ML Total Risk</span><span class="left-stat-val" style="color: {total_color};">{total_display}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">ML Base Risk</span><span class="left-stat-val">{base_display}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Weather Penalty (route avg)</span><span class="left-stat-val" style="color: {CRIT_TEXT if weather_pct > 0 else TEXT_MAIN};">{penalty_text}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Route Penalty (distance + terrain)</span><span class="left-stat-val">{route_penalty_text}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Penalty Split</span><span class="left-stat-val">{weather_note}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Route Distance</span><span class="left-stat-val">{route_km:,.0f} km</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Shipping Mode</span><span class="left-stat-val">{current_mode}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Weather Window</span><span class="left-stat-val">{window_text}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Worst Conditions</span><span class="left-stat-val">{weather_display}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Worst Segment</span><span class="left-stat-val">{worst_text}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Avg Rainfall / Wind</span><span class="left-stat-val">{avg_text}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Avg Temperature</span><span class="left-stat-val">{temp_text}</span></div>'
        f'<div class="left-stat-row"><span class="left-stat-label">Est. Arrival</span><span class="left-stat-val">{arrival_text}</span></div>'
        f'{terrain_html}'
        f'{what_if_html}'
        f'{mitigation_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if current_pred and active_status != STATUS_STABLE:
        st.write("")
        if active_status == STATUS_MODERATE and current_mode == "Standard Class":
            if st.button("Apply Second Class Upgrade & Re-Score", use_container_width=True):
                st.session_state["pending_mode_update"] = "Second Class"
                run_and_store_assessment(
                    active_hub_rec,
                    order_quantity,
                    sales_per_customer,
                    product_price,
                    "Second Class",
                    current_days,
                    dispatch,
                )
                st.rerun()
        elif current_mode != "First Class":
            if st.button("Apply First Class Upgrade & Re-Score", use_container_width=True):
                st.session_state["pending_mode_update"] = "First Class"
                run_and_store_assessment(
                    active_hub_rec,
                    order_quantity,
                    sales_per_customer,
                    product_price,
                    "First Class",
                    current_days,
                    dispatch,
                )
                st.rerun()

        if current_days < 6:
            if st.button("Add +1 Transit Day & Re-Score", use_container_width=True):
                next_d = current_days + 1
                st.session_state["pending_days_update"] = next_d
                run_and_store_assessment(
                    active_hub_rec,
                    order_quantity,
                    sales_per_customer,
                    product_price,
                    current_mode,
                    next_d,
                    dispatch,
                )
                st.rerun()

    if current_pred:
        st.write("")
        manifest_record = {
            "dispatch_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "origin_hub": ORIGIN_HUB,
            "destination_city": active_hub_rec["city"],
            "destination_state": active_hub_rec["state"],
            "distance_km": route_km,
            "dispatch_date": dispatch.isoformat(),
            "weather_available": weather_info["available"],
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
        manifest_csv = pd.DataFrame([manifest_record]).to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export Dispatch Manifest (CSV)",
            data=manifest_csv,
            file_name=f"cargosense_manifest_{active_hub_rec['city'].lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    return active_status


def render_simulator_page(
    active_hub,
    committed_days,
    shipping_mode,
    prediction,
    what_if_data,
    dispatch_date,
    order_quantity,
    sales_per_customer,
    product_price,
    expected_payload,
):
    left_col, right_col = st.columns([1.15, 2.35], gap="medium")
    with left_col:
        current_status = render_shipment_summary_card(
            active_hub,
            committed_days,
            shipping_mode,
            prediction,
            what_if_data,
            dispatch_date,
            order_quantity,
            sales_per_customer,
            product_price,
            expected_payload,
        )
    with right_col:
        deck = build_clean_map_deck(
            get_all_city_records(),
            active_hub=active_hub,
            active_status=current_status if active_hub else None,
            is_scored=prediction is not None,
        )
        st.pydeck_chart(deck, width="stretch", height=540)
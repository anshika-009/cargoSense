import pandas as pd
import pydeck as pdk

from core.states_cities import DELHI_HQ_COORDS, ORIGIN_HUB
from dashboard.theme import (
    ARC_SOURCE_RGB,
    PIN_LABEL_COLOR,
    STATE_BORDER_COLOR,
    STATUS_CRITICAL,
    STATUS_FILL_RGB,
    load_india_states_geojson,
    svg_to_data_uri,
)

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
    '<stop offset="55%" stop-color="#0284c7" stop-opacity="0.95"/>'
    '<stop offset="100%" stop-color="#0369a1" stop-opacity="0.98"/>'
    "</linearGradient>"
    "</defs>"
    '<path d="M28 4 C14.7 4 4 14.5 4 27.5 C4 45.5 28 66 28 66 C28 66 52 45.5 52 27.5 '
    'C52 14.5 41.3 4 28 4 Z" fill="url(#glassGrad)" stroke="#e0e7ff" stroke-width="2.8"/>'
    '<ellipse cx="21" cy="17" rx="6" ry="3.5" transform="rotate(-25 21 17)" fill="#ffffff" opacity="0.65"/>'
    '<circle cx="28" cy="27" r="8.5" fill="#eef2ff" stroke="#0284c7" stroke-width="2.2"/>'
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


def build_clean_map_deck(all_records, active_hub=None, active_status=None, is_scored=False):
    arc_data = []
    if active_hub is not None:
        status_rgb = STATUS_FILL_RGB[active_status]
        arc_data.append(
            {
                "from_lon": DELHI_HQ_COORDS[0],
                "from_lat": DELHI_HQ_COORDS[1],
                "to_lon": active_hub["coords"][0],
                "to_lat": active_hub["coords"][1],
                "core_source": ARC_SOURCE_RGB + [255],
                "core_target": status_rgb + [255],
                "glow_source": ARC_SOURCE_RGB + [70],
                "glow_target": status_rgb + [70],
                "core_width": 5.0,
                "glow_width": 13.0,
            }
        )
    df_arcs = pd.DataFrame(arc_data)

    pins_data = []
    primary_labels = []

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
                get_line_color=STATE_BORDER_COLOR,
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

    layers.append(
        pdk.Layer(
            "TextLayer",
            data=pd.DataFrame(primary_labels),
            get_position=["lon", "lat"],
            get_text="text",
            get_color=PIN_LABEL_COLOR,
            get_size=13,
            get_pixel_offset="offset",
            background=True,
            get_background_color=[255, 253, 248, 235],
            get_border_color=STATE_BORDER_COLOR,
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
        map_style=pdk.map_styles.CARTO_LIGHT,
        tooltip={"text": "{name}"},
    )
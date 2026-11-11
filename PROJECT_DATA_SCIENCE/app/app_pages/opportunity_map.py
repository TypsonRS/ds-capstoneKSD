import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from common import (AOI_KM2, BEST_MODEL, FEATURE_INFO, MODEL_COLS, RDYLGN_HEX, TIER_COLORS, TIER_NAMES, dot, hex_to_rgb,
                    compact_deck, hexbin_mean, load_countries, load_points, rdylgn,
                    surface_png)

st.title(':color[Opportunity map]{foreground="#00a443"}', anchor=False)
st.caption("Each sampled 250 m site colours the area around it. Click the map to see the conditions of the nearest site.")

df = load_points()

with st.sidebar:
    st.header("Map settings", anchor=False)
    model = st.selectbox("Model", list(MODEL_COLS), index=list(MODEL_COLS).index(BEST_MODEL))
    view = st.segmented_control("Show", ["Probability", "Tiers", "Hexagons", "Model agreement"],
                                default="Probability", required=True)
    low_t, high_t = st.slider("Tier thresholds (low ≤ / high ≥)", 0.0, 1.0, (0.40, 0.60), 0.05)
    hide_protected = st.toggle("Hide protected areas", help="Protected areas are for conservation, not restoration")
    if view == "Hexagons":
        hex_km = st.slider("Hexagon size (km, centre to corner)", 1.0, 8.0, 2.5, 0.5)
    else:
        show_points = st.toggle("Show sample points",
                                help="The map is filled from the nearest sample point, as in the notebook's "
                                     "interactive map. Turn this on to see the points themselves.")

score_col = MODEL_COLS[model]
m = df.loc[df[score_col].notna()].copy()
m["score"] = m[score_col]
m["tier"] = np.where(m["score"] >= high_t, 2, np.where(m["score"] <= low_t, 0, 1))
scores = m[list(MODEL_COLS.values())].to_numpy()
m["votes"] = (scores >= 0.5).sum(axis=1)
m["spread"] = scores.std(axis=1)
if hide_protected:
    m = m.loc[m["protected"] == 0]

# ---- tier areas (each uniformly sampled site stands for an equal share of the region) ----
cell_km2 = AOI_KM2 / len(df)
with st.container(horizontal=True):
    for k in (2, 1, 0):
        n = int((m["tier"] == k).sum())
        st.metric(TIER_NAMES[k], f"{n * cell_km2:,.0f} km²", f"{n / len(m):.0%} of shown sites",
                  delta_color="off", delta_arrow="off", border=True)

# ---- colours per view ----
if view == "Tiers":
    m[["r", "g", "b"]] = np.array([hex_to_rgb(c) for c in TIER_COLORS])[m["tier"]]
    legend = " &nbsp;·&nbsp; ".join(f"{dot(c)} {n}" for c, n in zip(TIER_COLORS, TIER_NAMES))
elif view == "Model agreement":
    n_models = len(MODEL_COLS)
    m[["r", "g", "b"]] = rdylgn(m["votes"] / n_models)
    legend = f"Number of models predicting *high* (≥ 0.5): {dot(RDYLGN_HEX[0])} 0 → {dot(RDYLGN_HEX[1])} {n_models}"
else:
    m[["r", "g", "b"]] = rdylgn(m["score"])
    legend = f"Probability of high potential: {dot(RDYLGN_HEX[0])} 0 → {dot(RDYLGN_HEX[0.5])} 0.5 → {dot(RDYLGN_HEX[1])} 1"

m["tier_name"] = np.array(TIER_NAMES)[m["tier"]]
# Keep the payload sent to the browser small (about 5 MB instead of 25 MB for 100,000 sites): short column names
# and only what the tooltip needs. The full conditions of a site appear below the map when it is clicked.
plot = pd.DataFrame({"i": m.index, "x": m["lon"].round(4), "y": m["lat"].round(4), "p": m["score"].round(2),
                     "v": m["votes"]})

layers = []
if view == "Hexagons":
    # averages are computed here (deck.gl's own HexagonLayer ignores the score and only counts points)
    hexes = hexbin_mean(m["lon"], m["lat"], m["score"], size_km=hex_km)
    hexes[["r", "g", "b"]] = rdylgn(hexes["mean"])
    hexes["mean"] = hexes["mean"].round(2)
    layers.append(pdk.Layer(
        "PolygonLayer", hexes, id="hexagons", get_polygon="polygon", get_fill_color=["r", "g", "b", 200],
        get_line_color=[255, 255, 255, 120], line_width_min_pixels=0.5, stroked=True, pickable=True,
        auto_highlight=True))
    tooltip = {"html": f"<b>{model}</b><br/>Mean P(high potential): <b>{{mean}}</b><br/>Sites in hexagon: {{count}}"}
    legend = f"{model}: average probability of high potential per hexagon: {dot(RDYLGN_HEX[0])} 0 → {dot(RDYLGN_HEX[0.5])} 0.5 → {dot(RDYLGN_HEX[1])} 1"
else:
    # wall-to-wall surface (nearest sample point, like the notebook's folium map) + the points on top for clicks
    spacing = float(np.sqrt(AOI_KM2 / len(df)))                       # km between neighbouring sites
    image, bounds = surface_png(m["lon"].round(5).to_numpy(), m["lat"].round(5).to_numpy(),
                                m[["r", "g", "b"]].to_numpy(), spacing, reach=1.5)
    layers.append(pdk.Layer("BitmapLayer", None, id="surface", image=pdk.types.String(image), bounds=bounds))
    if show_points:                                   # colours are only sent when the points are visible
        plot[["r", "g", "b"]] = m[["r", "g", "b"]].to_numpy()
    layers.append(pdk.Layer(
        "ScatterplotLayer", plot, id="sites", get_position=["x", "y"],
        get_fill_color=["r", "g", "b", 255] if show_points else [0, 0, 0, 1],   # alpha 1: invisible but clickable
        get_line_color=[30, 30, 30, 160 if show_points else 0], stroked=True, line_width_min_pixels=0.3,
        get_radius=spacing * 450, radius_min_pixels=1, pickable=True, auto_highlight=True))
    tooltip = {"html": "<b>P(high potential): {p}</b><br/>{v} of 4 models say high"
                       "<br/><i>Click for the conditions of this site</i>"}

countries = load_countries()
if countries:
    layers.append(pdk.Layer("GeoJsonLayer", countries, id="borders", stroked=True, filled=False,
                            get_line_color=[60, 60, 60], line_width_min_pixels=1.5))

deck = compact_deck(
    layers=layers,
    initial_view_state=pdk.ViewState(latitude=float(m["lat"].mean()), longitude=float(m["lon"].mean()), zoom=8),
    tooltip=tooltip,
)
event = st.pydeck_chart(deck, height=620, on_select="rerun", selection_mode="single-object", key="map",
                        alt=f"Map of {model} restoration-potential scores, coloured by {view.lower()}")
st.markdown(legend, unsafe_allow_html=True)

# ---- details of the clicked site ----
picked = (event.selection.objects.get("sites") or []) if event and event.selection else []
if picked:
    site_id = int(picked[0]["i"])
    row = df.loc[site_id]
    with st.container(border=True):
        st.subheader(f"Site {site_id}  ·  {row['lat']:.4f}° N, {row['lon']:.4f}° E", anchor=False)
        with st.container(horizontal=True):
            for name, col in MODEL_COLS.items():
                st.metric(name, f"{row[col]:.2f}")
        details = pd.DataFrame(
            [(FEATURE_INFO[c][0], row[c], FEATURE_INFO[c][1]) for c in FEATURE_INFO if c in row.index],
            columns=["Condition", "Value", "Unit"])
        st.dataframe(details, hide_index=True, alt="Conditions at the selected site",
                     column_config={"Value": st.column_config.NumberColumn(format="%.4g")})
        if st.button("Score this site with custom changes", icon=":material/tune:"):
            st.session_state.predict_site = site_id
            st.switch_page("app_pages/predict.py")

# ---- top sites + download ----
with st.expander("Top 100 sites and download", icon=":material/download:"):
    top = m.nlargest(100, "score")[["lon", "lat", "score", "votes", "soil_moisture", "elevation", "soc",
                                    "ndvi_trend", "protected"]]
    st.dataframe(top, alt="Top 100 sites by opportunity score",
                 column_config={"score": st.column_config.ProgressColumn("P(high)", min_value=0, max_value=1,
                                                                        format="%.2f")})
    # a callable: the 100,000-row CSV is only built when the button is clicked, not on every rerun
    st.download_button("Download all shown sites (CSV)",
                       lambda: m.drop(columns=["r", "g", "b", "tier_name"]).to_csv(index=False),
                       file_name=f"agrorestore_{score_col}.csv", mime="text/csv", icon=":material/download:")

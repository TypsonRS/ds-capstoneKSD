import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from common import (AOI_KM2, BEST_MODEL, FEATURE_INFO, MODEL_COLS, TIER_COLORS, TIER_NAMES, hex_to_rgb,
                    load_countries, load_points, rdylgn)

st.title("Opportunity map", anchor=False)
st.caption("Each dot is a sampled 250 m site. Click a dot to see its conditions.")

df = load_points()

with st.sidebar:
    st.header("Map settings", anchor=False)
    model = st.selectbox("Model", list(MODEL_COLS), index=list(MODEL_COLS).index(BEST_MODEL))
    view = st.segmented_control("Show", ["Probability", "Tiers", "Hexagons", "Model agreement"],
                                default="Probability", required=True)
    low_t, high_t = st.slider("Tier thresholds (low ≤ / high ≥)", 0.0, 1.0, (0.40, 0.60), 0.05)
    hide_protected = st.toggle("Hide protected areas", help="Protected areas are for conservation, not restoration")
    radius = st.slider("Dot size (m)", 50, 400, 120, 10)

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
    st.metric("Mean score", f"{m['score'].mean():.2f}", border=True)

# ---- colours per view ----
if view == "Tiers":
    m[["r", "g", "b"]] = np.array([hex_to_rgb(c) for c in TIER_COLORS])[m["tier"]]
    legend = " · ".join(f":{c}[●] {n}" for c, n in zip(["red", "orange", "green"], TIER_NAMES))
elif view == "Model agreement":
    n_models = len(MODEL_COLS)
    m[["r", "g", "b"]] = rdylgn(m["votes"] / n_models)
    legend = f"Number of models predicting *high* (≥ 0.5): :red[● 0] → :green[● {n_models}]"
else:
    m[["r", "g", "b"]] = rdylgn(m["score"])
    legend = "Probability of high potential: :red[● 0] → :orange[● 0.5] → :green[● 1]"

m["tier_name"] = np.array(TIER_NAMES)[m["tier"]]
# keep the payload sent to the browser small: only what the layers and the tooltip use
plot = m[["lon", "lat", "r", "g", "b", "tier_name", "votes", "score", "precipitation_mean", "soil_moisture",
          "elevation", "slope", "ndvi_trend"]].reset_index(names="site_id")
plot[["lon", "lat"]] = plot[["lon", "lat"]].round(5)
plot = plot.round({"score": 2, "precipitation_mean": 2, "soil_moisture": 0, "elevation": 0, "slope": 1,
                   "ndvi_trend": 5})

layers = []
if view == "Hexagons":
    layers.append(pdk.Layer(
        "HexagonLayer", plot, id="hexagons", get_position=["lon", "lat"], radius=2500,
        get_color_weight="score", color_aggregation="MEAN", get_elevation_weight="score",
        elevation_aggregation="MEAN", color_domain=[0, 1], extruded=False, opacity=0.75, pickable=True,
        color_range=[hex_to_rgb(c) for c in ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]]))
    tooltip = {"text": "Mean P(high) in hexagon: {colorValue}\nSites: {count}"}
else:
    layers.append(pdk.Layer(
        "ScatterplotLayer", plot, id="sites", get_position=["lon", "lat"], get_fill_color=["r", "g", "b", 220],
        get_radius=radius, radius_min_pixels=1, pickable=True, auto_highlight=True))
    tooltip = {"html": "<b>P(high potential): {score}</b><br/>{tier_name} · {votes} of 4 models say high"
                       "<br/>Rain {precipitation_mean} mm/day · Soil moisture {soil_moisture} mm"
                       "<br/>Elevation {elevation} m · Slope {slope}°<br/>NDVI trend {ndvi_trend}/yr"}

countries = load_countries()
if countries:
    layers.append(pdk.Layer("GeoJsonLayer", countries, id="borders", stroked=True, filled=False,
                            get_line_color=[60, 60, 60], line_width_min_pixels=1.5))

deck = pdk.Deck(
    layers=layers,
    initial_view_state=pdk.ViewState(latitude=float(m["lat"].mean()), longitude=float(m["lon"].mean()), zoom=8),
    tooltip=tooltip,
)
event = st.pydeck_chart(deck, height=620, on_select="rerun", selection_mode="single-object", key="map",
                        alt=f"Map of {model} restoration-potential scores, coloured by {view.lower()}")
st.markdown(legend)

# ---- details of the clicked site ----
picked = (event.selection.objects.get("sites") or []) if event and event.selection else []
if picked:
    site = picked[0]
    with st.container(border=True):
        st.subheader(f"Site {site['site_id']}  ·  {site['lat']:.4f}° N, {site['lon']:.4f}° E", anchor=False)
        row = df.loc[site["site_id"]]
        with st.container(horizontal=True):
            for name, col in MODEL_COLS.items():
                st.metric(name, f"{row[col]:.2f}")
        details = pd.DataFrame(
            [(FEATURE_INFO[c][0], row[c], FEATURE_INFO[c][1]) for c in FEATURE_INFO if c in row.index],
            columns=["Condition", "Value", "Unit"])
        st.dataframe(details, hide_index=True, alt="Conditions at the selected site",
                     column_config={"Value": st.column_config.NumberColumn(format="%.4g")})
        if st.button("Score this site with custom changes", icon=":material/tune:"):
            st.session_state.predict_site = int(site["site_id"])
            st.switch_page("app_pages/predict.py")

# ---- top sites + download ----
with st.expander("Top 100 sites and download", icon=":material/download:"):
    top = m.nlargest(100, "score")[["lon", "lat", "score", "votes", "soil_moisture", "elevation", "soc",
                                    "ndvi_trend", "protected"]]
    st.dataframe(top, alt="Top 100 sites by opportunity score",
                 column_config={"score": st.column_config.ProgressColumn("P(high)", min_value=0, max_value=1,
                                                                        format="%.2f")})
    st.download_button("Download all shown sites (CSV)", m.drop(columns=["r", "g", "b"]).to_csv(index=False),
                       file_name=f"agrorestore_{score_col}.csv", mime="text/csv", icon=":material/download:")

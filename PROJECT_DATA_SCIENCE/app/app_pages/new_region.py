import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from common import (FEATURE_INFO, REGION, TIER_COLORS, TIER_NAMES, cnn_predict, hex_to_rgb, hexbin_mean, load_cnn,
                    load_models, load_points, rdylgn, surface_png)

CNN_NAME = "CNN (2D patches)"
TABLE_MODELS = ["Random Forest", "XGBoost", "Logistic Regression"]

st.title("Score a new region", anchor=False)
st.caption(f"Pull the same satellite, climate and soil layers for any area and score it with the models trained "
           f"on the {REGION}. Takes 1-3 minutes per region (a little more with the CNN); results are kept for a day.")


# ============================ CACHED STEPS ============================
@st.cache_resource(show_spinner=False)
def connect_ee():
    import features

    features.init_ee()
    return True


@st.cache_data(ttl="1d", max_entries=10, show_spinner=False)
def fetch_region(place, n_points, with_patches):
    """Boundary, sampled features and (optionally) CNN image patches of a region - the slow Earth Engine part."""
    import features

    aoi, name = features.geocode_region(place)
    image = features.get_features_image(aoi)
    df = features.sample_features(aoi, n_points, image=image)
    P = None
    if with_patches:
        cnn = load_cnn()
        P = features.fetch_patches(df, image, cnn["channels"], cnn["radius"])
    return df, P, aoi.__geo_interface__, name, features.region_km2(aoi)


@st.cache_data(max_entries=20, show_spinner=False)
def score(df, P):
    """One probability column per model (same scoring as notebook section 10)."""
    bundle = load_models()
    ok = df[bundle["features"]].notna().all(axis=1).to_numpy()
    out = df.loc[ok].copy()
    for name, model in bundle["models"].items():
        out[name] = model.predict_proba(out[bundle["features"]])[:, 1]
    if P is not None:
        cnn = load_cnn()
        S = out[list(cnn["scalars"])].to_numpy(np.float32) if cnn["scalars"] else None
        out[CNN_NAME] = cnn_predict(cnn, P[ok], S)
    return out.reset_index(drop=True), int((~ok).sum())


# ============================ INPUT ============================
with st.form("region"):
    with st.container(horizontal=True, vertical_alignment="bottom"):
        place = st.text_input("Place (as in the notebook's PLACES)", value="Plateaux Region, Togo",
                              help="Any name OpenStreetMap knows as an area: a region, district, country...",
                              width=420)
        n_points = st.select_slider("Sample points", [1000, 2000, 3000, 4000, 5000], value=3000,
                                    help="More points = a finer map but a slower request (max 5,000).")
        with_cnn = st.toggle("Include the CNN", value=True,
                             help="Also downloads a 5×5-pixel patch of 15 layers around every point (about +1 min).")
        submitted = st.form_submit_button("Score region", type="primary", icon=":material/travel_explore:")
if submitted:
    st.session_state.region_query = (place.strip(), n_points, with_cnn)

if "region_query" not in st.session_state:
    st.info("Enter a place and press **Score region**. Try other regions of Togo or neighbouring Benin and Ghana: "
            "the models are most reliable where conditions are similar to the Centrale Region.",
            icon=":material/lightbulb:")
    st.stop()

place, n_points, with_cnn = st.session_state.region_query

with st.status(f"Scoring **{place}**...", expanded=False) as status:
    try:
        st.write("Connecting to Earth Engine")
        connect_ee()
        st.write("Finding the boundary and sampling the satellite, climate and soil layers"
                 + (", then the CNN image patches" if with_cnn else ""))
        df, P, boundary, full_name, area_km2 = fetch_region(place, n_points, with_cnn)
        st.write(f"Scoring {len(df):,} points with the trained models")
        scored, n_missing = score(df, P)
    except Exception as e:  # geocoding, Earth Engine or model errors are shown to the user, not raised
        status.update(label=f"Could not score {place}", state="error", expanded=True)
        msg = str(e).lower()
        if "credentials" in msg or "authenticate" in msg:
            st.error("Earth Engine login has expired. Run `ee.Authenticate()` once in the notebook, then retry.",
                     icon=":material/key:")
        st.exception(e)
        st.stop()
    status.update(label=f"**{full_name}**: {len(scored):,} points scored", state="complete")

if scored.empty:
    st.warning("No point in this region has all the inputs the models need.")
    st.stop()

models = [m for m in [*TABLE_MODELS, CNN_NAME] if m in scored.columns]

# ============================ MAP SETTINGS (same as the Opportunity map) ============================
spacing = float(np.sqrt(area_km2 / len(scored)))                         # km between neighbouring points
with st.sidebar:
    st.header("Map settings", anchor=False)
    model = st.selectbox("Model", models, key="nr_model")
    view = st.segmented_control("Show", ["Probability", "Tiers", "Hexagons", "Model agreement"],
                                default="Hexagons", required=True, key="nr_view")
    low_t, high_t = st.slider("Tier thresholds (low ≤ / high ≥)", 0.0, 1.0, (0.40, 0.60), 0.05, key="nr_tiers")
    hide_protected = st.toggle("Hide protected areas", key="nr_protected",
                               help="Protected areas are for conservation, not restoration")
    if view == "Hexagons":
        hex_km = st.slider("Hexagon size (km, centre to corner)", 1.0, 15.0,
                           float(np.clip(round(spacing * 1.6 * 2) / 2, 1.0, 15.0)), 0.5, key="nr_hex")
    else:
        show_points = st.toggle("Show sample points", key="nr_points",
                                help="The map is filled from the nearest sample point, as in the notebook's "
                                     "interactive map. Turn this on to see the points themselves.")
    if not with_cnn:
        st.caption("Tick **Include the CNN** and score again to add the CNN.")

m = scored.copy()
m["score"] = m[model]
m["tier"] = np.where(m["score"] >= high_t, 2, np.where(m["score"] <= low_t, 0, 1))
m["votes"] = (m[models].to_numpy() >= 0.5).sum(axis=1)
if hide_protected:
    m = m.loc[m["protected"] == 0]
if m.empty:
    st.warning("Every point is in a protected area. Switch off **Hide protected areas**.")
    st.stop()

cell_km2 = area_km2 / len(scored)
with st.container(horizontal=True):
    st.metric("Region area", f"{area_km2:,.0f} km²", border=True)
    for k in (2, 1, 0):
        n = int((m["tier"] == k).sum())
        st.metric(TIER_NAMES[k], f"{n * cell_km2:,.0f} km²", f"{n / len(m):.0%} of shown points",
                  delta_color="off", delta_arrow="off", border=True)
    st.metric("Mean score", f"{m['score'].mean():.2f}", border=True)

# ---- colours per view ----
if view == "Tiers":
    m[["r", "g", "b"]] = np.array([hex_to_rgb(c) for c in TIER_COLORS])[m["tier"]]
    legend = " · ".join(f":{c}[●] {n}" for c, n in zip(["red", "orange", "green"], TIER_NAMES))
elif view == "Model agreement":
    m[["r", "g", "b"]] = rdylgn(m["votes"] / len(models))
    legend = f"Number of models predicting *high* (≥ 0.5): :red[● 0] → :green[● {len(models)}]"
else:
    m[["r", "g", "b"]] = rdylgn(m["score"])
    legend = f"{model}: probability of high potential :red[● 0] → :orange[● 0.5] → :green[● 1]"

m["tier_name"] = np.array(TIER_NAMES)[m["tier"]]
plot = m[["lon", "lat", "r", "g", "b", "tier_name", "votes", "score"]].round({"lon": 5, "lat": 5, "score": 2})

if view == "Hexagons":
    hexes = hexbin_mean(m["lon"], m["lat"], m["score"], size_km=hex_km, min_points=3)
    hexes[["r", "g", "b"]] = rdylgn(hexes["mean"])
    hexes["mean"] = hexes["mean"].round(2)
    layers = [pdk.Layer("PolygonLayer", hexes, id="hexagons", get_polygon="polygon",
                        get_fill_color=["r", "g", "b", 200], get_line_color=[255, 255, 255, 120],
                        line_width_min_pixels=0.5, stroked=True, pickable=True, auto_highlight=True)]
    tooltip = {"html": f"<b>{model}</b><br/>Mean P(high potential): <b>{{mean}}</b><br/>Points in hexagon: {{count}}"}
    legend = f"{model}: average probability of high potential per hexagon: :red[● 0] → :orange[● 0.5] → :green[● 1]"
else:
    # wall-to-wall surface (nearest sample point, clipped to the region) + the points on top for hover
    image, bounds = surface_png(plot["lon"].to_numpy(), plot["lat"].to_numpy(), plot[["r", "g", "b"]].to_numpy(),
                                spacing, boundary)
    layers = [
        pdk.Layer("BitmapLayer", None, id="surface", image=pdk.types.String(image), bounds=bounds),
        pdk.Layer("ScatterplotLayer", plot, id="points", get_position=["lon", "lat"],
                  get_fill_color=["r", "g", "b", 255 if show_points else 1],   # alpha 1: invisible but still hoverable
                  get_line_color=[30, 30, 30, 160 if show_points else 0], stroked=True, line_width_min_pixels=0.5,
                  get_radius=spacing * 250, radius_min_pixels=2, pickable=True, auto_highlight=True),
    ]
    tooltip = {"html": f"<b>P(high potential): {{score}}</b><br/>{{tier_name}} · {{votes}} of {len(models)} "
                       "models say high"}

outline = pdk.Layer("GeoJsonLayer", boundary, id="boundary", stroked=True, filled=False,
                    get_line_color=[40, 40, 40], line_width_min_pixels=2)
span = max(scored["lon"].max() - scored["lon"].min(), scored["lat"].max() - scored["lat"].min(), 0.01)
zoom = float(np.clip(np.log2(360 / span) - 0.6, 3, 11))
st.pydeck_chart(pdk.Deck(layers=[*layers, outline], tooltip=tooltip,
                         initial_view_state=pdk.ViewState(latitude=float(scored["lat"].mean()),
                                                          longitude=float(scored["lon"].mean()), zoom=zoom)),
                height=600, alt=f"Map of {model} restoration-potential scores in {full_name}, {view.lower()} view")
st.markdown(legend)

# ---- how far is this region from what the models were trained on? ----
train = load_points()
check = [c for c in load_models()["features"] if c not in ("built_up", "water", "protected")]
lo, hi = train[check].quantile(0.005), train[check].quantile(0.995)
out_of_range = (scored[check] < lo) | (scored[check] > hi)
any_out = out_of_range.any(axis=1).mean()
if any_out > 0.25:
    st.warning(f"**{any_out:.0%} of the points have conditions the models never saw** in the {REGION}. "
               "Scores there are extrapolations and less reliable - see the comparison below.",
               icon=":material/warning:")
else:
    st.success(f"Conditions are mostly within the training range ({1 - any_out:.0%} of points), "
               "so the scores are as reliable as in the Centrale Region.", icon=":material/verified:")

with st.expander("Compare with the training region", icon=":material/compare_arrows:", expanded=any_out > 0.25):
    comp = pd.DataFrame({
        "Condition": [FEATURE_INFO[c][0] for c in check],
        REGION: train[check].median().values,
        place: scored[check].median().values,
        "Outside training range": out_of_range.mean().values,
    })
    st.dataframe(comp.sort_values("Outside training range", ascending=False), hide_index=True,
                 alt="Median conditions in the training region and the new region",
                 column_config={REGION: st.column_config.NumberColumn(f"{REGION} (median)", format="%.3g"),
                                place: st.column_config.NumberColumn(f"{place} (median)", format="%.3g"),
                                "Outside training range": st.column_config.ProgressColumn(
                                    "Points outside training range", min_value=0, max_value=1, format="percent")})

with st.expander("Model comparison and download", icon=":material/download:"):
    summary = pd.DataFrame({
        "Mean P(high)": [scored[c].mean() for c in models],
        "High potential (km²)": [round((scored[c] >= high_t).sum() * cell_km2) for c in models],
        "Low potential (km²)": [round((scored[c] <= low_t).sum() * cell_km2) for c in models],
    }, index=pd.Index(models, name="Model"))
    st.dataframe(summary, alt="Mean score and tier areas per model",
                 column_config={"Mean P(high)": st.column_config.NumberColumn(format="%.2f"),
                                "High potential (km²)": st.column_config.NumberColumn(format="localized"),
                                "Low potential (km²)": st.column_config.NumberColumn(format="localized")})
    if n_missing:
        st.caption(f"{n_missing} points were skipped because a model input was missing.")
    st.download_button("Download scored points (CSV)", scored.to_csv(index=False),
                       file_name=f"agrorestore_{place.split(',')[0].strip().replace(' ', '_').lower()}.csv",
                       mime="text/csv", icon=":material/download:")

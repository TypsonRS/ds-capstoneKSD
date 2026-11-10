import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

import adapt
from common import (FEATURE_INFO, REGION, RDYLGN_HEX, TIER_COLORS, TIER_NAMES, dot, cnn_predict, hex_to_rgb, hexbin_mean, load_cnn,
                    load_models, load_points, rdylgn, surface_png)

CNN_NAME = "CNN (2D patches)"
TABLE_MODELS = ["Random Forest", "XGBoost", "Logistic Regression"]

st.title(':color[Score a new region]{foreground="#00a443"}', anchor=False)
st.caption(f"Pull the same satellite, climate and soil layers for any area, score it with the models trained on the "
           f"{REGION}, and fine-tune the CNN on the new region with its own 20-year vegetation record. A region "
           "takes 1-3 minutes, about 1-2 more with the CNN. The first region in a new country also downloads its "
           "OpenStreetMap roads, about 1 minute more. Results are kept for a day.")


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
    df, osm_error = features.add_osm_distances(df, aoi)
    # same rule as the notebook: a point with no road / settlement found counts as "very far" (the largest distance);
    # if OpenStreetMap could not be read at all, use the training region's median so the models still run
    train = load_points()
    for col in features.OSM_DIST_COLS:
        fill = df[col].max() if df[col].notna().any() else train[col].median()
        df[col] = df[col].fillna(fill)
    P = None
    if with_patches:
        cnn = load_cnn()
        P = features.fetch_patches(df, image, cnn["channels"], cnn["radius"])
    return df, P, aoi.__geo_interface__, name, features.region_km2(aoi), osm_error


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
    return out.reset_index(drop=True), int((~ok).sum()), (P[ok] if P is not None else None)


@st.cache_data(max_entries=20, show_spinner=False)
def fine_tune_cnn(df, P):
    """The CNN fine-tuned on this region, scored with spatial cross-validation (see adapt.py)."""
    return adapt.adapt_cnn(df, P, load_cnn())


# ============================ INPUT ============================
with st.form("region"):
    with st.container(horizontal=True, vertical_alignment="bottom"):
        place = st.text_input("Place", value="Plateaux Region, Togo",
                              help="Any name OpenStreetMap knows as an area: a region, district, country...",
                              width=420)
        n_points = st.select_slider("Sample points", [1000, 2000, 3000, 4000, 5000], value=3000,
                                    help="More points = a finer map but a slower request (max 5,000).")
        with_cnn = st.toggle("Include the CNN", value=True,
                             help="Downloads a 5×5-pixel patch of 15 layers around every point and fine-tunes the "
                                  "CNN on this region (about +1-2 min).")
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
        st.write("Finding the boundary, sampling the satellite, climate and soil layers and measuring the "
                 "distances to roads and settlements (OpenStreetMap)"
                 + (", then the CNN image patches" if with_cnn else ""))
        df, P, boundary, full_name, area_km2, osm_error = fetch_region(place, n_points, with_cnn)
        st.write(f"Scoring {len(df):,} points with the trained models")
        scored, n_missing, P_ok = score(df, P)
        tuned, tune_info, cnn_centrale_auc = None, None, None
        if P_ok is not None:
            st.write("Fine-tuning the CNN on this region's own NDVI trend 2006-2025 (spatial cross-validation)")
            cnn_centrale_auc = adapt.local_metrics(scored, [CNN_NAME]).loc[CNN_NAME, "ROC-AUC"]
            tuned, tune_info = fine_tune_cnn(scored, P_ok)
            if tuned is not None:
                scored[CNN_NAME] = tuned             # the CNN shown is the one fine-tuned on this region
    except Exception as e:  # geocoding, Earth Engine or model errors are shown to the user, not raised
        status.update(label=f"Could not score {place}", state="error", expanded=True)
        msg = str(e).lower()
        if "credentials" in msg or "authenticate" in msg:
            st.error("Earth Engine login has expired. Run `ee.Authenticate()` once in the notebook, then retry.",
                     icon=":material/key:")
        st.exception(e)
        st.stop()
    status.update(label=f"**{full_name}**: {len(scored):,} points scored", state="complete")

if osm_error:
    st.warning("**Distances to roads and settlements could not be measured** (OpenStreetMap unavailable), so every "
               f"point uses the typical distance of the {REGION}. Scores ignore local access; try again later.\n\n"
               f"Details: `{osm_error}`", icon=":material/signal_disconnected:")

if scored.empty:
    st.warning("No point in this region has all the inputs the models need.")
    st.stop()

models = [m for m in [*TABLE_MODELS, CNN_NAME] if m in scored.columns]
local = adapt.local_metrics(scored, models)          # every model checked against this region's own outcome
best = local["ROC-AUC"].idxmax()

# ============================ MAP SETTINGS (same as the Opportunity map) ============================
spacing = float(np.sqrt(area_km2 / len(scored)))                         # km between neighbouring points
with st.sidebar:
    st.header("Map settings", anchor=False)
    model = st.selectbox("Model", models, index=models.index(best), key="nr_model",
                         help="Starts on the model that ranks this region's sites best (see the reliability check)")
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
    legend = " &nbsp;·&nbsp; ".join(f"{dot(c)} {n}" for c, n in zip(TIER_COLORS, TIER_NAMES))
elif view == "Model agreement":
    m[["r", "g", "b"]] = rdylgn(m["votes"] / len(models))
    legend = f"Number of models predicting *high* (≥ 0.5): {dot(RDYLGN_HEX[0])} 0 → {dot(RDYLGN_HEX[1])} {len(models)}"
else:
    m[["r", "g", "b"]] = rdylgn(m["score"])
    legend = f"{model}: probability of high potential {dot(RDYLGN_HEX[0])} 0 → {dot(RDYLGN_HEX[0.5])} 0.5 → {dot(RDYLGN_HEX[1])} 1"

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
    legend = f"{model}: average probability of high potential per hexagon: {dot(RDYLGN_HEX[0])} 0 → {dot(RDYLGN_HEX[0.5])} 0.5 → {dot(RDYLGN_HEX[1])} 1"
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
st.markdown(legend, unsafe_allow_html=True)

# ---- how far is this region from what the models were trained on? ----
train = load_points()
check = [c for c in load_models()["features"] if c not in ("built_up", "water", "protected")]
lo, hi = train[check].quantile(0.005), train[check].quantile(0.995)
out_of_range = (scored[check] < lo) | (scored[check] > hi)
any_out = out_of_range.any(axis=1).mean()
n_out = out_of_range.sum(axis=1)                                  # conditions outside the range, per point

# ---- reliability, measured: each model against what actually happened here ----
st.subheader("How reliable are the scores here?", anchor=False)
auc = local.loc[best, "ROC-AUC"]
# best score of the models as trained on the Centrale Region only (the CNN before fine-tuning)
centrale_aucs = local.loc[TABLE_MODELS, "ROC-AUC"].tolist() + ([cnn_centrale_auc] if cnn_centrale_auc is not None else [])
centrale_best = max(centrale_aucs)
level = ("good" if auc >= 0.75 else "moderate" if auc >= 0.65 else "weak")
text = (f"Checked against this region's own outcome, the NDVI trend 2006-2025 labelled as in training "
        f"(top 30% = high, bottom 30% = low potential). **{best}** ranks the sites best here, with a "
        f"ROC-AUC of **{auc:.2f}** (target 0.80, chance 0.50): **{level}** reliability.")
if tuned is not None:
    text += (f"\n\nThe CNN is fine-tuned on this region: it starts from the network trained on the {REGION} and "
             f"learns from this region's own vegetation record (ROC-AUC {cnn_centrale_auc:.2f} before, "
             f"{local.loc[CNN_NAME, 'ROC-AUC']:.2f} after). Every point is scored by a version that never saw its "
             f"{tune_info['block_km']:g} km block, so its score is not inflated.")
if centrale_best < 0.65:
    text += (f"\n\nThe models trained only on the {REGION} do not transfer here (best ROC-AUC {centrale_best:.2f}): "
             f"**{any_out:.0%} of the points** have conditions they never saw, typically "
             f"{n_out.median():.0f} of {len(check)}.")
{"good": st.success, "moderate": st.info, "weak": st.warning}[level](
    text, icon={"good": ":material/verified:", "moderate": ":material/info:", "weak": ":material/warning:"}[level])
if P_ok is None:
    st.caption("Tick **Include the CNN** and score again: the CNN is then fine-tuned on this region, which usually "
               "makes the scores much more reliable here.")
elif tuned is None:
    st.caption(f"The CNN was not fine-tuned: the region has too few labelled points ({tune_info['n_labelled']}) or "
               f"spatial blocks ({tune_info['n_blocks']}). Use a larger region or more sample points.")
st.dataframe(local.sort_values("ROC-AUC", ascending=False), alt="Local accuracy of every model in this region",
             column_config={"ROC-AUC": st.column_config.ProgressColumn("ROC-AUC here", min_value=0.5, max_value=1,
                                                                       format="%.2f"),
                            "F1 macro": st.column_config.NumberColumn("F1 macro here", format="%.2f")})

with st.expander("Compare with the training region", icon=":material/compare_arrows:"):
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

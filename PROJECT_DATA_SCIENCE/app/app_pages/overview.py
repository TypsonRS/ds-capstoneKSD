import numpy as np
import streamlit as st

from common import (AOI_KM2, BEST_MODEL, HIGH_T, LOW_T, REGION, TIER_NAMES, TUNED_RESULTS, load_points)

st.title(":color[:material/eco: AgroRestore AI :material/eco:]{foreground=\"#00a443\"}", anchor=False)
st.markdown(f":color[Where is land restoration most likely to succeed in the **{REGION}**? "
            "Machine-learning models trained on 20 years of satellite, climate and soil data "
            "map the probability that a 250 m site has **high restoration potential**.]{foreground=\"#008a3a\"}")

df = load_points()
res = TUNED_RESULTS.loc[BEST_MODEL]
cell_km2 = AOI_KM2 / len(df)
tier_km2 = np.bincount(df["tier"], minlength=3) * cell_km2

with st.container(horizontal=True):
    st.metric("Study area", f"{AOI_KM2:,} km²", border=True)
    st.metric("Sampled sites (250 m)", f"{len(df):,}", border=True)
    st.metric("Best model", BEST_MODEL, border=True, help="Chosen on spatial cross-validation F1 macro")
    st.metric("Test ROC-AUC", f"{res['Test ROC-AUC']:.2f}", f"{res['Test ROC-AUC'] - 0.80:+.2f} vs target 0.80",
              border=True)
    st.metric("Test F1 macro", f"{res['Test F1 macro']:.2f}", f"{res['Test F1 macro'] - 0.75:+.2f} vs target 0.75",
              border=True)

st.subheader("Restoration potential across the region", anchor=False)
with st.container(horizontal=True):
    for k, name in reversed(list(enumerate(TIER_NAMES))):
        rule = {0: f"P ≤ {LOW_T}", 1: f"{LOW_T} < P < {HIGH_T}", 2: f"P ≥ {HIGH_T}"}[k]
        st.metric(f"{name} ({rule})", f"{tier_km2[k]:,.0f} km²",
                  f"{tier_km2[k] / AOI_KM2:.0%} of the area", delta_color="off", delta_arrow="off", border=True)

left, right = st.columns(2)
with left:
    with st.container(border=True, height="stretch"):
        st.markdown("**:material/database: Data (Google Earth Engine)**")
        st.markdown(
            "- **Climate**: CHIRPS rainfall, TerraClimate temperature and soil moisture (2006-2024)\n"
            "- **Soil**: iSDAsoil organic carbon and pH (0-20 cm)\n"
            "- **Terrain**: SRTM elevation and slope\n"
            "- **Land cover**: ESA WorldCover built-up and water, WDPA protected areas\n"
            "- **Vegetation**: MODIS NDVI mean, variability, resilience and 20-year trend\n"
            "- 100,000 random points sampled at 250 m across the region")
with right:
    with st.container(border=True, height="stretch"):
        st.markdown("**:material/schema: Method**")
        st.markdown(
            "1. **Label**: the NDVI trend 2006-2025. Top 30% of sites = *high potential*, "
            "bottom 30% = *low potential*, the ambiguous middle is dropped.\n"
            "2. **Spatial split**: the region is cut into 10 km blocks; 30% of the blocks are held out "
            "for testing so the score reflects new places, not neighbours.\n"
            "3. **Models**: Random Forest, XGBoost, Logistic Regression and a 2D CNN on 5×5 image patches, "
            "tuned with grouped 5-fold cross-validation.\n"
            "4. **Opportunity score**: the best model's probability of *high potential* for every site.")

st.info("Use the **Opportunity map** to find priority areas, **Explore the data** to see what drives the "
        "scores, and **Score a site** to test your own conditions.", icon=":material/lightbulb:")

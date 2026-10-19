import numpy as np
import pandas as pd
import streamlit as st

from common import BEST_MODEL, FEATURE_INFO, HIGH_T, LOW_T, TIER_NAMES, load_models, load_points, tier_of

st.title("Score a site", anchor=False)
st.caption("Start from a real site, change its conditions, and see how the trained models respond.")

df = load_points()
BINARY = ["built_up", "water", "protected"]
CONTINUOUS = ["precipitation_mean", "soil_moisture", "tmean", "tmin", "tmax", "soc", "ph", "elevation", "slope",
              "ndvi_mean", "ndvi_std", "ndvi_resilience"]
lo_q, hi_q = df[CONTINUOUS].quantile(0.001), df[CONTINUOUS].quantile(0.999)


def load_site(idx):
    """Copy the conditions of one sampled site into the input widgets."""
    row = df.loc[idx]
    for c in CONTINUOUS:
        st.session_state[f"in_{c}"] = float(np.clip(row[c], lo_q[c], hi_q[c]))
    for c in BINARY:
        st.session_state[f"in_{c}"] = bool(row[c])
    st.session_state.site_label = f"site {idx} ({row['lat']:.4f}° N, {row['lon']:.4f}° E)"


# a site chosen on the map arrives here; otherwise start from the median site
if "predict_site" in st.session_state:
    load_site(st.session_state.pop("predict_site"))
elif "in_soil_moisture" not in st.session_state:
    load_site((df[CONTINUOUS] - df[CONTINUOUS].median()).abs().div(df[CONTINUOUS].std()).sum(axis=1).idxmin())

with st.container(border=True):
    st.markdown("**Start from a location**")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        lat = st.number_input("Latitude", float(df["lat"].min()), float(df["lat"].max()), float(df["lat"].median()),
                              format="%.4f")
        lon = st.number_input("Longitude", float(df["lon"].min()), float(df["lon"].max()),
                              float(df["lon"].median()), format="%.4f")
        if st.button("Load nearest site", icon=":material/my_location:"):
            kx = np.cos(np.deg2rad(lat))
            load_site((((df["lon"] - lon) * kx) ** 2 + (df["lat"] - lat) ** 2).idxmin())
            st.rerun()
        if st.button("Random high-potential site", icon=":material/shuffle:"):
            load_site(df.loc[df["tier"] == 2].sample(1).index[0])
            st.rerun()
    st.caption(f"Current inputs come from {st.session_state.site_label}.")

with st.form("conditions"):
    st.markdown("**Conditions**")
    cols = st.columns(3)
    for i, c in enumerate(CONTINUOUS):
        label, unit, source = FEATURE_INFO[c]
        cols[i % 3].slider(f"{label}" + (f" ({unit})" if unit else ""), float(lo_q[c]), float(hi_q[c]),
                           key=f"in_{c}", help=f"Source: {source}", format="%.3f" if hi_q[c] < 10 else "%.1f")
    with st.container(horizontal=True):
        for c in BINARY:
            st.toggle(FEATURE_INFO[c][0], key=f"in_{c}")
    st.form_submit_button("Score", type="primary", icon=":material/play_arrow:")

try:
    bundle = load_models()
except MemoryError:
    st.error("Not enough free memory to load models.pkl (the Random Forest alone is about 270 MB). "
             "Close other programs, such as the Jupyter kernel, and reload the page.", icon=":material/memory:")
    st.stop()
x =pd.DataFrame([{c: float(st.session_state[f"in_{c}"]) for c in bundle["features"]}])[bundle["features"]]
probs = {name: float(m.predict_proba(x)[0, 1]) for name, m in bundle["models"].items()}

best = probs[BEST_MODEL]
tier = int(tier_of(best))
with st.container(border=True):
    st.subheader(f"{TIER_NAMES[tier]}", anchor=False)
    st.progress(best, text=f"{BEST_MODEL}: P(high potential) = {best:.2f}  "
                           f"(low ≤ {LOW_T}, high ≥ {HIGH_T})")
    with st.container(horizontal=True):
        for name, p in probs.items():
            st.metric(name, f"{p:.2f}", border=True)
    st.caption("The CNN is not available here: it needs the 5×5 satellite image patch around a real site, "
               "not single values. Its scores are on the Opportunity map.")

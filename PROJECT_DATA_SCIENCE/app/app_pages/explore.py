import altair as alt
import pandas as pd
import streamlit as st

from common import FEATURE_INFO, TIER_COLORS, TIER_NAMES, load_points

st.title("Explore the data", anchor=False)
st.caption("How do conditions differ between high- and low-potential sites?")

df = load_points()
df["Tier"] = pd.Categorical(pd.Series(TIER_NAMES).iloc[df["tier"]].values, TIER_NAMES)
features = [c for c in FEATURE_INFO if c in df.columns]
fmt = lambda c: f"{FEATURE_INFO[c][0]}" + (f" ({FEATURE_INFO[c][1]})" if FEATURE_INFO[c][1] else "")

feature = st.selectbox("Condition", features, format_func=fmt, index=features.index("soil_moisture"))
sample = df.sample(min(20_000, len(df)), random_state=42)
tier_scale = alt.Scale(domain=TIER_NAMES, range=TIER_COLORS)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.markdown(f"**Distribution of {FEATURE_INFO[feature][0].lower()} by tier**")
        hist = alt.Chart(sample).mark_bar(opacity=0.7, binSpacing=0).encode(
            alt.X(f"{feature}:Q", bin=alt.Bin(maxbins=40), title=fmt(feature)),
            alt.Y("count():Q", stack=None, title="Sites"),
            alt.Color("Tier:N", scale=tier_scale))
        st.altair_chart(hist, alt=f"Histogram of {feature} by restoration tier")
with right:
    with st.container(border=True):
        st.markdown(f"**Opportunity score vs {FEATURE_INFO[feature][0].lower()}**")
        scatter = alt.Chart(sample.sample(5_000, random_state=0)).mark_circle(size=12, opacity=0.4).encode(
            alt.X(f"{feature}:Q", scale=alt.Scale(zero=False), title=fmt(feature)),
            alt.Y("opportunity:Q", title="P(high potential)"),
            alt.Color("Tier:N", scale=tier_scale), tooltip=[feature, "opportunity"])
        st.altair_chart(scatter, alt=f"Scatter of opportunity score against {feature}")

with st.container(border=True):
    st.markdown("**Average conditions per tier**")
    summary = df.groupby("Tier", observed=True)[features].mean().T
    summary.index = [fmt(c) for c in summary.index]
    summary["High − Low"] = summary["High potential"] - summary["Low potential"]
    st.dataframe(summary, alt="Mean of each condition per restoration tier",
                 column_config={c: st.column_config.NumberColumn(format="%.4g") for c in summary.columns})

with st.container(border=True):
    st.markdown("**Correlation between conditions**")
    corr = df[features + ["opportunity"]].corr().round(2).reset_index(names="a").melt("a", var_name="b")
    heat = alt.Chart(corr).mark_rect().encode(
        alt.X("a:N", title=None, sort=None), alt.Y("b:N", title=None, sort=None),
        alt.Color("value:Q", scale=alt.Scale(scheme="redblue", domain=[-1, 1]), title="r"),
        tooltip=["a", "b", "value"])
    text = heat.mark_text(fontSize=9).encode(text="value:Q", color=alt.value("black"))
    st.altair_chart((heat + text).properties(height=520), alt="Correlation matrix of all conditions")

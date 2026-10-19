import altair as alt
import pandas as pd
import streamlit as st

from common import BEST_MODEL, FEATURE_INFO, FIGURES, PERM_IMPORTANCE, TUNED_RESULTS, load_baseline

st.title("Model performance", anchor=False)
st.caption("All scores are on held-out 10 km blocks (17,305 test sites in 49 blocks) that the models never saw. "
           f"The best model, **{BEST_MODEL}**, was chosen on spatial cross-validation, not on the test set.")

metric_cols = ["Test F1 macro", "Test ROC-AUC", "Test PR-AUC", "Test accuracy"]
with st.container(border=True):
    st.markdown("**Tuned models (randomized search, grouped 5-fold spatial CV)**")
    st.dataframe(TUNED_RESULTS, alt="Test metrics of the tuned models",
                 column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=1, format="%.3f")
                                for c in ["CV F1 macro", *metric_cols]})

left, right = st.columns(2)
with left:
    with st.container(border=True, height="stretch"):
        st.markdown("**Scores vs targets** (F1 macro > 0.75, ROC-AUC > 0.80)")
        long = TUNED_RESULTS[["Test F1 macro", "Test ROC-AUC"]].reset_index().melt("Model", var_name="Metric")
        bars = alt.Chart(long).mark_bar().encode(
            alt.X("Model:N", title=None, axis=alt.Axis(labelAngle=0)), alt.XOffset("Metric:N"),
            alt.Y("value:Q", scale=alt.Scale(domain=[0, 1]), title="Score"), alt.Color("Metric:N"),
            tooltip=["Model", "Metric", alt.Tooltip("value:Q", format=".3f")])
        rules = alt.Chart(pd.DataFrame({"y": [0.75, 0.80]})).mark_rule(strokeDash=[4, 4]).encode(y="y:Q")
        st.altair_chart(bars + rules, alt="Bar chart of test F1 macro and ROC-AUC per model with target lines")
with right:
    with st.container(border=True, height="stretch"):
        st.markdown("**Tuning gain over default hyperparameters**")
        baseline = load_baseline()
        if baseline is None:
            st.warning("results_baseline_no_tune.csv not found.")
        else:
            gain = (TUNED_RESULTS[metric_cols] - baseline[metric_cols]).dropna()
            st.dataframe(gain, alt="Difference between tuned and default models",
                         column_config={c: st.column_config.NumberColumn(format="%+.3f") for c in metric_cols})
            st.caption("Positive = tuning improved the held-out score.")

with st.container(border=True):
    st.markdown("**Which conditions matter?** Permutation importance: drop in F1 macro when a condition is shuffled")
    model = st.segmented_control("Model", list(PERM_IMPORTANCE.columns), default=BEST_MODEL, required=True)
    imp = PERM_IMPORTANCE[model].dropna().sort_values(ascending=False).reset_index()
    imp["Condition"] = imp["Feature"].map(lambda c: FEATURE_INFO[c][0])
    chart = alt.Chart(imp).mark_bar(color="#1a9850").encode(
        alt.X(f"{model}:Q", title="Drop in F1 macro"), alt.Y("Condition:N", sort="-x", title=None),
        tooltip=["Condition", alt.Tooltip(f"{model}:Q", format=".3f")])
    st.altair_chart(chart, alt=f"Permutation importance of each condition for {model}")
    if model == "CNN (2D patches)":
        st.caption("The CNN only sees 7 image layers (5×5 patches), so the NDVI and land-cover inputs are blank.")

st.subheader("Figures from the notebook", anchor=False)
figures = {
    "Model comparison": "05a_model_comparison.png",
    "Confusion matrices": "05b_confusion_matrices.png",
    "Feature importance": "06_feature_importance.png",
    "Maps per model": "07a_maps_per_model.png",
    "Best model map": "07b_map_best_model.png",
    "Model agreement": "07c_map_model_agreement.png",
    "Labels, split and errors": "07d_map_labels_split_errors.png",
    "Correlation matrix": "02_correlation_matrix.png",
    "Feature trends by year": "01a_time_varying_features_by_year.png",
}
available = {k: v for k, v in figures.items() if (FIGURES / v).exists()}
choice = st.pills("Figure", list(available), default="Model comparison", label_visibility="collapsed")
if choice:
    st.image(str(FIGURES / available[choice]), width="stretch", alt=choice)

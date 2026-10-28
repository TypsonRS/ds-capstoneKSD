import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from common import AOI_KM2, BEST_MODEL, HIGH_T, LOW_T, hex_to_rgb, load_countries, load_points
from costs import CARBON_PRICE, DISCOUNT_RATE, HORIZON_YRS, REFERENCES, SCEN_COLORS, cost_return

st.title("Cost and return", anchor=False)
st.caption(f"Cost and expected return per hectare of two general land uses, for the **high** and **low** potential "
           f"sites of the best model (**{BEST_MODEL}**). Costs and revenues are present values in USD; the expected "
           "return is the revenue if restoration succeeds × the model's probability of high potential, reduced by "
           "fire risk. Protected areas, water and built-up land are excluded.")

with st.sidebar:
    st.header("Investor settings", anchor=False)
    carbon_price = st.slider("Carbon price (USD/tCO2e)", 0.0, 50.0, CARBON_PRICE, 0.5,
                             help="Default: ARR credits 2023, Ecosystem Marketplace")
    discount_rate = st.slider("Discount rate", 0.03, 0.20, DISCOUNT_RATE, 0.01, format="%.2f")
    horizon = st.slider("Investment horizon (years)", 10, 40, HORIZON_YRS, 5)
    low_t, high_t = st.slider("Tier thresholds (low ≤ / high ≥)", 0.0, 1.0, (LOW_T, HIGH_T), 0.05,
                              help="Applied to P, the best model's probability that a site is high potential. Left "
                                   "handle: low potential if P ≤ it. Right handle: high potential if P ≥ it. Sites "
                                   "in between are uncertain and left out.")

df = load_points()
ha_per_site = AOI_KM2 * 100 / len(df)                     # each uniformly sampled site = equal share of the region
keep = (df[["protected", "water", "built_up"]].fillna(0) == 0).all(axis=1) & df["opportunity"].notna()
inv = df.loc[keep]
inv = inv.join(cost_return(inv[["opportunity", "slope", "ph", "fire_freq", "dist_to_road_m",
                                "dist_to_settlement_m"]], carbon_price, discount_rate, horizon))

LEVELS = {"High potential": f"P ≥ {high_t:.2f}", "Low potential": f"P ≤ {low_t:.2f}"}
inv["level"] = np.select([inv["opportunity"] >= high_t, inv["opportunity"] <= low_t], list(LEVELS), "Uncertain")
USES = {"Forest restoration": "forest", "Agriculture": "agri"}
LOSS = "Not profitable"
EXCLUDED = "Excluded"
MAP_COLORS = {**SCEN_COLORS, LOSS: "#8c8c8c", EXCLUDED: "#4a90d9"}
HELP = {
    "Cost": f"Present value of all costs over {horizon} years: establishment, maintenance, access, erosion "
            f"control, fire treatment and liming, discounted at {discount_rate:.0%} per year.",
    "Expected return": f"Present value of the revenue over {horizon} years if the land use succeeds, × the model's "
                       "probability of high potential, reduced by fire risk.",
    "NPV": "Net present value = expected return − cost (both in today's money). Above 0, the investment earns "
           f"more than the {discount_rate:.0%} discount rate.",
    "ROI": "Return on investment = NPV ÷ cost. The net gain per dollar invested, in today's money: 25% means "
           "every 1 USD invested brings back 1.25 USD.",
    "Profitable sites": "Share of sites in this potential level where the NPV is above 0.",
}

with st.expander("How to read NPV and ROI", icon=":material/help:", expanded=True):
    st.markdown(
        f"- **Net present value (NPV)**: all money in and out over the {horizon}-year horizon, converted to "
        f"today's value with a {discount_rate:.0%} discount rate (1 USD next year is worth "
        f"{1 / (1 + discount_rate):.2f} USD today), i.e. NPV = expected return − cost. "
        "NPV > 0: the land use pays back its costs **and** beats the discount rate. NPV < 0: it does not.\n"
        "- **Return on investment (ROI)**: NPV ÷ present value of the costs, i.e. the net gain per dollar "
        "invested. ROI = 25% means each 1 USD invested brings back 1.25 USD in today's money; "
        "ROI = −40% means only 0.60 USD comes back.")

# ---- distribution of P and the tier thresholds ----
LEVEL_COLORS = {"Low potential": "#d73027", "Uncertain": "#bdbdbd", "High potential": "#1a9850"}
with st.container(border=True):
    st.markdown("**Where the tier thresholds cut the model probability P**")
    with st.container(horizontal=True):
        for lvl, rule in [("Low potential", f"P ≤ {low_t:.2f}"), ("Uncertain", f"{low_t:.2f} < P < {high_t:.2f}"),
                          ("High potential", f"P ≥ {high_t:.2f}")]:
            n = int((inv["level"] == lvl).sum())
            st.metric(f"{lvl} ({rule})", f"{n:,} sites", f"{n / len(inv):.0%} of sites", delta_color="off",
                      delta_arrow="off", border=True)
    hist = (inv.assign(P=(np.floor(inv["opportunity"].clip(0, 0.999) * 40) / 40).round(3))   # 0.025-wide bins
            .groupby(["P", "level"]).size().rename("Sites").reset_index())
    hist["P_end"] = hist["P"] + 0.025
    bars = alt.Chart(hist).mark_bar(binSpacing=0).encode(
        alt.X("P:Q", title="P = best model's probability of high potential", scale=alt.Scale(domain=[0, 1])),
        alt.X2("P_end"), alt.Y("Sites:Q", title="Number of sites"),
        alt.Color("level:N", title=None, scale=alt.Scale(domain=list(LEVEL_COLORS), range=list(LEVEL_COLORS.values())),
                  legend=alt.Legend(orient="bottom")),
        tooltip=[alt.Tooltip("P:Q", title="P from", format=".3f"), alt.Tooltip("P_end:Q", title="P to", format=".3f"),
                 alt.Tooltip("level:N", title="Tier"), alt.Tooltip("Sites:Q", format=",")])
    cuts = pd.DataFrame({"P": [low_t, high_t], "label": [f"low ≤ {low_t:.2f}", f"high ≥ {high_t:.2f}"]})
    rules = alt.Chart(cuts).mark_rule(strokeDash=[4, 4], color="#333").encode(x="P:Q")
    text = alt.Chart(cuts).mark_text(align="left", dx=4, dy=-6, baseline="top", fontSize=11).encode(
        x="P:Q", y=alt.value(0), text="label:N")
    st.altair_chart((bars + rules + text).properties(height=300),
                    alt="Histogram of the model probability P across all investable sites, coloured by tier, "
                        "with the low and high thresholds as dashed lines")
    st.caption("Move the **Tier thresholds (low ≤ / high ≥)** slider in the sidebar: the dashed lines move, the bars change "
               "colour, and every card, chart and map below is recomputed for the new tiers.")

# ---- one card per potential level: land uses side by side ----
USE_DOT = {"Forest restoration": ":green[●]", "Agriculture": ":orange[●]"}


def signed(v, fmt):
    """Green if the land use pays back, red if it loses money."""
    return f":{'green' if v > 0 else 'red'}[**{v:{fmt}}**]".replace("-", "−")


rows = []
for col, (level, rule) in zip(st.columns(2), LEVELS.items()):
    sub = inv.loc[inv["level"] == level]
    with col, st.container(border=True, height="stretch"):
        st.subheader(f"{level} · {rule}", anchor=False)
        if sub.empty:
            st.info("No site in this range. Move the tier thresholds in the sidebar.", icon=":material/info:")
            continue
        st.caption(f"{len(sub):,} investable sites · {len(sub) * ha_per_site:,.0f} ha · "
                   f"mean P {sub['opportunity'].mean():.2f}")
        cells = {}
        for use, k in USES.items():
            cost, ret, npv = sub[f"cost_{k}"].mean(), sub[f"return_{k}"].mean(), sub[f"npv_{k}"].mean()
            profitable, best = (sub[f"npv_{k}"] > 0).mean(), (sub["best_use"] == use).mean()
            cells[use] = [f"{cost:,.0f}", f"{ret:,.0f}", signed(npv, "+,.0f"), signed(npv / cost, "+.0%"),
                          f"{profitable:.0%}", f"{best:.0%}"]
            rows.append({"Potential": level, "Land use": use, "Sites": len(sub), "Area (ha)": len(sub) * ha_per_site,
                         "Cost (USD/ha)": cost, "Expected return (USD/ha)": ret, "NPV (USD/ha)": npv,
                         "ROI": npv / cost, "Profitable sites": profitable,
                         "Total NPV (M USD)": sub[f"npv_{k}"].sum() * ha_per_site / 1e6, "Best use at": best})
        labels = ["Cost invested (USD/ha)", "Expected return (USD/ha)", "NPV (USD/ha)", "ROI",
                  "Profitable sites", "Better use on"]
        table = ["| | " + " | ".join(f"{USE_DOT[u]} **{u}**" for u in USES) + " |", "|:--|--:|--:|"]
        table += [f"| {lab} | " + " | ".join(cells[u][i] for u in USES) + " |" for i, lab in enumerate(labels)]
        st.markdown("\n".join(table))

st.caption("Values per hectare in today's money (present value over the investment horizon). "
           ":green[**Green**] = pays back (NPV > 0), :red[**red**] = loses money. Definitions: "
           "**How to read NPV and ROI** above, or hover the column names of the summary table below.")

summary = pd.DataFrame(rows)

# ---- charts ----
left, right = st.columns(2)
with left, st.container(border=True, height="stretch"):
    st.markdown("**Average cost invested vs expected return per hectare**")
    long = summary.melt(["Potential", "Land use"], ["Cost (USD/ha)", "Expected return (USD/ha)"],
                        var_name="Measure", value_name="USD/ha")
    long["Measure"] = long["Measure"].map({"Cost (USD/ha)": "Cost invested",
                                           "Expected return (USD/ha)": "Expected return"})
    long["Group"] = long["Land use"] + ", " + long["Potential"].str.replace(" potential", "")
    base = alt.Chart(long).encode(
        alt.Y("Group:N", title=None, sort=list(dict.fromkeys(long["Group"])), axis=alt.Axis(labelLimit=250)),
        alt.YOffset("Measure:N", sort=["Cost invested", "Expected return"]),
        alt.X("USD/ha:Q", title="Present value over the horizon (USD/ha)", scale=alt.Scale(nice=True)),
        tooltip=["Land use", "Potential", "Measure", alt.Tooltip("USD/ha:Q", format=",.0f")])
    bars = base.mark_bar().encode(alt.Color("Measure:N", title=None, sort=["Cost invested", "Expected return"],
                                            scale=alt.Scale(range=["#d73027", "#1a9850"]),
                                            legend=alt.Legend(orient="bottom")))
    labels = base.mark_text(align="left", dx=4, fontSize=11).encode(text=alt.Text("USD/ha:Q", format=",.0f"))
    st.altair_chart((bars + labels).properties(height=320), alt="Horizontal grouped bar chart of mean cost "
                    "invested and expected return per hectare, by land use and potential level")
    st.caption(f"Cost invested = everything paid per hectare over {horizon} years (set-up, upkeep, access, "
               f"fire and soil treatment), in today's money. Return bar longer than cost bar = NPV > 0.")
with right, st.container(border=True, height="stretch"):
    st.markdown("**Spread of NPV per hectare across sites**")
    ranked = inv.loc[inv["level"].isin(list(LEVELS))]
    sample = ranked.sample(min(6000, len(ranked)), random_state=0)
    spread = pd.concat([pd.DataFrame({"Potential": sample["level"].to_numpy(), "Land use": use,
                                      "NPV (USD/ha)": sample[f"npv_{k}"].to_numpy()}) for use, k in USES.items()])
    box = alt.Chart(spread).mark_boxplot(extent="min-max", size=28).encode(
        alt.X("Potential:N", title=None, sort=list(LEVELS), axis=alt.Axis(labelAngle=0)),
        alt.Y("NPV (USD/ha):Q"), alt.Color("Land use:N", scale=alt.Scale(domain=list(SCEN_COLORS),
                                                                         range=list(SCEN_COLORS.values())),
                                           legend=alt.Legend(orient="bottom")),
        alt.XOffset("Land use:N"))
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart(box + zero, alt="Box plot of NPV per hectare by potential level and land use; dashed line = "
                                    "break-even")
    st.caption(f"Random sample of {len(sample):,} sites. Above the dashed line the land use pays back.")

# ---- map of the better use ----
with st.container(border=True):
    level = st.segmented_control("Map", ["All tiers", "High potential", "Uncertain", "Low potential"],
                                 default="All tiers", required=True)
    cols = ["lon", "lat", "opportunity", "level", "best_use", "cost_forest", "npv_forest", "cost_agri", "npv_agri"]
    m = inv[cols] if level == "All tiers" else inv.loc[inv["level"] == level, cols]
    best_npv = np.where(m["best_use"] == "Forest restoration", m["npv_forest"], m["npv_agri"])
    m = m.assign(status=np.where(best_npv > 0, m["best_use"], LOSS))   # grey = loses money even with the better use
    if level == "All tiers":                                 # protected areas, water and built-up land: no investment
        m = pd.concat([m, df.loc[~keep, ["lon", "lat", "opportunity"]].assign(
            level="—", best_use="—", status=EXCLUDED)], ignore_index=True)
    share = m["status"].value_counts(normalize=True)
    shown = st.pills("Show", list(MAP_COLORS), default=list(MAP_COLORS), selection_mode="multi",
                     format_func=lambda s: f"{s} ({share.get(s, 0):.0%})")
    m = m.loc[m["status"].isin(shown)]
    m[["r", "g", "b"]] = np.array([hex_to_rgb(MAP_COLORS[s]) for s in m["status"]]).reshape(-1, 3)
    m["a"] = 220
    m = m.round({"lon": 5, "lat": 5, "opportunity": 2, "cost_forest": 0, "npv_forest": 0, "cost_agri": 0,
                 "npv_agri": 0})
    spacing = float(np.sqrt(AOI_KM2 / len(df)))
    layers = [pdk.Layer("ScatterplotLayer", m, id="sites", get_position=["lon", "lat"],
                        get_fill_color=["r", "g", "b", "a"], get_radius=spacing * 450, radius_min_pixels=1,
                        pickable=True, auto_highlight=True)]
    countries = load_countries()
    if countries:
        layers.append(pdk.Layer("GeoJsonLayer", countries, id="borders", stroked=True, filled=False,
                                get_line_color=[60, 60, 60], line_width_min_pixels=1.5))
    tooltip = {"html": "<b>{status}</b><br/>Tier: {level}<br/>Better use: {best_use}<br/>P(high potential): {opportunity}"
                       "<br/>Forest restoration: cost {cost_forest} · NPV {npv_forest} USD/ha"
                       "<br/>Agriculture: cost {cost_agri} · NPV {npv_agri} USD/ha"}
    st.pydeck_chart(pdk.Deck(layers=layers, tooltip=tooltip, initial_view_state=pdk.ViewState(
        latitude=float(inv["lat"].mean()), longitude=float(inv["lon"].mean()), zoom=8)), height=560,
        alt=f"Map of the better land use for {level.lower()} sites")
    st.markdown(":green[●] Forest restoration pays back · :orange[●] Agriculture pays back · "
                ":gray[●] Not profitable: loses money with either use · :blue[●] Excluded: protected area, "
                "water or built-up land (shown with **All tiers** only)")

# ---- table, download, sources ----
with st.container(border=True):
    st.markdown("**Summary per potential level and land use**")
    st.dataframe(summary, hide_index=True, alt="Cost and return summary per potential level and land use",
                 column_config={
                     "Area (ha)": st.column_config.NumberColumn(format="%,.0f"),
                     "Cost (USD/ha)": st.column_config.NumberColumn(format="%,.0f", help=HELP["Cost"]),
                     "Expected return (USD/ha)": st.column_config.NumberColumn(format="%,.0f",
                                                                               help=HELP["Expected return"]),
                     "NPV (USD/ha)": st.column_config.NumberColumn(format="%,.0f", help=HELP["NPV"]),
                     "ROI": st.column_config.NumberColumn(format="percent", help=HELP["ROI"]),
                     "Profitable sites": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent",
                                                                         help=HELP["Profitable sites"]),
                     "Total NPV (M USD)": st.column_config.NumberColumn(format="%,.1f"),
                     "Best use at": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})
    st.download_button("Download site-level costs (CSV)",
                       inv.loc[inv["level"].isin(list(LEVELS)), ["lon", "lat", "opportunity", "level", *[
                           c for c in inv.columns if c.startswith(("cost_", "return_", "npv_"))], "best_use"]]
                       .to_csv(index=False), file_name="agrorestore_cost_return.csv", mime="text/csv",
                       icon=":material/download:")

with st.expander("Inputs and sources", icon=":material/menu_book:"):
    st.dataframe(REFERENCES, hide_index=True, alt="Reference values used in the cost model")
    st.caption("Forest restoration earns carbon credits only (no species-specific products). Agriculture uses a "
               "generic cereal benchmark. Walking time to the nearest settlement and carrying loads from the "
               "nearest road are paid every year for agriculture and once for forest restoration. Files and page "
               "numbers: references/cost_return_sources/README.md.")

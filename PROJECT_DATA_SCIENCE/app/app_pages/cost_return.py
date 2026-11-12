import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from common import AOI_KM2, BEST_MODEL, HIGH_T, LOW_T, compact_deck, hex_to_rgb, load_countries, load_points
from costs import (forest_income, AGRI_INCOME_HA_YR, CARBON_PRICE, CROP_PRICE_XOF_KG, CROP_YIELD_KG_HA, FARMGATE_SHARE, CROP_COST_XOF_HA, DISCOUNT_RATE, DISCOUNT_RATE_RANGE, FOREST_EST_COST,
                   FOREST_EST_COST_RANGE, FOREST_MAINT_COST, FOREST_MAINT_COST_RANGE, FOREST_MAINT_YRS, WAGE_XOF_H,
                   XOF_PER_USD, FOREST_INCOME_HA_YR, FOREST_INCOME_HA_YR_MAX, FUELWOOD_START_YR, HORIZON_YRS, REFERENCES,
                   SCEN_COLORS, SHEA_START_YR, WORKDAY_H, cost_return)

st.title(':color[Cost and return]{foreground="#00a443"}', anchor=False)
st.caption(f"Cost and expected return per hectare of two general land uses, for the **high** and **low** potential "
           f"sites of the best model (**{BEST_MODEL}**). Costs and revenues are present values in USD; the expected "
           "return is the revenue if restoration succeeds × the model's probability of high potential, reduced by "
           "fire risk. Protected areas, water and built-up land are excluded.")

with st.sidebar:
    st.header("Investor settings", anchor=False)
    # Forest income is not a setting: the cited income lines (costs.py) feed the model unchanged. The box shows
    # their average per year over the horizon in today's money, so it follows the horizon and the discount rate.
    forest_income_ha_yr = FOREST_INCOME_HA_YR
    income_box = st.container()
    horizon = st.slider("Investment horizon (years)", 1, 40, HORIZON_YRS, 1)
    low_t, high_t = st.slider("P tier thresholds (low ≤ / high ≥)", 0.0, 1.0, (LOW_T, HIGH_T), 0.05,
                              key="cr_tiers", help="P = best model's probability of high potential. Sites with "
                                                   "P ≤ low are low potential, P ≥ high are high potential, "
                                                   "anything in between is uncertain.")
    p_min, p_max = st.slider("Probability of high potential (P)", 0.0, 1.0, (0.0, 1.0), 0.05, key="cr_p_range",
                             help="Only sites whose P lies in this range are costed. Narrow it to compare how "
                                  "cost and return change between low-P and high-P sites.")

    st.header("Cost settings", anchor=False)
    st.caption("Every slider starts at its cited reference value (see **Inputs and sources** below).")
    forest_est_cost = st.slider(
        "Forest establishment (USD/ha, once)", 0, 1500, FOREST_EST_COST, 10, key="cr_forest_est",
        help=f"Planting or assisted natural regeneration in year 1. Default {FOREST_EST_COST} USD/ha "
             f"(FAO & AUDA-NEPAD 2021, Madagascar); cited range {FOREST_EST_COST_RANGE[0]}-"
             f"{FOREST_EST_COST_RANGE[1]:,} USD/ha (Ethiopia). Farmer-managed natural regeneration costs 40-50.")
    forest_maint_cost = st.slider(
        "Forest maintenance (USD/ha/yr)", 0, 220, FOREST_MAINT_COST, 1, key="cr_forest_maint",
        help=f"Weeding, fire breaks and replanting in years 1-{FOREST_MAINT_YRS}. Default {FOREST_MAINT_COST}; "
             f"cited range {FOREST_MAINT_COST_RANGE[0]}-{FOREST_MAINT_COST_RANGE[1]} USD/ha/yr (Bodin et al. 2021).")
    # shown in USD like every other cost; the sources (and costs.py) are in FCFA, converted at XOF_PER_USD
    crop_cost_usd_ha = st.slider(
        "Crop production cost (USD/ha/yr)", 0.0, 335.0, CROP_COST_XOF_HA / XOF_PER_USD, 1.0, key="cr_crop_cost_usd",
        format="%.0f",
        help=f"Seed, fertiliser, tools and hired labour every year. Default {CROP_COST_XOF_HA / XOF_PER_USD:.0f} "
             f"USD/ha ({CROP_COST_XOF_HA:,} FCFA at {XOF_PER_USD} FCFA/USD; Togo 2022, La Cinquième 2024).")
    wage_usd_h = st.slider(
        "Farm wage (USD/hour)", 0.25, 1.00, WAGE_XOF_H / XOF_PER_USD, 0.01, key="cr_wage_usd", format="%.2f",
        help=f"Prices the labour for land clearing, stone bunds and walking to the site. Default "
             f"{WAGE_XOF_H / XOF_PER_USD:.2f} USD/h ({WAGE_XOF_H:.0f} FCFA/h at {XOF_PER_USD} FCFA/USD), the Togo "
             "minimum wage (SMIG = SMAG, 2023).")
    # same wage per year for one full-time worker: the 40-h week implied by the SMIG, 52 weeks
    st.caption(f"= **{wage_usd_h * WORKDAY_H * 5 * 52:,.0f} USD/yr** for one full-time worker "
               f"({WORKDAY_H} h/day, 5 days/week, 52 weeks)")
    crop_cost_xof_ha, wage_xof_h = crop_cost_usd_ha * XOF_PER_USD, wage_usd_h * XOF_PER_USD
    discount_rate = st.slider(
        "Discount rate", DISCOUNT_RATE_RANGE[0], DISCOUNT_RATE_RANGE[1], DISCOUNT_RATE, 0.01, key="cr_discount",
        format="percent", help=f"How much less money is worth each year later. Default {DISCOUNT_RATE:.0%} "
                               "(an assumption). A higher rate makes late income, such as forest carbon, worth less.")

df = load_points()
ha_per_site = AOI_KM2 * 100 / len(df)                     # each uniformly sampled site = equal share of the region
keep = (df[["protected", "water", "built_up"]].fillna(0) == 0).all(axis=1) & df["opportunity"].notna()
inv = df.loc[keep & df["opportunity"].between(p_min, p_max)]
if inv.empty:
    st.warning(f"No investable site with {p_min:.2f} ≤ P ≤ {p_max:.2f}. Widen the P range in the sidebar.",
               icon=":material/warning:")
    st.stop()
if (p_min, p_max) != (0.0, 1.0):
    st.info(f"Showing only sites with {p_min:.2f} ≤ P ≤ {p_max:.2f} ({len(inv):,} sites).",
            icon=":material/filter_alt:")
inv = inv.join(cost_return(inv[["opportunity", "slope", "ph", "fire_freq", "dist_to_road_m",
                                "dist_to_settlement_m"]], forest_income_ha_yr, discount_rate, horizon,
                           forest_est_cost, forest_maint_cost, crop_cost_xof_ha, wage_xof_h))

LEVELS = {"High potential": f"P ≥ {high_t:.2f}", "Low potential": f"P ≤ {low_t:.2f}"}
inv["level"] = np.select([inv["opportunity"] >= high_t, inv["opportunity"] <= low_t], list(LEVELS), "Uncertain")

# ---- forest income: average per year over the horizon, in today's money ----
# The forest earns nothing at first (carbon from year 4, fuelwood from year 6, shea from year 15), so its average
# yearly income depends on the horizon and the discount rate: present value of the income ÷ present value of 1 USD/yr.
years = np.arange(1, horizon + 1)
disc = 1 / (1 + discount_rate) ** years
income_pv = (sum(forest_income(forest_income_ha_yr, horizon).values()) * disc).sum()
income_per_year = income_pv / disc.sum()
# agriculture earns the same from year 1, so its average is computed the same way for a like-for-like comparison
agri_per_year = (np.full(horizon, AGRI_INCOME_HA_YR) * disc).sum() / disc.sum()
gap = income_per_year - agri_per_year                      # changes with the horizon and the discount rate
with income_box, st.container(horizontal=True):
    st.metric("Forest income (USD/ha/yr)", f"{income_per_year:,.0f}", f"{gap:+,.0f} vs agriculture".replace("-", "−"),
              border=True,
              help=f"Average money one hectare of restored forest earns per year over the {horizon}-year horizon, "
                   f"in today's money at the {discount_rate:.0%} discount rate. It updates automatically with the "
                   f"horizon and the discount rate. In full production the forest earns {forest_income_ha_yr:.0f} "
                   f"USD/ha/yr: carbon credits at {CARBON_PRICE} USD/t (2023 average) from year 4, fuelwood (FAO "
                   f"1983, Central Togo prices) from year {FUELWOOD_START_YR} and shea kernels (FAO & Global Shea "
                   f"Alliance 2020) from year {SHEA_START_YR}, minus the carbon the burnt wood no longer earns. "
                   "Before the model probability and fire risk. Details: **Inputs and sources** below.")
    st.metric("Agriculture income (USD/ha/yr)", f"{agri_per_year:,.0f}",
              f"{-gap:+,.0f} vs forest".replace("-", "−"), border=True,
              help=f"Average money one hectare of cereal earns per year over the {horizon}-year horizon, in today's "
                   f"money at the {discount_rate:.0%} discount rate: {CROP_YIELD_KG_HA:,} kg/ha × "
                   f"{CROP_PRICE_XOF_KG} FCFA/kg retail × {FARMGATE_SHARE:.0%} farm-gate share ÷ {XOF_PER_USD} "
                   "FCFA/USD. Harvests start in year 1, so the average stays the same whatever the horizon or "
                   "discount rate; the difference with the forest (green or red below the value) moves with them. "
                   "Before the crop production cost, the model probability and fire risk.")

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
            st.info("**No investable sites** in this range. Move the tier thresholds or the P range in the sidebar.",
                    icon=":material/info:")
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
        table = [f"| **Total money (USD/ha/{horizon} yr)** | " + " | ".join(f"{USE_DOT[u]} **{u}**" for u in USES) + " |", "|:--|--:|--:|"]
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
    # One layer per status with a fixed colour, and short column names: about 5 times less data is sent to the
    # browser than one layer with a colour and the full tooltip on every one of the 100,000 sites.
    spacing = float(np.sqrt(AOI_KM2 / len(df)))
    layers = []
    for s in shown:
        part = m.loc[m["status"] == s]
        if part.empty:
            continue
        pts = pd.DataFrame({"x": part["lon"].round(4), "y": part["lat"].round(4), "p": part["opportunity"].round(2),
                            "s": s, "nf": part["npv_forest"].round(0), "na": part["npv_agri"].round(0)})
        layers.append(pdk.Layer("ScatterplotLayer", pts, id=f"sites-{s}", get_position=["x", "y"],
                                get_fill_color=[*hex_to_rgb(MAP_COLORS[s]), 220], get_radius=spacing * 450,
                                radius_min_pixels=1, pickable=True, auto_highlight=True))
    countries = load_countries()
    if countries:
        layers.append(pdk.Layer("GeoJsonLayer", countries, id="borders", stroked=True, filled=False,
                                get_line_color=[60, 60, 60], line_width_min_pixels=1.5))
    tooltip = {"html": "<b>{s}</b><br/>P(high potential): {p}"
                       "<br/>NPV forest restoration: {nf} USD/ha<br/>NPV agriculture: {na} USD/ha"}
    st.pydeck_chart(compact_deck(layers=layers, tooltip=tooltip, initial_view_state=pdk.ViewState(
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
    st.download_button("Download site-level costs (CSV)",            # built only when clicked
                       lambda: inv.loc[inv["level"].isin(list(LEVELS)), ["lon", "lat", "opportunity", "level", *[
                           c for c in inv.columns if c.startswith(("cost_", "return_", "npv_"))], "best_use"]]
                       .to_csv(index=False), file_name="agrorestore_cost_return.csv", mime="text/csv",
                       icon=":material/download:")

with st.expander("Inputs and sources", icon=":material/menu_book:"):
    st.dataframe(REFERENCES, hide_index=True, alt="Reference values used in the cost model")
    st.caption("Forest restoration earns carbon credits, shea kernels and sustainable fuelwood together (the burnt "
               "fuelwood is deducted from the carbon credits). The values below set the default of **Forest income** "
               "in the sidebar; the slider scales all of them together. Non-market ecosystem services "
               "(water, soil, biodiversity) are real but not paid to the investor, so they are not in the NPV. "
               "Agriculture uses a generic cereal benchmark. Walking time to the nearest settlement and carrying "
               "loads from the nearest road are paid every year for agriculture and once for forest restoration. "
               "Files and page numbers: references/cost_return_sources/README.md.")

"""Cost and return per hectare for two general land uses (mirrors section 11 of AgroRestoreAI.ipynb).

Sources for every value: references/cost_return_sources/README.md. Values marked ASSUMPTION have no reference.
"""

import numpy as np
import pandas as pd
import streamlit as st

# ============================ REFERENCE DATA ============================
XOF_PER_USD = 600        # World Bank WDI PA.NUS.FCRF, Togo 2022-2025

# ---- Forest carbon: IPCC 2019 Refinement Vol. 4 Ch. 4 + IPCC 2006 Table 4.3 ----
AGB_GROWTH_T_DM = 3.9    # Table 4.9: Africa, tropical dry forest, secondary <= 20 yr (t d.m./ha/yr)
ROOT_SHOOT = 0.332       # Table 4.4: Africa, tropical dry forest, natural, AGB <= 125 t/ha
CARBON_FRACTION = 0.47   # IPCC 2006 Table 4.3, tropical forest
CREDIT_SHARE = 0.8       # ASSUMPTION: share sold after buffer / uncertainty deductions
CO2_T_HA_YR = AGB_GROWTH_T_DM * (1 + ROOT_SHOOT) * CARBON_FRACTION * 44 / 12   # ~8.9 tCO2e/ha/yr
CARBON_PRICE = 15.6      # Ecosystem Marketplace, State of the VCM 2023, Table 4: ARR credits 2023

# ---- Forest restoration costs ----
FOREST_EST_COST = 680    # FAO & AUDA-NEPAD 2021 (Madagascar; Ethiopia 87-1,445 USD/ha)
FOREST_MAINT_COST = 50   # Bodin et al. 2021 (FAO TEER): 2-213 USD/ha/yr
FOREST_MAINT_YRS = 5     # Bodin et al. 2021: maintenance years 1-5

# ---- Forest products besides carbon (optional) ----
SHEA_KERNEL_KG_HA = 60   # Bockel et al. 2020 (FAO & GSA), Table 4: improved parklands, 0.060 t/ha
SHEA_USD_KG = 23.96 / 85 # same report, Table 6: price per 85-kg bag sold by collecting women
SHEA_START_YR = 15       # same report, p. 3: shea starts fruiting at about 15 years (Hofer 2009)
FUELWOOD_M3_HA = 1.0     # de Montalembert & Clement 1983 (FAO), ch. IV: wooded savanna 0.8-1.2 m3/ha/yr
FUELWOOD_T_M3 = 696_256.94 / 838_863.78  # Kaina et al. 2020, Region Centrale: tonnes / m3 of fuelwood
FUELWOOD_XOF_KG = 23.6   # same study: mean fuelwood price, Region Centrale 2019-2020
WOOD_DENSITY = 0.53      # IPCC 2006 Table 4.13: Daniellia oliveri (t d.m./m3)
FUELWOOD_START_YR = 6    # ASSUMPTION: first harvest after the maintenance years
# carbon not credited because the harvested wood is burnt
FUELWOOD_CO2_HA = FUELWOOD_M3_HA * WOOD_DENSITY * CARBON_FRACTION * 44 / 12

# ---- Agriculture: generic cereal benchmark for Togo ----
CROP_YIELD_KG_HA = 1198  # World Bank WDI AG.YLD.CREL.KG (FAO), Togo 2024
CROP_PRICE_XOF_KG = 231  # WFP market prices (HDX): median retail maize, Centrale, 2021-2026
FARMGATE_SHARE = 0.75    # ASSUMPTION: producer price vs retail
CROP_COST_XOF_HA = 96_700  # production cost per ha, Togo 2022 (La Cinquieme)

# ---- Site extras ----
WAGE_XOF_H = 302.89      # Togo SMIG = SMAG, 2023
WORKDAY_H = 8            # 40-h week implied by the SMIG
WAGE_USD_DAY = WAGE_XOF_H * WORKDAY_H / XOF_PER_USD
WALK_KMH = 5.0           # Tobler (1993), flat ground
HEADLOAD_USD_TKM = 1.5   # Starkey et al. 2002 in Hine 2014 (World Bank SSATP WP 100)
CROP_LABOUR_DAYS = 88    # Amegbeto (FAO), Togo, Table 9: manual maize
CLEARING_DAYS = 30       # same study, Table 14
FOREST_LABOUR_DAYS = 100 # FAO SFM Toolbox: 50-150 person-days/ha, years 1-3
SEEDLINGS_HA = 1000      # Trillion Trees 2022, p. 8
SEEDLING_KG = 1.0        # ASSUMPTION
BUND_DAYS = 75           # Critchley 1991: stone bunds 50-100 person-days/ha
FIRE_TREAT_USD_HA = 62.02  # Barnes et al. 2020, Ghana: prescribed burning
LIME_USD_T = 107         # Jaleta et al. 2024
LIME_T_HA = 0.86         # same study, maize fields
LIME_EFFECT_YRS = 4      # same study (ASSUMPTION: one main season per year)

SLOPE_FREE_DEG = 2       # ASSUMPTION: bunds needed above this slope
LOW_PH = 5.5             # acidic soil threshold
HORIZON_YRS = 20
DISCOUNT_RATE = 0.10     # ASSUMPTION

SCENARIOS = {
    "Forest restoration": dict(
        base_cost_ha=FOREST_EST_COST, yearly_cost_ha=FOREST_MAINT_COST, yearly_cost_yrs=FOREST_MAINT_YRS,
        labour_days=FOREST_LABOUR_DAYS, haul_t=SEEDLINGS_HA * SEEDLING_KG / 1000, access_yearly=False,
        bund_cost_ha=0, fire_cost_ha_yr=FIRE_TREAT_USD_HA, lime_cost_ha=0,
        carbon=True, revenue_start_yr=4, fire_loss=0.6),          # ASSUMPTION: revenue start, fire loss
    "Agriculture": dict(
        base_cost_ha=CLEARING_DAYS * WAGE_USD_DAY, yearly_cost_ha=CROP_COST_XOF_HA / XOF_PER_USD,
        yearly_cost_yrs=None, labour_days=CROP_LABOUR_DAYS, haul_t=CROP_YIELD_KG_HA / 1000, access_yearly=True,
        bund_cost_ha=BUND_DAYS * WAGE_USD_DAY, fire_cost_ha_yr=0, lime_cost_ha=LIME_T_HA * LIME_USD_T,
        carbon=False, revenue_start_yr=1, fire_loss=0.2),          # ASSUMPTION: fire loss
}
SCEN_COLORS = {"Forest restoration": "#1a9850", "Agriculture": "#fdae61"}

# forest income lines at the cited values: (USD/ha/yr in full production, first year)
FOREST_INCOME_LINES = {
    "Carbon credits": (CO2_T_HA_YR * CREDIT_SHARE * CARBON_PRICE,
                       SCENARIOS["Forest restoration"]["revenue_start_yr"]),
    "Shea kernels": (SHEA_KERNEL_KG_HA * SHEA_USD_KG, SHEA_START_YR),
    "Fuelwood": (FUELWOOD_M3_HA * FUELWOOD_T_M3 * 1000 * FUELWOOD_XOF_KG * FARMGATE_SHARE / XOF_PER_USD,
                 FUELWOOD_START_YR),
    "Carbon lost to fuelwood": (-FUELWOOD_CO2_HA * CREDIT_SHARE * CARBON_PRICE, FUELWOOD_START_YR),  # wood is burnt
}
FOREST_INCOME_HA_YR = sum(usd for usd, _ in FOREST_INCOME_LINES.values())   # ~142 USD/ha/yr
# top of the cited ranges (carbon price has no cited maximum, so it stays at the 2023 average)
SHEA_KERNEL_KG_HA_MAX = 84   # Bockel et al. 2020, Table 4: improved parklands, upgraded value chain, 0.084 t/ha
FUELWOOD_M3_HA_MAX = 1.2     # de Montalembert & Clement 1983: 0.8-1.2 m3/ha/yr
FUELWOOD_XOF_KG_MAX = 28     # Kaina et al. 2020: 20-28 FCFA/kg
FOREST_INCOME_HA_YR_MAX = (
    CO2_T_HA_YR * CREDIT_SHARE * CARBON_PRICE + SHEA_KERNEL_KG_HA_MAX * SHEA_USD_KG
    + FUELWOOD_M3_HA_MAX * FUELWOOD_T_M3 * 1000 * FUELWOOD_XOF_KG_MAX * FARMGATE_SHARE / XOF_PER_USD
    - FUELWOOD_M3_HA_MAX * WOOD_DENSITY * CARBON_FRACTION * 44 / 12 * CREDIT_SHARE * CARBON_PRICE)   # ~157

REFERENCES = pd.DataFrame(
    [("Carbon removal (forest)", f"{CO2_T_HA_YR:.1f} tCO2e/ha/yr", "IPCC 2019 Tables 4.4, 4.9; IPCC 2006 Table 4.3"),
     ("Carbon price", f"{CARBON_PRICE} USD/t", "Ecosystem Marketplace, State of the VCM 2023"),
     ("Forest establishment", f"{FOREST_EST_COST} USD/ha", "FAO & AUDA-NEPAD 2021"),
     ("Forest maintenance", f"{FOREST_MAINT_COST} USD/ha/yr, years 1-{FOREST_MAINT_YRS}", "Bodin et al. 2021 (FAO)"),
     ("Shea kernels (forest)", f"{SHEA_KERNEL_KG_HA} kg/ha/yr x {SHEA_USD_KG:.2f} USD/kg from year {SHEA_START_YR}",
      "Bockel et al. 2020, FAO & Global Shea Alliance, Tables 4 and 6, p. 3"),
     ("Fuelwood (forest)", f"{FUELWOOD_M3_HA:g} m3/ha/yr x {FUELWOOD_T_M3:.2f} t/m3 x {FUELWOOD_XOF_KG} FCFA/kg "
      f"from year {FUELWOOD_START_YR}", "de Montalembert & Clement 1983 (FAO Forestry Paper); Kaina et al. 2020"),
     ("Carbon lost to fuelwood", f"{FUELWOOD_CO2_HA:.2f} tCO2e/ha/yr (wood density {WOOD_DENSITY})",
      "IPCC 2006 Tables 4.3, 4.13"),
     ("Crop yield", f"{CROP_YIELD_KG_HA:,} kg/ha", "World Bank WDI (FAO), Togo 2024"),
     ("Crop price", f"{CROP_PRICE_XOF_KG} FCFA/kg retail", "WFP market prices, Centrale 2021-2026"),
     ("Crop production cost", f"{CROP_COST_XOF_HA:,} FCFA/ha/yr", "La Cinquieme 2024 (Togo 2022)"),
     ("Wage", f"{WAGE_XOF_H} FCFA/h", "Togo SMIG/SMAG 2023"),
     ("Walking speed", f"{WALK_KMH:g} km/h", "Tobler 1993"),
     ("Head-loading", f"{HEADLOAD_USD_TKM} USD/t-km", "Hine 2014, World Bank SSATP WP 100"),
     ("Labour, agriculture", f"{CROP_LABOUR_DAYS} person-days/ha/yr", "Amegbeto (FAO), Togo"),
     ("Labour, forest", f"{FOREST_LABOUR_DAYS} person-days/ha", "FAO SFM Toolbox"),
     ("Stone bunds", f"{BUND_DAYS} person-days/ha", "Critchley 1991"),
     ("Fire fuel treatment", f"{FIRE_TREAT_USD_HA} USD/ha", "Barnes et al. 2020, Ghana"),
     ("Lime", f"{LIME_T_HA} t/ha x {LIME_USD_T} USD/t every {LIME_EFFECT_YRS} yr", "Jaleta et al. 2024"),
     ("Exchange rate", f"{XOF_PER_USD} FCFA/USD", "World Bank WDI")],
    columns=["Input", "Value", "Source"])


def forest_income(total: float, horizon: int) -> dict:
    """Forest income per hectare for each year 1..horizon (USD, not discounted), one array per income line.
    total = combined USD/ha/yr in full production; every line is scaled by the same factor and keeps its start
    year. Before the model probability and fire risk, which cost_return() applies per site."""
    years = np.arange(1, horizon + 1)
    scale = total / FOREST_INCOME_HA_YR
    return {name: np.where(years >= start, usd * scale, 0.0) for name, (usd, start) in FOREST_INCOME_LINES.items()}


@st.cache_data(max_entries=20, show_spinner="Costing every site...")
def cost_return(df: pd.DataFrame, forest_income_ha_yr: float = FOREST_INCOME_HA_YR,
                discount_rate: float = DISCOUNT_RATE, horizon: int = HORIZON_YRS) -> pd.DataFrame:
    """Cost, expected return and NPV per hectare (present values, USD) of both land uses for every site.
    Expects the columns of common.load_points(): opportunity, slope, ph, fire_freq and the two OSM distances.
    forest_income_ha_yr: combined forest income (carbon + shea + fuelwood) in full production, USD/ha/yr."""
    years = np.arange(1, horizon + 1)
    disc = 1 / (1 + discount_rate) ** years
    pv_lime = disc[(years - 1) % LIME_EFFECT_YRS == 0].sum()
    fire = df["fire_freq"].fillna(0)
    d_settle_km = df["dist_to_settlement_m"].fillna(df["dist_to_settlement_m"].max()) / 1000   # as the notebook
    d_road_km = df["dist_to_road_m"].fillna(df["dist_to_road_m"].max()) / 1000

    out = pd.DataFrame(index=df.index)
    for name, s in SCENARIOS.items():
        k = "forest" if s["carbon"] else "agri"
        if s["carbon"]:
            yearly_rev = sum(forest_income(forest_income_ha_yr, horizon).values(), np.zeros(horizon))
        else:
            yearly_rev = np.where(years >= s["revenue_start_yr"],
                                  CROP_YIELD_KG_HA * CROP_PRICE_XOF_KG * FARMGATE_SHARE / XOF_PER_USD, 0.0)
        access = (s["labour_days"] * 2 * d_settle_km / WALK_KMH * WAGE_XOF_H / XOF_PER_USD
                  + s["haul_t"] * d_road_km * HEADLOAD_USD_TKM)
        once = (s["base_cost_ha"] + np.where(df["slope"] > SLOPE_FREE_DEG, s["bund_cost_ha"], 0)
                + (0 if s["access_yearly"] else access))
        every_year = s["fire_cost_ha_yr"] * fire + (access if s["access_yearly"] else 0)
        maint = disc if s["yearly_cost_yrs"] is None else disc[years <= s["yearly_cost_yrs"]]
        pv_rev = (yearly_rev * disc).sum()
        out[f"cost_{k}"] = (once + s["yearly_cost_ha"] * maint.sum() + every_year * disc.sum()
                            + np.where(df["ph"] < LOW_PH, s["lime_cost_ha"], 0) * pv_lime)
        out[f"return_{k}"] = df["opportunity"] * (1 - s["fire_loss"] * fire) * pv_rev
        out[f"npv_{k}"] = out[f"return_{k}"] - out[f"cost_{k}"]
    out["best_use"] = np.where(out["npv_forest"] / out["cost_forest"] >= out["npv_agri"] / out["cost_agri"],
                               "Forest restoration", "Agriculture")
    return out

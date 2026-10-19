"""Shared paths, constants and cached loaders for the AgroRestore AI app.

Everything here reads the files written by AgroRestoreAI.ipynb, so run the notebook first.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ============================ PATHS ============================
ROOT = Path(__file__).resolve().parents[1]           # PROJECT_DATA_SCIENCE/
DATA_PROCESSED = ROOT / "data" / "DATA_PROCESSED"
FIGURES = ROOT / "reports" / "FIGURES"
FEATURES_GPKG = DATA_PROCESSED / "week1_features_sample.gpkg"
PREDICTIONS_GPKG = DATA_PROCESSED / "predictions.gpkg"
MODELS_PKL = DATA_PROCESSED / "models.pkl"
BASELINE_CSV = ROOT / "results_baseline_no_tune.csv"
COUNTRIES_SHP = ROOT / "data" / "countries_near_aoi.shp"

# ============================ SETTINGS (mirrors the notebook) ============================
REGION = "Centrale Region, Togo"
AOI_KM2 = 13_242                       # study frame area printed by the notebook (sum of the tier areas)
HIGH_T, LOW_T = 0.60, 0.40             # tiers: >= 0.60 high | <= 0.40 low | in between uncertain
LABEL_LOW, LABEL_HIGH = -0.000726, 0.000898   # ndvi_trend quantiles (30% / 70%) used for the labels
BEST_MODEL = "Random Forest"           # chosen on spatial-CV F1 macro

MODEL_COLS = {
    "Random Forest": "opportunity_random_forest",
    "XGBoost": "opportunity_xgboost",
    "Logistic Regression": "opportunity_logistic_regression",
    "CNN (2D patches)": "opportunity_cnn_2d_patches",
}

PREDICTORS = ["precipitation_mean", "soil_moisture", "tmean", "soc", "ph", "elevation", "slope",
              "built_up", "ndvi_mean", "ndvi_resilience", "ndvi_std", "tmax", "protected", "tmin", "water"]

FEATURE_INFO = {   # label, unit, source
    "precipitation_mean": ("Mean daily rainfall", "mm/day", "CHIRPS 2006-2024"),
    "soil_moisture": ("Soil moisture (Jul-Oct)", "mm", "TerraClimate"),
    "tmean": ("Mean temperature", "°C", "TerraClimate"),
    "tmin": ("Min temperature", "°C", "TerraClimate"),
    "tmax": ("Max temperature", "°C", "TerraClimate"),
    "soc": ("Soil organic carbon (0-20 cm)", "g/kg", "iSDAsoil"),
    "ph": ("Soil pH (0-20 cm)", "", "iSDAsoil"),
    "elevation": ("Elevation", "m", "SRTM"),
    "slope": ("Slope", "°", "SRTM"),
    "built_up": ("Built-up", "0/1", "ESA WorldCover"),
    "water": ("Water", "0/1", "ESA WorldCover"),
    "protected": ("Protected area", "0/1", "WDPA"),
    "ndvi_mean": ("NDVI mean", "", "MODIS 2006-2025"),
    "ndvi_std": ("NDVI std", "", "MODIS 2006-2025"),
    "ndvi_resilience": ("NDVI resilience (mean / std)", "", "MODIS 2006-2025"),
    "ndvi_trend": ("NDVI trend (label source)", "NDVI/yr", "MODIS 2006-2025"),
    "fire_freq": ("Fire frequency", "share of years", "MODIS MCD64A1"),
}

TIER_NAMES = ["Low potential", "Uncertain", "High potential"]
TIER_COLORS = ["#d73027", "#fee08b", "#1a9850"]

# Results printed by the notebook (section 7b, tuned with spatial CV) -------------------------
TUNED_RESULTS = pd.DataFrame(
    {"CV F1 macro":   [0.738, 0.733, 0.666, 0.710],
     "Test accuracy": [0.760, 0.761, 0.708, 0.736],
     "Test F1 macro": [0.760, 0.761, 0.707, 0.736],
     "Test ROC-AUC":  [0.842, 0.845, 0.774, 0.790],
     "Test PR-AUC":   [0.818, 0.822, 0.727, 0.742],
     "Training time (s)": [1682, 456, 82, 1977]},
    index=pd.Index(["Random Forest", "XGBoost", "Logistic Regression", "CNN (2D patches)"], name="Model"))

# Permutation importance printed by the notebook (section 9, drop in F1 macro on held-out blocks)
PERM_IMPORTANCE = pd.DataFrame(
    {"Random Forest":       [0.065, 0.034, 0.027, 0.026, 0.019, 0.011, 0.010, 0.009, 0.008, 0.006, 0.006, 0.003, 0.001, 0.001, 0.000],
     "Logistic Regression": [0.033, 0.041, 0.064, 0.248, 0.135, 0.100, 0.019, 0.132, 0.002, 0.110, 0.179, 0.000, 0.005, 0.004, 0.000],
     "XGBoost":             [0.072, 0.047, 0.016, 0.023, 0.025, 0.026, 0.013, 0.012, 0.011, 0.011, 0.020, 0.004, 0.004, 0.002, 0.000],
     "CNN (2D patches)":    [0.164, 0.153, np.nan, np.nan, np.nan, 0.106, np.nan, np.nan, 0.069, 0.179, np.nan, 0.021, 0.045, np.nan, np.nan]},
    index=pd.Index(["soil_moisture", "elevation", "ndvi_std", "ndvi_resilience", "tmin", "soc", "protected",
                    "ndvi_mean", "precipitation_mean", "tmean", "tmax", "slope", "ph", "built_up", "water"],
                   name="Feature"))


# ============================ HELPERS ============================
def tier_of(p):
    """0 = low, 1 = uncertain, 2 = high (same rule as the notebook maps)."""
    p = np.asarray(p, dtype=float)
    return np.where(p >= HIGH_T, 2, np.where(p <= LOW_T, 0, 1))


def hex_to_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def rdylgn(p):
    """Matplotlib-free RdYlGn colormap -> (n, 3) uint8 array."""
    stops = np.array([[165, 0, 38], [215, 48, 39], [244, 109, 67], [253, 174, 97], [254, 224, 139],
                      [255, 255, 191], [217, 239, 139], [166, 217, 106], [102, 189, 99], [26, 152, 80],
                      [0, 104, 55]], dtype=float)
    x = np.clip(np.nan_to_num(np.asarray(p, dtype=float), nan=0.5), 0, 1) * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    f = (x - i)[:, None]
    return (stops[i] * (1 - f) + stops[i + 1] * f).astype(np.uint8)


# ============================ CACHED LOADERS ============================
@st.cache_data(show_spinner="Loading sampled points and predictions...")
def load_points() -> pd.DataFrame:
    """Features of the 99,913 sampled points + the opportunity score of every model (same row order)."""
    import geopandas as gpd

    feats = gpd.read_file(FEATURES_GPKG)
    preds = gpd.read_file(PREDICTIONS_GPKG)
    if len(feats) != len(preds) or not np.allclose(feats.geometry.x.values, preds.geometry.x.values):
        raise RuntimeError("Features and predictions are not aligned - re-run the notebook.")

    df = pd.DataFrame(feats.drop(columns=["geometry", "dummy", "proxy_target", "dist_to_road_m",
                                          "dist_to_settlement_m"], errors="ignore"))
    df["lon"], df["lat"] = feats.geometry.x.values, feats.geometry.y.values
    for col in ["opportunity", *MODEL_COLS.values()]:
        df[col] = preds[col].values
    df["tier"] = tier_of(df["opportunity"])
    df["label"] = np.where(df["ndvi_trend"] >= LABEL_HIGH, "high",
                           np.where(df["ndvi_trend"] <= LABEL_LOW, "low", "middle (not used)"))
    return df


@st.cache_data
def load_countries():
    import geopandas as gpd

    if not COUNTRIES_SHP.exists():
        return None
    return gpd.read_file(COUNTRIES_SHP).to_crs("EPSG:4326").__geo_interface__


@st.cache_data
def load_baseline() -> pd.DataFrame | None:
    return pd.read_csv(BASELINE_CSV, index_col="Model") if BASELINE_CSV.exists() else None


@st.cache_resource(show_spinner="Loading the trained models (about 15 s, once)...")
def load_models() -> dict:
    """models.pkl from the notebook: RF, LR and XGBoost pipelines (the CNN needs image patches, so it is not here)."""
    import joblib

    return joblib.load(MODELS_PKL)

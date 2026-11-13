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

# Compressed copies for the online app (written by app/prepare_deploy.py, committed to git). Used only when the
# full-size files above are missing, as on Streamlit Community Cloud (models.pkl and the patches are > 100 MB).
DEPLOY_DIR = ROOT / "deploy"
DEPLOY_MODELS = DEPLOY_DIR / "models.joblib.xz"
DEPLOY_PATCHES = DEPLOY_DIR / "P_all.npz"

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
    "dist_to_road_m": ("Distance to nearest road", "m", "OpenStreetMap"),
    "dist_to_settlement_m": ("Distance to nearest settlement", "m", "OpenStreetMap"),
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
    {"CV F1 macro":   [0.738, 0.733, 0.666, 0.729],
     "Test accuracy": [0.760, 0.761, 0.708, 0.767],
     "Test F1 macro": [0.760, 0.761, 0.707, 0.767],
     "Test ROC-AUC":  [0.842, 0.845, 0.774, 0.836],
     "Test PR-AUC":   [0.818, 0.822, 0.727, 0.776],
     "Training time (s)": [1576, 554, 105, 1842]},
    index=pd.Index(["Random Forest", "XGBoost", "Logistic Regression", "CNN (2D patches)"], name="Model"))

# Permutation importance printed by the notebook (section 9, drop in F1 macro on held-out blocks)
PERM_IMPORTANCE = pd.DataFrame(
    {"Random Forest":       [0.065, 0.034, 0.027, 0.026, 0.019, 0.011, 0.010, 0.009, 0.008, 0.006, 0.006, 0.003, 0.001, 0.001, 0.000],
     "Logistic Regression": [0.033, 0.041, 0.064, 0.248, 0.135, 0.100, 0.019, 0.132, 0.002, 0.110, 0.179, 0.000, 0.005, 0.004, 0.000],
     "XGBoost":             [0.072, 0.047, 0.016, 0.023, 0.025, 0.026, 0.013, 0.012, 0.011, 0.011, 0.020, 0.004, 0.004, 0.002, 0.000],
     "CNN (2D patches)":    [0.069, 0.112, 0.039, 0.040, 0.034, 0.110, 0.050, 0.052, 0.032, 0.055, 0.043, 0.035, 0.017, 0.017, 0.000]},
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


def dot(color):
    """Legend marker in the exact colour the map uses (Streamlit's :red[] etc. are theme tints)."""
    return f'<span style="color:{color};font-size:1.3em;line-height:1">&#9679;</span>'


def compact_deck(**kwargs):
    """A pydeck Deck whose JSON has no indentation. pydeck writes indent=2, which roughly triples the size of
    100,000 map points sent to the browser on every rerun. The map itself is unchanged."""
    import json

    import pydeck as pdk
    from pydeck.bindings.json_tools import default_serialize

    class _CompactDeck(pdk.Deck):
        def to_json(self):
            return json.dumps(self, sort_keys=True, default=default_serialize, separators=(",", ":"))

    return _CompactDeck(**kwargs)


# RdYlGn end/mid points as hex, for continuous-scale legends
RDYLGN_HEX = {0: "#a50026", 0.5: "#ffffbf", 1: "#006837"}


def rdylgn(p):
    """Matplotlib-free RdYlGn colormap -> (n, 3) uint8 array."""
    stops = np.array([[165, 0, 38], [215, 48, 39], [244, 109, 67], [253, 174, 97], [254, 224, 139],
                      [255, 255, 191], [217, 239, 139], [166, 217, 106], [102, 189, 99], [26, 152, 80],
                      [0, 104, 55]], dtype=float)
    x = np.clip(np.nan_to_num(np.asarray(p, dtype=float), nan=0.5), 0, 1) * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    f = (x - i)[:, None]
    return (stops[i] * (1 - f) + stops[i + 1] * f).astype(np.uint8)


@st.cache_data(max_entries=30, show_spinner=False)
def surface_png(lon, lat, rgb, spacing_km, boundary=None, reach=2.5, max_px=1200):
    """Wall-to-wall image like the notebook's folium overlay: every pixel takes the colour of its nearest
    sample point (up to `reach` point spacings away), clipped to the region boundary when one is given.
    Returns (PNG data URL, [west, south, east, north]) for a pydeck BitmapLayer."""
    import base64
    import io

    import shapely
    from PIL import Image
    from scipy.spatial import cKDTree

    lon, lat, rgb = np.asarray(lon, float), np.asarray(lat, float), np.asarray(rgb, np.uint8)
    kx = np.cos(np.deg2rad(lat.mean()))
    geom = shapely.geometry.shape(boundary["features"][0]["geometry"]) if boundary else None
    pad = spacing_km / 110.57
    west, south, east, north = geom.bounds if geom is not None else (
        lon.min() - pad / kx, lat.min() - pad, lon.max() + pad / kx, lat.max() + pad)

    # pixels of about a third of the point spacing, capped at max_px on the long side
    w_km, h_km = (east - west) * kx * 111.32, (north - south) * 110.57
    px_km = max(spacing_km / 3, max(w_km, h_km) / max_px)
    W, H = max(int(np.ceil(w_km / px_km)), 1), max(int(np.ceil(h_km / px_km)), 1)
    X, Y = np.meshgrid(west + (np.arange(W) + 0.5) * (east - west) / W,
                       north - (np.arange(H) + 0.5) * (north - south) / H)

    dist, idx = cKDTree(np.column_stack([lon * kx, lat])).query(
        np.column_stack([X.ravel() * kx, Y.ravel()]), distance_upper_bound=reach * spacing_km / 110.57)
    keep = np.isfinite(dist)
    if geom is not None:
        keep &= shapely.contains_xy(geom, X.ravel(), Y.ravel())

    img = np.zeros((H * W, 4), dtype=np.uint8)
    img[keep, :3] = rgb[idx[keep]]
    img[keep, 3] = 225
    buf = io.BytesIO()
    Image.fromarray(img.reshape(H, W, 4), "RGBA").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), [west, south, east, north]


def hexbin_mean(lon, lat, values, size_km=2.5, min_points=3):
    """Average of `values` per pointy-top hexagon (size = centre-to-corner in km), like plt.hexbin in the notebook.
    Returns one row per hexagon: polygon (list of [lon, lat]), mean, count."""
    lat0 = float(np.mean(lat))
    kx, ky = 111.32 * np.cos(np.deg2rad(lat0)), 110.57                    # km per degree
    x, y = np.asarray(lon) * kx, np.asarray(lat) * ky

    # axial coordinates, rounded to the nearest hexagon (cube rounding)
    q = (np.sqrt(3) / 3 * x - y / 3) / size_km
    r = (2 / 3 * y) / size_km
    s = -q - r
    rq, rr, rs = np.round(q), np.round(r), np.round(s)
    dq, dr, ds = np.abs(rq - q), np.abs(rr - r), np.abs(rs - s)
    fix_q = (dq > dr) & (dq > ds)
    fix_r = ~fix_q & (dr > ds)
    rq = np.where(fix_q, -rr - rs, rq)
    rr = np.where(fix_r, -rq - rs, rr)

    g = (pd.DataFrame({"q": rq.astype(int), "r": rr.astype(int), "v": values})
         .dropna().groupby(["q", "r"])["v"].agg(["mean", "count"]).reset_index())
    g = g.loc[g["count"] >= min_points]

    cx = size_km * np.sqrt(3) * (g["q"] + g["r"] / 2)
    cy = size_km * 1.5 * g["r"]
    ang = np.deg2rad(30 + 60 * np.arange(6))
    g["polygon"] = [[[(px + size_km * np.cos(a)) / kx, (py + size_km * np.sin(a)) / ky] for a in ang]
                    for px, py in zip(cx, cy)]
    return g[["polygon", "mean", "count"]].reset_index(drop=True)


# ============================ CACHED LOADERS ============================
@st.cache_data(show_spinner="Loading sampled points and predictions...")
def load_points() -> pd.DataFrame:
    """Features of the 99,913 sampled points + the opportunity score of every model (same row order)."""
    import geopandas as gpd

    feats = gpd.read_file(FEATURES_GPKG)
    preds = gpd.read_file(PREDICTIONS_GPKG)
    if len(feats) != len(preds) or not np.allclose(feats.geometry.x.values, preds.geometry.x.values):
        raise RuntimeError("Features and predictions are not aligned - re-run the notebook.")

    df = pd.DataFrame(feats.drop(columns=["geometry", "dummy", "proxy_target"], errors="ignore"))
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
    # simplified to about 100 m: the borders look the same at the map's zoom, with far less data to send
    g = gpd.read_file(COUNTRIES_SHP).to_crs("EPSG:4326")
    g["geometry"] = g.geometry.simplify(0.001).set_precision(1e-4)
    return g.__geo_interface__


@st.cache_data
def load_baseline() -> pd.DataFrame | None:
    return pd.read_csv(BASELINE_CSV, index_col="Model") if BASELINE_CSV.exists() else None


CNN_PT = DATA_PROCESSED / "patch_cnn.pt"


@st.cache_resource(show_spinner="Loading the CNN...")
def load_cnn() -> dict:
    """patch_cnn.pt from the notebook, rebuilt as the same network (notebook section "5. THE 2D CNN")."""
    import torch
    import torch.nn as nn

    class _Net(nn.Module):
        def __init__(self, c_in, n_scalar, filters, dropout):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(c_in, filters, 3, padding=1), nn.BatchNorm2d(filters), nn.ReLU(),
                nn.Conv2d(filters, filters * 2, 3, padding=1), nn.BatchNorm2d(filters * 2), nn.ReLU(),
                nn.AdaptiveAvgPool2d(2), nn.Flatten())
            self.head = nn.Sequential(nn.Linear(filters * 2 * 4 + n_scalar, 64), nn.ReLU(),
                                      nn.Dropout(dropout), nn.Linear(64, 1))

        def forward(self, x, s):
            z = self.conv(x)
            if s.shape[1] > 0:
                z = torch.cat([z, s], dim=1)
            return self.head(z).squeeze(1)

    ck = torch.load(CNN_PT, weights_only=False, map_location="cpu")
    net = _Net(len(ck["channels"]), len(ck["scalars"]), ck["params"]["filters"], ck["params"]["dropout"])
    net.load_state_dict(ck["state_dict"])
    net.eval()
    return {"net": net, **{k: ck[k] for k in ("channels", "scalars", "radius", "mu", "sd", "smu", "ssd")}}


PATCHES_DIR = DATA_PROCESSED / "patches"


@st.cache_resource(show_spinner=False)
def load_site_patches(n_points, n_channels, radius):
    """P_all from the notebook's patch cache (section "2. IMAGE PATCHES"): one patch per sampled point, same row
    order as load_points(). The newest cache that fits the points and the CNN layers wins; None if none does.
    Read fully into memory, not memory-mapped: on Windows a mapped file cannot be overwritten, which breaks
    the notebook's np.save while the app is running."""
    side = 2 * radius + 1
    for f in sorted(PATCHES_DIR.glob(f"*/P_all_r{radius}.npy"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = np.load(f, mmap_mode="r")                    # cheap shape check without reading the data
        ok = m.shape == (n_points, n_channels, side, side)
        P = np.array(m) if ok else None                  # copy into RAM
        del m                                            # closes the mapping, so the file is free again
        if ok:
            return P
    if DEPLOY_PATCHES.exists():                          # online app: compressed copy from prepare_deploy.py
        P = np.load(DEPLOY_PATCHES)["P"]
        if P.shape == (n_points, n_channels, side, side):
            return P
    return None


def cnn_predict(cnn, P, S=None):
    """P(high potential) from patches P (n, C, H, W) and optional scalar inputs S (n, k)."""
    import torch

    S = np.zeros((len(P), 0), dtype=np.float32) if S is None else S
    Pn = (P - cnn["mu"][None, :, None, None]) / cnn["sd"][None, :, None, None]
    Sn = (np.log1p(np.clip(S, 0, None)) - cnn["smu"]) / cnn["ssd"]
    out = []
    with torch.no_grad():
        for i in range(0, len(Pn), 1024):
            out.append(torch.sigmoid(cnn["net"](torch.tensor(Pn[i:i + 1024], dtype=torch.float32),
                                                torch.tensor(Sn[i:i + 1024], dtype=torch.float32))).numpy())
    return np.concatenate(out)


@st.cache_resource(show_spinner="Loading the trained models (about 15 s, once)...")
def load_models() -> dict:
    """models.pkl from the notebook: RF, LR and XGBoost pipelines (the CNN needs image patches, so it is not here)."""
    import joblib

    return joblib.load(MODELS_PKL if MODELS_PKL.exists() else DEPLOY_MODELS)

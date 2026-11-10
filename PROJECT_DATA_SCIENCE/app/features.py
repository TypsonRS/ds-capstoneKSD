"""Earth Engine feature extraction for a new region.

A copy of the notebook's settings and get_features_image() (AgroRestoreAI.ipynb, sections
"Common analysis grid", "Time windows" and "Feature engineering function").
If you change the features in the notebook, make the same change here.
"""

import warnings
from datetime import datetime, timezone

import ee
import geopandas as gpd
import numpy as np
import pandas as pd

# ============================ SETTINGS (same as the notebook) ============================
GEE_PROJECT = "agrorestore-ai"
TARGET_SCALE = 250                 # metres
CLIMATE_YEARS = (2006, 2025)
NDVI_YEARS = (2006, 2025)
FIRE_LONG_YEARS = (2006, 2025)
RANDOM_STATE = 42
CRITICAL_COLS = ["soc", "ph", "fire_freq", "ndvi_mean", "slope"]   # rows missing these are dropped, as in the notebook


def init_ee():
    """Connect to Earth Engine with the credentials saved by ee.Authenticate() in the notebook."""
    ee.Initialize(project=GEE_PROJECT)


def geocode_region(place):
    """Official boundary of a place from OpenStreetMap, merged into one valid, lightly simplified polygon."""
    import osmnx as ox

    gdf = ox.geocode_to_gdf(place)
    if not gdf.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError(f"'{place}' is not an area (OpenStreetMap returned a {gdf.geom_type.iloc[0]}).")
    name = gdf["display_name"].iloc[0]
    gdf = gdf.dissolve().reset_index(drop=True)[["geometry"]]
    gdf["geometry"] = gdf.geometry.make_valid().simplify(0.0003, preserve_topology=True)
    return gdf.set_crs("EPSG:4326", allow_override=True), name


def last_full_year(col_id):
    """Last calendar year that the collection fully covers."""
    ms = ee.ImageCollection(col_id).aggregate_max("system:time_start").getInfo()
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return d.year if (d.month, d.day) >= (12, 1) else d.year - 1


def get_features_image(aoi_gdf):
    """Computes and stacks all engineered features (sampled later at TARGET_SCALE)."""

    # ---- safe year windows (end is exclusive: next year's Jan 1) ----
    clim_end = min(CLIMATE_YEARS[1], last_full_year("UCSB-CHG/CHIRPS/DAILY"),
                   last_full_year("IDAHO_EPSCOR/TERRACLIMATE"))
    ndvi_end = min(NDVI_YEARS[1], last_full_year("MODIS/061/MOD13Q1"))
    fire_end = min(FIRE_LONG_YEARS[1], last_full_year("MODIS/061/MCD64A1"))

    # 1. Climate
    precipitation = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterDate(f"{CLIMATE_YEARS[0]}-01-01", f"{clim_end + 1}-01-01")
        .select("precipitation").mean()
        .rename("precipitation_mean"))

    tc = (ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE")
        .filterDate(f"{CLIMATE_YEARS[0]}-01-01", f"{clim_end + 1}-01-01")
        .select(["tmmn", "tmmx"]))
    tmin = tc.select("tmmn").mean().multiply(0.1).rename("tmin")   # TerraClimate scale 0.1 -> deg C
    tmax = tc.select("tmmx").mean().multiply(0.1).rename("tmax")
    tmean = tmin.add(tmax).divide(2).rename("tmean")

    soil_moisture = (ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE")
        .select("soil")
        .filterDate("1991-01-01", f"{clim_end + 1}-01-01")
        .filter(ee.Filter.calendarRange(7, 10, "month"))
        .mean().multiply(0.1).rename("soil_moisture"))             # mm

    # 2. Soil: iSDAsoil
    soil_soc = (ee.Image("ISDASOIL/Africa/v1/carbon_organic").select("mean_0_20")
                .divide(10).exp().subtract(1).rename("soc"))
    soil_ph = ee.Image("ISDASOIL/Africa/v1/ph").select("mean_0_20").divide(10).rename("ph")

    # 3. Topography
    dem = ee.Image("USGS/SRTMGL1_003")
    slope = ee.Terrain.slope(dem).rename("slope")
    elevation = dem.select("elevation").rename("elevation")

    # 4. Land cover
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    built_up = wc.eq(50).rename("built_up")
    water = wc.eq(80).rename("water")

    # 5. Protected zone
    region = ee.Geometry.BBox(*aoi_gdf.total_bounds)
    wdpa = (ee.FeatureCollection("WCMC/WDPA/current/polygons")
            .filterBounds(region)
            .filter(ee.Filter.inList("STATUS", ["Designated", "Inscribed", "Established", "Adopted"])))
    protected = ee.Image.constant(0).paint(wdpa, 1).rename("protected")

    # 6. Fire: fraction of years burned (one 0/1 flag per year, skip years with no data)
    burn = ee.ImageCollection("MODIS/061/MCD64A1").select("BurnDate")
    flags = []
    for y in range(FIRE_LONG_YEARS[0], fire_end + 1):
        yr = burn.filterDate(f"{y}-01-01", f"{y + 1}-01-01")
        if yr.size().getInfo() > 0:
            flags.append(yr.max().gt(0).unmask(0).rename("burned"))
    fire_freq = ee.ImageCollection.fromImages(flags).mean().rename("fire_freq")

    # 7. Vegetation
    ndvi_col = (ee.ImageCollection("MODIS/061/MOD13Q1")
        .filterDate(f"{NDVI_YEARS[0]}-01-01", f"{ndvi_end + 1}-01-01")
        .select("NDVI").map(lambda img: img.multiply(0.0001)))
    ndvi_mean = ndvi_col.mean().rename("ndvi_mean")
    ndvi_std = ndvi_col.reduce(ee.Reducer.stdDev()).rename("ndvi_std")
    ndvi_resilience = ndvi_mean.divide(ndvi_std.add(0.01)).rename("ndvi_resilience")

    # --- Outcome: NDVI trend (NDVI change per year, linear fit on annual mean NDVI) ---
    def annual_ndvi(y):
        start = ee.Date.fromYMD(y, 1, 1)
        nd = (ee.ImageCollection("MODIS/061/MOD13Q1").select("NDVI")
              .filterDate(start, start.advance(1, "year"))
              .mean().multiply(0.0001).rename("ndvi"))
        return ee.Image.cat([ee.Image.constant(y).float().rename("year"), nd])

    ndvi_trend = (ee.ImageCollection.fromImages(
                      [annual_ndvi(y) for y in range(NDVI_YEARS[0], ndvi_end + 1)])
                  .reduce(ee.Reducer.linearFit())
                  .select("scale").rename("ndvi_trend"))

    return ee.Image.cat([
        precipitation, tmean, tmin, tmax, soil_soc, soil_ph, soil_moisture, protected, ndvi_trend,
        elevation, slope, built_up, water, fire_freq, ndvi_mean, ndvi_std, ndvi_resilience
    ])


def sample_features(aoi_gdf, n_points, image=None):
    """Random 250 m points inside the region with all features (Earth Engine allows at most 5,000 per request)."""
    aoi_ee = ee.Geometry(aoi_gdf.geometry.iloc[0].__geo_interface__)
    image = image if image is not None else get_features_image(aoi_gdf)
    fc = image.sample(region=aoi_ee, scale=TARGET_SCALE, numPixels=n_points, seed=RANDOM_STATE,
                      geometries=True, tileScale=4).limit(5000)
    feats = fc.getInfo()["features"]
    if not feats:
        raise ValueError("Earth Engine returned no points for this region (outside the data coverage?).")
    gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["lon"], df["lat"] = gdf.geometry.x.values, gdf.geometry.y.values
    return df.dropna(subset=[c for c in CRITICAL_COLS if c in df.columns]).reset_index(drop=True)


# ============================ CNN IMAGE PATCHES (same as notebook section "2. IMAGE PATCHES") ============================
COARSE_BANDS = {"precipitation_mean", "soil_moisture", "tmean", "tmin", "tmax"}   # 4-5 km sources: interpolate
DIRECT_BANDS = {"protected", "ndvi_mean", "ndvi_std", "ndvi_resilience"}          # no native grid: compute on the grid
PATCH_BATCH = 250


def fetch_patches(df, image, channels, radius, progress=None):
    """(n, channels, 2r+1, 2r+1) patches around every point of df, on the region's UTM 250 m grid."""
    import re

    pts = gpd.GeoDataFrame(df[[]], geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    crs = pts.estimate_utm_crs().to_string()

    def on_grid(band):
        b = image.select(band)
        if band in COARSE_BANDS:
            return b.resample("bilinear").reproject(crs=crs, scale=TARGET_SCALE)
        if band in DIRECT_BANDS:
            return b.reproject(crs=crs, scale=TARGET_SCALE)
        return b.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(crs=crs, scale=TARGET_SCALE)

    patch_img = ee.Image.cat([on_grid(b) for b in channels]).neighborhoodToBands(ee.Kernel.square(radius, "pixels"))
    band_idx, H = {b: i for i, b in enumerate(channels)}, 2 * radius + 1
    name_rx = re.compile(r"^(.*)_(-?\d+)_(-?\d+)$")
    P = np.full((len(df), len(channels), H, H), np.nan, dtype=np.float32)

    def fetch(rows):
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(df["lon"].iat[j]), float(df["lat"].iat[j])]),
                                              {"pid": int(j)}) for j in rows])
        for attempt in range(3):
            try:
                return patch_img.sampleRegions(collection=fc, properties=["pid"], scale=TARGET_SCALE,
                                               tileScale=4, geometries=False).getInfo()["features"]
            except ee.EEException:
                if attempt == 2:
                    raise

    # Earth Engine requests wait on the network, so several batches run at the same time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    batches = [np.arange(s, min(s + PATCH_BATCH, len(df))) for s in range(0, len(df), PATCH_BATCH)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for done, fut in enumerate(as_completed([pool.submit(fetch, rows) for rows in batches]), start=1):
            for f in fut.result():
                p = f["properties"]
                for k, v in p.items():
                    mt = name_rx.match(k)
                    if mt and mt.group(1) in band_idx and v is not None:
                        P[int(p["pid"]), band_idx[mt.group(1)], int(mt.group(3)) + radius, int(mt.group(2)) + radius] = v
            if progress:
                progress(done / len(batches))

    # fill gaps exactly as the notebook: patch-channel mean first, then the global channel mean
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # all-empty channels are filled below
        P = np.where(np.isnan(P), np.nanmean(P, axis=(2, 3), keepdims=True), P)
        P = np.where(np.isnan(P), np.nanmean(P, axis=(0, 2, 3), keepdims=True), P)
    return P.astype(np.float32)


def region_km2(aoi_gdf):
    return float(aoi_gdf.to_crs(aoi_gdf.estimate_utm_crs()).area.sum() / 1e6)


def spacing_km(area_km2, n):
    return float(np.sqrt(area_km2 / max(n, 1)))


# ============================ OSM ACCESS DISTANCES (same as the notebook's "Accessibility" step) ============================
# The notebook reads roads and settlements from a local OpenStreetMap extract. For a new region the app
# downloads the Geofabrik extract of every country the region touches (once, kept in cache/osm/) and
# measures the same two distances with the same road and place classes.
from pathlib import Path

OSM_ROAD_CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary",
                    "unclassified", "residential", "track"]
OSM_PLACE_CLASSES = ["village", "hamlet", "town", "city"]
OSM_DIST_COLS = ["dist_to_road_m", "dist_to_settlement_m"]
OSM_CACHE = Path(__file__).resolve().parents[1] / "cache" / "osm"
GEOFABRIK_INDEX = "https://download.geofabrik.de/index-v1.json"
OSM_SEARCH_BUFFER_DEG = 0.2        # also read roads/places ~20 km outside the boundary, so edge points are not penalised


def _download(url, dest):
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)                  # only a complete download gets the final name
    return dest


def _country_extracts(aoi_gdf):
    """Paths of the Geofabrik country extracts that overlap the region (downloaded when missing)."""
    index_path = OSM_CACHE / "geofabrik-index-v1.json"
    if not index_path.exists():
        _download(GEOFABRIK_INDEX, index_path)
    index = gpd.read_file(index_path)
    continents = set(index.loc[index["parent"].isna(), "id"])
    countries = index[index["parent"].isin(continents)]          # one level below the continents
    area = aoi_gdf.to_crs("EPSG:4326").geometry.union_all().buffer(OSM_SEARCH_BUFFER_DEG)
    hits = countries[countries.intersects(area)]
    if hits.empty:
        raise ValueError("No OpenStreetMap country extract covers this region.")
    paths = []
    for _, row in hits.iterrows():
        name = row["id"].replace("/", "_")
        layers = OSM_CACHE / f"{name}-roads-places.gpkg"
        if not layers.exists():
            pbf = OSM_CACHE / f"{name}-latest.osm.pbf"
            if not pbf.exists():
                _download(row["urls"]["pbf"], pbf)
            _extract_layers(pbf, layers)
        paths.append(layers)
    return paths


def _extract_layers(pbf, dest):
    """Keeps only the road lines and place points of a country extract (parsing the .pbf is slow, the GPKG is not)."""
    in_list = lambda vals: ", ".join(f"'{v}'" for v in vals)
    roads = gpd.read_file(pbf, layer="lines", columns=["highway"],
                          where=f"highway IN ({in_list(OSM_ROAD_CLASSES)})")
    places = gpd.read_file(pbf, layer="points", columns=["place"],
                           where=f"place IN ({in_list(OSM_PLACE_CLASSES)})")
    tmp = dest.with_suffix(".part.gpkg")
    tmp.unlink(missing_ok=True)
    roads.to_file(tmp, layer="roads", driver="GPKG")
    places.to_file(tmp, layer="places", driver="GPKG")
    tmp.replace(dest)


def add_osm_distances(df, aoi_gdf):
    """Adds dist_to_road_m and dist_to_settlement_m (metres to the nearest OSM road / place point).

    Returns (df, None) on success, or (df with NaN distances, error message) when OpenStreetMap is unavailable."""
    df = df.copy()
    try:
        minx, miny, maxx, maxy = aoi_gdf.to_crs("EPSG:4326").total_bounds
        b = OSM_SEARCH_BUFFER_DEG
        bbox = (minx - b, miny - b, maxx + b, maxy + b)
        roads, places = [], []
        for gpkg in _country_extracts(aoi_gdf):
            roads.append(gpd.read_file(gpkg, layer="roads", bbox=bbox))
            places.append(gpd.read_file(gpkg, layer="places", bbox=bbox))
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
        utm = pts.estimate_utm_crs()
        pts = pts.to_crs(utm)
        for col, parts in zip(OSM_DIST_COLS, (roads, places)):
            layer = pd.concat(parts, ignore_index=True)
            if layer.empty:
                df[col] = np.nan
                continue
            near = gpd.sjoin_nearest(pts, layer[["geometry"]].to_crs(utm), distance_col="d")
            df[col] = near.groupby(level=0)["d"].min().reindex(pts.index).to_numpy()
        return df, None
    except Exception as e:  # no internet, Geofabrik down, unreadable file...: score without the distances
        for col in OSM_DIST_COLS:
            df[col] = np.nan
        return df, f"{type(e).__name__}: {e}"

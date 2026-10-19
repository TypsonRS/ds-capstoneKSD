# AgroRestore AI

**Where is land restoration most likely to succeed?** AgroRestore AI maps the restoration potential
of every 250 m site in the **Centrale Region of Togo** (13,242 km²). It combines 20 years of
satellite, climate and soil data, trains four machine-learning models, and turns their predictions
into an opportunity map with low, uncertain and high-potential zones.

Capstone project, neuefische Data Science Bootcamp, Berlin.

| | |
|---|---|
| **Study area** | Centrale Region, Togo: 13,242 km², 99,913 sampled sites at 250 m |
| **Data** | Google Earth Engine: CHIRPS, TerraClimate, iSDAsoil, SRTM, ESA WorldCover, WDPA, MODIS NDVI and burned area (2006-2025) |
| **Target** | NDVI trend 2006-2025: top 30% of sites = high potential, bottom 30% = low potential |
| **Models** | Random Forest, XGBoost, Logistic Regression, 2D CNN on 5×5 image patches |
| **Validation** | Spatial: whole 10 km blocks held out, grouped 5-fold cross-validation |
| **Best model** | Random Forest: test F1 macro 0.76, ROC-AUC 0.84 (targets 0.75 / 0.80) |
| **Deliverables** | Notebook, saved models, static and interactive maps, Streamlit web app |

## Results

**Model performance** on held-out blocks (17,305 test sites in 49 blocks the models never saw):

| Model | CV F1 macro | Test F1 macro | Test ROC-AUC | Test PR-AUC |
|---|---|---|---|---|
| **Random Forest** (selected) | **0.738** | 0.760 | 0.842 | 0.818 |
| XGBoost | 0.733 | 0.761 | 0.845 | 0.822 |
| CNN (2D patches) | 0.729 | 0.767 | 0.836 | 0.776 |
| Logistic Regression | 0.666 | 0.707 | 0.774 | 0.727 |

The best model is chosen on the spatial cross-validation score, not on the test set, so the test
scores stay an honest estimate. Random Forest, XGBoost and the CNN all meet both targets; the
three are within 0.01 of each other on test F1.

**Restoration potential across the region** (Random Forest):

| Tier | Rule | Area | Share |
|---|---|---|---|
| High potential | P(high) ≥ 0.60 | 6,209 km² | 47% |
| Uncertain | 0.40 < P < 0.60 | 1,455 km² | 11% |
| Low potential | P(high) ≤ 0.40 | 5,578 km² | 42% |

All four models agree on *high* for 32% of the sites and on *low* for 27%, which are the most
robust priority and avoid zones.

**What drives the predictions:** soil moisture and elevation are the two most important
conditions for Random Forest and XGBoost, followed by NDVI variability and resilience and minimum
temperature. The CNN relies most on elevation, soil organic carbon and mean temperature.

## How the notebook works

Everything lives in [PROJECT_DATA_SCIENCE/AgroRestoreAI.ipynb](PROJECT_DATA_SCIENCE/AgroRestoreAI.ipynb).
Run it top to bottom; each step saves its output, so later steps can be re-run on their own.

### 1. Configuration

All settings live at the top of the notebook:

- **Paths**: `data/DATA_RAW`, `data/DATA_PROCESSED`, `data/DATA_LABELS`, `reports/FIGURES`
- **Google Earth Engine** project (`agrorestore-ai`)
- **Analysis grid**: 250 m, the native resolution of SoilGrids and MODIS NDVI
- **Time windows**: 2006-2025 for climate, NDVI and fire. Each collection is clipped automatically
  to its last complete year (climate to 2024, NDVI and fire to 2025).
- **Dataset choices and thresholds**: DEM, WorldCover, settlement, fire confidence, OSM road
  classes, block size, random seed

### 2. Area of interest

`PLACES = ["Centrale Region, Togo"]`. The official boundary is downloaded from OpenStreetMap with
`osmnx`, merged into one polygon, repaired and slightly simplified for Earth Engine.

### 3. Feature engineering (Google Earth Engine)

`get_features_image()` stacks 17 layers for the whole region:

| Group | Layers | Source |
|---|---|---|
| Climate | mean daily rainfall; mean, min and max temperature; soil moisture (Jul-Oct) | CHIRPS, TerraClimate |
| Soil | organic carbon and pH, 0-20 cm | iSDAsoil |
| Terrain | elevation, slope | SRTM |
| Land cover | built-up, water | ESA WorldCover 2021 |
| Protection | inside a designated protected area | WDPA |
| Fire | share of years burned | MODIS MCD64A1 |
| Vegetation | NDVI mean, variability (std), resilience (mean / std) | MODIS MOD13Q1 |
| **Outcome** | **NDVI trend**: slope of a linear fit on annual mean NDVI | MODIS MOD13Q1 |

### 4. Sampling

100,000 random points are sampled at 250 m across the region (99,913 returned). Points missing a
critical layer are dropped and the table is saved as `week1_features_sample.gpkg` / `.csv`.

### 5. Exploratory data analysis

- Yearly time series of every climate and vegetation layer, with the spatial 10th-90th
  percentile band and the trend per decade (`01a_time_varying_features_by_year.png`)
- Distributions of the static layers (`01b_static_feature_distributions.png`)
- Correlation matrix and pair plots (`02_correlation_matrix.png`, `02b_pairplot_features.png`).
  The temperature layers are strongly correlated with each other and with elevation
  (|ρ| 0.85-0.97), and soil carbon with NDVI mean (ρ 0.84).

### 6. Modelling

1. **Predictors**: 15 layers, every candidate with more than 95% valid values. The NDVI trend is
   excluded because it defines the label, and fire frequency is kept for a separate risk score.
2. **Image patches for the CNN**: a 5×5-pixel window (1.25 km × 1.25 km) of the same 15 layers
   around every point, downloaded from Earth Engine in batches. The cache folder is named after a
   fingerprint of the points, layers and patch size, so stale patches can never be reused. A check
   confirms the centre pixel of each patch matches the table value.
3. **Labels**: NDVI trend ≥ 70th percentile (+0.0009 NDVI/yr) = high (1), ≤ 30th percentile
   (−0.0007 NDVI/yr) = low (0). The ambiguous middle 40% is dropped, leaving 59,948 balanced
   points.
4. **Spatial split**: the region is cut into 10 km blocks. 30% of the blocks are held out for the
   final test (42,643 training points in 114 blocks, 17,305 test points in 49 blocks), so the
   models are tested on new places, not on neighbours of training points.
5. **Models**, all as scikit-learn pipelines (median imputation, then power transform):
   - Random Forest and Logistic Regression with balanced class weights
   - XGBoost with `scale_pos_weight`
   - a 2D CNN in PyTorch: two convolution blocks plus a dense head, with rotation and flip
     augmentation and early stopping on held-out blocks. It is wrapped as a scikit-learn
     classifier, so it is tuned and evaluated exactly like the others.
6. **Baseline**: every model with default hyperparameters (`results_baseline_no_tune.csv`)
7. **Tuning**: randomized search with `GroupKFold(5)` on the training blocks only, scored on
   F1 macro (20 configurations per tabular model, 6 for the CNN)

### 7. Evaluation and interpretation

- ROC and precision-recall curves, score bars against the targets, confusion matrices
  (`05a_model_comparison.png`, `05b_confusion_matrices.png`)
- Permutation importance on the held-out blocks, with the same metric for every model. For the
  CNN, whole input layers are shuffled (`06_feature_importance.png`).
- Logistic regression coefficients for the direction of each effect

### 8. Opportunity scores and maps

- The tuned models are saved (`models.pkl`, `best_model.pkl`, `patch_cnn.pt`), and every model
  scores all 99,913 sites as P(high potential)
- Maps: one per model, the best model as probability, tiers and hexagon averages, model agreement,
  and labels, spatial split and errors (`07a`-`07d_*.png`)
- `predictions.gpkg` for QGIS, and an interactive folium map
  (`reports/FIGURES/interactive/interactive_map.html`) with all layers, tiers, hexagons, country
  borders and click-for-details

## Web app

A Streamlit app in [PROJECT_DATA_SCIENCE/app/](PROJECT_DATA_SCIENCE/app/) presents the results:

| Page | What it shows |
|---|---|
| **Overview** | The question, data, method, key scores and tier areas |
| **Opportunity map** | Interactive map per model: probability, tiers, hexagon averages, model agreement. Adjustable tier thresholds, an option to hide protected areas, click-for-details, CSV download. |
| **Explore the data** | Distributions per tier, score against each condition, average conditions per tier, correlations |
| **Model performance** | Results table, targets, gain from tuning, permutation importance, notebook figures |
| **Score a site** | Load a real site or a location, change its conditions, get scores from the trained models |
| **Score a new region** | Type any place name: the app samples the same layers from Earth Engine, scores them with all four models, and warns when conditions fall outside the training range |

## Running it

**1. Environment.** The notebook and the app use the virtual environment in
`PROJECT_DATA_SCIENCE/venv` (Python 3.13). To create it from scratch:

```bash
cd PROJECT_DATA_SCIENCE
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

**2. Earth Engine.** You need a Google Cloud project registered for Earth Engine. Set
`GEE_PROJECT` in the notebook, then run the `ee.Authenticate()` cell once.

**3. Notebook.** Open `AgroRestoreAI.ipynb`, select the `venv` kernel, and run all cells. The first
full run takes a few hours, mostly Earth Engine downloads and model tuning. Patches and yearly
statistics are cached, so later runs are faster.

**4. App.** From `PROJECT_DATA_SCIENCE`:

```bash
venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

Then open http://localhost:8501. Call Streamlit through `python -m`, because the
`venv\Scripts\streamlit.exe` launcher can break if the folder is moved. The last cell of the
notebook starts the app in the background too.

## Project structure

```
PROJECT_DATA_SCIENCE/
├── AgroRestoreAI.ipynb          the full pipeline
├── requirements.txt
├── results_baseline_no_tune.csv
├── app/                         Streamlit web app
│   ├── streamlit_app.py         entry point and navigation
│   ├── common.py                paths, settings, loaders, map helpers
│   ├── features.py              Earth Engine features for new regions (copy of the notebook's)
│   └── app_pages/               one file per page
├── data/
│   ├── DATA_RAW/                raw downloads
│   └── DATA_PROCESSED/          features, patches, models, predictions
└── reports/FIGURES/             all figures and the interactive map
```

The root folders (`src/`, `notebooks/`, `tests/`, `Makefile`, `pyproject.toml`) come from the
bootcamp capstone template. See [TOOLS.md](TOOLS.md) and [UV_SETUP.md](UV_SETUP.md) for those
tools.

## Limitations and next steps

- **Proxy target.** The NDVI trend measures greening, not restoration success on the ground.
  Validating against field data or restoration project records is the most important next step.
- **NDVI-based predictors.** NDVI mean, variability and resilience come from the same satellite
  signal as the label. They describe the starting vegetation, not its trend, but a model without
  them would show how much the prediction depends on that signal.
- **No accessibility.** Distance to roads and settlements was planned from OpenStreetMap, but the
  extraction failed: the `.pbf` path in the notebook points to an old folder. Both columns are
  empty and were left out of the models.
- **One region.** The models learned from Centrale Region only. The app's new-region scoring
  flags conditions outside the training range. In Plateaux Region, for example, 71% of the
  points fall outside it, mainly because soil moisture is much lower there.
- **Coarse climate.** Rainfall and temperature come from 4-5 km sources and are interpolated to
  250 m, so their local detail is limited.

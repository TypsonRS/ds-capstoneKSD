"""Adapt the CNN to any new region with that region's own outcome data.

The label of the project is the NDVI trend 2006-2025, which Earth Engine provides everywhere. So for a new
region we can (1) check how well each trained model ranks sites there, and (2) fine-tune the CNN trained on the
Centrale Region on the new region's own labelled points. Both use spatial cross-validation on the new region:
every point is scored by a version of the CNN that never saw its block, so the local scores are honest.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold

LABEL_COL = "ndvi_trend"
LOW_Q, HIGH_Q = 0.30, 0.70     # same rule as the notebook: bottom 30% = low, top 30% = high potential
N_FOLDS = 5
MIN_LABELLED, MIN_BLOCKS = 300, 5
# fine-tuning settings (chosen on two test regions, Zabzugu District in Ghana and the Plateaux Region in Togo)
FT_EPOCHS, FT_LR, FT_BATCH, FT_WEIGHT_DECAY = 30, 1e-3, 64, 1e-5


def local_labels(df):
    """1 = high, 0 = low potential, NaN = ambiguous middle; quantiles of this region's own NDVI trend."""
    lo, hi = df[LABEL_COL].quantile([LOW_Q, HIGH_Q])
    y = pd.Series(np.nan, index=df.index)
    y[df[LABEL_COL] <= lo] = 0
    y[df[LABEL_COL] >= hi] = 1
    return y


def spatial_blocks(df):
    """Square blocks on the region's UTM grid: 10 km as in the notebook, smaller for small regions."""
    pts = gpd.GeoSeries(gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    utm = pts.to_crs(pts.estimate_utm_crs())
    for size in (10_000, 5_000, 2_500):
        blocks = ((utm.x // size).astype(int).astype(str) + "_" + (utm.y // size).astype(int).astype(str)).to_numpy()
        if len(set(blocks)) >= 15:
            break
    return blocks, size / 1000


def _fine_tune(net, P, S, y, seed):
    """Copy of the CNN trained further on (P, S, y), with the notebook's flips and rotations as augmentation."""
    import copy

    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = copy.deepcopy(net)
    net.train()
    opt = torch.optim.AdamW(net.parameters(), lr=FT_LR, weight_decay=FT_WEIGHT_DECAY)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    P, S, y = torch.tensor(P), torch.tensor(S), torch.tensor(y)
    for _ in range(FT_EPOCHS):
        order = torch.tensor(rng.permutation(len(y)))
        for i in range(0, len(order), FT_BATCH):
            j = order[i:i + FT_BATCH]
            x = torch.rot90(P[j], int(rng.integers(4)), (2, 3))
            if rng.random() < 0.5:
                x = torch.flip(x, (3,))
            loss = loss_fn(net(x, S[j]), y[j])
            opt.zero_grad()
            loss.backward()
            opt.step()
    net.eval()
    return net


def adapt_cnn(df, P, cnn, seed=42):
    """P(high potential) for every row of df from the CNN fine-tuned on this region (None if the region is too
    small for a fair check), plus a dict describing the fit."""
    import torch

    y = local_labels(df).to_numpy()
    labelled = ~np.isnan(y)
    blocks, block_km = spatial_blocks(df)
    info = {"n_labelled": int(labelled.sum()), "n_blocks": len(set(blocks[labelled])), "block_km": block_km}
    if info["n_labelled"] < MIN_LABELLED or info["n_blocks"] < MIN_BLOCKS:
        return None, info

    # same normalisation as the trained CNN (cnn_predict), so fine-tuning starts from what it already knows
    Pn = ((P - cnn["mu"][None, :, None, None]) / cnn["sd"][None, :, None, None]).astype(np.float32)
    S = df[list(cnn["scalars"])].to_numpy(np.float32) if cnn["scalars"] else np.zeros((len(df), 0), np.float32)
    Sn = ((np.log1p(np.clip(S, 0, None)) - cnn["smu"]) / cnn["ssd"]).astype(np.float32)

    probs = np.full(len(df), np.nan)
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=min(N_FOLDS, info["n_blocks"])).split(df, groups=blocks)):
        tr = tr[labelled[tr]]
        net = _fine_tune(cnn["net"], Pn[tr], Sn[tr], y[tr].astype(np.float32), seed + fold)
        with torch.no_grad():
            probs[te] = torch.sigmoid(net(torch.tensor(Pn[te]), torch.tensor(Sn[te]))).numpy()
    return probs, info


def local_metrics(df, columns):
    """ROC-AUC and F1 macro of every score column against this region's own labels."""
    y = local_labels(df)
    m = y.notna()
    rows = {}
    for col in columns:
        p = df.loc[m, col]
        rows[col] = {"ROC-AUC": roc_auc_score(y[m], p), "F1 macro": f1_score(y[m], p >= 0.5, average="macro")}
    return pd.DataFrame(rows).T.rename_axis("Model")

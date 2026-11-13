"""Write the compressed files the ONLINE app needs into PROJECT_DATA_SCIENCE/deploy/ (committed to git).

models.pkl (~190 MB) and the CNN image patches (~150 MB) are too big for GitHub (100 MB per file), so the
online app (Streamlit Community Cloud) loads these lossless compressed copies instead:
    deploy/models.joblib.xz   the RF, LR and XGBoost pipelines (~20 MB)
    deploy/P_all.npz          the 5x5 image patches of the sampled sites, for the CNN (~50 MB)

Run it again after re-running the notebook, then commit and push:
    venv\\Scripts\\python.exe app\\prepare_deploy.py
"""

import warnings

warnings.filterwarnings("ignore")

import joblib
import numpy as np

import common


def main() -> None:
    common.DEPLOY_DIR.mkdir(exist_ok=True)

    bundle = joblib.load(common.MODELS_PKL)
    joblib.dump(bundle, common.DEPLOY_MODELS, compress=("xz", 6))
    print(f"{common.DEPLOY_MODELS.name}: {common.DEPLOY_MODELS.stat().st_size / 1e6:.1f} MB")

    cnn = common.load_cnn()
    n = len(common.load_points())
    P = common.load_site_patches(n, len(cnn["channels"]), cnn["radius"])
    if P is None:
        print("No image patches match the sampled sites: run the notebook first. The CNN will be off online.")
        return
    np.savez_compressed(common.DEPLOY_PATCHES, P=P)
    print(f"{common.DEPLOY_PATCHES.name}: {common.DEPLOY_PATCHES.stat().st_size / 1e6:.1f} MB  {P.shape}")


if __name__ == "__main__":
    main()

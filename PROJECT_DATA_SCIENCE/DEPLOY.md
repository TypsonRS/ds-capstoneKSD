# Putting AgroRestore AI online

`https://agrorestoreai` only works on this computer: `setup_hostname.bat` points that name at `127.0.0.1`
in the Windows hosts file. To let anyone open the app and the map, without the notebook and without this PC
running, publish them as below. Both are free.

| What | Where it goes | Address |
|---|---|---|
| Web app (`app/streamlit_app.py`) | Streamlit Community Cloud | `https://agrorestoreai.streamlit.app` (if the name is free) |
| Interactive map (`reports/FIGURES/interactive/`) | GitHub Pages | `https://typsonrs.github.io/ds-capstoneKSD/` |

## 1. Push the deployment files to GitHub

```bash
venv\Scripts\python.exe app\prepare_deploy.py      # only after re-running the notebook
git add deploy app DEPLOY.md ../.github/workflows/deploy_map.yml
git commit -m "Online deployment"
git push
```

`deploy/` holds compressed copies of `models.pkl` (~20 MB) and the CNN image patches (~50 MB): the
originals are over GitHub's 100 MB limit. The online app loads them only when the originals are missing,
and its predictions are identical.

## 2. Interactive map on GitHub Pages (once)

1. GitHub repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Actions** tab → **Deploy interactive map** → **Run workflow** (later pushes that change the map redeploy it).
3. Open `https://typsonrs.github.io/ds-capstoneKSD/`.

## 3. Web app on Streamlit Community Cloud (once)

1. Sign in at <https://share.streamlit.io> with the GitHub account that owns the repo.
2. **Create app → Deploy a public app from GitHub**:
   - Repository: `TypsonRS/ds-capstoneKSD`, branch `main`
   - Main file path: `PROJECT_DATA_SCIENCE/app/streamlit_app.py`
   - App URL: `agrorestoreai`
   - **Advanced settings → Python version: 3.13**
3. Also in **Advanced settings → Secrets** (needed only for the "Score a new region" page): paste the
   Earth Engine key from `secrets/ee-service-account.json`, converted to TOML:

   ```toml
   [ee_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   token_uri = "https://oauth2.googleapis.com/token"
   ```

   Ready to paste: `secrets/streamlit_secrets.toml` (made from the JSON key; `secrets/` is git-ignored).
   Never commit this key.
4. **Deploy**. The first build takes several minutes. Packages come from `app/requirements.txt`.

Every `git push` to `main` updates the online app automatically. Free apps go to sleep after a few days
without visitors; the first visitor then clicks "Yes, get this app back up" and waits about a minute.

## Running it locally (no notebook)

Double-click **Start AgroRestore AI** / **Stop AgroRestore AI** in `PROJECT_DATA_SCIENCE`, or run
`install_autostart.bat` once to start it at every Windows logon. It opens at `https://agrorestoreai`.
To open the map without the notebook, double-click `reports/FIGURES/interactive/interactive_map.html`.

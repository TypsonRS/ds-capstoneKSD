"""AgroRestore AI - Streamlit web app.

Run from PROJECT_DATA_SCIENCE (or double-click run_app.bat):
    venv\\Scripts\\python.exe -m streamlit run app\\streamlit_app.py
"""

import threading

import streamlit as st

from common import load_cnn, load_models, load_points, load_site_patches

st.set_page_config(page_title="AgroRestore AI", page_icon=":material/eco:", layout="wide")


@st.cache_resource(show_spinner=False)
def _warm_up():
    """Load the trained models and the CNN image patches in the background, once per server start, while the
    first page is shown. The "Score a site" and "Score a new region" pages then open without waiting."""
    def work():
        try:
            load_models()
            cnn = load_cnn()
            load_site_patches(len(load_points()), len(cnn["channels"]), cnn["radius"])
        except Exception:                # the pages load (and report) the files themselves if this fails
            pass

    t = threading.Thread(target=work, name="warm-up", daemon=True)
    t.start()
    return t


_warm_up()

page = st.navigation(
    [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/home:", default=True),
        st.Page("app_pages/opportunity_map.py", title="Opportunity map", icon=":material/map:"),
        st.Page("app_pages/explore.py", title="Explore the data", icon=":material/query_stats:"),
        st.Page("app_pages/models.py", title="Model performance", icon=":material/model_training:"),
        st.Page("app_pages/cost_return.py", title="Cost and return", icon=":material/payments:"),
        st.Page("app_pages/predict.py", title="Score a site", icon=":material/psychology:"),
        st.Page("app_pages/new_region.py", title="Score a new region", icon=":material/travel_explore:"),
    ],
    position="top",
)

page.run()

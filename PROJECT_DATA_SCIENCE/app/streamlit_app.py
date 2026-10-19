"""AgroRestore AI - Streamlit web app.

Run from PROJECT_DATA_SCIENCE:
    venv\\Scripts\\streamlit run app\\streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="AgroRestore AI", page_icon=":material/eco:", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/home:", default=True),
        st.Page("app_pages/opportunity_map.py", title="Opportunity map", icon=":material/map:"),
        st.Page("app_pages/explore.py", title="Explore the data", icon=":material/query_stats:"),
        st.Page("app_pages/models.py", title="Model performance", icon=":material/model_training:"),
        st.Page("app_pages/predict.py", title="Score a site", icon=":material/psychology:"),
    ],
    position="top",
)

page.run()

"""Conviction Budget Fund app. Run from the repository root: streamlit run streamlit_app.py"""

import streamlit as st

st.set_page_config(page_title="Conviction Budget Fund", layout="wide")

pages = [
    st.Page("app/mandate_and_views.py", title="Mandate and Views", default=True),
    st.Page("app/proposed_portfolio.py", title="Proposed Portfolio"),
    st.Page("app/results.py", title="Results"),
]
st.navigation(pages).run()

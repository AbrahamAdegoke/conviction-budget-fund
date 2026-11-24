"""Conviction Budget Fund app. Run from the repository root: streamlit run streamlit_app.py"""

import streamlit as st

from app import common

st.set_page_config(page_title="Conviction Budget Fund", layout="wide")

pages = [
    st.Page("app/the_fund.py", title="The Fund", default=True),
    st.Page("app/mandate_and_views.py", title="Mandate and Views"),
    st.Page("app/proposed_portfolio.py", title="Proposed Portfolio"),
    st.Page("app/results.py", title="Results"),
]
nav = st.navigation(pages)

common.init_state()
st.sidebar.markdown("### Conviction Budget Fund")
st.sidebar.caption("Black-Litterman tilts within a 2% tracking-error budget")
st.sidebar.divider()
common.sidebar_summary()
st.sidebar.divider()
st.sidebar.caption("Data to 30 Oct 2026 · ETF prices: Refinitiv Datastream · risk-free rate: FRED")

nav.run()
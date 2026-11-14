"""Shared state and cached loaders for the Streamlit app (plan task 9). Everything reads data/ (offline)."""

import pandas as pd
import streamlit as st

from src import config
from src.backtest import RESULTS_DIR, load_results
from src.data import TICKERS
from src.optimizer import BENCH, load_inputs, propose_portfolio

RULE_SETS = {"Full mandate": "full", "TE budget only (long-only)": "long_only"}
PORTFOLIO_LABELS = {"benchmark": "Benchmark", "bl_te_only": "BL, TE budget only", "bl_full": "BL, full mandate"}

# User choices made on "Mandate and Views", used by "Proposed Portfolio"
DEFAULTS = {"month": None, "rules_label": "Full mandate", "confidence": config.DEFAULT_CONFIDENCE,
            "use_manual": False, "mv_long": "SPY", "mv_short": "TLT", "mv_q": 1.0, "mv_conf": 0.50}


def init_state():
    """Default choices, so each page also works when opened directly.

    Re-assigning each key keeps the choices when the user changes page (Streamlit drops the state of
    widgets that are not drawn on the current page).
    """
    for k, v in DEFAULTS.items():
        st.session_state[k] = st.session_state.get(k, v)
    if st.session_state.month is None:
        st.session_state.month = str(months()[-1])


@st.cache_resource
def inputs():
    return load_inputs()


def months():
    """Decision months with views and a full covariance window."""
    inp = inputs()
    return [m for m in inp.month_ends.index if m in set(inp.views["Month"]) and m >= pd.Period("2009-01", "M")]


def manual_view():
    s = st.session_state
    if not s.use_manual or s.mv_long == s.mv_short:
        return None
    return {"long": s.mv_long, "short": s.mv_short, "q": s.mv_q / 100, "confidence": s.mv_conf}


@st.cache_data(show_spinner="Optimizing...")
def proposal(month, rules, confidence, manual):
    """Weights for the current choices. x_prev=None: a fresh portfolio, so no turnover cap."""
    mv = dict(manual) if manual else None
    return propose_portfolio(month, inputs(), x_prev=None, rules=rules, confidence=confidence, manual_view=mv)


def current_proposal(with_manual=True):
    s = st.session_state
    mv = manual_view() if with_manual else None
    return proposal(s.month, RULE_SETS[s.rules_label], s.confidence,
                    tuple(sorted(mv.items())) if mv else None)       # hashable for the cache


@st.cache_data
def results():
    net, gross, log = load_results()
    metrics = pd.read_csv(RESULTS_DIR / "metrics.csv", index_col="portfolio")
    yearly = pd.read_csv(RESULTS_DIR / "metrics_by_year.csv", index_col=0, header=[0, 1])
    return net, gross, log, metrics, yearly


def pct(x, digits=2):
    return f"{x:.{digits}%}"

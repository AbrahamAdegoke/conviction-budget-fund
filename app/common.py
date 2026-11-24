"""Shared state and cached loaders for the Streamlit app (plan task 9). Everything reads data/ (offline)."""

import pandas as pd
import streamlit as st

from src import config
from src.backtest import RESULTS_DIR, load_results
from src.data import TICKERS
from src.optimizer import BENCH, load_inputs, propose_portfolio

RULE_SETS = {"Full mandate": "full", "TE budget only (long-only)": "long_only"}
PORTFOLIO_LABELS = {"benchmark": "Benchmark", "bl_te_only": "BL, TE budget only", "bl_full": "BL, full mandate",
                    "mvo_naive": "Naive MVO"}

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
def extra_results():
    """Ex-ante vs realized TE by asset block (src.metrics) and backtest variants on both periods (src.variants)."""
    blocks = pd.read_csv(RESULTS_DIR / "te_by_block.csv", index_col=[0, 1])
    variants = pd.read_csv(RESULTS_DIR / "variants.csv")
    return blocks, variants


@st.cache_data
def results():
    net, gross, log = load_results()
    metrics = pd.read_csv(RESULTS_DIR / "metrics.csv", index_col="portfolio")
    yearly = pd.read_csv(RESULTS_DIR / "metrics_by_year.csv", index_col=0, header=[0, 1])
    return net, gross, log, metrics, yearly


def pct(x, digits=2):
    return f"{x:.{digits}%}"


# Look and feel: the same colours on every page, so a portfolio is recognised at a glance.
# One colour per portfolio on every chart; benchmark in neutral ink (it is the reference).
COLORS = {"benchmark": "#898781", "bl_full": "#2a78d6", "bl_te_only": "#eb6834", "mvo_naive": "#6250d6"}
LABEL_COLORS = {PORTFOLIO_LABELS[k]: v for k, v in COLORS.items()}
# ETFs: one hue per asset class (equities blue, bonds green, alternatives amber), lighter for smaller weights
ETF_COLORS = {"SPY": "#1f4e8c", "EFA": "#2a78d6", "EEM": "#8ab8ec",
              "IEF": "#0f6b4f", "LQD": "#1baf7a", "TLT": "#8fd9b6",
              "VNQ": "#b06a12", "GLD": "#eda100"}
OVER, UNDER = "#2a78d6", "#e34948"           # diverging pair for active weights
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"


def header(title, question):
    st.title(title)
    st.markdown(f"<p style='color:#52514e;font-size:1.05rem;margin-top:-0.6rem'>{question}</p>",
                unsafe_allow_html=True)


def style(fig, title=None, yfmt=None, height=380):
    """Shared Plotly layout: quiet grid, legend on top, percent axes and hovers."""
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        title=dict(text=title, font=dict(size=15, color=INK), x=0, xanchor="left") if title else None,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color="#52514e", size=12),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=1, xanchor="right", title=None),
        hoverlabel=dict(bgcolor="white", font_size=12), plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb",
    )
    fig.update_xaxes(showgrid=False, linecolor="#c3c2b7", title=None)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="#c3c2b7", tickformat=yfmt)
    return fig


def sidebar_summary():
    """Current choices, always visible during the demo."""
    s = st.session_state
    mv = manual_view()
    st.sidebar.markdown("**Current choices**")
    st.sidebar.markdown(
        f"Month: **{s.month}**  \nRules: **{s.rules_label}**  \nView confidence: **{s.confidence:.0%}**  \n"
        + (f"Manual view: **{mv['long']} > {mv['short']} (+{s.mv_q:.1f}%)**" if mv else "Manual view: none"))

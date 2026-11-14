"""Page 1: the mandate, the automatic Black-Litterman views, and the user's inputs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so the page also runs on its own

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import common
from src import config
from src.data import TICKERS
from src.optimizer import BENCH

common.init_state()
common.header("Mandate and Views", "What is the fund allowed to hold, and what do the signals say this month?")

# --- Mandate -----------------------------------------------------------------------------------
left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Benchmark")
    classes = {t: c for c, ts in config.ASSET_CLASSES.items() for t in ts}
    fig = go.Figure(go.Bar(x=[[classes[t] for t in TICKERS], TICKERS], y=BENCH.values,
                           marker_color=[common.ETF_COLORS[t] for t in TICKERS],
                           text=[common.pct(v, 0) for v in BENCH], textposition="outside",
                           hovertemplate="%{x}<br>%{y:.0%}<extra></extra>"))
    common.style(fig, yfmt=".0%", height=300).update_yaxes(range=[0, 0.36])
    st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Mandate rules")
    with st.container(border=True):
        st.markdown(f"""
- Long-only, fully invested
- Bonds between **{config.BOND_MIN:.0%}** and **{config.BOND_MAX:.0%}**
- EEM ≤ **one third** of equities
- Each ETF ≤ **{config.MAX_WEIGHT:.0%}**
- Ex-ante tracking error ≤ **{config.TE_TARGET:.0%}** a year
""")
    st.radio("Rules for the proposed portfolio", list(common.RULE_SETS), key="rules_label",
             help="'TE budget only' drops the bond range, the EEM rule and the 40% cap, keeping long-only.")

st.divider()

# --- Automatic views -----------------------------------------------------------------------------
st.subheader("Automatic views")
c1, c2 = st.columns([1, 2], gap="large")
c1.selectbox("Decision month (signal at the month-end close)", [str(m) for m in common.months()][::-1],
             key="month")
c2.slider("Confidence in the automatic views", 0.05, 1.0, step=0.05, key="confidence", format="%.2f",
          help="Idzorek confidence. The 2% TE budget is always fully used, so confidence changes the mix "
               "of bets more than their size (docs/open_decisions.md, item 4).")

x, diag = common.current_proposal(with_manual=False)
views = diag["views"]
table = pd.DataFrame({"Signal adds (Q)": views["Q_over_equilibrium"], "Prior spread": views["prior_spread"],
                      "Posterior spread": views["posterior_spread"]})
st.dataframe(table.style.format("{:+.2%}"), width="stretch")
st.caption("Q is the extra spread the signal adds on top of the spread the benchmark prior already implies "
           "(equilibrium-relative views, docs/open_decisions.md item 2).")

st.divider()

# --- Manual view ---------------------------------------------------------------------------------
st.subheader("Manual relative view")
st.toggle("Add a manual view", key="use_manual")
if st.session_state.use_manual:
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.selectbox("Outperformer", TICKERS, key="mv_long")
        c2.selectbox("Underperformer", TICKERS, key="mv_short")
        c3.number_input("Extra spread, % a year", -10.0, 10.0, step=0.5, key="mv_q", format="%.1f")
        c4.slider("Confidence", 0.05, 1.0, step=0.05, key="mv_conf", format="%.2f")

        s = st.session_state
        if s.mv_long == s.mv_short:
            st.error("Choose two different ETFs: the manual view is ignored until then.")
        else:
            prior = diag["returns"]["prior_pi"]
            gap = prior[s.mv_long] - prior[s.mv_short]
            st.info(f"The prior already expects **{s.mv_long}** to beat **{s.mv_short}** by {common.pct(gap)} "
                    f"a year. Your view adds {s.mv_q:+.1f}%, so the total view is {common.pct(gap + s.mv_q / 100)}.")
            st.caption("Open **Proposed Portfolio** to see its effect.")

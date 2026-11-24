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

# Mandate: the benchmark the fund is measured against, and the rules every portfolio must respect.
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
- IEF, LQD and TLT within **±{config.BOND_ACTIVE_CAP * 100:.0f} points** of their benchmark weight
- Ex-ante tracking error ≤ **{config.TE_TARGET:.0%}** a year
""")
    st.radio("Rules for the proposed portfolio", list(common.RULE_SETS), key="rules_label",
             help="'TE budget only' drops the bond range, the EEM rule, the 40% cap and the bond limits, "
                  "keeping long-only.")

st.divider()

# Automatic views: pick a month and a confidence, and see what the signals say and how far
# they move the expected spreads away from the benchmark's.
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
           "(equilibrium-relative views, docs/open_decisions.md item 2). The benchmark spread assumes a "
           f"Sharpe ratio of {config.BENCHMARK_SR:.2f} for the benchmark: it changes the spreads shown here, "
           "not the portfolio weights.")

st.divider()

# Manual view: the user can add one relative view (A beats B by q) with its own confidence.
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
            prior, post = diag["returns"]["prior_pi"], diag["returns"]["posterior_mu"]
            gap = prior[s.mv_long] - prior[s.mv_short]                 # what the benchmark implies
            implied = post[s.mv_long] - post[s.mv_short]               # after the automatic views
            total = gap + s.mv_q / 100
            direction = ("adds conviction in" if total > implied + 1e-6 else
                         "works against" if total < implied - 1e-6 else "leaves unchanged")
            st.info(f"The benchmark implies that **{s.mv_long}** beats **{s.mv_short}** by {common.pct(gap)} a "
                    f"year, and the automatic views already raise this to **{common.pct(implied)}**. Your view sets "
                    f"it at {common.pct(total)}, so it **{direction}** {s.mv_long} over {s.mv_short}. To push further "
                    f"towards {s.mv_long}, enter more than {(implied - gap) * 100:+.1f}%.")
            st.caption("Open **Proposed Portfolio** to see its effect.")

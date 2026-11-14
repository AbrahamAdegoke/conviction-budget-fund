"""Page 2: the portfolio proposed for the chosen month, rules and views."""

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
s = st.session_state
st.title("Proposed Portfolio")
st.caption(f"Decision at the close of {s.month}, traded at the next session · {s.rules_label} · "
           f"automatic views at {s.confidence:.0%} confidence"
           + (f" · manual view {s.mv_long} > {s.mv_short} (+{s.mv_q:.1f}%)" if common.manual_view() else ""))

x, diag = common.current_proposal()

# --- Headline numbers and rule check -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ex-ante tracking error", common.pct(diag["te_ex_ante"]), help=f"Budget {config.TE_TARGET:.0%}")
c2.metric("Expected active return", common.pct(diag["expected_active_return"]))
c3.metric("Active share", common.pct((x - BENCH).abs().sum() / 2, 1))
c4.metric("Rules", "All satisfied" if not diag["violations"] else "Violated")
if diag["violations"]:
    st.error("Violations: " + ", ".join(diag["violations"]))

# --- Weights vs benchmark ------------------------------------------------------------------------
fig = go.Figure([go.Bar(name="Benchmark", x=TICKERS, y=BENCH.values),
                 go.Bar(name="Proposed", x=TICKERS, y=x.values)])
fig.update_layout(barmode="group", yaxis_tickformat=".0%", height=380, margin=dict(t=30, b=10),
                  legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig, width="stretch")

table = pd.DataFrame({"Benchmark": BENCH, "Proposed": x, "Active": x - BENCH,
                      "Alpha (BL)": diag["returns"]["alpha"]})
if common.manual_view():
    x0, _ = common.current_proposal(with_manual=False)
    table["Effect of manual view"] = x - x0
st.dataframe(table.style.format("{:.2%}"), width="stretch")

# --- Mandate totals ------------------------------------------------------------------------------
eq, bonds = config.ASSET_CLASSES["Equities"], config.ASSET_CLASSES["Bonds"]
st.markdown(f"**Bonds** {common.pct(x[bonds].sum(), 1)} (range {config.BOND_MIN:.0%}–{config.BOND_MAX:.0%}) · "
            f"**EEM / equities** {common.pct(x['EEM'] / x[eq].sum(), 1)} (max 33.3%) · "
            f"**Largest position** {x.idxmax()} {common.pct(x.max(), 1)} (max {config.MAX_WEIGHT:.0%})")
st.caption("A fresh portfolio for the chosen month: no turnover cap (the backtest applies it from the "
           f"previous holdings). Covariance: Ledoit-Wolf on 252 days, shrinkage {diag['shrinkage_delta']:.2f}.")

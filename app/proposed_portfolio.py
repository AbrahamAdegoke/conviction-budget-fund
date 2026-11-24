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
common.header("Proposed Portfolio", "What would the fund hold after this month's decision?")
st.caption(f"Decision at the close of {s.month}, traded at the next session · {s.rules_label} · "
           f"automatic views at {s.confidence:.0%} confidence"
           + (f" · manual view {s.mv_long} > {s.mv_short} ({s.mv_q:+.1f}%)" if common.manual_view() else ""))

x, diag = common.current_proposal()
active = x - BENCH

# --- Headline numbers and rule check -------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ex-ante tracking error", common.pct(diag["te_ex_ante"]), border=True,
          help=f"Budget {config.TE_TARGET:.0%}")
c2.metric("Expected active return", common.pct(diag["expected_active_return"]), border=True)
c3.metric("Active share", common.pct(active.abs().sum() / 2, 1), border=True)
c4.metric("Rules", "✅ All satisfied" if not diag["violations"] else "❌ Violated", border=True)
if diag["violations"]:
    st.error("Violations: " + ", ".join(diag["violations"]))
if diag["fallback_to_benchmark"]:
    st.warning("The optimizer found no portfolio that meets the mandate and the tracking-error budget, "
               "so the fund holds the benchmark this month.")

# --- Weights vs benchmark, and active weights -----------------------------------------------------
classes = {t: c for c, ts in config.ASSET_CLASSES.items() for t in ts}
xcat = [[classes[t] for t in TICKERS], TICKERS]
left, right = st.columns([3, 2], gap="large")
with left:
    fig = go.Figure([
        go.Bar(name="Benchmark", x=xcat, y=BENCH.values, marker_color=common.COLORS["benchmark"],
               hovertemplate="%{x}<br>Benchmark %{y:.1%}<extra></extra>"),
        go.Bar(name="Proposed", x=xcat, y=x.values, marker_color=common.COLORS["bl_full"],
               hovertemplate="%{x}<br>Proposed %{y:.1%}<extra></extra>")])
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
    st.plotly_chart(common.style(fig, "Weights", ".0%"), width="stretch")
with right:
    fig = go.Figure(go.Bar(
        x=active.values, y=TICKERS, orientation="h",
        marker_color=[common.OVER if v >= 0 else common.UNDER for v in active],
        text=[f"{v:+.1%}" for v in active], textposition="outside",
        hovertemplate="%{y}<br>Active %{x:+.1%}<extra></extra>"))
    lim = max(0.05, active.abs().max() * 1.35)
    common.style(fig, "Active weights (over / under)", height=380)
    fig.update_xaxes(tickformat=".0%", range=[-lim, lim], zeroline=True, zerolinecolor="#c3c2b7")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

# --- Detail table --------------------------------------------------------------------------------
table = pd.DataFrame({"Asset class": [classes[t] for t in TICKERS], "Benchmark": BENCH, "Proposed": x,
                      "Active": active, "Alpha (BL)": diag["returns"]["alpha"]})
if common.manual_view():
    x0, _ = common.current_proposal(with_manual=False)
    table["Effect of manual view"] = x - x0
signed = [c for c in ["Active", "Alpha (BL)", "Effect of manual view"] if c in table]
st.dataframe(
    table.style.format("{:.1%}", subset=["Benchmark", "Proposed"])
         .format("{:+.2%}", subset=signed)
         .map(lambda v: f"color: {common.OVER if v > 1e-6 else common.UNDER if v < -1e-6 else common.MUTED}",
              subset=signed),
    width="stretch")

# --- Mandate totals ------------------------------------------------------------------------------
eq, bonds = config.ASSET_CLASSES["Equities"], config.ASSET_CLASSES["Bonds"]
m1, m2, m3 = st.columns(3)
m1.metric("Bonds", common.pct(x[bonds].sum(), 1), help=f"Range {config.BOND_MIN:.0%}–{config.BOND_MAX:.0%}")
m2.metric("EEM / equities", common.pct(x["EEM"] / x[eq].sum(), 1), help="Max 33.3%")
m3.metric(f"Largest position ({x.idxmax()})", common.pct(x.max(), 1), help=f"Max {config.MAX_WEIGHT:.0%}")
st.caption("A fresh portfolio for the chosen month: no turnover cap (the backtest applies it from the "
           f"previous holdings). Covariance: Ledoit-Wolf on 252 days, shrinkage {diag['shrinkage_delta']:.2f}.")

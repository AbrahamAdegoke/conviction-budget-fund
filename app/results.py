"""Page 3: backtest results, read from data/results (run src.backtest.run_all and src.metrics.compute_all)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so the page also runs on its own

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app import common
from src import config
from src.data import TICKERS

st.title("Results")
net, gross, log, metrics, yearly = common.results()
labels = common.PORTFOLIO_LABELS
st.caption(f"Walk-forward backtest {net.index[0]:%d %b %Y} – {net.index[-1]:%d %b %Y}, monthly decisions, "
           "next-day trading, 5 bp cost on traded notional, automatic views at 50% confidence. "
           "Base case: the manual view and the sliders do not change these results.")

# --- Headline metrics ----------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
full = metrics.loc["bl_full"]
c1.metric("Active return (full mandate, net)", common.pct(full["Active return (net)"]))
c2.metric("Realized tracking error", common.pct(full["Realized TE"]), help=f"Ex-ante budget {config.TE_TARGET:.0%}")
c3.metric("Information ratio", f"{full['Information ratio']:.2f}")
c4.metric("Cost per year", common.pct(full["Cost (per year)"]))

pct_rows = [r for r in metrics.columns if r not in ("Sharpe", "Information ratio", "t-stat active return")]
show = metrics.rename(index=labels).T
st.dataframe(show.apply(lambda row: row.map(lambda v: "" if pd.isna(v) else
                                            (f"{v:.2%}" if row.name in pct_rows else f"{v:.2f}")), axis=1),
             width="stretch")

# --- Cumulative performance ----------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Growth of $1", "Cumulative active return", "Tracking error by year"])
with tab1:
    fig = px.line((1 + net).cumprod().rename(columns=labels), labels={"value": "Value", "variable": ""})
    st.plotly_chart(fig, width="stretch")
with tab2:
    active = net.drop(columns="benchmark").sub(net["benchmark"], axis=0)
    fig = px.line((1 + active).cumprod().sub(1).rename(columns=labels),
                  labels={"value": "Cumulative active return", "variable": ""})
    fig.update_layout(yaxis_tickformat=".1%")
    st.plotly_chart(fig, width="stretch")
with tab3:
    te = yearly["Realized TE"].rename(columns=labels)
    fig = go.Figure([go.Bar(name=c, x=te.index.astype(str), y=te[c]) for c in te.columns])
    fig.add_hline(y=config.TE_TARGET, line_dash="dash", annotation_text="2% ex-ante budget")
    fig.update_layout(barmode="group", yaxis_tickformat=".1%")
    st.plotly_chart(fig, width="stretch")

# --- Weights and trading over time ---------------------------------------------------------------
st.subheader("Weights and trading over time")
choice = st.radio("Portfolio", ["bl_full", "bl_te_only"], format_func=labels.get, horizontal=True)
sub = log.loc[log["portfolio"] == choice].set_index("month")
sub.index = sub.index.to_timestamp()
w = sub[[f"w_{t}" for t in TICKERS]].set_axis(TICKERS, axis=1)
fig = px.area(w, labels={"value": "Weight", "month": "", "variable": ""})
fig.update_layout(yaxis_tickformat=".0%")
st.plotly_chart(fig, width="stretch")
fig = px.bar(sub["traded"], labels={"value": "Traded (two-way)", "month": ""})
fig.add_hline(y=config.MAX_TURNOVER, line_dash="dash", annotation_text="20% cap")
fig.update_layout(yaxis_tickformat=".0%", showlegend=False)
st.plotly_chart(fig, width="stretch")
relaxed = sub["relaxed_turnover_cap"].dropna()
if len(relaxed):
    st.caption("Turnover cap relaxed to keep TE ≤ 2%: "
               + ", ".join(f"{d:%Y-%m} ({c:.0%})" for d, c in relaxed.items()))

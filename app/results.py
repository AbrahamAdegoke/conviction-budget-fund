"""Page 3: backtest results, read from data/results (run src.backtest.run_all and src.metrics.compute_all)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so the page also runs on its own

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import common
from src import config
from src.data import TICKERS

common.header("Results", "Did the views add value after costs, within the risk budget?")
net, gross, log, metrics, yearly = common.results()
labels = common.PORTFOLIO_LABELS
st.caption(f"Walk-forward backtest {net.index[0]:%d %b %Y} – {net.index[-1]:%d %b %Y} · monthly decisions, "
           "next-day trading, 5 bp cost on traded notional, automatic views at 50% confidence · "
           "base case: the sliders and the manual view do not change these results.")

# Headline metrics: did the views add value after costs, and was the risk budget respected?
full, te_only = metrics.loc["bl_full"], metrics.loc["bl_te_only"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Active return (net)", common.pct(full["Active return (net)"]), border=True,
          delta=f"TE only: {te_only['Active return (net)']:+.2%}", delta_color="off",
          help="Full mandate, a year, net of the 5 bp trading cost. Below: the portfolio with the TE budget only.")
c2.metric("Realized TE, monthly", common.pct(full["Realized TE (monthly)"]), border=True,
          delta=f"daily: {common.pct(full['Realized TE'])}", delta_color="off",
          help=f"Budget: {config.TE_TARGET:.0%} ex ante. Measured on monthly returns, the horizon at which the fund "
               "is reviewed. Measured on daily returns it is a little higher, because daily differences partly "
               "cancel within a month.")
c3.metric("Information ratio", f"{full['Information ratio']:.2f}", border=True,
          delta=f"Jensen t: {full['t-stat Jensen alpha (Newey-West)']:.2f}", delta_color="off",
          help="Information ratio of the full mandate. Below: t-stat of Jensen's alpha (Newey-West); about 2 would "
               "be needed to call it significant.")
c4.metric("Cost per year", common.pct(full["Cost (per year)"]), border=True,
          delta=f"Turnover {full['Turnover (two-way, per year)']:.0%} a year", delta_color="off")


def series_fig(df, title, yfmt, hover_fmt):
    fig = go.Figure([go.Scatter(x=df.index, y=df[c], name=labels[c], mode="lines",
                                line=dict(color=common.COLORS[c], width=2),
                                hovertemplate=f"{labels[c]}: %{{y:{hover_fmt}}}<extra></extra>")
                     for c in df.columns])
    for x0, x1, text in [("2020-02-19", "2020-04-30", "COVID"), ("2022-01-01", "2022-10-31", "2022 rates")]:
        fig.add_vrect(x0=x0, x1=x1, fillcolor="#e1e0d9", opacity=0.45, line_width=0,
                      annotation_text=text, annotation_position="top left",
                      annotation_font=dict(size=11, color=common.MUTED))
    common.style(fig, title, yfmt, height=420).update_layout(hovermode="x unified")
    return fig


# Performance charts: growth, cumulative extra return, drawdowns and tracking error by year.
tab1, tab2, tab3, tab4 = st.tabs(["Growth of $1", "Cumulative active return", "Drawdown",
                                  "Tracking error by year"])
with tab1:
    st.plotly_chart(series_fig((1 + net).cumprod(), "Growth of $1 (net of costs)", ".2f", ".3f"),
                    width="stretch")
with tab2:
    active = net.drop(columns="benchmark").sub(net["benchmark"], axis=0)
    fig = series_fig((1 + active).cumprod() - 1, "Cumulative active return vs benchmark", ".1%", "+.2%")
    fig.add_hline(y=0, line_color="#c3c2b7", line_width=1)
    st.plotly_chart(fig, width="stretch")
with tab3:
    nav = (1 + net).cumprod()
    peak = nav.cummax().clip(lower=1.0)                     # the starting capital counts as a peak
    st.plotly_chart(series_fig(nav / peak - 1, "Drawdown from previous peak (or starting capital)", ".0%", ".1%"),
                    width="stretch")
with tab4:
    te = yearly["Realized TE"]
    fig = go.Figure([go.Bar(name=labels[c], x=te.index.astype(str), y=te[c], marker_color=common.COLORS[c],
                            hovertemplate=f"{labels[c]}<br>%{{x}}: %{{y:.2%}}<extra></extra>")
                     for c in ["bl_full", "bl_te_only"]])
    fig.add_hline(y=config.TE_TARGET, line_dash="dash", line_color=common.INK, line_width=1,
                  annotation_text="2% ex-ante budget", annotation_position="top left")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    st.plotly_chart(common.style(fig, "Realized tracking error by calendar year", ".1%", height=420),
                    width="stretch")
    st.caption("Measured on daily returns, which overstate the monthly risk a little (see below).")

# Tracking error by asset block: where the risk model is right, and where it underestimates the risk.
blocks, variants = common.extra_results()
b = blocks.loc["bl_full"].drop(index="Total")
with st.expander("Why can realized tracking error exceed the 2% budget?"):
    st.markdown(
        f"Month by month the fund stays within budget ({common.pct(full['Realized TE (monthly)'])}). Day by day it "
        f"is a little higher ({common.pct(full['Realized TE'])}). The table splits the active risk by asset block: "
        f"a ratio above 1 means the covariance underestimated that block's risk. Bonds are no longer "
        f"underestimated thanks to the ±{config.BOND_ACTIVE_CAP:.0%} limit on IEF, LQD and TLT "
        f"(without it, in the TE-budget-only portfolio: {blocks.loc[('bl_te_only', 'Bonds'), 'Realized / ex-ante']:.2f}); "
        f"the real-estate vs gold bets still are.")
    st.dataframe(pd.DataFrame({
        "Ex-ante TE": b["Ex-ante TE"].map(lambda v: f"{v:.2%}"),
        "Realized TE": b["Realized TE"].map(lambda v: f"{v:.2%}"),
        "Realized ÷ ex-ante": b["Realized / ex-ante"].map(lambda v: f"{v:.2f}"),
        "Share of active risk": b["Share of realized active variance"].map(lambda v: f"{v:.0%}")}),
        width="stretch")

# Metrics table: every backtest measure for the three portfolios side by side.
st.subheader("All metrics")
ratios = ["Sharpe", "Information ratio", "t-stat active return", "Jensen beta",
          "t-stat Jensen alpha (Newey-West)"]
key_rows = ["Active return (net)", "Realized TE", "Information ratio"]
show = metrics.T[["benchmark", "bl_te_only", "bl_full", "mvo_naive"]].rename(columns=labels)
fmt = lambda row: row.map(lambda v: "–" if pd.isna(v) or (v == 0 and row.name != "Return (CAGR)") else
                          (f"{v:.2f}" if row.name in ratios else f"{v:.2%}"))
st.dataframe(show.apply(fmt, axis=1).style.apply(
                 lambda row: ["background-color: #e8f0fb" if row.name in key_rows else ""] * len(row), axis=1),
             width="stretch", height=720, column_config={"_index": st.column_config.Column(width=250)})
st.caption("Annualized except drawdowns and ES (daily). Benchmark active metrics are zero by construction (–). "
           "Benchmark turnover is its monthly rebalancing, charged no cost.")

# Robustness: the same model on the calibration period, other strategies, and one setting changed at a time.
st.subheader("Other periods and settings")
rows = [("BL, full mandate (base case)", "bl_full", 0.02, 5.0), ("BL, TE budget only", "bl_te_only", 0.02, 5.0),
        ("Naive MVO", "mvo_naive", 0.02, 5.0), ("Full mandate, no trading cost", "bl_full", 0.02, 0.0),
        ("Full mandate, 25 bp cost", "bl_full", 0.02, 25.0), ("Full mandate, 1% TE budget", "bl_full", 0.01, 5.0),
        ("Full mandate, 3% TE budget", "bl_full", 0.03, 5.0)]
v = variants.set_index(["period", "strategy", "TE budget", "cost (bp)"])
robust = pd.DataFrame({
    (period, col): [fmt_v(v.loc[(period, s, te, c), measure]) for _, s, te, c in rows]
    for period in ["2009-2015", "2016-2026"]
    for col, measure, fmt_v in [("Active return", "Active return (net)", lambda x: f"{x:+.2%}"),
                                ("IR", "Information ratio", lambda x: f"{x:.2f}")]},
    index=[r[0] for r in rows])
st.dataframe(robust, width="stretch")
st.caption("2009–2015 is the period used to calibrate the views; 2016–2026 is the test period. Settings were "
           "chosen on 2009–2015, except the ±5-point bond limit, adopted after also looking at 2016–2026. The price "
           "of the mandate is the gap between the first two rows: it changes sign between the periods.")

# Weights and trading: what the fund held at each decision and how much it traded.
st.divider()
st.subheader("Weights and trading over time")
choice = st.radio("Portfolio", ["bl_full", "bl_te_only"], format_func=labels.get, horizontal=True)
sub = log.loc[log["portfolio"] == choice].set_index("month")
sub.index = sub.index.to_timestamp()
w = sub[[f"w_{t}" for t in TICKERS]].set_axis(TICKERS, axis=1)
fig = go.Figure([go.Scatter(x=w.index, y=w[t], name=t, stackgroup="one", mode="lines",
                            line=dict(width=0.5, color="#fcfcfb"), fillcolor=common.ETF_COLORS[t],
                            hovertemplate=f"{t}: %{{y:.1%}}<extra></extra>") for t in TICKERS])
fig.update_layout(hovermode="x unified")
st.plotly_chart(common.style(fig, "Target weights at each decision", ".0%", height=400).update_yaxes(range=[0, 1]),
                width="stretch")

fig = go.Figure(go.Bar(x=sub.index, y=sub["traded"], marker_color=common.COLORS[choice],
                       hovertemplate="%{x|%b %Y}: %{y:.1%}<extra></extra>"))
fig.add_hline(y=config.MAX_TURNOVER, line_dash="dash", line_color=common.INK, line_width=1,
              annotation_text="20% two-way cap", annotation_position="top left")
st.plotly_chart(common.style(fig, "Traded each month (two-way)", ".0%", height=300), width="stretch")
relaxed = sub["relaxed_turnover_cap"].dropna()
if len(relaxed):
    st.caption("Turnover cap relaxed to keep TE ≤ 2%: "
               + ", ".join(f"{d:%b %Y} (to {c:.0%})" for d, c in relaxed.items())
               + ". Trades are measured on the trade day, so they can sit slightly above the cap.")

"""Page 0: what the fund does, how to read its risk measures, and why an investor would choose it.

Every number is read from data/results, so the page stays in line with the backtest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so the page also runs on its own

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import common
from src import config

common.init_state()
common.header("The Fund", "What do we do, and why would an investor choose it?")
net, gross, log, metrics, yearly = common.results()
labels = common.PORTFOLIO_LABELS
bench, full, te_only = metrics.loc["benchmark"], metrics.loc["bl_full"], metrics.loc["bl_te_only"]

active_by_year = yearly["Active return"]["bl_full"]
years_up, n_years = int((active_by_year > 0).sum()), len(active_by_year)
full_log = log.loc[log["portfolio"] == "bl_full"]
n_violations = int(full_log["violations"].notna().sum())                      # empty = no violation
n_relaxed = int(full_log["relaxed_turnover_cap"].notna().sum())
blocks, variants = common.extra_results()
alt_ratio = blocks.loc[("bl_full", "Alternatives"), "Realized / ex-ante"]
base = variants[(variants["TE budget"] == config.TE_TARGET) & (variants["cost (bp)"] == config.TRADING_COST_BP)]
base = base.set_index(["period", "strategy"])["Active return (net)"]
rules_price = {p: base[(p, "bl_full")] - base[(p, "bl_te_only")] for p in ["2009-2015", "2016-2026"]}

st.markdown("#### A benchmark portfolio with small, controlled bets on top.")
st.markdown(
    f"We hold a diversified portfolio of 8 ETFs and, each month, take small bets on the ETFs our signals favour. "
    f"We decide in advance how far we may deviate from the benchmark (a **{config.TE_TARGET:.0%} tracking-error "
    f"budget**, our *conviction budget*) and spend it on our best ideas, never more.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Extra return a year", f"{full['Active return (net)']:+.2%}", border=True,
          delta="net of trading costs", delta_color="off",
          help="Return of the full-mandate fund minus the benchmark's, a year, net of the 5 bp trading cost.")
c2.metric("Sharpe ratio", f"{full['Sharpe']:.2f}", border=True,
          delta=f"benchmark {bench['Sharpe']:.2f}", delta_color="off")
c3.metric("Max drawdown", common.pct(full["Max drawdown"], 1), border=True,
          delta=f"benchmark {common.pct(bench['Max drawdown'], 1)}", delta_color="off")
c4.metric("Years ahead", f"{years_up} of {n_years}", border=True,
          delta=f"{net.index[0]:%Y}–{net.index[-1]:%Y} (to {net.index[-1]:%b})", delta_color="off",
          help="Calendar years in which the full-mandate fund beat the benchmark, net of costs.")

st.divider()

# How the model works: the four monthly steps, in plain words.
st.subheader("How the model works, every month")
steps = [
    ("1 · Signals", "**Momentum:** within equities, within bonds, and between real estate and gold, last "
                    "year's winner should keep beating last year's loser.  \n**Trend:** if the S&P 500 is above its 200-day average, equities "
                    "should beat bonds; below it, the reverse."),
    ("2 · Black-Litterman", "Start from the returns the benchmark implies (those that make it the right "
                            "portfolio). Each signal says how much **more** one ETF should earn than another, "
                            "**on top of** what the benchmark already implies. Black-Litterman combines these "
                            "views with the prior and with each other, so expected returns move only moderately."),
    ("3 · Optimizer", f"Pick the weights with the highest expected extra return, with tracking error ≤ "
                      f"{config.TE_TARGET:.0%}, every mandate rule respected (see **Mandate and Views**) and at "
                      f"most {config.MAX_TURNOVER:.0%} of the portfolio traded. A trade is made only if its "
                      f"expected gain over {config.COST_HORIZON_MONTHS} months pays its cost."),
    ("4 · Trade and hold", "Signal at the month-end close, trade at the next session, pay 5 bp on what we "
                           "trade, hold for the month, repeat. Tested walk-forward: each decision only "
                           "uses data available at the time."),
]
for col, (title, text) in zip(st.columns(4), steps):
    with col.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(text)

st.divider()

# Performance: return against risk, and the extra return year by year.
st.subheader("What it delivered")
left, right = st.columns(2, gap="large")
with left:
    order = ["benchmark", "bl_full", "bl_te_only", "mvo_naive"]
    fig = go.Figure([go.Scatter(
        x=[metrics.loc[p, "Volatility"]], y=[metrics.loc[p, "Return (CAGR)"]], name=labels[p],
        mode="markers",
        marker=dict(size=16, color=common.COLORS[p]),
        hovertemplate=f"{labels[p]}<br>Return %{{y:.2%}}<br>Volatility %{{x:.2%}}<extra></extra>")
        for p in order])
    vol, ret = metrics.loc[order, "Volatility"], metrics.loc[order, "Return (CAGR)"]
    common.style(fig, "Return vs risk (a year, net)", ".1%", height=400).update_layout(
        legend=dict(orientation="h", y=-0.22, yanchor="top", x=0, xanchor="left"))
    fig.update_xaxes(tickformat=".1%", title="Volatility",
                     range=[vol.min() - 0.006, vol.max() + 0.006])
    fig.update_yaxes(title="Return (CAGR)", range=[ret.min() - 0.004, ret.max() + 0.004])
    st.plotly_chart(fig, width="stretch")
    st.caption("Each dot is one portfolio over the whole test period. Higher and to the left is better.")
with right:
    fig = go.Figure(go.Bar(
        x=active_by_year.index.astype(str), y=active_by_year.values,
        marker_color=[common.OVER if v > 0 else common.UNDER for v in active_by_year],
        hovertemplate="%{x}: %{y:+.2%}<extra></extra>"))
    common.style(fig, "Extra return vs benchmark by year (full mandate)", ".0%", height=380)
    fig.update_yaxes(zeroline=True, zerolinecolor="#c3c2b7")
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Ahead in {years_up} of {n_years} calendar years ({net.index[-1]:%Y} to {net.index[-1]:%b}). "
               "Losses stay small because the tracking-error budget caps every bet.")

st.divider()

# Risk measures: what each number means, with the fund's and the benchmark's values.
st.subheader("How to read the risk measures")
rows = [
    ("Sharpe ratio", "Return above cash per unit of total risk. Is the return worth the risk?", "Sharpe", "{:.2f}"),
    ("Max drawdown", "Worst fall from a previous peak. What an investor actually feels.", "Max drawdown", "{:.1%}"),
    ("Volatility", "How much returns swing, a year.", "Volatility", "{:.1%}"),
    ("Tracking error", "How much the fund's return differs from the benchmark's.",
     "Realized TE", "{:.2%}"),
    ("Information ratio", "Extra return ÷ tracking error. Judges the manager.",
     "Information ratio", "{:.2f}"),
    ("Expected shortfall 95%", "Average loss on the worst 5% of days.", "ES 95% (daily)", "{:.2%}"),
]
table = pd.DataFrame(
    {"Measure": [r[0] for r in rows], "What it tells you": [r[1] for r in rows],
     **{labels[p]: ["–" if pd.isna(v := metrics.loc[p, col]) or (p == "benchmark" and v == 0) else f.format(v)
                    for _, _, col, f in rows]
        for p in ["benchmark", "bl_full", "bl_te_only"]}})
st.dataframe(table, hide_index=True, width="stretch",
             column_config={"What it tells you": st.column_config.TextColumn(width="large")})

st.divider()

# Benefits and limits: why an investor would choose the fund, and what we do not claim.
good, limits = st.columns(2, gap="large")
with good:
    st.subheader("What the fund offers")
    st.markdown(f"""
- **Extra return after costs:** {full['Active return (net)']:+.2%} a year with the full mandate,
  {te_only['Active return (net)']:+.2%} with the TE budget only.
- **Similar total risk:** max drawdown {common.pct(full['Max drawdown'], 1)} vs {common.pct(bench['Max drawdown'], 1)},
  volatility {common.pct(full['Volatility'], 1)} vs {common.pct(bench['Volatility'], 1)}.
- **Rules always respected:** {n_violations} mandate violations in {len(full_log)} monthly decisions; {
  "the turnover cap never had to be loosened" if n_relaxed == 0 else
  f"the turnover cap was loosened in only {n_relaxed} month{'s' if n_relaxed != 1 else ''}"}.
- **Low trading cost:** {common.pct(full['Cost (per year)'])} a year, out of a gross extra return of
  {full['Active return (gross)']:+.2%}.
- **Explainable:** every position comes from a view that can be read on **Mandate and Views**; no
  discretionary decisions.
- **Interactive:** add a view, set its confidence and see the new portfolio at once
  (**Mandate and Views**, **Proposed Portfolio**).
""")
with limits:
    st.subheader("What we do not claim")
    st.markdown(f"""
- **The edge is small and not statistically proven:** Jensen alpha t-stat
  {full['t-stat Jensen alpha (Newey-West)']:.2f} (about 2 would be needed). {n_years} years are not enough to prove skill.
- **Tracking error:** {common.pct(full['Realized TE (monthly)'])} measured month by month, within the
  {config.TE_TARGET:.0%} budget, but {common.pct(full['Realized TE'])} day by day. The risk model still underestimates
  the real-estate vs gold bets (realized risk {alt_ratio:.2f}× the forecast).
- **The mandate's price depends on the period:** {rules_price['2016-2026']:+.2%} a year vs the TE-budget-only
  version on 2016–2026, but {rules_price['2009-2015']:+.2%} on 2009–2015. The rules protect in some markets only.
- **A simpler model did as well:** a naive mean-variance on past-year returns earned
  {metrics.loc['mvo_naive', 'Active return (net)']:+.2%} a year (information ratio
  {metrics.loc['mvo_naive', 'Information ratio']:.2f} vs {full['Information ratio']:.2f}), but trading more
  ({metrics.loc['mvo_naive', 'Turnover (two-way, per year)']:.0%} vs {full['Turnover (two-way, per year)']:.0%} of the
  portfolio a year). Black-Litterman's value here is control and explainability, not extra return.

In short: a **disciplined use of a small, controlled risk budget**, not a promise of large returns.
""")
st.caption("Details and all charts: **Results**. Backtest net of a 5 bp cost on traded notional.")

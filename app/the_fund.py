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

st.markdown(f"#### Benchmark-like risk, plus a disciplined and fully controlled source of extra return.")
st.markdown(
    f"We hold a diversified portfolio of 8 ETFs and, each month, take small bets on the ETFs our signals favour. "
    f"We decide in advance how far we may deviate from the benchmark (a **{config.TE_TARGET:.0%} tracking-error "
    f"budget**, our *conviction budget*) and spend it on our best ideas, never more.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Extra return vs benchmark", f"{full['Active return (net)']:+.2%} a year", border=True,
          delta="net of trading costs", delta_color="off")
c2.metric("Sharpe ratio", f"{full['Sharpe']:.2f}", border=True,
          delta=f"benchmark {bench['Sharpe']:.2f}", delta_color="off")
c3.metric("Max drawdown", common.pct(full["Max drawdown"], 1), border=True,
          delta=f"benchmark {common.pct(bench['Max drawdown'], 1)}", delta_color="off")
c4.metric("Years ahead of the benchmark", f"{years_up} of {n_years}", border=True,
          delta=f"{net.index[0]:%Y}–{net.index[-1]:%Y} (to {net.index[-1]:%b})", delta_color="off")

st.divider()

# How the model works: the four monthly steps, in plain words.
st.subheader("How the model works, every month")
steps = [
    ("1 · Signals", "**Momentum:** within equities and within bonds, last year's winner should keep beating "
                    "last year's loser.  \n**Trend:** if the S&P 500 is above its 200-day average, equities "
                    "should beat bonds; below it, the reverse."),
    ("2 · Black-Litterman", "Start from the returns the market implicitly expects (those that make the "
                            "benchmark the right portfolio), then blend in our views according to our "
                            "confidence. Expected returns stay reasonable, never extreme."),
    ("3 · Optimizer", f"Pick the weights with the highest expected extra return, with tracking error ≤ "
                      f"{config.TE_TARGET:.0%}, the mandate respected (bonds {config.BOND_MIN:.0%}–"
                      f"{config.BOND_MAX:.0%}, EEM ≤ ⅓ of equities, each ETF ≤ {config.MAX_WEIGHT:.0%}, "
                      f"each bond ETF within ±{config.BOND_ACTIVE_CAP:.0%} of the benchmark, long-only) "
                      f"and at most {config.MAX_TURNOVER:.0%} of the portfolio traded."),
    ("4 · Trade and hold", "Signal at the month-end close, trade at the next session, pay 5 bp on what we "
                           "trade, hold for the month, repeat. Tested walk-forward: each decision only "
                           "uses data available at the time."),
]
for col, (title, text) in zip(st.columns(4), steps):
    with col.container(border=True, height=270):
        st.markdown(f"**{title}**")
        st.markdown(text)

st.divider()

# Performance: return against risk, and the extra return year by year.
st.subheader("What it delivered")
left, right = st.columns(2, gap="large")
with left:
    order = ["benchmark", "bl_full", "bl_te_only"]
    fig = go.Figure([go.Scatter(
        x=[metrics.loc[p, "Volatility"]], y=[metrics.loc[p, "Return (CAGR)"]], name=labels[p],
        mode="markers+text", text=[labels[p]], textposition="top center",
        marker=dict(size=16, color=common.COLORS[p]),
        hovertemplate=f"{labels[p]}<br>Return %{{y:.2%}}<br>Volatility %{{x:.2%}}<extra></extra>")
        for p in order])
    vol, ret = metrics.loc[order, "Volatility"], metrics.loc[order, "Return (CAGR)"]
    common.style(fig, "Return vs risk (a year, net)", ".1%", height=380).update_layout(showlegend=False)
    fig.update_xaxes(tickformat=".1%", title="Volatility",
                     range=[vol.min() - 0.006, vol.max() + 0.006])
    fig.update_yaxes(title="Return (CAGR)", range=[ret.min() - 0.004, ret.max() + 0.004])
    st.plotly_chart(fig, width="stretch")
    st.caption("Higher and to the left is better. The views add return for almost no extra volatility.")
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
    ("Tracking error", "How much the fund's return differs from the benchmark's: the risk of being different.",
     "Realized TE", "{:.2%}"),
    ("Information ratio", "Extra return ÷ tracking error: the Sharpe ratio of the bets. Judges the manager.",
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
    st.subheader("Why choose it")
    st.markdown(f"""
- **Beats the benchmark after costs:** {full['Active return (net)']:+.2%} a year with the full mandate,
  {te_only['Active return (net)']:+.2%} with the TE budget only.
- **Same crash risk:** max drawdown {common.pct(full['Max drawdown'], 1)} vs {common.pct(bench['Max drawdown'], 1)},
  volatility {common.pct(full['Volatility'], 1)} vs {common.pct(bench['Volatility'], 1)}.
- **Rules always respected:** {n_violations} mandate violations in {len(full_log)} monthly decisions; the turnover
  cap was loosened in only {n_relaxed} month{'s' if n_relaxed != 1 else ''}, to keep tracking error within budget.
- **Cheap:** {common.pct(full['Cost (per year)'])} a year of trading costs; most of the gross edge
  ({full['Active return (gross)']:+.2%}) survives.
- **Transparent and systematic:** every position comes from a view you can explain, with no discretionary
  decisions.
- **Flexible:** the manager can add a view and set its confidence, and sees the effect at once
  (**Mandate and Views**, **Proposed Portfolio**).
""")
with limits:
    st.subheader("What we do not claim")
    st.markdown(f"""
- **The edge is small and not statistically proven:** t-stat {full['t-stat active return']:.2f}
  (about 2 would be needed). {n_years} years are not enough to prove skill.
- **Realized tracking error ({common.pct(full['Realized TE'])}) is above the {config.TE_TARGET:.0%} target:** a risk
  model based on the past year underestimates sudden crises such as March 2020.
- **The mandate has a price:** the TE-budget-only version earns more
  ({te_only['Active return (net)']:+.2%} vs {full['Active return (net)']:+.2%}).

The model does not promise large returns. It promises a **disciplined use of a small, controlled risk budget**.
""")
st.caption("Details and all charts: **Results**. Backtest net of a 5 bp cost on traded notional.")

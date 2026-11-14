"""Performance metrics for the backtest (Person C, plan task 8).

Inputs: the saved backtest (src/backtest.py), daily simple returns net and gross of the 5 bp cost.
Conventions:
- Annualization with 252 sessions. Active return = portfolio - benchmark, daily.
- Active return and IR use arithmetic means (IR = mean active x 252 / realized TE); CAGR is reported too.
- Risk-free: FRED DGS1MO (annual %), last published value carried over bond-market holidays, applied to the
  next session as yield / 252. Only the Sharpe ratio uses it: active return and IR do not need it.
- 95% ES: historical, average of the worst 5% daily returns, reported as a positive loss.
"""

import numpy as np
import pandas as pd

from .backtest import RESULTS_DIR, load_results
from .config import ANNUALIZATION as A
from .data import load_risk_free

ES_LEVEL = 0.95


def risk_free_daily(index):
    """Daily risk-free return on each session of `index`, known at the previous close (no look-ahead)."""
    rf = load_risk_free()
    rf = rf.reindex(rf.index.union(index)).ffill() / 100 / A
    return rf.shift(1).reindex(index)


def cagr(r):
    return (1 + r).prod() ** (A / len(r)) - 1


def max_drawdown(r):
    """Largest peak-to-trough fall of the cumulative value (positive number)."""
    nav = (1 + r).cumprod()
    return float(-(nav / nav.cummax() - 1).min())


def expected_shortfall(r, level=ES_LEVEL):
    """Historical ES: mean of the returns at or below the (1 - level) quantile, as a positive loss."""
    return float(-r[r <= r.quantile(1 - level)].mean())


def summary(net, gross, log, benchmark="benchmark"):
    """One row per portfolio with the plan's metrics (all annualized except ES and drawdowns)."""
    rf = risk_free_daily(net.index)
    years = len(net) / A
    rows = {}
    for p in net.columns:
        r, active = net[p], net[p] - net[benchmark]
        te = active.std() * np.sqrt(A)
        trades = log.loc[log["portfolio"] == p]
        rows[p] = {
            "Return (CAGR)": cagr(r),
            "Volatility": r.std() * np.sqrt(A),
            "Sharpe": (r - rf).mean() * A / (r.std() * np.sqrt(A)),
            "Active return (net)": active.mean() * A,
            "Active return (gross)": (gross[p] - gross[benchmark]).mean() * A,
            "Active CAGR": cagr(r) - cagr(net[benchmark]),
            "Realized TE": te,
            "Information ratio": active.mean() * A / te if te > 0 else np.nan,
            "t-stat active return": active.mean() / active.std() * np.sqrt(len(active)) if te > 0 else np.nan,
            "Turnover (two-way, per year)": trades["traded"].sum() / years,
            "Cost (per year)": trades["cost"].sum() / years,
            "Max drawdown": max_drawdown(r),
            "Max relative drawdown": max_drawdown(active) if te > 0 else 0.0,
            "ES 95% (daily)": expected_shortfall(r),
            "Active ES 95% (daily)": expected_shortfall(active) if te > 0 else 0.0,
        }
    return pd.DataFrame(rows).T


def by_year(net, benchmark="benchmark"):
    """Calendar-year active return and realized TE (checks the 2% budget out of sample, year by year)."""
    active = net.drop(columns=benchmark).sub(net[benchmark], axis=0)
    g = active.groupby(active.index.year)
    return pd.concat({"Active return": g.mean() * A, "Realized TE": g.std() * np.sqrt(A)}, axis=1)


def compute_all(save=True):
    """Metrics from the saved backtest; saved for the app's Results page (works offline)."""
    net, gross, log = load_results()
    table, yearly = summary(net, gross, log), by_year(net)
    if save:
        table.to_csv(RESULTS_DIR / "metrics.csv", index_label="portfolio")
        yearly.to_csv(RESULTS_DIR / "metrics_by_year.csv", index_label="year")
    return table, yearly

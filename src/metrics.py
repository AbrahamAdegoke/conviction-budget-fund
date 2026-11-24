"""Performance metrics for the backtest (Person C, plan task 8).

Inputs: the saved backtest (src/backtest.py), daily simple returns net and gross of the 5 bp cost.
Conventions:
- Annualization with 252 sessions. Active return = portfolio - benchmark, daily.
- Active return and IR use arithmetic means (IR = mean active x 252 / realized TE); CAGR is reported too.
- Risk-free: FRED DGS1MO (annual %), last published value carried over bond-market holidays, applied to the
  next session as yield / 252. Only the Sharpe ratio uses it: active return and IR do not need it.
- 95% ES: historical, average of the worst 5% daily returns, reported as a positive loss.
- Realized TE is given on daily returns (x sqrt 252) and on monthly returns (x sqrt 12): daily active returns
  are slightly negatively autocorrelated, so the two differ; the committee looks at the fund monthly.
- Jensen's alpha (LN2): monthly OLS of R(x) - r on R(b) - r, t-stat with Newey-West standard errors.
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


def monthly(r):
    """Compound daily returns into calendar-month returns."""
    return (1 + r).groupby(r.index.to_period("M")).prod() - 1


def newey_west_lags(n):
    """Usual automatic lag length floor(4 (n/100)^(2/9))."""
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def jensen(port_excess, bench_excess, lags=None):
    """OLS port_excess = alpha + beta bench_excess + e, with Newey-West (Bartlett) standard errors.

    Returns (alpha, beta, t-stat of alpha), alpha per period of the inputs.
    """
    y = np.asarray(port_excess, float)
    X = np.column_stack([np.ones(len(y)), np.asarray(bench_excess, float)])
    n = len(y)
    lags = newey_west_lags(n) if lags is None else lags
    XtX_inv = np.linalg.inv(X.T @ X)
    coef = XtX_inv @ X.T @ y
    u = y - X @ coef
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        G = Xu[lag:].T @ Xu[:-lag]
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    return float(coef[0]), float(coef[1]), float(coef[0] / np.sqrt(cov[0, 0]))


def summary(net, gross, log, benchmark="benchmark"):
    """One row per portfolio with the plan's metrics (all annualized except ES and drawdowns)."""
    rf = risk_free_daily(net.index)
    years = len(net) / A
    rf_m, bench_m = monthly(rf), monthly(net[benchmark])
    rows = {}
    for p in net.columns:
        r, active = net[p], net[p] - net[benchmark]
        te = active.std() * np.sqrt(A)
        port_m = monthly(r)
        alpha, beta, t_alpha = jensen(port_m - rf_m, bench_m - rf_m) if te > 0 else (np.nan, 1.0, np.nan)
        trades = log.loc[log["portfolio"] == p]
        rows[p] = {
            "Return (CAGR)": cagr(r),
            "Volatility": r.std() * np.sqrt(A),
            "Sharpe": (r - rf).mean() * A / (r.std() * np.sqrt(A)),
            "Active return (net)": active.mean() * A,
            "Active return (gross)": (gross[p] - gross[benchmark]).mean() * A,
            "Active CAGR": cagr(r) - cagr(net[benchmark]),
            "Realized TE": te,
            "Realized TE (monthly)": (port_m - bench_m).std() * np.sqrt(12),
            "Information ratio": active.mean() * A / te if te > 0 else np.nan,
            "t-stat active return": active.mean() / active.std() * np.sqrt(len(active)) if te > 0 else np.nan,
            "Jensen alpha (annualized)": alpha * 12,
            "Jensen beta": beta,
            "t-stat Jensen alpha (Newey-West)": t_alpha,
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

"""Automatic signals and Black-Litterman views for the Conviction Budget Fund.

Moved from notebooks/01_data_audit.ipynb (cells 8 and 10) so that the views used by the backtest and the app
come from tested code. Conventions:
- Momentum 12-1 at month-end t: RI(t-1) / RI(t-12) - 1. Month t is skipped, so it uses data up to month-end t-1.
- Trend at month-end t: SPY price / its 200-session moving average - 1, using prices up to the close of t.
- Weights decided at month-end t are traded on the next session and earn the returns of month t+1.
- Views are equilibrium-relative (see src/black_litterman.py): Q is the spread the signal adds on top of the
  spread the benchmark already implies.
"""

import numpy as np
import pandas as pd

from . import config
from .data import TICKERS


# Month-end values: read a daily series on the last NYSE session of each month. A missing month-end stays
# NaN, and the incomplete final month (data ending before its last session) is dropped.
def at_month_ends(daily, month_ends, incomplete_final=None):
    """Values of a daily Series/DataFrame at each month-end session, indexed by month (Period)."""
    me = month_ends if incomplete_final is None else month_ends.drop(index=incomplete_final.index)
    values = daily.reindex(me.values)
    values.index = me.index
    return values


# Momentum signal: how much each ETF gained over the last 12 months, leaving out the most recent month.
def momentum_12_1(ri, month_ends, incomplete_final=None):
    """12-1 momentum from the Total Return Index, one row per decision month (NaN until 12 months exist)."""
    ri_me = at_month_ends(ri, month_ends, incomplete_final)
    return ri_me.shift(1) / ri_me.shift(12) - 1


# Trend signal: is the S&P 500 above (equities favoured) or below (bonds favoured) its 200-day average?
def trend_spy_ma200(spy_price, month_ends, incomplete_final=None):
    """SPY vs its 200-session moving average at each month-end: price, MA200, Trend, Signal (+1 / -1)."""
    ma200 = spy_price.rolling(200, min_periods=200).mean()     # backward-looking: sessions up to t
    me = month_ends if incomplete_final is None else month_ends.drop(index=incomplete_final.index)
    trend = pd.DataFrame({
        "MonthEnd": me.dt.strftime("%Y-%m-%d").values,
        "SPY_price": spy_price.reindex(me.values).values,
        "MA200": ma200.reindex(me.values).values,
    }, index=me.index)
    trend["Trend"] = trend["SPY_price"] / trend["MA200"] - 1
    trend["Signal"] = np.sign(trend["Trend"])
    return trend.dropna(subset=["Trend"])


# Calibration: choose K so that the 5% cap binds for about 10% of views, using 2009-2015 only.
def calibration_months(index, start=config.CALIB_START, end=config.CALIB_END):
    """Months of the index inside the calibration window."""
    return index[(index >= pd.Period(start, "M")) & (index <= pd.Period(end, "M"))]


def calibrate_k(momentum, trend, cap=config.VIEW_CAP, target=config.CAP_TARGET_SHARE,
                start=config.CALIB_START, end=config.CALIB_END):
    """(K_MOM, K_TREND) such that K x (1 - target) quantile of the signal = cap, on the calibration window.

    One K for all momentum views (pooled over the three asset classes), one K for the trend view.
    """
    months = calibration_months(momentum.index, start, end)
    spreads = pd.Series([momentum.loc[m, members].max() - momentum.loc[m, members].min()
                         for m in months for members in config.ASSET_CLASSES.values()])
    trend_abs = trend.loc[trend.index.isin(months), "Trend"].abs()
    q_mom, q_trend = spreads.quantile(1 - target), trend_abs.quantile(1 - target)
    if not (np.isfinite(q_mom) and q_mom > 0 and np.isfinite(q_trend) and q_trend > 0):
        raise ValueError("Calibration window has no usable signal")
    return cap / q_mom, cap / q_trend


# Views: each month, 3 momentum views (best beats worst ETF in each asset class) and 1 trend view
# (equities vs bonds, weighted like the benchmark). Q = K x signal, capped at 5% a year.
def build_views(momentum, trend, k_mom=config.K_MOM, k_trend=config.K_TREND, cap=config.VIEW_CAP):
    """One row per view: Month, View, one P column per ticker, Q (annual, decimal)."""
    bench = pd.Series(config.BENCHMARK)
    eq = bench[config.ASSET_CLASSES["Equities"]]
    bd = bench[config.ASSET_CLASSES["Bonds"]]
    rows = []
    for month in momentum.dropna(how="all").index:
        mom = momentum.loc[month]
        for cls, members in config.ASSET_CLASSES.items():
            m = mom[members]
            if m.isna().any():
                continue
            best, worst = m.idxmax(), m.idxmin()
            p = pd.Series(0.0, index=TICKERS)
            p[best], p[worst] = 1.0, -1.0
            q = min(k_mom * (m[best] - m[worst]), cap)
            rows.append({"Month": month, "View": f"Momentum {cls}: {best} > {worst}", **p, "Q": q})
        if month in trend.index:
            p = pd.Series(0.0, index=TICKERS)
            p[eq.index] = eq / eq.sum()
            p[bd.index] = -bd / bd.sum()
            q = float(np.clip(k_trend * trend.loc[month, "Trend"], -cap, cap))
            rows.append({"Month": month, "View": "Trend: equities vs bonds", **p, "Q": q})
    return pd.DataFrame(rows)


def check_views(views, cap=config.VIEW_CAP):
    """Raise if a view is not relative, a month lacks its 4 views, the trend baskets are wrong or |Q| > cap."""
    trend_rows = views["View"] == "Trend: equities vs bonds"
    if not np.allclose(views[TICKERS].sum(axis=1), 0):
        raise ValueError("A view is not relative (P row does not sum to 0)")
    if not (views.groupby("Month").size() == 4).all():
        raise ValueError("Not 4 views every month")
    if not (np.allclose(views.loc[trend_rows, config.ASSET_CLASSES["Equities"]].sum(axis=1), 1.0)
            and np.allclose(views.loc[trend_rows, config.ASSET_CLASSES["Bonds"]].sum(axis=1), -1.0)):
        raise ValueError("Trend view baskets do not sum to +1 / -1")
    if views["Q"].abs().max() > cap + 1e-12:
        raise ValueError("Q above cap")

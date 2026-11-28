"""Tests for src/signals.py: no look-ahead, view structure, caps and calibration on 2009-2015 only.

The first tests use a small synthetic dataset; the last ones use the exported signals in data/processed/
(no raw Datastream file needed).
"""

import numpy as np
import pandas as pd
import pytest

from src import config, data, signals
from src.data import TICKERS


# Synthetic data: random total return indices on real NYSE sessions, 2006-2010.
@pytest.fixture(scope="module")
def synthetic():
    sessions = data.nyse_sessions("2006-01-01", "2010-12-31")
    rng = np.random.default_rng(0)
    ri = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(sessions), len(TICKERS))), axis=0)),
                      index=sessions, columns=TICKERS)
    month_ends = data.month_end_sessions(sessions[0], sessions[-1])
    return ri, month_ends


def test_momentum_has_no_look_ahead(synthetic):
    ri, month_ends = synthetic
    month = pd.Period("2009-06", "M")
    before = signals.momentum_12_1(ri, month_ends).loc[month]
    shocked = ri.copy()
    shocked.loc[shocked.index > month_ends[month - 1]] *= 3.0     # change everything after month-end t-1
    after = signals.momentum_12_1(shocked, month_ends).loc[month]
    pd.testing.assert_series_equal(before, after)


def test_momentum_equals_compounded_monthly_returns(synthetic):
    ri, month_ends = synthetic
    mom = signals.momentum_12_1(ri, month_ends)
    monthly = data.monthly_returns(ri)[0]
    compounded = (1 + monthly).shift(1).rolling(11, min_periods=11).apply(np.prod, raw=True) - 1
    common = mom.dropna().index.intersection(compounded.dropna().index)
    assert len(common) > 0
    assert np.allclose(mom.loc[common], compounded.loc[common], atol=1e-12)


def test_trend_has_no_look_ahead(synthetic):
    ri, month_ends = synthetic
    spy = ri["SPY"]
    month = pd.Period("2009-06", "M")
    before = signals.trend_spy_ma200(spy, month_ends).loc[month, "Trend"]
    shocked = spy.copy()
    shocked.loc[shocked.index > month_ends[month]] *= 3.0          # change everything after month-end t
    after = signals.trend_spy_ma200(shocked, month_ends).loc[month, "Trend"]
    assert before == after


def test_views_are_relative_capped_and_complete(synthetic):
    ri, month_ends = synthetic
    mom = signals.momentum_12_1(ri, month_ends)
    trend = signals.trend_spy_ma200(ri["SPY"], month_ends)
    views = signals.build_views(mom, trend, k_mom=10.0, k_trend=10.0)  # huge K: the cap must bind
    signals.check_views(views)                                         # P rows sum to 0, 4 views a month
    assert np.isclose(views["Q"].abs().max(), config.VIEW_CAP)


# Real exported signals (data/processed/), indexed by decision month.
@pytest.fixture(scope="module")
def exported():
    mom = pd.read_csv(data.PROCESSED_DIR / "momentum_12_1.csv", index_col="Month").drop(columns="MonthEnd")
    mom.index = pd.PeriodIndex(mom.index, freq="M")
    trend = pd.read_csv(data.PROCESSED_DIR / "trend_spy_ma200.csv", index_col="Month")
    trend.index = pd.PeriodIndex(trend.index, freq="M")
    views = pd.read_csv(data.PROCESSED_DIR / "bl_views.csv")
    return mom, trend, views


def test_calibration_uses_2009_2015_only(exported):
    mom, trend, _ = exported
    k = signals.calibrate_k(mom, trend)
    later = mom.index > pd.Period(config.CALIB_END, "M")
    mom2, trend2 = mom.copy(), trend.copy()
    mom2.loc[later] *= 5.0
    trend2.loc[trend2.index > pd.Period(config.CALIB_END, "M"), "Trend"] *= 5.0
    assert signals.calibrate_k(mom2, trend2) == k


def test_config_k_is_the_rounded_calibration(exported):
    mom, trend, _ = exported
    k_mom, k_trend = signals.calibrate_k(mom, trend)
    assert (round(k_mom, 2), round(k_trend, 2)) == (config.K_MOM, config.K_TREND)


def test_build_views_reproduces_exported_views(exported):
    mom, trend, saved = exported
    views = signals.build_views(mom, trend)
    views["Month"] = views["Month"].astype(str)
    pd.testing.assert_frame_equal(views.reset_index(drop=True), saved, check_exact=False, rtol=0, atol=1e-15)

"""Checks for the walk-forward backtest (plan task 7). Short sample (2016) to keep them fast."""

import numpy as np
import pandas as pd
import pytest

from src.backtest import run_backtest
from src.data import TICKERS, load_processed
from src.optimizer import BENCH, check_rules, load_inputs

FIRST, LAST = "2015-12", "2016-11"


@pytest.fixture(scope="module")
def inputs():
    return load_inputs()


@pytest.fixture(scope="module")
def full(inputs):
    return run_backtest("full", inputs, FIRST, LAST)


def weights(monthly):
    return monthly[[f"w_{t}" for t in TICKERS]].set_axis(TICKERS, axis=1)


def test_one_return_per_session_of_the_evaluation_period(inputs, full):
    daily, _ = full
    sessions = inputs.daily.loc["2016-01-01":"2016-12-31"].index
    assert daily.index.equals(sessions)


def test_targets_respect_the_mandate(full):
    _, monthly = full
    for _, x in weights(monthly).iterrows():
        assert check_rules(x, "full") == []


def test_cost_is_5bp_of_traded_notional(full):
    daily, monthly = full
    assert np.allclose(monthly["cost"], 5e-4 * monthly["traded"])
    assert np.isclose(daily["cost"].sum(), monthly["cost"].sum())
    assert np.allclose(1 + daily["net"], (1 + daily["gross"]) * (1 - daily["cost"]))


def test_zero_cost_gives_gross(inputs):
    daily, _ = run_backtest("full", inputs, FIRST, LAST, cost_bp=0.0)
    assert np.allclose(daily["net"], daily["gross"])


def test_benchmark_close_to_static_monthly_weights(inputs):
    """Differences come only from intra-month drift and the next-day rebalance."""
    daily, monthly = run_backtest(None, inputs, FIRST, LAST)
    assert (monthly["cost"] == 0).all()
    _, _, mon = load_processed()
    static = mon.loc["2016-01":"2016-12", TICKERS] @ BENCH
    realized = (1 + daily["net"]).groupby(daily.index.to_period("M")).prod() - 1
    assert (realized - static).abs().mean() < 5e-4


def test_no_look_ahead(inputs):
    """Corrupting returns after the last decision's month-end must not change any decision."""
    _, base = run_backtest("full", inputs, FIRST, "2016-06")
    cut = inputs.month_ends[pd.Period("2016-06", "M")]
    daily = inputs.daily.copy()
    daily.loc[daily.index > cut, TICKERS] *= -3
    corrupted = type(inputs)(daily=daily, month_ends=inputs.month_ends, views=inputs.views)
    _, other = run_backtest("full", corrupted, FIRST, "2016-06")
    pd.testing.assert_frame_equal(weights(base), weights(other))


def test_failed_optimization_falls_back_to_benchmark(inputs, monkeypatch):
    import src.optimizer as op
    equal = pd.Series(1 / len(TICKERS), index=TICKERS)        # what a broken optimizer might return
    monkeypatch.setattr(op, "propose_weights", lambda *args, **kwargs: (equal, False, 2.0))
    x, diag = op.propose_portfolio("2020-03", inputs, x_prev=BENCH, rules="full")
    assert diag["fallback_to_benchmark"] and not diag["ok"]
    assert np.allclose(x.values, BENCH.values) and check_rules(x, "full") == []
    _, monthly = run_backtest("full", inputs=inputs, first="2016-01", last="2016-02")
    assert monthly["fallback_to_benchmark"].all()


def test_naive_mvo_alpha_has_no_look_ahead(inputs):
    from src.optimizer import naive_alpha
    month_end = inputs.month_ends[pd.Period("2020-06", "M")]
    before = naive_alpha(inputs.daily, month_end)
    shocked = inputs.daily.copy()
    later = shocked.index > month_end
    shocked.loc[later, TICKERS] = shocked.loc[later, TICKERS] * 50
    assert np.allclose(naive_alpha(shocked, month_end), before)


def test_frontier_rules_only_lower_it(inputs):
    from src.frontier import frontier
    f = frontier("2026-10", inputs, te_grid=[0.01, 0.02, 0.04]).set_index(["rules", "TE budget"])
    mu = f["Expected active return"]
    free = f.loc["none", "Ex-ante IR"]
    assert np.allclose(free, free.iloc[0], rtol=1e-3)            # no rules: straight line, constant IR
    for te in [0.01, 0.02, 0.04]:                                  # nested rule sets: full <= long-only <= none
        assert mu[("full", te)] <= mu[("long_only", te)] + 1e-7 <= mu[("none", te)] + 2e-7

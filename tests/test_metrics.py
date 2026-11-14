"""Checks for the performance metrics (plan task 8): known answers on small synthetic series."""

import numpy as np
import pandas as pd
import pytest

from src.metrics import cagr, expected_shortfall, max_drawdown, risk_free_daily, summary

DAYS = pd.bdate_range("2020-01-01", periods=252)


def test_cagr_of_constant_daily_return():
    r = pd.Series(0.001, index=DAYS)
    assert np.isclose(cagr(r), 1.001 ** 252 - 1)


def test_max_drawdown_known_path():
    r = pd.Series([0.10, -0.20, 0.05, -0.10, 0.50])        # NAV 1.1, 0.88, 0.924, 0.8316, ...
    assert np.isclose(max_drawdown(r), 1 - 0.8316 / 1.1)


def test_expected_shortfall_is_mean_of_worst_tail():
    r = pd.Series(np.arange(-10, 10) / 100)                  # 20 returns, worst 5% = the single -10%
    assert np.isclose(expected_shortfall(r), 0.10)


def test_risk_free_uses_previous_close():
    days = pd.DatetimeIndex(["2026-10-29", "2026-10-30", "2026-11-02"])
    rf = risk_free_daily(days)
    assert rf.notna().all()
    assert np.isclose(rf["2026-11-02"], 4.06 / 100 / 252)  # DGS1MO published on 2026-10-30


@pytest.fixture
def toy():
    rng = np.random.default_rng(0)
    bench = pd.Series(rng.normal(3e-4, 0.01, 252), index=DAYS)
    port = bench + rng.normal(1e-4, 0.001, 252)
    net = pd.DataFrame({"benchmark": bench, "port": port})
    gross = net.assign(port=port + 5e-5)
    log = pd.DataFrame({"portfolio": ["benchmark", "port"], "traded": [0.0, 1.0], "cost": [0.0, 5e-4]})
    return net, gross, log


def test_summary_definitions(toy):
    net, gross, log = toy
    t = summary(net, gross, log)
    active = net["port"] - net["benchmark"]
    assert np.isclose(t.loc["port", "Realized TE"], active.std() * np.sqrt(252))
    assert np.isclose(t.loc["port", "Information ratio"],
                      t.loc["port", "Active return (net)"] / t.loc["port", "Realized TE"])
    assert np.isclose(t.loc["port", "Active return (gross)"] - t.loc["port", "Active return (net)"], 5e-5 * 252)
    assert np.isclose(t.loc["port", "Cost (per year)"], 5e-4)  # one year of data
    assert t.loc["benchmark", "Realized TE"] == 0 and np.isnan(t.loc["benchmark", "Information ratio"])

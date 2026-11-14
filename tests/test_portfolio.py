"""Tests for src/black_litterman.py and src/optimizer.py (synthetic inputs, no data files needed).

Run from the project root with:  pytest
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.black_litterman import (add_manual_view, bl_alpha, bl_posterior, covariance_at,  # noqa: E402
                                 implied_excess_returns, ledoit_wolf_cc)
from src.data import TICKERS  # noqa: E402
from src.optimizer import BENCH, check_rules, optimize, propose_weights, tracking_error  # noqa: E402

N = len(TICKERS)


def make_sigma(seed=0):
    """Realistic 8-asset annual covariance: equity block, bond block, alternatives."""
    vol = np.array([0.15, 0.17, 0.22, 0.06, 0.07, 0.13, 0.19, 0.15])
    C = np.full((N, N), 0.2)
    C[:3, :3], C[3:6, 3:6] = 0.8, 0.85
    C[:3, 3:6] = C[3:6, :3] = -0.1
    np.fill_diagonal(C, 1.0)
    return C * np.outer(vol, vol)


def random_alpha(seed):
    return np.random.default_rng(seed).normal(0, 0.01, N)


# --- Covariance -------------------------------------------------------------
def brute_force_delta(X):
    """Direct (loop) implementation of the Ledoit-Wolf constant-correlation intensity."""
    T, n = X.shape
    X = X - X.mean(0)
    S = X.T @ X / T
    sd = np.sqrt(np.diag(S))
    rbar = ((S / np.outer(sd, sd)).sum() - n) / (n * (n - 1))
    F = rbar * np.outer(sd, sd)
    np.fill_diagonal(F, np.diag(S))
    pi = sum(np.mean((X[:, i] * X[:, j] - S[i, j]) ** 2) for i in range(n) for j in range(n))
    rho = sum(np.mean((X[:, i] ** 2 - S[i, i]) ** 2) for i in range(n))
    for i in range(n):
        for j in range(n):
            if i != j:
                t_ii = np.mean((X[:, i] ** 2 - S[i, i]) * (X[:, i] * X[:, j] - S[i, j]))
                t_jj = np.mean((X[:, j] ** 2 - S[j, j]) * (X[:, i] * X[:, j] - S[i, j]))
                rho += rbar / 2 * (np.sqrt(S[j, j] / S[i, i]) * t_ii + np.sqrt(S[i, i] / S[j, j]) * t_jj)
    return float(np.clip((pi - rho) / ((F - S) ** 2).sum() / T, 0, 1))


def test_ledoit_wolf_matches_brute_force_and_is_psd():
    X = np.random.default_rng(1).multivariate_normal(np.zeros(N), make_sigma() / 252, size=252)
    Sigma, delta, _ = ledoit_wolf_cc(X)
    assert 0 <= delta <= 1
    assert abs(delta - brute_force_delta(X)) < 1e-10
    assert np.allclose(Sigma, Sigma.T) and np.linalg.eigvalsh(Sigma).min() > 0


def test_ledoit_wolf_shrinks_fully_when_truth_is_constant_correlation():
    C = np.full((N, N), 0.5) + 0.5 * np.eye(N)
    X = np.random.default_rng(2).multivariate_normal(np.zeros(N), C * 1e-4, size=252)
    assert ledoit_wolf_cc(X)[1] > 0.9


def test_covariance_uses_only_past_regular_returns():
    dates = pd.bdate_range("2020-01-01", periods=400)
    daily = pd.DataFrame(np.random.default_rng(3).normal(0, 0.01, (400, N)), index=dates, columns=TICKERS)
    daily["regular"] = True
    end = dates[300]
    Sigma, _, _ = covariance_at(daily, end)
    shocked = daily.copy()
    shocked.loc[dates[301]:, TICKERS] *= 50                 # future data must not matter
    assert np.allclose(covariance_at(shocked, end)[0], Sigma)
    with pytest.raises(ValueError):
        covariance_at(daily, dates[100])                     # fewer than 252 observations


# --- Black-Litterman ----------------------------------------------------------
def test_ln4_example_4_implied_returns():
    s = np.array([0.15, 0.20, 0.25, 0.30])
    C = np.array([[1, .1, .4, .5], [.1, 1, .7, .4], [.4, .7, 1, .8], [.5, .4, .8, 1]])
    pi, phi, sigma_b = implied_excess_returns(C * np.outer(s, s), [.4, .3, .2, .1], sr=0.25)
    assert abs(sigma_b - 0.1535) < 5e-5 and abs(phi - 1.63) < 5e-3
    assert np.allclose(0.03 + pi, [0.0547, 0.0668, 0.0870, 0.0906], atol=5e-5)


def test_posterior_properties():
    Sigma = make_sigma()
    pi = implied_excess_returns(Sigma, BENCH, 0.4)[0]
    P = np.zeros((2, N)); P[0, [0, 2]] = [-1, 1]; P[1, [4, 5]] = [1, -1]
    Q = np.array([0.02, 0.01])
    base = bl_posterior(pi, Sigma, P, P @ pi + Q, 0.5)
    assert np.allclose(bl_posterior(pi, Sigma, P, P @ pi + Q, 0.5, tau=1.0), base)   # tau cancels
    assert np.allclose(bl_posterior(pi, Sigma, P, P @ pi, 0.5), pi)                  # no excess view
    assert np.allclose(P @ bl_posterior(pi, Sigma, P, P @ pi + Q, 1.0), P @ pi + Q)  # full confidence
    assert np.allclose(base - pi, bl_alpha(Sigma, P, Q, 0.5))                         # prior cancels
    with pytest.raises(ValueError):
        bl_posterior(pi, Sigma, P, Q, 0.0)


# --- Optimizer ---------------------------------------------------------------
def test_unconstrained_optimizer_matches_closed_form():
    Sigma, alpha = make_sigma(), random_alpha(4)
    Si, one = np.linalg.inv(Sigma), np.ones(N)
    a = Si @ (alpha - (one @ Si @ alpha) / (one @ Si @ one) * one)
    a *= config.TE_TARGET / np.sqrt(a @ Sigma @ a)
    x, ok = optimize(alpha, Sigma, rules="none")
    assert ok and np.allclose(x.values - BENCH.values, a, atol=1e-6)


def test_benchmark_is_feasible_and_no_view_gives_benchmark():
    assert check_rules(BENCH, "full") == []
    x, ok = optimize(np.zeros(N), make_sigma(), rules="full")
    assert ok and np.allclose(x, BENCH)


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("rules", ["full", "long_only"])
def test_mandate_and_te_budget_hold(seed, rules):
    Sigma = make_sigma()
    x, ok = optimize(random_alpha(seed), Sigma, rules=rules)
    assert ok and check_rules(x, rules) == []
    assert tracking_error(x, Sigma) == pytest.approx(config.TE_TARGET, rel=1e-4)


def test_view_moves_portfolio_in_its_direction():
    Sigma = make_sigma()
    P, Q, names, conf = add_manual_view(np.zeros((0, N)), np.zeros(0), [], np.zeros(0),
                                        {"long": "EFA", "short": "SPY", "q": 0.03, "confidence": 0.8})
    x, ok = optimize(bl_alpha(Sigma, P, Q, conf), Sigma, rules="full")
    assert ok and names == ["Manual: EFA > SPY"]
    assert x["EFA"] > BENCH["EFA"] and x["SPY"] < BENCH["SPY"]


def test_turnover_cap_is_respected_and_relaxed_only_when_needed():
    Sigma, alpha = make_sigma(), random_alpha(5)
    x_prev = BENCH.copy()
    x, ok, relaxed = propose_weights(alpha, Sigma, "full", x_prev=x_prev, max_turnover=0.05)
    assert ok and relaxed is None and np.abs(x - x_prev).sum() <= 0.05 + 1e-6
    assert check_rules(x, "full") == [] and tracking_error(x, Sigma) <= config.TE_TARGET * (1 + 1e-5)

    far = pd.Series([0.40, 0.10, 0.0, 0.0, 0.0, 0.25, 0.25, 0.0], index=TICKERS)   # TE far above 2%
    x, ok, relaxed = propose_weights(alpha, Sigma, "full", x_prev=far, max_turnover=0.05)
    assert ok and relaxed is not None and relaxed > 0.05
    assert check_rules(x, "full") == [] and tracking_error(x, Sigma) <= config.TE_TARGET * (1 + 1e-5)

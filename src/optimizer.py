"""Constrained optimizer and rule checks for the Conviction Budget Fund (Person B).

Problem (LN2 sigma-problem, active weights a = x - b):
    max  alpha' a
    s.t. 1'x = 1,  a' Sigma a <= TE^2,  mandate rules (G x <= h),
         optional LN3 turnover cap sum|x - x_prev| <= cap (Scherer split x = x_prev + u+ - u-).
Priority when infeasible: mandate and TE are hard; the turnover cap is relaxed to the smallest feasible
value (bisection) and flagged. If no valid portfolio is found at all, the fund holds the benchmark
(diagnostics flag 'fallback_to_benchmark').

Entry point for the backtest and the app: propose_portfolio(month, inputs, x_prev, rules, ...).
rules: 'full' (mandate), 'long_only' (x >= 0 only), 'none' (fully invested only).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import config
from .black_litterman import (add_manual_view, bl_alpha, covariance_at, implied_excess_returns,
                              load_views, view_matrices)
from .data import TICKERS, load_processed

BENCH = pd.Series(config.BENCHMARK)[TICKERS]
EQUITY, BONDS = config.ASSET_CLASSES["Equities"], config.ASSET_CLASSES["Bonds"]
RULES = ("full", "long_only", "none")
MAX_TWO_WAY_TURNOVER = 2.0      # selling everything and buying a new portfolio: sum|x - x_prev| <= 2
RELAX_TOL = 1e-4                # precision of the relaxed turnover cap (0.01 percentage point)


# Mandate: write the fund's rules (long-only, bond range, EEM share of equities, 40% cap per ETF)
# as linear constraints G x <= h, and check a portfolio against them.
def linear_rules(rules):
    """Mandate as G x <= h."""
    if rules not in RULES:
        raise ValueError(f"rules must be one of {RULES}")
    n, eye = len(TICKERS), np.eye(len(TICKERS))
    ind = lambda names: np.array([t in names for t in TICKERS], float)
    G, h = [], []
    if rules in ("full", "long_only"):
        G += list(-eye); h += [0.0] * n
    if rules == "full":
        G += list(eye); h += [config.MAX_WEIGHT] * n
        G += [-ind(BONDS), ind(BONDS)]; h += [-config.BOND_MIN, config.BOND_MAX]
        G += [ind(["EEM"]) - config.EEM_MAX_SHARE_OF_EQUITY * ind(EQUITY)]; h += [0.0]
        for t in BONDS:                                      # |x_t - b_t| <= BOND_ACTIVE_CAP
            G += [ind([t]), -ind([t])]
            h += [BENCH[t] + config.BOND_ACTIVE_CAP, -(BENCH[t] - config.BOND_ACTIVE_CAP)]
    if not G:
        return np.zeros((0, n)), np.zeros(0)
    return np.array(G), np.array(h)


def check_rules(x, rules="full", tol=1e-6):
    """List of violated rules (empty list = valid portfolio)."""
    x = pd.Series(x, index=TICKERS) if not isinstance(x, pd.Series) else x
    bad = []
    if abs(x.sum() - 1) > tol:
        bad.append("sum != 1")
    if rules in ("full", "long_only") and (x < -tol).any():
        bad.append("short position")
    if rules == "full":
        if (x > config.MAX_WEIGHT + tol).any():
            bad.append("weight > 40%")
        if not (config.BOND_MIN - tol <= x[BONDS].sum() <= config.BOND_MAX + tol):
            bad.append("bonds outside 25-45%")
        if x["EEM"] > config.EEM_MAX_SHARE_OF_EQUITY * x[EQUITY].sum() + tol:
            bad.append("EEM > 1/3 equity")
        if ((x[BONDS] - BENCH[BONDS]).abs() > config.BOND_ACTIVE_CAP + tol).any():
            bad.append("bond ETF more than 5 points from benchmark")
    return bad


def tracking_error(x, Sigma, b=BENCH):
    a = np.asarray(x, float) - np.asarray(b, float)
    return float(np.sqrt(a @ np.asarray(Sigma, float) @ a))


# Optimizer: pick the weights with the highest expected extra return while keeping tracking
# error within budget, the mandate respected and turnover capped (the sigma-problem of LN2).
def optimize(alpha, Sigma, rules="full", te=config.TE_TARGET, b=BENCH, x_prev=None, max_turnover=None,
             cost=0.0):
    """Solve the sigma-problem; returns (weights Series, feasible flag).

    cost: penalty per unit of two-way turnover, in the units of alpha (annual return); used only when x_prev
    is given. 0 = the objective ignores trading costs.
    """
    n = len(TICKERS)
    a_vec, S, b_vec = np.asarray(alpha, float), np.asarray(Sigma, float), np.asarray(b, float)
    norm = np.linalg.norm(a_vec)
    d = a_vec / norm if norm > 1e-12 else np.zeros(n)       # only the direction of alpha matters
    G, h = linear_rules(rules)
    use_tc = x_prev is not None and max_turnover is not None

    if not use_tc and norm <= 1e-12:                         # no conviction -> hold the benchmark
        return pd.Series(b_vec, index=TICKERS), True

    m = 3 * n if use_tc else n                                # z = [a, u_plus, u_minus] or z = a
    A = lambda z: z[:n]
    pad = lambda v: np.r_[v, np.zeros(m - n)]
    padG = lambda M: np.hstack([M, np.zeros((M.shape[0], m - n))])
    cons = [{"type": "eq", "fun": lambda z: A(z).sum(), "jac": lambda z: pad(np.ones(n))},
            {"type": "ineq", "fun": lambda z: 1 - A(z) @ S @ A(z) / te ** 2,
             "jac": lambda z: pad(-2 * S @ A(z) / te ** 2)}]
    if len(h):
        cons.append({"type": "ineq", "fun": lambda z: h - G @ (b_vec + A(z)), "jac": lambda z: padG(-G)})
    if use_tc:
        x0 = np.asarray(x_prev, float)
        cons += [{"type": "eq", "fun": lambda z: b_vec + A(z) - x0 - z[n:2 * n] + z[2 * n:],
                  "jac": lambda z: np.hstack([np.eye(n), -np.eye(n), np.eye(n)])},
                 {"type": "ineq", "fun": lambda z: max_turnover - z[n:].sum(),
                  "jac": lambda z: np.r_[np.zeros(n), -np.ones(2 * n)]}]
        z0, bounds = np.r_[x0 - b_vec, np.zeros(2 * n)], [(None, None)] * n + [(0, None)] * (2 * n)
    else:
        z0, bounds = np.zeros(n), None

    # Objective scaled by 1/|alpha| for conditioning: -(alpha'a - cost * total trade) / |alpha|
    w = cost / norm if (use_tc and cost > 0 and norm > 1e-12) else 0.0
    grad = pad(-d) + (np.r_[np.zeros(n), np.full(2 * n, w)] if w else 0.0)
    objective = (lambda z: -d @ A(z) + w * z[n:].sum()) if w else (lambda z: -d @ A(z))
    res = minimize(objective, z0, jac=lambda z: grad, bounds=bounds, method="SLSQP",
                   constraints=cons, options={"ftol": 1e-12, "maxiter": 1000})
    x = b_vec + res.x[:n]
    x[np.abs(x) < 1e-9] = 0.0                                 # solver noise
    x = pd.Series(x, index=TICKERS)
    # SLSQP may report 'positive directional derivative' AT the optimum when many constraints bind,
    # so feasibility is checked directly
    feasible = not check_rules(x, rules) and tracking_error(x, S, b_vec) <= te * (1 + 1e-5)
    if use_tc:
        feasible = feasible and np.abs(x.values - x0).sum() <= max_turnover + 1e-6
    return x, bool(res.success) or feasible


def propose_weights(alpha, Sigma, rules="full", x_prev=None, max_turnover=config.MAX_TURNOVER,
                    te=config.TE_TARGET, cost=0.0):
    """Optimize; if the turnover cap makes it infeasible, relax it only as far as needed.

    The mandate and the TE budget are hard constraints. When they cannot be met within the turnover cap,
    the smallest feasible cap is found by bisection between the cap and 2.0 (the maximum two-way
    turnover), to within RELAX_TOL. Returns (weights, ok, relaxed_cap or None).
    """
    cap = max_turnover if x_prev is not None else None
    x, ok = optimize(alpha, Sigma, rules, te, x_prev=x_prev, max_turnover=cap, cost=cost)
    if ok or cap is None:
        return x, ok, None
    hi = MAX_TWO_WAY_TURNOVER
    x_hi, ok_hi = optimize(alpha, Sigma, rules, te, x_prev=x_prev, max_turnover=hi, cost=cost)
    if not ok_hi:                                             # infeasible even with no cap at all
        return x_hi, False, hi
    lo = cap
    while hi - lo > RELAX_TOL:
        mid = (lo + hi) / 2
        x_mid, ok_mid = optimize(alpha, Sigma, rules, te, x_prev=x_prev, max_turnover=mid, cost=cost)
        if ok_mid:
            hi, x_hi = mid, x_mid
        else:
            lo = mid
    return x_hi, True, hi


# Entry point: one call that gives the proposed portfolio for a month. The backtest and the
# app both use it, so they always run the same model.
@dataclass
class Inputs:
    daily: pd.DataFrame       # daily returns + 'regular' flag
    month_ends: pd.Series     # Period('YYYY-MM') -> last NYSE session (complete months only)
    views: pd.DataFrame       # automatic views (Month, View, P columns, Q)


def load_inputs():
    """Read the saved processed files (works offline)."""
    _, daily, monthly = load_processed()
    return Inputs(daily=daily, month_ends=pd.to_datetime(monthly["MonthEnd"]), views=load_views())


def propose_portfolio(month, inputs, x_prev=None, rules="full", confidence=config.DEFAULT_CONFIDENCE,
                      manual_view=None, max_turnover=config.MAX_TURNOVER, te=config.TE_TARGET, cost=None):
    """Weights decided at the close of `month` (traded next session, earn month t+1).

    x_prev: pre-trade (drifted) weights; None = no turnover cap and no cost (e.g. first month or the app).
    cost: turnover penalty in annual-return units; None = config.cost_penalty() (0 unless a horizon is set).
    manual_view: optional {'long', 'short', 'q', 'confidence'} relative view (q on top of equilibrium).
    Returns (weights Series, diagnostics dict).
    """
    month = pd.Period(month, "M")
    if month not in inputs.month_ends.index:
        raise ValueError(f"{month} is not a complete month in the data")
    Sigma, delta, rbar = covariance_at(inputs.daily, inputs.month_ends[month])
    P, Q, names = view_matrices(inputs.views, month)
    conf = np.full(len(Q), float(confidence))
    if manual_view is not None:
        P, Q, names, conf = add_manual_view(P, Q, names, conf, manual_view)

    alpha = bl_alpha(Sigma, P, Q, conf)
    if x_prev is not None:
        x_prev = pd.Series(x_prev, index=TICKERS) if not isinstance(x_prev, pd.Series) else x_prev[TICKERS]
    cost = config.cost_penalty() if cost is None else cost
    x, ok, relaxed = propose_weights(alpha, Sigma, rules, x_prev, max_turnover, te, cost)
    fallback = not ok
    if fallback:   # no valid portfolio found: hold the benchmark, which always meets the mandate (TE = 0)
        x = BENCH.copy()

    pi = implied_excess_returns(Sigma, BENCH, config.BENCHMARK_SR)[0]   # display only
    a = (x - BENCH).values
    diagnostics = {
        "month": month,
        "ok": ok,
        "fallback_to_benchmark": fallback,
        "violations": check_rules(x, rules),
        "relaxed_turnover_cap": relaxed,
        "te_ex_ante": tracking_error(x, Sigma),
        "expected_active_return": float(alpha @ a),
        "turnover": None if x_prev is None else float(np.abs(x - x_prev).sum()),
        "shrinkage_delta": delta,
        "avg_correlation": rbar,
        "Sigma": Sigma,
        "returns": pd.DataFrame({"prior_pi": pi, "alpha": alpha, "posterior_mu": pi + alpha}, index=TICKERS),
        "views": pd.DataFrame({"Q_over_equilibrium": Q, "confidence": conf, "prior_spread": P @ pi,
                               "posterior_spread": P @ (pi + alpha)}, index=names),
    }
    return x, diagnostics


# Naive mean-variance benchmark strategy (the proposal's 4th portfolio): same optimizer, mandate, TE budget,
# turnover cap and cost penalty, but alpha is simply the average daily return of the last 252 sessions.
def naive_alpha(daily, month_end, window=config.COV_WINDOW):
    """Annualized mean of the last `window` regular daily returns up to month_end (no later data)."""
    hist = daily.loc[:pd.Timestamp(month_end)]
    hist = hist.loc[hist["regular"].astype(bool), TICKERS].tail(window)
    return hist.mean().to_numpy(float) * config.ANNUALIZATION


def propose_mvo(month, inputs, x_prev=None, rules="full", max_turnover=config.MAX_TURNOVER,
                te=config.TE_TARGET, cost=None):
    """Naive MVO weights for `month` (same diagnostics keys as propose_portfolio that the backtest logs)."""
    month = pd.Period(month, "M")
    Sigma, _, _ = covariance_at(inputs.daily, inputs.month_ends[month])
    alpha = naive_alpha(inputs.daily, inputs.month_ends[month])
    if x_prev is not None:
        x_prev = pd.Series(x_prev, index=TICKERS) if not isinstance(x_prev, pd.Series) else x_prev[TICKERS]
    cost = config.cost_penalty() if cost is None else cost
    x, ok, relaxed = propose_weights(alpha, Sigma, rules, x_prev, max_turnover, te, cost)
    if not ok:
        x = BENCH.copy()
    return x, {"ok": ok, "fallback_to_benchmark": not ok, "violations": check_rules(x, rules),
               "relaxed_turnover_cap": relaxed, "te_ex_ante": tracking_error(x, Sigma),
               "expected_active_return": float(alpha @ (x - BENCH).values),
               "turnover": None if x_prev is None else float(np.abs(x - x_prev).sum())}

"""Covariance and Black-Litterman views for the Conviction Budget Fund (Person B).

Conventions (see notebooks/02_bl_optimizer.ipynb):
- Covariance at decision month t: Ledoit-Wolf (2003) shrinkage to constant correlation (LN3) on the
  last COV_WINDOW regular daily returns up to the close of month-end t, annualized x252.
- Prior (LN4): pi = mu_tilde - r = phi * Sigma b, phi = SR(b) / sigma(b).
- Views are EQUILIBRIUM-RELATIVE: Q is the spread the signal adds on top of the prior spread,
  Q_eff = P pi + Q. Hence alpha = mu_bar - pi = Gamma P' (P Gamma P' + Omega)^-1 Q (pi cancels).
- Omega_k = (1 - c_k) / c_k * P_k Gamma P_k' (Idzorek confidence, Walters closed form); tau cancels.
"""

import numpy as np
import pandas as pd

from .config import ANNUALIZATION, COV_WINDOW
from .data import PROCESSED_DIR, TICKERS

VIEWS_FILE = PROCESSED_DIR / "bl_views.csv"


# ---------------------------------------------------------------------------
# Covariance
# ---------------------------------------------------------------------------
def ledoit_wolf_cc(X):
    """Ledoit-Wolf shrinkage to the constant-correlation target.

    X: (T, N) returns. Returns (Sigma, delta, rbar) in the units of X.
    """
    X = np.asarray(X, float)
    T, N = X.shape
    X = X - X.mean(axis=0)
    S = X.T @ X / T
    var = np.diag(S)
    sd = np.sqrt(var)
    rbar = ((S / np.outer(sd, sd)).sum() - N) / (N * (N - 1))
    F = rbar * np.outer(sd, sd)
    np.fill_diagonal(F, var)

    X2 = X ** 2
    pi_mat = X2.T @ X2 / T - S ** 2
    theta = (X ** 3).T @ X / T - var[:, None] * S
    np.fill_diagonal(theta, 0.0)
    rho = np.trace(pi_mat) + rbar * ((sd[None, :] / sd[:, None]) * theta).sum()
    gamma = ((F - S) ** 2).sum()
    delta = float(np.clip((pi_mat.sum() - rho) / gamma / T, 0.0, 1.0))
    return delta * F + (1 - delta) * S, delta, rbar


def covariance_at(daily, month_end, window=COV_WINDOW):
    """Annualized LW covariance known at the close of month_end (no later data is used).

    daily: frame of daily returns with the TICKERS columns and a boolean 'regular' column.
    Returns (Sigma as DataFrame, delta, rbar).
    """
    end = pd.Timestamp(month_end)
    hist = daily.loc[:end]
    hist = hist.loc[hist["regular"].astype(bool), TICKERS].tail(window)
    if len(hist) < window or hist.isna().any().any() or hist.index[-1] != end:
        last = hist.index[-1].date() if len(hist) else None
        raise ValueError(f"Incomplete covariance window at {end.date()}: {len(hist)} obs, last {last}")
    Sigma, delta, rbar = ledoit_wolf_cc(hist.values)
    return pd.DataFrame(Sigma * ANNUALIZATION, index=TICKERS, columns=TICKERS), delta, rbar


# ---------------------------------------------------------------------------
# Prior and posterior
# ---------------------------------------------------------------------------
def implied_excess_returns(Sigma, b, sr):
    """LN4 implied risk premia: pi = phi * Sigma b with phi = sr / sigma(b). Returns (pi, phi, sigma_b)."""
    Sigma, b = np.asarray(Sigma, float), np.asarray(b, float)
    sigma_b = float(np.sqrt(b @ Sigma @ b))
    phi = sr / sigma_b
    return phi * Sigma @ b, phi, sigma_b


def bl_posterior(mu_prior, Sigma, P, Q, conf, tau=0.05):
    """LN4 conditional mean with Gamma = tau Sigma and Omega_k = (1 - c_k)/c_k * P_k Gamma P_k'."""
    Sigma = np.asarray(Sigma, float)
    P = np.atleast_2d(np.asarray(P, float))
    Q = np.asarray(Q, float)
    c = np.broadcast_to(np.asarray(conf, float), Q.shape)
    if np.any(c <= 0) or np.any(c > 1):
        raise ValueError("Confidence must be in (0, 1]")
    Gamma = tau * Sigma
    Omega = np.diag((1 - c) / c * np.diag(P @ Gamma @ P.T))
    return np.asarray(mu_prior, float) + Gamma @ P.T @ np.linalg.solve(P @ Gamma @ P.T + Omega, Q - P @ mu_prior)


def bl_alpha(Sigma, P, Q, conf):
    """Alpha = mu_bar - pi for equilibrium-relative views (the prior cancels: only Sigma, P, Q, conf matter)."""
    n = np.asarray(Sigma).shape[0]
    return bl_posterior(np.zeros(n), Sigma, P, Q, conf)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
def load_views(path=VIEWS_FILE):
    """Automatic views exported by the data notebook (one set of rows per decision month)."""
    views = pd.read_csv(path)
    views["Month"] = pd.PeriodIndex(views["Month"], freq="M")
    return views


def view_matrices(views, month):
    """P (k x n), Q (k,), names for one decision month."""
    v = views.loc[views["Month"] == pd.Period(month, "M")]
    if v.empty:
        raise ValueError(f"No views for {month}")
    return v[TICKERS].to_numpy(float), v["Q"].to_numpy(float), v["View"].tolist()


def add_manual_view(P, Q, names, conf, manual_view):
    """Append one manual relative view: {'long': 'SPY', 'short': 'TLT', 'q': 0.02, 'confidence': 0.6}.

    q is annual and, like the automatic views, measured ON TOP of the equilibrium spread.
    """
    long, short = manual_view["long"], manual_view["short"]
    if long not in TICKERS or short not in TICKERS or long == short:
        raise ValueError("Manual view needs two different tickers")
    p = np.zeros(len(TICKERS))
    p[TICKERS.index(long)], p[TICKERS.index(short)] = 1.0, -1.0
    return (np.vstack([P, p]), np.append(Q, float(manual_view["q"])),
            [*names, f"Manual: {long} > {short}"], np.append(conf, float(manual_view["confidence"])))

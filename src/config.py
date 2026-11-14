"""Project settings shared by the optimizer, the backtest and the app (single source of truth)."""

from .data import TICKERS

BENCHMARK = {"SPY": 0.30, "EFA": 0.12, "EEM": 0.08, "IEF": 0.15,
             "LQD": 0.10, "TLT": 0.10, "VNQ": 0.08, "GLD": 0.07}

ASSET_CLASSES = {
    "Equities": ["SPY", "EFA", "EEM"],
    "Bonds": ["IEF", "LQD", "TLT"],
    "Alternatives": ["VNQ", "GLD"],
}

# Mandate
MAX_WEIGHT = 0.40               # each ETF <= 40%
BOND_MIN, BOND_MAX = 0.25, 0.45  # bonds between 25% and 45%
EEM_MAX_SHARE_OF_EQUITY = 1 / 3  # EEM <= one third of equities

# Method
TE_TARGET = 0.02                # annualized ex-ante tracking-error budget
MAX_TURNOVER = 0.20             # two-way turnover cap, LN3 definition: sum_i |x_i - x_prev_i|
COV_WINDOW = 252                # trailing regular daily returns for the covariance
ANNUALIZATION = 252
DEFAULT_CONFIDENCE = 0.50       # Idzorek confidence of the automatic views
BENCHMARK_SR = 0.40             # only used to DISPLAY implied returns: it cancels out of alpha

assert set(BENCHMARK) == set(TICKERS) and abs(sum(BENCHMARK.values()) - 1) < 1e-12

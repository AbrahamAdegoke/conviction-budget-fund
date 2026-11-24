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
BOND_ACTIVE_CAP = 0.05          # IEF, LQD, TLT within +/-5 points of their benchmark weight (decision 7):
                                # these bonds are ~0.86 correlated, so the covariance understates the risk
                                # of swapping one for another and the optimizer over-trades them

# Method
TE_TARGET = 0.02                # annualized ex-ante tracking-error budget
MAX_TURNOVER = 0.20             # two-way turnover cap, LN3 definition: sum_i |x_i - x_prev_i|
COV_WINDOW = 252                # trailing regular daily returns for the covariance
ANNUALIZATION = 252
DEFAULT_CONFIDENCE = 0.50       # Idzorek confidence of the automatic views
BENCHMARK_SR = 0.40             # only used to DISPLAY implied returns: it cancels out of alpha

# Trading costs
TRADING_COST_BP = 5.0           # cost on traded notional, in basis points (backtest and optimizer)
COST_HORIZON_MONTHS = None      # months over which the expected gain of a trade must pay its cost;
                                # None = the optimizer ignores costs (they are only charged in the backtest)


def cost_penalty(cost_bp=None, horizon_months=None):
    """Penalty per unit of two-way turnover in annual-return units: cost x 12 / horizon (0 if no horizon)."""
    cost_bp = TRADING_COST_BP if cost_bp is None else cost_bp
    horizon_months = COST_HORIZON_MONTHS if horizon_months is None else horizon_months
    return 0.0 if not horizon_months else cost_bp / 1e4 * 12 / horizon_months

# Automatic views (see src/signals.py)
CALIB_START, CALIB_END = "2009-01", "2015-12"  # calibration window: the test period is never used
VIEW_CAP = 0.05                 # |Q| <= 5% a year for every automatic view
CAP_TARGET_SHARE = 0.10         # K is set so that the cap binds for about 10% of views on 2009-2015
# View size Q = K x signal. Frozen at the 2009-2015 calibration rounded to 2 decimals (0.1598 and 0.3892);
# tests/test_signals.py checks that these values still match the calibration.
K_MOM = 0.16
K_TREND = 0.39

assert set(BENCHMARK) == set(TICKERS) and abs(sum(BENCHMARK.values()) - 1) < 1e-12

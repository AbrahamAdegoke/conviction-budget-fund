"""Monthly walk-forward backtest for the Conviction Budget Fund.

Timing (see docs/methodology.md, section 7):
- Decision at the close of month-end t, using only data up to that close (propose_portfolio).
- Trade at the close of the first session of month t+1: that session is still earned by the old,
  drifted weights, then the portfolio is rebalanced to the target.
- Between rebalances the weights drift with daily returns; the drifted weights at month-end t are
  passed to the optimizer as x_prev (turnover cap is measured from what the fund actually holds).
- Cost: cost_bp on traded notional sum|x_target - w_drifted|, deducted on the trade day.
  The benchmark is rebalanced to its fixed weights at no cost (it is the reference index).
- First decision (2015-12) starts from the benchmark weights.

Simulated with daily returns so the next-day trade is exact and the metrics can use realized TE,
drawdown and ES from daily data.
"""

import pandas as pd

from . import config
from .data import PROJECT_ROOT, TICKERS
from .optimizer import BENCH, load_inputs, propose_mvo, propose_portfolio

RESULTS_DIR = PROJECT_ROOT / "data" / "results"

FIRST_DECISION, LAST_DECISION = "2015-12", "2026-09"   # returns earned Jan 2016 - Oct 2026
COST_BP = config.TRADING_COST_BP

# Portfolio name -> optimizer rule set (None = fixed benchmark weights)
# "mvo" = naive mean-variance (past-year average returns as alpha), full mandate
PORTFOLIOS = {"benchmark": None, "bl_te_only": "long_only", "bl_full": "full", "mvo_naive": "mvo"}


def run_backtest(rules, inputs=None, first=FIRST_DECISION, last=LAST_DECISION, cost_bp=COST_BP,
                 max_turnover=config.MAX_TURNOVER, confidence=config.DEFAULT_CONFIDENCE, te=config.TE_TARGET):
    """Sequential backtest of one portfolio.

    rules: None for the benchmark, 'mvo' for the naive MVO, else 'full' / 'long_only' / 'none' (optimizer.RULES).
    cost_bp is both charged on each trade and passed to the optimizer's cost penalty; te is the TE budget.
    Returns (daily, monthly):
      daily   DataFrame indexed by session: gross, cost, net (simple returns)
      monthly DataFrame indexed by decision month: target weights and trade/optimizer diagnostics
    """
    inputs = inputs or load_inputs()
    rets = inputs.daily[TICKERS]
    month_ends = inputs.month_ends
    w = BENCH.copy()                                      # holdings after drift
    penalty = config.cost_penalty(cost_bp)                # the optimizer knows the cost it will be charged
    daily_rows, monthly_rows = [], []

    for m in pd.period_range(first, last, freq="M"):
        # 1) Decision at the close of month-end m
        if rules is None:
            x, diag = BENCH.copy(), {}
        elif rules == "mvo":
            x, diag = propose_mvo(m, inputs, x_prev=w, max_turnover=max_turnover, te=te, cost=penalty)
        else:
            x, diag = propose_portfolio(m, inputs, x_prev=w, rules=rules, confidence=confidence,
                                        max_turnover=max_turnover, te=te, cost=penalty)

        # 2) Hold through month m+1; trade at the close of its first session
        sessions = rets.loc[month_ends[m]:month_ends[m + 1]].iloc[1:]
        for i, (day, r) in enumerate(sessions.iterrows()):
            gross = float(w @ r)
            w = w * (1 + r) / (1 + gross)                 # drift
            cost = 0.0
            if i == 0:
                traded = float((x - w).abs().sum())
                cost = trade_cost = 0.0 if rules is None else cost_bp / 1e4 * traded
                w = x.copy()
            daily_rows.append((day, gross, cost, (1 + gross) * (1 - cost) - 1))

        monthly_rows.append({
            "month": m, "traded": traded, "cost": trade_cost,
            "turnover_ex_ante": diag.get("turnover"), "te_ex_ante": diag.get("te_ex_ante"),
            "expected_active_return": diag.get("expected_active_return"),
            "relaxed_turnover_cap": diag.get("relaxed_turnover_cap"),
            "fallback_to_benchmark": diag.get("fallback_to_benchmark", False),
            "violations": "; ".join(diag.get("violations", [])),
            **{f"w_{t}": x[t] for t in TICKERS},
        })

    daily = pd.DataFrame(daily_rows, columns=["date", "gross", "cost", "net"]).set_index("date")
    monthly = pd.DataFrame(monthly_rows).set_index("month")
    return daily, monthly


def run_all(save=True, **kwargs):
    """Run the four portfolios of the plan and save the results for the metrics and the app (offline)."""
    inputs = load_inputs()
    daily, monthly = {}, {}
    for name, rules in PORTFOLIOS.items():
        daily[name], monthly[name] = run_backtest(rules, inputs, **kwargs)

    net = pd.DataFrame({k: v["net"] for k, v in daily.items()})
    gross = pd.DataFrame({k: v["gross"] for k, v in daily.items()})
    log = pd.concat(monthly, names=["portfolio"]).reset_index()
    if save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        net.to_csv(RESULTS_DIR / "daily_returns_net.csv", index_label="Date")
        gross.to_csv(RESULTS_DIR / "daily_returns_gross.csv", index_label="Date")
        log.to_csv(RESULTS_DIR / "monthly_log.csv", index=False)
    return net, gross, log


def load_results():
    """Read the saved backtest (used by the app and the metrics)."""
    net = pd.read_csv(RESULTS_DIR / "daily_returns_net.csv", index_col="Date", parse_dates=True)
    gross = pd.read_csv(RESULTS_DIR / "daily_returns_gross.csv", index_col="Date", parse_dates=True)
    log = pd.read_csv(RESULTS_DIR / "monthly_log.csv")
    log["month"] = pd.PeriodIndex(log["month"], freq="M")
    return net, gross, log

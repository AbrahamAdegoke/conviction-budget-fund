"""Variants of the backtest on the calibration (2009-2015) and test (2016-2026) periods.

What the proposal promised besides the base case: the four strategies, tracking-error budgets of 1, 2 and 3%,
trading costs of 0, 5 and 25 bp, and the price of the mandate's rules (full mandate vs TE budget only).
Everything uses the same model as the base case; nothing here is tuned. Results are saved to
data/results/variants.csv for the app.

Run from the repository root:  python -m src.variants   (a few minutes)
"""

import numpy as np
import pandas as pd

from . import config
from .backtest import COST_BP, RESULTS_DIR, run_backtest
from .optimizer import load_inputs

PERIODS = {"2009-2015": ("2008-12", "2015-11"), "2016-2026": ("2015-12", "2026-09")}
STRATEGIES = {"bl_full": "full", "bl_te_only": "long_only", "mvo_naive": "mvo"}
TE_BUDGETS = (0.01, 0.02, 0.03)
COSTS_BP = (0.0, 5.0, 25.0)


def measures(daily, monthly, bench):
    """Annualized active return, realized TE (daily and monthly), IR, turnover and cost of one run."""
    active = daily["net"] - bench["net"]
    m_port = (1 + daily["net"]).groupby(daily.index.to_period("M")).prod()
    m_bench = (1 + bench["net"]).groupby(bench.index.to_period("M")).prod()
    years = len(active) / config.ANNUALIZATION
    te = active.std() * np.sqrt(config.ANNUALIZATION)
    return {"Active return (net)": active.mean() * config.ANNUALIZATION,
            "Realized TE": te,
            "Realized TE (monthly)": (m_port - m_bench).std() * np.sqrt(12),
            "Information ratio": active.mean() * config.ANNUALIZATION / te,
            "Turnover (two-way, per year)": monthly["traded"].sum() / years,
            "Cost (per year)": daily["cost"].sum() / years}


def run_variants(save=True):
    """One row per (period, strategy, TE budget, cost). All strategies at the base case; the full mandate
    over the whole TE x cost grid."""
    inputs = load_inputs()
    rows = []
    for period, (first, last) in PERIODS.items():
        bench, _ = run_backtest(None, inputs=inputs, first=first, last=last)
        runs = [(s, config.TE_TARGET, COST_BP) for s in STRATEGIES]
        runs += [("bl_full", te, c) for te in TE_BUDGETS for c in COSTS_BP
                 if (te, c) != (config.TE_TARGET, COST_BP)]
        for strategy, te, cost in runs:
            daily, monthly = run_backtest(STRATEGIES[strategy], inputs=inputs, first=first, last=last,
                                          cost_bp=cost, te=te)
            rows.append({"period": period, "strategy": strategy, "TE budget": te, "cost (bp)": cost,
                         **measures(daily, monthly, bench)})
    table = pd.DataFrame(rows)
    if save:
        table.to_csv(RESULTS_DIR / "variants.csv", index=False)
    return table


def price_of_rules(table):
    """Active return and IR of the full mandate minus those of the TE-budget-only portfolio, per period."""
    base = table[(table["TE budget"] == config.TE_TARGET) & (table["cost (bp)"] == COST_BP)].set_index(
        ["period", "strategy"])
    out = {}
    for period in PERIODS:
        full, free = base.loc[(period, "bl_full")], base.loc[(period, "bl_te_only")]
        out[period] = {"Active return": full["Active return (net)"] - free["Active return (net)"],
                       "Information ratio": full["Information ratio"] - free["Information ratio"]}
    return pd.DataFrame(out).T


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    t = run_variants()
    print(t.round(4).to_string(index=False))
    print("\nPrice of the rules (full mandate minus TE budget only):\n", price_of_rules(t).round(4))

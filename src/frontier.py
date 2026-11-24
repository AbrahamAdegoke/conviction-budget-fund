"""Ex-ante active frontier with and without the mandate's rules (LN2: mu(x | b) against sigma(x | b)).

For one decision month, the optimizer is solved for TE budgets from 0.25% to 5% under three rule sets:
'none' (fully invested only, short sales allowed), 'long_only' and 'full' (the mandate). The gap between the
curves is the ex-ante price of the rules. Without rules the frontier is a straight line from the origin (constant
information ratio); rules bend it down as they start to bind. Saved to data/results/frontier.csv for the app.

Run from the repository root:  python -m src.frontier
"""

import numpy as np
import pandas as pd

from . import config
from .backtest import RESULTS_DIR
from .black_litterman import bl_alpha, covariance_at, view_matrices
from .optimizer import BENCH, load_inputs, optimize, tracking_error

TE_GRID = np.round(np.arange(0.0025, 0.0501, 0.0025), 4)
RULE_SETS = ("none", "long_only", "full")


def frontier(month, inputs=None, te_grid=TE_GRID, rule_sets=RULE_SETS, confidence=config.DEFAULT_CONFIDENCE):
    """One row per (rule set, TE budget): ex-ante TE reached, expected active return alpha'a, and their ratio."""
    inputs = inputs or load_inputs()
    month = pd.Period(month, "M")
    Sigma, _, _ = covariance_at(inputs.daily, inputs.month_ends[month])
    P, Q, _ = view_matrices(inputs.views, month)
    alpha = bl_alpha(Sigma, P, Q, np.full(len(Q), confidence))
    rows = []
    for rules in rule_sets:
        for te in te_grid:
            x, ok = optimize(alpha, Sigma, rules, te)
            sigma, mu = tracking_error(x, Sigma), float(alpha @ (x - BENCH).values)
            rows.append({"month": str(month), "rules": rules, "TE budget": te, "ok": ok,
                         "Ex-ante TE": sigma, "Expected active return": mu,
                         "Ex-ante IR": mu / sigma if sigma > 1e-9 else np.nan})
    return pd.DataFrame(rows)


def save_latest(inputs=None):
    """Frontier of the latest decision month with views, saved for the app."""
    inputs = inputs or load_inputs()
    month = max(set(inputs.views["Month"]) & set(inputs.month_ends.index))
    table = frontier(month, inputs)
    table.to_csv(RESULTS_DIR / "frontier.csv", index=False)
    return table


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    t = save_latest()
    print(t[t["TE budget"].isin([0.005, 0.01, 0.02, 0.03, 0.05])].round(4).to_string(index=False))

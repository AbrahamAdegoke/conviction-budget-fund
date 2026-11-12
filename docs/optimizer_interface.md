# Optimizer interface (Person B → Person C)

```python
from src.optimizer import load_inputs, propose_portfolio, BENCH

inputs = load_inputs()                        # reads data/processed, works offline
x, diag = propose_portfolio(
    month,                                    # decision month, e.g. "2026-10" (signal at month-end close)
    inputs,
    x_prev=None,                              # PRE-TRADE weights after drift (pd.Series, TICKERS order);
                                              # None = no turnover cap (first month, app "fresh" portfolio)
    rules="full",                             # "full" mandate | "long_only" | "none" (fully invested only)
    confidence=0.5,                           # Idzorek confidence of the automatic views, in (0, 1]
    manual_view=None,                         # {"long": "SPY", "short": "TLT", "q": 0.02, "confidence": 0.6}
)
```

- `x`: target weights (sum 1), traded at the next session, earning month t+1.
- `diag` keys: `ok`, `violations` (list), `relaxed_turnover_cap` (None or the cap used), `te_ex_ante`,
  `expected_active_return`, `turnover` (two-way, None if `x_prev` is None), `shrinkage_delta`,
  `avg_correlation`, `Sigma` (annual), `returns` (prior / alpha / posterior per ETF),
  `views` (Q, confidence, prior and posterior spreads per view).

Conventions
- Turnover cap: two-way, sum |x - x_prev| <= 20% (LN3). Mandate and TE <= 2% are hard; if the cap makes the
  problem infeasible it is relaxed (x1.25 steps) and reported in `relaxed_turnover_cap` (only 2020-03).
- The backtest must be sequential and pass the real drifted pre-trade weights as `x_prev`.
- Benchmark portfolio: `BENCH`. "BL with TE budget only": `rules="long_only"` or `"none"` (team to decide).
- Q values are spreads ON TOP of the equilibrium spread (equilibrium-relative views); the manual view too.

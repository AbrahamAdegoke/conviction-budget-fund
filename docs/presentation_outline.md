# 15-minute presentation outline

| # | Min | Who | Content | Show |
|---|---|---|---|---|
| 1 | 1 | Any | The fund: beat a fixed 8-ETF benchmark with a 2% tracking-error budget, long-only mandate | Benchmark and rules (app page 1) |
| 2 | 2 | A | Data: Datastream total return index, NYSE calendar, quality checks; 12–1 momentum and 200-day trend, no look-ahead | `data_quality_report.csv`, one momentum example |
| 3 | 3 | B | Black-Litterman: benchmark prior, views as spreads on top of equilibrium (why: textbook reading tilts against the signal), Ledoit-Wolf covariance | Views table for 2026-10 (app page 1) |
| 4 | 2 | B | Optimizer: max alpha minus trading costs s.t. TE ≤ 2%, mandate (incl. ±5-point limit on each bond ETF), 20% turnover cap; checks (closed form, tests) | — |
| 5 | 3 | C | **Live demo**: 2026-10 portfolio, toggle full mandate / TE only, add a manual view and show its effect; confidence slider and why it moves little | App page 2 |
| 6 | 3 | C | Backtest: next-day trading, 5 bp cost, daily drift. Results 2016–2026: +0.49% (full) / +0.83% (TE only) a year net, IR 0.22 / 0.36, Jensen alpha t 0.83, cost 0.05%/yr; naive MVO IR 0.36 | App page 3: growth of $1, metrics table |
| 7 | 1 | Any | Honest limits and next steps | see below |

**Key messages for slide 7**
- Positive active return after costs, but Jensen alpha t-stat 0.83: not statistically significant over 11 years.
- The price of the mandate changes sign: −0.34% a year on 2016–2026, +0.31% on 2009–2015.
- Realized TE 1.84% monthly (within budget), 2.18% daily; the real-estate vs gold bets are still underestimated
  (realized 1.25× ex ante). The ±5-point bond limit removed the bond underestimation (1.24 → 0.95).
- A naive mean-variance does as well (IR 0.36): BL brings control and explainability, not extra return.
- The trend view dilutes the momentum views (IR 0.50 with a neutral trend view vs 0.22): not changed, to avoid
  tuning on the test period (`docs/open_decisions.md` item 10).

**Likely questions**
- Why equilibrium-relative views? → `docs/open_decisions.md` item 2 (tilt against signal up to 52% of months).
- Why does confidence barely matter? → TE budget always fully used; confidence changes the mix, not the size.
- Look-ahead? → momentum lags one month, calibration on 2009–2015, covariance and backtest tested for it.
- Why no cost on the benchmark? → it is the reference index; its rebalancing would cost ~0.01%/yr anyway.
- Why limit bond positions to ±5 points? → IEF/LQD/TLT are ~0.86 correlated: the optimizer took large swaps where
  the covariance is least reliable (LN3 error maximisation); item 7.
- Why costs in the objective, and why 3 months? → do not trade when the expected gain does not pay the cost;
  alpha keeps 62% of its direction after 3 months on 2009–2015; item 9.
- Daily vs monthly TE? → daily active returns partly cancel within a month, so √252 × daily overstates
  the monthly risk.

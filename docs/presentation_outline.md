# 15-minute presentation outline

| # | Min | Who | Content | Show |
|---|---|---|---|---|
| 1 | 1 | Any | The fund: beat a fixed 8-ETF benchmark with a 2% tracking-error budget, long-only mandate | Benchmark and rules (app page 1) |
| 2 | 2 | A | Data: Datastream total return index, NYSE calendar, quality checks; 12–1 momentum and 200-day trend, no look-ahead | `data_quality_report.csv`, one momentum example |
| 3 | 3 | B | Black-Litterman: benchmark prior, views as spreads on top of equilibrium (why: textbook reading tilts against the signal), Ledoit-Wolf covariance | Views table for 2026-10 (app page 1) |
| 4 | 2 | B | Optimizer: max alpha s.t. TE ≤ 2%, mandate, 20% turnover cap; checks (49 tests, closed form) | — |
| 5 | 3 | C | **Live demo**: 2026-10 portfolio, toggle full mandate / TE only, add a manual view and show its effect; confidence slider and why it moves little | App page 2 |
| 6 | 3 | C | Backtest: next-day trading, 5 bp cost, daily drift. Results: +0.30% (full) / +0.56% (TE only) a year net, IR 0.13 / 0.24, cost 0.11%/yr | App page 3: growth of $1, metrics table |
| 7 | 1 | Any | Honest limits and next steps | see below |

**Key messages for slide 7**
- Positive active return after costs, but t-stat < 1: not statistically significant over 11 years.
- The mandate costs about 0.26% a year of active return (TE-only vs full mandate).
- Realized TE 2.35% vs 2% ex ante: the covariance forecast underestimates risk in stress (2020: 3.5%).
- Bond swaps (IEF/LQD/TLT, ~0.86 correlated) add risk for little return → next step: cap each active weight.

**Likely questions**
- Why equilibrium-relative views? → `docs/open_decisions.md` item 2 (tilt against signal up to 52% of months).
- Why does confidence barely matter? → TE budget always fully used; confidence changes the mix, not the size.
- Look-ahead? → momentum lags one month, calibration on 2009–2015, covariance and backtest tested for it.
- Why no cost on the benchmark? → it is the reference index; its rebalancing would cost ~0.01%/yr anyway.

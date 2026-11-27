# Methodology

How the fund is built, step by step: what each choice is and why we made it. Results are in the
[README](../README.md); the code is in `src/`.

Each month-end the fund (1) reads two signals, (2) turns them into Black-Litterman views, (3) picks the weights
with the highest expected extra return inside a 2% tracking-error budget and the client's rules, and (4) trades
at the next session. Choices are made on the calibration period 2009–2015; 2016–2026 is the test period.

---

## 1. Data

| Item | Choice |
|---|---|
| ETFs | SPY, EFA, EEM (equities) · IEF, LQD, TLT (bonds) · VNQ, GLD (alternatives) |
| Prices | Refinitiv Datastream, daily price and **total return index** (dividends reinvested), 3 Jan 2007 – 4 Nov 2026. Licensed: the raw file `data/raw/ETF.xlsx` is not in the repository |
| Risk-free rate | FRED DGS1MO (1-month T-bill), used only for the Sharpe ratio |
| Calendar | Official NYSE sessions only (4,992 sessions) |

Cleaning rules (`src/data.py`, `notebooks/01_data_audit.ipynb`):
- Nothing is interpolated or filled. A session with a missing or non-positive value for any ETF would be dropped
  for all ETFs (no such case in the data).
- 186 non-NYSE dates (US holidays, almost all copies of the previous day) are removed: kept, they would create
  fake zero returns and understate volatility.
- 9 daily moves above 15% (2008–2009 crisis, VNQ on 16 March 2020) are real and kept.
- Returns are computed from the total return index. Monthly returns use the last NYSE session of each month.
- Every check and its decision is logged in `data/reports/data_quality_report.csv`.

## 2. Signals and views

| Signal | Definition | View |
|---|---|---|
| Momentum 12–1 | Return from month-end t−12 to t−1 (the last month is skipped) | In each asset class, the best ETF beats the worst one |
| Trend | SPY price vs its 200-day average, at the month-end close | Equities beat bonds (above the average) or the reverse (below), weighted like the benchmark |

The view size is **Q = K × signal, capped at 5% a year**. K is set so that the cap binds about 10% of the time on
2009–2015 only (`K_MOM = 0.160`, `K_TREND = 0.389`, computed by `src/signals.py` and checked by a test).

**Q is read on top of what the benchmark already implies** (Q_eff = Pπ + Q, i.e. LN4 with Q = Pμ̃ + κ·signal).
Why: the benchmark already implies large spreads. In October 2026 it implies that equities beat bonds by 3.90%
a year, while the trend signal gives Q = 1.44%. Read as a total spread, a *positive* trend signal would push
the portfolio *towards bonds*. Read on top of equilibrium, every view pushes in the direction of its signal.

## 3. Black-Litterman

- **Prior:** π = φ Σ b, with φ = SR(b) / σ(b) (LN4). The benchmark Sharpe ratio (0.40) is only used to display
  the implied spreads.
- **Confidence:** Idzorek confidence c (50% for the automatic views), Walters form Ω_k = (1 − c)/c · P_k τΣ P_kᵀ.
- **What enters the weights:** α = μ̄ − π = ΓPᵀ(PΓPᵀ + Ω)⁻¹Q. τ cancels (Ω is proportional to τ), and so do π
  and the benchmark Sharpe ratio. Only Σ, P, Q and the confidence matter.
- **Why maximize α and not μ̄:** πᵀ(x − b) = φσ_b²(β_x − 1), so maximizing μ̄ would buy beta even with no view.
- **Confidence moves the portfolio little:** the 2% budget is always fully used, so confidence changes the mix
  of bets, not their size. In October 2026, going from 5% to 100% moves any weight by 4 points at most.

## 4. Covariance

Ledoit-Wolf (2003) shrinkage towards the constant-correlation matrix (LN3), on the last 252 regular daily
returns up to the decision close, annualized ×252. The shrinkage intensity is small (median 0.07, range
0.02–0.24): the sample matrix is already well estimated with 8 assets and 252 observations.

## 5. Optimizer (`src/optimizer.py`)

The LN2 σ-problem on active weights a = x − b:

    maximize   αᵀa − cost × turnover
    subject to aᵀΣa ≤ (2%)²,  fully invested,  mandate rules,  turnover ≤ 20%

It gives the same weights as the γ-problem when the budget binds, which it always does. Solved with SLSQP.

| Constraint | Rule | Why |
|---|---|---|
| Mandate | Long-only, fully invested; bonds 25–45%; EEM ≤ ⅓ of equities; each ETF ≤ 40% | The client's rules |
| Bond limit | IEF, LQD and TLT each within ±5 points of their benchmark weight | See below |
| Turnover | Σ\|x − x_prev\| ≤ 20% a month (two-way, LN3), from the drifted holdings (Scherer split) | Limits trading |
| If infeasible | The turnover cap is multiplied by 1.25 until a solution exists; if none exists at all, the fund holds the benchmark | The mandate and the TE budget always come first. Needed once (March 2020, TE-budget-only portfolio, cap 31.25%); the fund itself never needed it, and never fell back to the benchmark |

**Trading costs in the objective.** Each unit of turnover costs 5 bp × 12 / 3 = 0.20% a year in the objective,
so a trade is made only if its expected gain over 3 months pays its cost.
- Why 3 months: on 2009–2015 the direction of α keeps 88% / 62% / 29% / about 0% of its content after
  1 / 3 / 6 / 12 months. Full-mandate IR on 2009–2015 by horizon: 0.21 / 0.42 / 0.43 / 0.36, vs 0.30 without
  the penalty; 3 is the cautious end of the best range.
- Effect: turnover is about halved (0.99 a year on 2016–2026).
- Limit: α is not a calibrated forecast, so the strength of the penalty depends on its scale.

**Bond limit (±5 points).** IEF, LQD and TLT are about 0.86 correlated: swapping one for another looks almost
free in tracking error, so the optimizer made large bond swaps for small differences in α, exactly where the
covariance is least reliable (LN3 "error maximisation"). Without the limit, the realized risk of the bond bets
was 1.24× the forecast; with it, 0.95×.

| Full mandate, 5 bp | 2009–2015 | 2016–2026 |
|---|---|---|
| Cost penalty, no bond limit | +0.63% a year, IR 0.32 | +0.70% a year, IR 0.30 |
| Cost penalty and bond limit (current model) | +0.83% a year, IR 0.42 | +0.49% a year, IR 0.22 |

The limit helps on the calibration period and costs on the test period. It is kept: method choices are made on
2009–2015. It was adopted after also looking at 2016–2026 (one value tried, 5 points), and the test result is
reported as it is.

## 6. Portfolios compared

| Portfolio | Definition |
|---|---|
| Benchmark | SPY 30%, EFA 12%, EEM 8%, IEF 15%, LQD 10%, TLT 10%, VNQ 8%, GLD 7%, rebalanced monthly at no cost |
| BL, TE budget only | Same model, long-only and TE ≤ 2% only (no bond range, EEM rule, 40% cap or bond limit). Long-only rather than unconstrained, because a short position is something the fund could never hold. The gap with the next line is the price of the mandate |
| BL, full mandate | The fund |
| Naive MVO | Same optimizer, rules, budget and costs, but α = average daily return of the last 252 sessions (no prior, no views). Its α is about 17 times larger than the BL α, so the same cost penalty weighs much less on it |

## 7. Backtest (`src/backtest.py`)

| Item | Convention |
|---|---|
| Decisions | Each month-end close, 2015-12 → 2026-09 (returns Jan 2016 – Oct 2026). Calibration run: 2008-12 → 2015-11 |
| Information | Only data known at the decision close (tests shock future data and check nothing changes) |
| Trading | At the close of the first session of the next month; that session is still earned by the old weights |
| Holdings | Drift with daily returns; the drifted weights are the starting point of the next decision |
| Costs | 5 bp × Σ\|x_target − w_drifted\|, deducted on the trade day. The benchmark trades at no cost |
| Start | The first decision starts from the benchmark |

## 8. Metrics (`src/metrics.py`)

- Annualization with 252 sessions; active return = portfolio − benchmark, arithmetic mean.
- Realized tracking error on daily returns (×√252) and on monthly returns (×√12). Daily active returns partly
  cancel within a month, so the monthly figure is lower; both are always shown.
- Information ratio = active return / realized TE.
- Jensen's alpha and beta (LN2): monthly OLS of excess returns on the benchmark's, t-stat with Newey-West
  standard errors (Bartlett, automatic lag).
- 95% expected shortfall (LN6), historical, daily. Maximum drawdown, with the starting capital counted as a peak.
- Sharpe ratio uses the risk-free rate known at the previous close.

## 9. Robustness checks

- **Other settings** (`python -m src.variants`, shown on the Results page): TE budget 1% or 3%, costs 0 or 25 bp,
  one at a time, on both periods. At 25 bp the full mandate keeps an IR of 0.22 on 2016–2026.
- **Weight of the trend view** (`python -m src.sensitivity`): K_TREND × 0 / 0.5 / 1 / 2 gives a
  full-mandate IR of 0.69 / 0.58 / 0.42 / 0.31 on 2009–2015 and 0.50 / 0.32 / 0.22 / 0.16 on 2016–2026. The less
  the trend view weighs, the better the fund does, on both periods. The model is not changed: choosing the
  weight now would mean tuning on the test period.
- **Reversed views** (every Q × −1): −0.82% a year on 2009–2015 and −0.75% on 2016–2026, against +0.83% and +0.49%.
  The views carry information, even if the sample is too short to prove it statistically.
- **One K for three asset classes:** the 5% cap binds for 23% of the alternatives views, 7% of equities and 1%
  of bonds on 2009–2015. The cap truncates the information of one class mostly.

## 10. Limits

- The active return is positive but not statistically significant (Jensen t-stat 0.83).
- Realized TE is 1.84% measured monthly but 2.18% daily; the covariance still underestimates the real-estate vs
  gold bets (realized risk 1.25× the forecast).
- The price of the mandate changes sign between periods (+0.31% a year on 2009–2015, −0.33% on 2016–2026).
- The naive MVO does as well as Black-Litterman on both periods. Black-Litterman's value here is control and
  explainability, not extra return.
- The trend view dilutes the momentum views (section 9).

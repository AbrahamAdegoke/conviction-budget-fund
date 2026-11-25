# Open decisions: Black-Litterman and optimizer


**Last updated:** 14 November 2026
**Code:** `src/black_litterman.py`, `src/optimizer.py`, `src/config.py`, notebook `02_bl_optimizer.ipynb`
**Interface for the backtest and the app:** `docs/optimizer_interface.md`

Each open item lists who has to decide, the options, the evidence from the notebook, and a recommendation.
Tick the box and record the choice once the team has agreed.

---

## To settle/ Watched out to

### 1. Rules for the "BL with tracking-error budget only" portfolio
- **Who:** Assia (backtest)
- **Why it matters:** the plan compares three portfolios (benchmark, BL with TE budget only, BL under full mandate). The middle one is not defined precisely.
- **Options:**
  - `rules="long_only"`: fully invested, no short positions, TE ≤ 2%. This isolates the cost of the mandate rules (bonds 25–45%, EEM ≤ 1/3 of equity, 40% cap).
  - `rules="none"`: fully invested and TE ≤ 2% only; short positions allowed (e.g. TLT −19.7% in 2026-10). This is the pure LN2 problem and has a closed-form check.
- **Recommendation:** `long_only`. A short position is outside the agreed to "long-only" rule, so `none` would compare against something the fund could never hold.
- **Decision:** [X] long_only

### 2. Q now means "spread on top of equilibrium" (equilibrium-relative views)
- **Who:** Abraham (owner of `bl_views.csv` and the calibration) and Mustafa
- **What changed:** the optimizer uses Q_eff = P·π + Q. Q is therefore read as the extra spread the signal adds to the spread the prior already expects, not as the total expected spread (LN4 textbook reading).
- **Evidence (cell 4, 131 decision months, 2015-12 → 2026-10, confidence 50%):**

  | Reading | Benchmark SR | Months where the tilt goes against the signal | Corr(Q, tilt) |
  |---|---|---|---|
  | Textbook | 0.4 | Trend 52%, Alternatives 29%, Equities 22%, Bonds 15% | +0.51 to +0.63 |
  | Textbook | 0.2 | Trend 38%, Alternatives 21%, Equities 11%, Bonds 7% | +0.66 to +0.82 |
  | Relative | any | Trend 11%, Alternatives 11%, Bonds 2%, Equities 0% | +0.84 to +0.97 |

  Example (2026-10, textbook, SR 0.4): SPY is above its 200-day average, yet the trend view tilts towards bonds, because the prior already expects equities to beat bonds by 3.9% while Q = 1.4%.
- **Consequences:**
  - α = Γ Pᵀ (P Γ Pᵀ + Ω)⁻¹ Q. The prior π, the benchmark Sharpe ratio and τ all cancel out of the weights.
  - The K/cap calibration (5% cap binding about 10% of the time on 2009–2015) still makes sense, read as "momentum alpha".
  - `journal_donnees.md` and the report must describe Q this way.
- **Action:** disscus to confirm and update the wording in the journal. [ ] done
- **Decision (14 Nov):** [X] keep the equilibrium-relative reading. To confirm with Abraham, who updates the wording in `journal_donnees.md` and the report.

### 3. Meaning of the manual view in the app
- **Who:** Assia (app), Mustafa
- **Current implementation:** the manual view's `q` is also measured on top of equilibrium (same reading as item 2).
- **Risk:** a user typing "SPY beats TLT by 2%" will expect a total spread.
- **Recommendation:** keep it consistent with item 2 and show the prior spread next to the input. It is available in `diag["views"]["prior_spread"]`.
- **Decision (14 Nov):** [X] agreed: same reading as item 2; the app shows the prior spread next to the input (task 9). To confirm with Mustafa.
- **Update (24 Nov):** a positive manual view could lower the favoured ETF (2026-10: "SPY beats TLT by +0.5%"
  lowered SPY) because the automatic views already imply a larger spread. The app now shows the spread implied by
  the benchmark, the spread after the automatic views, and the threshold to exceed to push further (+1.14% for
  SPY over TLT in 2026-10). Views held at 100% confidence that overlap (e.g. a manual view on the same pair as an
  automatic one) now give a clear message instead of a crash.

### 4. The confidence slider barely moves the portfolio
- **Who:** Assia (app), whole team (presentation)
- **Why:** with the σ-problem (option b) the 2% TE budget is always fully used, so confidence only changes the *mix* of bets, not their size.
- **Evidence (full mandate, average over all months, sum of absolute weight changes vs confidence 50%):** 25% → 4.3%, 75% → 5.7%, 95% → 11.8%.
- **Options:**
  - Explain it in the demo, and use the manual view (with its own confidence) as the interactive part.
  - Change the method so that TE grows with conviction up to 2% (option c from the first discussion). Not recommended this close to the deadline.
- **Decision (14 Nov):** [X] explain in demo  [ ] other. The manual view is the interactive part of the demo.

### 5. Turnover cap: definition
- **Who:** whole team
- **Implemented:** two-way, Σ|xᵢ − x_prev,ᵢ| ≤ 20% (LN3 definition), measured from the drifted pre-trade weights.
- **Evidence (full mandate, sequential path):**

  | | No cap | Cap 20% two-way |
  |---|---|---|
  | Mean turnover (two-way) | 26.7% | 17.4% |
  | Months at the cap | n/a | 83 of 131 |
  | Median ex-ante active return | 0.26% | 0.26% |

  A 20% one-way cap (= 40% two-way) barely binds (mean turnover 24.3%).
- **Decision (14 Nov):** [X] two-way 20% (current)  [ ] one-way 20% → set `MAX_TURNOVER = 0.40` in `src/config.py`. The one-way cap barely binds; two-way cuts turnover with no loss of ex-ante active return.

### 6. When the turnover cap makes the problem infeasible
- **Who:** whole team
- **Implemented:** the mandate and TE ≤ 2% are hard constraints; the cap is multiplied by 1.25 until a solution exists (25%, 31.25%, 39.06%, …) and flagged in `diag["relaxed_turnover_cap"]`. The steps can go past the smallest feasible cap: a simple, predictable rule rather than an exact minimum.
- **Where it happens:** only 2020-03, and only for the TE-budget-only portfolio. After the COVID volatility jump, last month's holdings had an ex-ante TE of about 5% under the new covariance, so more than 20% had to be traded to come back to 2%: the cap goes to 31.25% (smallest feasible cap 30.5%). The full-mandate fund never needs it on 2009–2015 or 2016–2026 (the cost penalty and the bond limits keep it closer to its previous holdings).
- **Update (25 Nov):** a bisection to the smallest feasible cap was tried on 24 Nov and removed on 25 Nov. In the final model it changes nothing for the fund and 0.76 point of turnover in one month for the TE-only portfolio (IR 0.360 vs 0.363), so the simpler ×1.25 rule is kept.
- **Alternative:** keep the cap and accept 2.25% TE for that month.
- **Recommendation:** current rule. The TE budget is the fund's main promise; the cap is an optional extra from the plan.
- **Decision (14 Nov):** [X] relax the cap (current)  [ ] keep the cap, allow TE > 2%. In the backtest it happens only in 2020-03 (TE-budget-only portfolio), flagged in `monthly_log.csv`.

### 7. Large swaps inside the bond block
- **Who:** Mustafa, after Assia's first backtest
- **Issue:** IEF, LQD and TLT are about 0.86 correlated, so swapping between them costs little TE. The optimizer takes large positions for small α differences (2026-10: IEF 15% → 3.7%, LQD 10% → 21%, TLT 10% → 0%). Median active share is 24% with the cap (26% without). This is the "error maximiser" problem from LN3; the turnover cap slows it but does not remove it.
- **Option:** a cap on each active weight, e.g. |xᵢ − bᵢ| ≤ 10%.
- **Decision rule:** look at realized TE vs ex-ante 2% and at the contribution of bond swaps in the backtest. Add the cap only if realized TE is clearly above target or the bond swaps lose money.
- **Backtest evidence (14 Nov, Jan 2016 – Oct 2026):** realized TE 2.34% (full mandate) and 2.36% (TE budget only) vs 2% ex ante.
  Bond swaps inside the bond block: about −0.04% a year (full) and −0.11% (TE only); equities contribute about +0.55% / +0.68%
  (rough estimate: monthly returns × target weights, before costs).
- **Decision (14 Nov):** [X] no change  [ ] add active-weight cap. The decision rule is technically triggered but the effect is small,
  and changing the optimizer on code-freeze day is riskier than the gain. Reported as a finding and a next step (cap |xᵢ − bᵢ|).
- **Update (24 Nov): cap adopted, |xᵢ − bᵢ| ≤ 5 points on IEF, LQD and TLT only** (full mandate; `BOND_ACTIVE_CAP` in `src/config.py`).
  Why: the 0.86 correlation makes bond swaps look cheap in tracking error, but this is where the covariance is least reliable.
  Realized vs ex-ante TE of the bond positions is about 1.25–1.40 (equities about 1.0): the model understates their risk.
  Evidence on the calibration period 2009–2015 (full mandate, 5 bp): IR 0.15 → 0.30, active return +0.30% → +0.59% a year,
  turnover 1.94 → 1.60 a year. Test period 2016–2026: IR 0.14 → 0.17, +0.32% → +0.36% a year, realized TE 2.34% → 2.15%
  (daily) and 2.02% → 1.77% (monthly). A 10-point cap on every ETF, the other variant tried, was worse on both periods.
  Only 5 points was used; no other value was tried on 2016–2026.

### 8. Backtest inputs to the optimizer
- **Who:** Assia
- **Requirement:** the optimizer now depends on the previous portfolio, so the backtest must run month by month and pass the **actual pre-trade weights after drift** as `x_prev`.
- The notebook drifts with month-end to month-end returns. This is an approximation: trades happen on the session after the signal.
- The first decision (2015-12) starts from the benchmark.
- **Action:** [X] implemented in the backtest (`src/backtest.py`, 14 Nov). The backtest drifts with **daily**
  returns, so `x_prev` is the exact holding at the month-end close (no month-end approximation).

---

### 9. Trading costs in the optimizer's objective (added 24 Nov)
- **Issue:** the optimizer ignored costs: it traded even when the expected gain was below the 5 bp cost (cost was about a quarter of the gross active return).
- **Implemented:** objective = alpha'a − c × 12 / h × Σ|x − x_prev|, with c = 5 bp and h = `COST_HORIZON_MONTHS` (Scherer variables already in the turnover cap). A trade is made only if its expected gain over h months pays its cost.
- **Choice of h = 3 months, ex ante:** on 2009–2015 the direction of alpha keeps 88% / 62% / 29% / about 0% of its content after 1 / 3 / 6 / 12 months, so a trade earns mostly over its first 3 to 6 months; 3 is the cautious end. Horizons 1, 3, 6, 12 were compared on 2009–2015 only (full mandate IR 0.21 / 0.42 / 0.43 / 0.36, vs 0.30 without).
- **Result (5 bp, after decisions 6 and 7):** 2009–2015 full mandate IR 0.30 → 0.42, turnover 1.60 → 0.84 a year; 2016–2026 full mandate IR 0.17 → 0.22 (+0.36% → +0.49% a year), turnover 1.86 → 0.99, cost 0.09% → 0.05% a year; TE budget only IR 0.25 → 0.36.
- **Limit:** alpha is not a calibrated forecast (its size depends on K and on the confidence), so the strength of the penalty depends on that scale.

### 10. Sensitivity of the results to the size of the views (24 Nov, no model change)
- **Why:** only the direction of alpha matters, so the common scale of the views does not, but the weight of the trend view relative to the momentum views does. That weight is K_TREND / K_MOM ≈ 2.4, set by a mechanical rule (the 5% cap binds about 10% of the time for each signal), not by an economic argument.
- **Test:** views rebuilt with K_TREND × 0, 0.5, 1, 2 (K_MOM unchanged), current model (decisions 6, 7, 9), full mandate, 5 bp. Reproduce with `python scripts/sensitivity_k_ratio.py`.

  | K_TREND × | K_TREND / K_MOM | IR 2009–2015 | IR 2016–2026 | Active return 2009–2015 | Active return 2016–2026 |
  |---|---|---|---|---|---|
  | 0 (trend view neutral) | 0 | 0.69 | 0.50 | +1.27% | +1.08% |
  | 0.5 | 1.2 | 0.58 | 0.32 | +1.10% | +0.71% |
  | **1 (current)** | **2.4** | **0.42** | **0.23** | **+0.83%** | **+0.49%** |
  | 2 | 4.9 | 0.31 | 0.16 | +0.62% | +0.35% |

- **Reading:** the less weight the trend view gets, the better the fund does, on both periods and monotonically. With the bond cap and the cost penalty in place, the momentum views carry the result and the trend (equities vs bonds timing) view dilutes it. With K_TREND × 0 the trend view is still in the model but says "no spread beyond equilibrium".
- **One K for three asset classes:** the 5% cap binds for 22.6% of the alternatives views, 7.1% of equities and 1.2% of bonds on 2009–2015 (20.6%, 0.8%, 0.0% on 2016–2026; trend view 10.7% and 6.1%). The cap truncates the information of one class only.
- **Reversed views (check of information content):** with every Q multiplied by −1 the full mandate earns
  −0.82% a year on 2009–2015 (IR −0.41, vs +0.83%, 0.42) and −0.75% on 2016–2026 (IR −0.35, vs +0.49%, 0.22): the
  views carry information, even if the sample is too short to prove it statistically.
- **Decision (24 Nov):** no change to the model. The ratio was not chosen to maximize performance, and changing it now would be decided after seeing the test period. Reported as a sensitivity result and a limit.

## Carried over from `journal_donnees.md` (owner Abraham / Assia)

- [X] **Execution price:** trades happen at the close of the first session of month t+1; that session is earned by the old, drifted weights (see section 5 of the journal). Implemented in `src/backtest.py`.
- [X] **Risk-free rate:** convert DGS1MO to a monthly rate for the metrics. It is not needed by the optimizer, since 1ᵀ(x − b) = 0.
  **Decision (14 Nov):** done in `src/metrics.py`: DGS1MO / 252 per session, using the rate published at the previous close, last published value carried over bond-market holidays. Only the Sharpe ratio uses it; active return and IR do not.
- [ ] **Datastream licence:** keep the repository private until redistribution rights are clear, and remove restricted raw data before submission (plan, 15 November).
  **Decision (14 Nov):** keep the repo private; remove `data/raw/ETF.xlsx` before submission. Open question for the professor:
  `data/processed/etf_daily_clean.csv` holds Datastream prices, and the return files are derived from them, yet the app needs them offline.
  **Update (24 Nov):** `data/raw/ETF.xlsx` is no longer tracked (`.gitignore`); the tests, backtest and app run without
  it. Still to do by the repository owner: make the GitHub repository private (it is public) and, if needed, remove
  the file from the Git history. The app will be deployed for invited viewers only. No question to the professor.

---

## Backtest conventions (agreed 14 November, `src/backtest.py`)

| Topic | Decision |
|---|---|
| Decision months | 2015-12 → 2026-09, so returns are earned Jan 2016 → Oct 2026 (plan's evaluation period). The 2026-10 decision is only the app's proposed portfolio |
| Trade timing | Signal at the month-end close, trade at the close of the next session |
| Turnover cap | Applied to both BL portfolios; first decision starts from the benchmark |
| Benchmark | Rebalanced monthly to its fixed weights, no costs (reference index) |
| Costs | 5 bp × Σ\|x_target − w_drifted\|, deducted on the trade day |
| Outputs | `data/results/`: daily net and gross returns, monthly log (weights, traded, cost, ex-ante TE, relaxed cap) |

Note: `traded` is measured on the trade day, one session after the decision, so it can be slightly above the
20% cap that the optimizer applies to the month-end holdings.

## Already decided (for the record)

| Topic | Decision | Reason / evidence |
|---|---|---|
| Optimizer | LN2 σ-problem: max αᵀ(x − b) s.t. TE ≤ 2%, fully invested, mandate | Matches the "2% TE target"; no views → benchmark |
| Objective | α = μ̄ − π, not μ̄ | With μ̄, the optimizer tilts to beta even with no views: πᵀ(x − b) = φ σ_b² (β_x − 1) |
| Views | Equilibrium-relative (item 2) | Cell 4 evidence |
| Covariance | Ledoit-Wolf 2003, constant-correlation target (LN3), 252 regular daily returns, ×252 | Shrinkage δ median 0.07 (0.02–0.24): close to the sample matrix. Say so in the report |
| Confidence → Ω | Ω_k = (1 − c_k)/c_k · P_k τΣ P_kᵀ (Idzorek/Walters) | τ cancels; confidence in (0, 1] |
| Benchmark SR | 0.4, display only | Cancels out of α with relative views |
| Solver | scipy SLSQP | Matches the closed form (5e-9) and an independent convex solver on all 131 months × 3 rule sets (weights within 7e-5) |
| Turnover cap | 20%, two-way (item 5) | Plan's optional extra |

## Checks in place

- `tests/test_portfolio.py`: 49 tests (LN4 Example 4, Ledoit-Wolf vs brute force, no look-ahead in the covariance, closed form, rules and TE, no views → benchmark, view direction, turnover cap and relaxation).
- Notebook cell 7: `src/` reproduces the notebook path to 1.6e-8; no rule violations; only 2020-03 relaxed.

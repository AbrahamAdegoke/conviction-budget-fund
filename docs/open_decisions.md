# Open decisions: Black-Litterman and optimizer


**Last updated:** 11 November 2026
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

### 3. Meaning of the manual view in the app
- **Who:** Assia (app), Mustafa
- **Current implementation:** the manual view's `q` is also measured on top of equilibrium (same reading as item 2).
- **Risk:** a user typing "SPY beats TLT by 2%" will expect a total spread.
- **Recommendation:** keep it consistent with item 2 and show the prior spread next to the input. It is available in `diag["views"]["prior_spread"]`.
- **Decision:** [ ] agreed

### 4. The confidence slider barely moves the portfolio
- **Who:** Assia (app), whole team (presentation)
- **Why:** with the σ-problem (option b) the 2% TE budget is always fully used, so confidence only changes the *mix* of bets, not their size.
- **Evidence (full mandate, average over all months, sum of absolute weight changes vs confidence 50%):** 25% → 4.3%, 75% → 5.7%, 95% → 11.8%.
- **Options:**
  - Explain it in the demo, and use the manual view (with its own confidence) as the interactive part.
  - Change the method so that TE grows with conviction up to 2% (option c from the first discussion). Not recommended this close to the deadline.
- **Decision:** [ ] explain in demo  [ ] other

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
- **Decision:** [ ] two-way 20% (current)  [ ] one-way 20% → set `MAX_TURNOVER = 0.40` in `src/config.py`

### 6. When the turnover cap makes the problem infeasible
- **Who:** whole team
- **Implemented:** the mandate and TE ≤ 2% are hard constraints; the cap is relaxed in ×1.25 steps and flagged in `diag["relaxed_turnover_cap"]`.
- **Where it happens:** only 2020-03. After the COVID volatility jump, last month's portfolio had an ex-ante TE of 4.9%; with 20% turnover the best reachable TE was 2.25%. The cap was relaxed to 25%.
- **Alternative:** keep the cap and accept 2.25% TE for that month.
- **Recommendation:** current rule. The TE budget is the fund's main promise; the cap is an optional extra from the plan.
- **Decision:** [ ] relax the cap (current)  [ ] keep the cap, allow TE > 2%

### 7. Large swaps inside the bond block
- **Who:** Mustafa, after Assia's first backtest
- **Issue:** IEF, LQD and TLT are about 0.86 correlated, so swapping between them costs little TE. The optimizer takes large positions for small α differences (2026-10: IEF 15% → 3.7%, LQD 10% → 21%, TLT 10% → 0%). Median active share is 24% with the cap (26% without). This is the "error maximiser" problem from LN3; the turnover cap slows it but does not remove it.
- **Option:** a cap on each active weight, e.g. |xᵢ − bᵢ| ≤ 10%.
- **Decision rule:** look at realized TE vs ex-ante 2% and at the contribution of bond swaps in the backtest. Add the cap only if realized TE is clearly above target or the bond swaps lose money.
- **Decision:** [ ] no change  [ ] add active-weight cap

### 8. Backtest inputs to the optimizer
- **Who:** Assia
- **Requirement:** the optimizer now depends on the previous portfolio, so the backtest must run month by month and pass the **actual pre-trade weights after drift** as `x_prev`.
- The notebook drifts with month-end to month-end returns. This is an approximation: trades happen on the session after the signal.
- The first decision (2015-12) starts from the benchmark.
- **Action:** [ ] implemented in the backtest

---

## Carried over from `journal_donnees.md` (owner Abraham / Assia)

- [ ] **Execution price:** if trades happen at the close of the first session of month t+1, the new weights miss that session's return (see section 5 of the journal).
- [ ] **Risk-free rate:** convert DGS1MO to a monthly rate for the metrics. It is not needed by the optimizer, since 1ᵀ(x − b) = 0.
- [ ] **Datastream licence:** keep the repository private until redistribution rights are clear, and remove restricted raw data before submission (plan, 15 November).

---

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
| Turnover cap | 20%, two-way (pending item 5) | Plan's optional extra |

## Checks in place

- `tests/test_portfolio.py`: 49 tests (LN4 Example 4, Ledoit-Wolf vs brute force, no look-ahead in the covariance, closed form, rules and TE, no views → benchmark, view direction, turnover cap and relaxation).
- Notebook cell 7: `src/` reproduces the notebook path to 1.6e-8; no rule violations; only 2020-03 relaxed.

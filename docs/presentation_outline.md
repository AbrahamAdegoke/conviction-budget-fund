# Presentation: live demo of the app, then questions

About 15 minutes, all in the app (`streamlit run streamlit_app.py`, then http://localhost:8501).
One message throughout: **a disciplined use of a small, controlled active-risk budget, not a proven alpha.**

## Demo script

| # | Min | Page | Show | Say |
|---|---|---|---|---|
| 1 | 3 | **The Fund** | The four cards, the four monthly steps, "What we do not claim" | A fixed 8-ETF benchmark (50/35/15); each month we spend a 2% tracking-error budget on our views. Net of costs: +0.49% a year, ahead in 6 of 11 years; not statistically significant, and we say so. |
| 2 | 3 | **Mandate and Views** | Month 2026-10: the rules, then the views table (Q, prior spread, posterior spread) | Three momentum views (best vs worst ETF in each asset class) and one trend view (equities vs bonds). Q is what the signal adds on top of what the benchmark already implies. |
| 3 | 1 | Same page | Move the confidence slider from 5% to 100% | Weights move by 4 points at most: only the direction of the views matters, because the 2% budget is always fully used. Our conviction setting is the TE budget. |
| 4 | 2 | Same page | Manual view SPY beats TLT: enter **+0.5%**, read the message, then **+3%** | The automatic views already imply a 3.60% spread; +0.5% sets it at 2.96%, so it works *against* SPY. The app shows the threshold (+1.14%). At +3%, SPY rises to its 40% cap. |
| 5 | 2 | **Proposed Portfolio** | Without manual view; toggle **Full mandate** / **TE budget only** | Full mandate: IEF 10%, LQD 10%, TLT 5%, the ±5-point limits bind. TE budget only: IEF 3.8%, LQD 21%, TLT 0%: the large bond swap the limit prevents. TE 2.00%, every rule checked. |
| 6 | 3 | **Results** | Growth of $1, then the TE card and the expander, the metrics table, "Other periods and settings" | Monthly realized TE 1.84%, within budget (2.18% daily). Bonds no longer underestimated; real estate vs gold still are. The naive MVO does as well. The price of the mandate changes sign between periods. |
| 7 | 1 | **The Fund** | "What we do not claim" | Close on the limits and on what we would do next. |

## Key numbers (Jan 2016 – Oct 2026, net of 5 bp)

| | Full mandate | TE budget only | Naive MVO |
|---|---|---|---|
| Active return | +0.49% | +0.83% | +0.86% |
| Information ratio | 0.22 | 0.36 | 0.36 |
| Realized TE, monthly / daily | 1.84% / 2.18% | 1.99% / 2.29% | 2.02% / 2.35% |
| Jensen alpha (t, Newey-West) | +0.44% (0.83) | +0.84% (1.41) | +0.85% (1.31) |
| Turnover / cost per year | 0.99 / 0.05% | 1.05 / 0.05% | 1.58 / 0.08% |
| IR on 2009–2015 (calibration) | 0.42 | 0.27 | 0.63 |

## Likely questions, short answers

Where to read more: `docs/open_decisions.md` (item number in brackets).

**Model**
- *Why "views on top of equilibrium"?* It is LN4 with Q = Pμ̃ + κ·signal. Read as total returns, the trend view pushed against its own signal in 52% of months; on top of equilibrium, in 11% [2].
- *Where is τ?* Ω is proportional to τ (Idzorek confidence, Walters form), so τ cancels. We hit the TE budget with the LN2 sigma-problem, not by tuning τ as in the LN4 lab.
- *γ-problem or σ-problem?* Same weights when the budget binds (checked to 2e-7); we solve the σ version.
- *Why maximize α = μ̄ − π and not μ̄?* π'(x − b) = φσ_b²(β_x − 1): maximizing x'μ̄ would buy beta with no view at all.
- *Why does confidence barely matter?* Only the direction of α matters and the budget is always fully used [4].
- *How is the view size K set?* So that the 5% cap binds about 10% of the time on 2009–2015 only (K = 0.16 and 0.39); a test checks it.
- *Benchmark Sharpe 0.40?* Only used to display the implied spreads; it cancels out of the weights. A cautious long-run assumption (historical 0.88 on 2009–2015, 0.60 on 2016–2026).
- *Look-ahead?* Momentum skips the last month, the trend uses the close of the decision day, trades happen the next session; tests shock future data and check nothing changes.

**Choices added after the first backtest**
- *Why limit each bond ETF to ±5 points?* IEF, LQD and TLT are ~0.86 correlated, so large swaps look almost free in tracking error, exactly where the covariance is least reliable (LN3 "error maximisation"). Their realized risk was 1.24× the forecast without the limit, 0.95× with it. IR 0.15 → 0.30 on 2009–2015, 0.14 → 0.17 on 2016–2026 [7].
- *Why costs in the objective, and why 3 months?* A trade is made only if its expected gain pays its cost. On 2009–2015 the direction of α keeps 88% / 62% / 29% of its content after 1 / 3 / 6 months, so a trade earns over a few months; 3 is the cautious choice. Turnover halves; at 25 bp the fund stays positive [9].
- *What if no portfolio meets the rules?* The turnover cap is relaxed only as far as needed (bisection); if still impossible, the fund holds the benchmark. Never happened [6].

**Results**
- *Realized TE above 2%?* Monthly 1.84%, within budget. Daily active returns partly cancel within a month, so √252 × daily overstates the monthly risk. Measured daily, it exceeds 2% in 6 of 11 years, most in 2018 (2.8%) and 2026 (3.0%).
- *Is the alpha significant?* No: Jensen t-stat 0.83. With an IR of 0.22, about 80 years of data would be needed for t = 2.
- *The naive MVO does as well: why use Black-Litterman?* The past-year average return is itself a momentum signal on all 8 ETFs. BL gives controlled, explainable bets and trades less (0.99 vs 1.58 a year).
- *What do the rules cost?* −0.34% a year on 2016–2026 but +0.31% on 2009–2015: they protect in some markets only.
- *What would you change next?* The trend view dilutes the momentum views (IR 0.50 with a neutral trend view vs 0.22); we did not change it because that would be tuning on the test period [10]. Also: one K per asset class, and the real-estate vs gold risk.
- *Data?* Refinitiv Datastream total return indices (licensed, raw file not in the repository), NYSE calendar, quality report in `data/reports/`.

# Conviction Budget Fund

A multi-asset ETF fund that tilts a fixed benchmark with Black-Litterman views, within a 2% tracking-error budget
and a long-only mandate. Monthly walk-forward backtest, January 2016 – October 2026, and a Streamlit app.

## Setup

Python 3.11+. Run every command from the repository root (otherwise `src` is not found).

```bash
python -m venv .venv
# macOS / Linux
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q          # 92 tests (1 skipped if statsmodels is missing)
# Windows (PowerShell)
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q      # 92 tests (1 skipped if statsmodels is missing)
```

`requirements.txt` pins the exact versions with which the tests pass (tested with Python 3.11.4). pandas 3,
numpy 2.4 and scipy 1.17 need Python 3.11 or later; with an older Python the installation stops.

## Run

```bash
.venv/bin/streamlit run streamlit_app.py        # Windows: .venv\Scripts\streamlit run streamlit_app.py
```

Then open http://localhost:8501 (the browser does not open by itself: `.streamlit/config.toml` sets
`headless = true`). The app reads the saved files in `data/`, so it runs offline. Pages:
1. **The Fund** – what the fund does, how the model works each month, headline results and their limits.
2. **Mandate and Views** – benchmark, rules, tracking-error budget (0.5–4%), automatic views for a chosen month, confidence, one manual relative view.
3. **Proposed Portfolio** – optimized weights vs benchmark, ex-ante TE, rule checks, effect of the manual view.
4. **Results** – backtest metrics and charts (base case).

To rebuild the backtest results after a change:

```bash
.venv/bin/python -c "from src.backtest import run_all; from src.metrics import compute_all; run_all(); compute_all()"
```

## Method

| Item | Setting |
|---|---|
| Benchmark | SPY 30%, EFA 12%, EEM 8%, IEF 15%, LQD 10%, TLT 10%, VNQ 8%, GLD 7% |
| Mandate | Long-only, fully invested; bonds 25–45%; EEM ≤ ⅓ of equities; each ETF ≤ 40%; IEF, LQD, TLT within ±5 points of their benchmark weight |
| Views | Monthly: 12–1 momentum (best vs worst ETF in each asset class) and SPY 200-day trend (equities vs bonds). Q is the spread added on top of the benchmark-implied spread; size calibrated on 2009–2015 |
| Covariance | Ledoit-Wolf (constant-correlation target), trailing 252 daily returns |
| Optimizer | Maximize BL alpha × active weights minus trading costs (5 bp, to be paid back within 3 months) s.t. ex-ante TE ≤ 2%, mandate, two-way turnover ≤ 20% (if infeasible, the cap is multiplied by 1.25 until a solution exists) |
| Backtest | Signal at month-end close, trade at the next close, 5 bp on traded notional, daily drift; benchmark rebalanced monthly at no cost |
| Portfolios | Benchmark · BL with TE budget only (long-only) · BL under full mandate · naive MVO (past-year average returns instead of BL alpha, full mandate) |

Every method choice and why: [`docs/methodology.md`](docs/methodology.md).

## Results (Jan 2016 – Oct 2026, net of 5 bp costs)

| | Benchmark | BL, TE budget only | BL, full mandate | Naive MVO |
|---|---|---|---|---|
| Return (CAGR) | 8.17% | 9.01% | 8.64% | 9.07% |
| Active return | – | 0.82% | 0.49% | 0.86% |
| Realized TE, daily / monthly | – | 2.29% / 1.98% | 2.18% / 1.84% | 2.35% / 2.02% |
| Information ratio | – | 0.36 | 0.22 | 0.36 |
| Jensen's alpha (t, Newey-West) | – | 0.84% (1.41) | 0.44% (0.83) | 0.85% (1.31) |
| Turnover (two-way, per year) | 0.26 | 1.05 | 0.99 | 1.58 |
| Cost per year | – | 0.05% | 0.05% | 0.08% |
| Max drawdown | 24.2% | 23.8% | 24.1% | 23.9% |
| 95% ES (daily) | 1.54% | 1.64% | 1.65% | 1.61% |

The active return is positive after costs but not statistically significant (Jensen t-stat 1.4 and 0.8).
Measured monthly, as the committee looks at the fund, realized TE stays within the 2% budget; measured daily it is
a little higher because daily active returns partly offset each other within the month.
Full tables: `data/results/metrics.csv`, `te_by_block.csv` (ex-ante vs realized TE by asset class),
and `variants.csv` (both periods; TE 1% or 3%, costs 0 or 25 bp, one at a time; `python -m src.variants`).

Calibration period 2009–2015 (same model): IR 0.42 for the full mandate, 0.27 for the TE budget only, 0.63 for the
naive MVO. The price of the rules changes sign between periods (+0.31% a year on 2009–2015, −0.33% on
2016–2026), and the naive MVO beats Black-Litterman on both.

## Repository

```text
src/
  data.py             data cleaning, returns
  signals.py          momentum and trend signals, calibration of K, Black-Litterman views
  black_litterman.py  covariance, prior, views
  optimizer.py        TE-budget optimizer, mandate checks
  backtest.py         walk-forward backtest, costs
  metrics.py          performance metrics
  variants.py         other periods and settings (TE budget, costs)
  sensitivity.py      weight of the trend view, views at the cap, reversed views
  config.py           shared settings
app/                  Streamlit pages; entry point streamlit_app.py
notebooks/            01 data audit · 02 BL and optimizer · 03 backtest and metrics
tests/                pytest suite
data/processed/       clean returns, signals, views
data/results/         backtest output used by the app
docs/                 methodology.md: every method choice and why
```

## Data

ETF prices and total return indices: Refinitiv Datastream (licensed, not redistributed). The raw export
`data/raw/ETF.xlsx` is not in the repository (it is listed in `.gitignore`). The tests, the backtest and the
app do not need it: they read `data/processed/`. To rebuild `data/processed/` from scratch, put your own
Datastream export at `data/raw/ETF.xlsx` and run `notebooks/01_data_audit.ipynb`.
Risk-free rate: FRED DGS1MO (`data/raw/dgs1mo.csv`, public).

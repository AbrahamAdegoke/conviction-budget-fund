# Conviction Budget Fund

A multi-asset ETF fund that tilts a fixed benchmark with Black-Litterman views, within a 2% tracking-error budget
and a long-only mandate. Monthly walk-forward backtest, January 2016 – October 2026, and a Streamlit app.

## Setup

Python 3.11+. Run every command from the repository root (otherwise `src` is not found).

```bash
python -m venv .venv
# macOS / Linux
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q          # 80 tests
# Windows (PowerShell)
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q      # 80 tests
```

`requirements.txt` gives minimum versions. To reproduce the exact tested setup (Python 3.11.4), install
`requirements-lock.txt` instead.

## Run

```bash
.venv/bin/streamlit run streamlit_app.py        # Windows: .venv\Scripts\streamlit run streamlit_app.py
```

Then open http://localhost:8501 (the browser does not open by itself: `.streamlit/config.toml` sets
`headless = true`). The app reads the saved files in `data/`, so it runs offline. Pages:
1. **The Fund** – what the fund does, how the model works each month, headline results and their limits.
2. **Mandate and Views** – benchmark, rules, automatic views for a chosen month, confidence, one manual relative view.
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
| Optimizer | Maximize BL alpha × active weights minus trading costs (5 bp, to be paid back within 3 months) s.t. ex-ante TE ≤ 2%, mandate, two-way turnover ≤ 20% (relaxed only as far as needed if infeasible) |
| Backtest | Signal at month-end close, trade at the next close, 5 bp on traded notional, daily drift; benchmark rebalanced monthly at no cost |
| Portfolios | Benchmark · BL with TE budget only (long-only) · BL under full mandate |

All method choices and their evidence: [`docs/open_decisions.md`](docs/open_decisions.md).

## Results (Jan 2016 – Oct 2026, net of costs)

| | Benchmark | BL, TE budget only | BL, full mandate |
|---|---|---|---|
| Return (CAGR) | 8.17% | 8.73% | 8.45% |
| Active return | – | 0.56% | 0.30% |
| Realized TE | – | 2.36% | 2.34% |
| Information ratio | – | 0.24 | 0.13 |
| Cost per year | – | 0.11% | 0.11% |
| Max drawdown | 24.2% | 24.1% | 24.2% |
| 95% ES (daily) | 1.54% | 1.63% | 1.63% |

The active return is positive after costs but not statistically significant (t-stat 0.8 and 0.4).
Realized TE is somewhat above the 2% ex-ante budget. Full table: `data/results/metrics.csv`.

## Repository

```text
src/
  data.py             data cleaning, returns (Person A)
  signals.py          momentum and trend signals, calibration of K, Black-Litterman views
  black_litterman.py  covariance, prior, views (Person B)
  optimizer.py        TE-budget optimizer, mandate checks (Person B)
  backtest.py         walk-forward backtest, costs (Person C)
  metrics.py          performance metrics (Person C)
  config.py           shared settings
app/                  Streamlit pages; entry point streamlit_app.py
notebooks/            01 data audit · 02 BL and optimizer · 03 backtest and metrics
scripts/              sensitivity_k_ratio.py: sensitivity of the results to the size of the views
tests/                pytest suite
data/processed/       clean returns, signals, views
data/results/         backtest output used by the app
docs/                 project plan, data log, optimizer interface, decisions
```

## Data

ETF prices and total return indices: Refinitiv Datastream (licensed, not redistributed). The raw export
`data/raw/ETF.xlsx` is not in the repository (it is listed in `.gitignore`). The tests, the backtest and the
app do not need it: they read `data/processed/`. To rebuild `data/processed/` from scratch, put your own
Datastream export at `data/raw/ETF.xlsx` and run `notebooks/01_data_audit.ipynb`.
Risk-free rate: FRED DGS1MO (`data/raw/dgs1mo.csv`, public).

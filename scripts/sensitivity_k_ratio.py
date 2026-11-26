"""Sensitivity checks on the size of the automatic views (docs/methodology.md, section 9).

1. Weight of the trend view vs the momentum views: the views are rebuilt from the exported signals with
   K_TREND multiplied by 0, 0.5, 1 and 2 (K_MOM unchanged), and the full-mandate fund is backtested on the
   calibration period (2009-2015) and the test period (2016-2026). The model itself is not changed.
2. Share of views where the 5% cap binds, per asset class (one K_MOM is pooled across the three classes).
3. Reversed views: every Q multiplied by -1. If the views carry information, the fund should lose about what
   it gains; if the result were luck, the sign would not matter.

Run from the repository root:  python scripts/sensitivity_k_ratio.py   (about 3 minutes)
"""

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config, data, signals  # noqa: E402
from src.backtest import run_backtest  # noqa: E402
from src.optimizer import load_inputs  # noqa: E402

PERIODS = {"2009-2015 (calibration)": ("2008-12", "2015-11"), "2016-2026 (test)": ("2015-12", "2026-09")}
FACTORS = [0.0, 0.5, 1.0, 2.0]


def load_signals():
    mom = pd.read_csv(data.PROCESSED_DIR / "momentum_12_1.csv", index_col="Month").drop(columns="MonthEnd")
    mom.index = pd.PeriodIndex(mom.index, freq="M")
    trend = pd.read_csv(data.PROCESSED_DIR / "trend_spy_ma200.csv", index_col="Month")
    trend.index = pd.PeriodIndex(trend.index, freq="M")
    return mom, trend


def k_ratio_table():
    """IR and active return of the full mandate for each K_TREND multiplier, on both periods."""
    mom, trend = load_signals()
    base = load_inputs()
    rows = []
    for f in FACTORS:
        inputs = dataclasses.replace(base, views=signals.build_views(mom, trend, k_trend=config.K_TREND * f))
        for period, (first, last) in PERIODS.items():
            bench, _ = run_backtest(None, inputs=inputs, first=first, last=last)
            daily, monthly = run_backtest("full", inputs=inputs, first=first, last=last)
            active = daily["net"] - bench["net"]
            rows.append({"K_TREND x": f, "K_TREND / K_MOM": config.K_TREND * f / config.K_MOM, "period": period,
                         "IR": 252 * active.mean() / (active.std() * np.sqrt(252)),
                         "active return": 252 * active.mean()})
    return pd.DataFrame(rows).pivot_table(index=["K_TREND x", "K_TREND / K_MOM"], columns="period",
                                          values=["IR", "active return"])


def reversed_views_table():
    """Active return and IR of the full mandate with the views as they are and with every Q reversed."""
    base = load_inputs()
    reversed_views = base.views.copy()
    reversed_views["Q"] = -reversed_views["Q"]
    rows = []
    for label, inputs in [("views as they are", base),
                          ("views reversed", dataclasses.replace(base, views=reversed_views))]:
        for period, (first, last) in PERIODS.items():
            bench, _ = run_backtest(None, inputs=inputs, first=first, last=last)
            daily, _ = run_backtest("full", inputs=inputs, first=first, last=last)
            active = daily["net"] - bench["net"]
            rows.append({"views": label, "period": period, "active return": 252 * active.mean(),
                         "IR": 252 * active.mean() / (active.std() * np.sqrt(252))})
    return pd.DataFrame(rows).pivot_table(index="views", columns="period", values=["IR", "active return"])


def capped_share_table():
    """Share of views at the 5% cap, per asset class and period."""
    views = pd.read_csv(data.PROCESSED_DIR / "bl_views.csv")
    views["Month"] = pd.PeriodIndex(views["Month"], freq="M")
    views["class"] = views["View"].str.extract(r"Momentum (\w+):")[0].fillna("Trend")
    views["capped"] = views["Q"].abs() >= config.VIEW_CAP - 1e-12
    calib = views["Month"].between(pd.Period("2009-01", "M"), pd.Period("2015-12", "M"))
    test = views["Month"] >= pd.Period("2015-12", "M")
    return pd.DataFrame({"2009-2015": views[calib].groupby("class")["capped"].mean(),
                         "2016-2026": views[test].groupby("class")["capped"].mean()})


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print("Full mandate, 5 bp, current model:\n", k_ratio_table().round(3), "\n")
    print("Share of views at the 5% cap:\n", capped_share_table().round(3), "\n")
    print("Reversed views:\n", reversed_views_table().round(4))

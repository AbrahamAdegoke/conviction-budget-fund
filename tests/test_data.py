"""Tests for src/data.py on small synthetic datasets (Data Audit & Cleaning V1.4).

The real Datastream file has no missing values, duplicates or missing
month-ends, so these tests create those defects on purpose and check that
the pipeline applies the protocol rules.

Run from the project root with:  pytest
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import data  # noqa: E402

# Datastream-like column names (one keyword per ETF)
NAMES = {
    "SPY": "SPDR S&P 500 ETF TRUST",
    "EFA": "ISHARES MSCI EAFE ETF",
    "EEM": "ISHARES MSCI EMERGING MARKETS ETF",
    "IEF": "ISHARES 7-10 YEAR TREASURY BOND ETF",
    "LQD": "ISHARES IBOXX INV GRADE CORP BOND ETF",
    "TLT": "ISHARES 20+ YEAR TREASURY BOND ETF",
    "VNQ": "VANGUARD REAL ESTATE ETF",
    "GLD": "SPDR GOLD SHARES",
}


def make_ri(start="2007-01-01", end="2007-08-10", seed=0):
    """Synthetic RI on business days (includes some NYSE holidays, like Datastream)."""
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    values = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(dates), 8)), axis=0))
    return pd.DataFrame(values, index=dates, columns=data.TICKERS)


def write_excel(path, ri, price=None):
    """Write Price and RI sheets in Datastream layout (RI columns in another order)."""
    price = ri * 0.98 if price is None else price
    with pd.ExcelWriter(path) as writer:
        price.rename(columns=NAMES).rename_axis("Name").reset_index().to_excel(
            writer, sheet_name=data.PRICE_SHEET, index=False
        )
        ri[data.TICKERS[::-1]].rename(columns=NAMES).rename_axis("Name").reset_index().to_excel(
            writer, sheet_name=data.RI_SHEET, index=False
        )
    return path


def test_clean_data_gives_consistent_returns(tmp_path):
    """Clean input: no exclusion, no irregular return, daily and monthly returns agree."""
    out = data.build_clean_dataset(write_excel(tmp_path / "etf.xlsx", make_ri()))

    assert len(out["excluded_dates"]) == 0
    assert out["daily_returns"]["regular"].all()
    assert out["ri"].index.is_unique
    assert out["ri"].index.is_monotonic_increasing
    assert out["ri"].index.isin(out["sessions"]).all()
    assert (out["ri"] > 0).all().all()
    assert (out["price"] > 0).all().all()
    assert list(out["incomplete_final"].index.astype(str)) == ["2007-08"]

    monthly = out["monthly_returns"]
    compounded = data.compounded_monthly(out["daily_returns"])
    months = monthly.dropna().index  # all available months (first one is February)
    assert np.allclose(monthly.loc[months], compounded.loc[months], rtol=0, atol=1e-12)


def test_missing_or_non_positive_values_exclude_the_session(tmp_path):
    """A missing RI or a zero price removes the session for all ETFs and flags the next return."""
    ri = make_ri()
    ri.loc["2007-03-14", "EEM"] = np.nan
    price = ri * 0.98
    price.loc["2007-04-18", "SPY"] = 0.0

    out = data.build_clean_dataset(write_excel(tmp_path / "etf.xlsx", ri, price))

    excluded = list(out["excluded_dates"].strftime("%Y-%m-%d"))
    assert excluded == ["2007-03-14", "2007-04-18"]
    assert not out["ri"].index.isin(out["excluded_dates"]).any()

    daily = out["daily_returns"]
    irregular = list(daily.index[~daily["regular"]].strftime("%Y-%m-%d"))
    assert irregular == ["2007-03-15", "2007-04-19"]
    assert not daily[data.TICKERS].isna().any().any()  # no interpolation, no NaN left


def test_missing_nyse_session_flags_irregular_return(tmp_path):
    """A session absent from both sheets keeps the next return but flags it as irregular."""
    ri = make_ri().drop(pd.Timestamp("2007-03-14"))

    out = data.build_clean_dataset(write_excel(tmp_path / "etf.xlsx", ri))
    daily = out["daily_returns"]

    assert pd.Timestamp("2007-03-14") not in out["ri"].index
    assert not daily.loc["2007-03-15", "regular"]
    assert daily.loc["2007-03-15", data.TICKERS].notna().all()
    assert daily["regular"].sum() == len(daily) - 1  # only this return is irregular


def test_missing_month_end_makes_two_months_unavailable(tmp_path):
    """Without the 31 May session, May and June returns are NaN; other months are kept."""
    ri = make_ri()
    ri.loc["2007-05-31", "TLT"] = np.nan

    out = data.build_clean_dataset(write_excel(tmp_path / "etf.xlsx", ri))
    monthly = out["monthly_returns"]

    assert list(out["missing_month_end"].index.astype(str)) == ["2007-05"]
    nan_months = list(monthly.index[monthly.isna().any(axis=1)].astype(str))
    assert nan_months == ["2007-05", "2007-06"]
    assert monthly.loc[pd.Period("2007-07", "M")].notna().all()


def test_duplicated_dates_stop_the_pipeline(tmp_path):
    """A duplicated date in a Datastream sheet raises an error."""
    ri = make_ri()
    ri = pd.concat([ri, ri.iloc[[10]]]).sort_index()

    with pytest.raises(ValueError, match="Duplicated dates"):
        data.build_clean_dataset(write_excel(tmp_path / "etf.xlsx", ri))


def test_compounded_monthly_is_nan_when_a_day_is_missing():
    """One missing daily return makes the compounded month NaN for that ticker only."""
    ri = make_ri()
    daily = ri.pct_change(fill_method=None).iloc[1:]
    daily.loc["2007-06-12", "GLD"] = np.nan

    compounded = data.compounded_monthly(daily)
    june = pd.Period("2007-06", "M")

    assert np.isnan(compounded.loc[june, "GLD"])
    assert compounded.loc[june].drop("GLD").notna().all()


def test_column_mapping_rejects_missing_etf():
    """The keyword mapping fails if an ETF is missing or a column is unknown."""
    names = list(NAMES.values())
    with pytest.raises(ValueError):
        data.map_columns_to_tickers(names[:-1])
    with pytest.raises(ValueError):
        data.map_columns_to_tickers(names[:-1] + ["UNKNOWN FUND"])
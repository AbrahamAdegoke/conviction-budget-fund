"""Data loading, cleaning and return construction for the Conviction Budget Fund.

Protocol: Data Audit & Cleaning V1.4.
- Raw files are never modified.
- Only NYSE sessions are kept.
- Prices are never interpolated or forward-filled.
- Returns are simple returns computed from the Total Return Index (RI).
- Monthly returns use a common NYSE month-end; a missing month-end makes
  that month's and the next month's returns unavailable (NaN).
"""

from pathlib import Path

import pandas as pd
import pandas_market_calendars as mcal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ETF_FILE = PROJECT_ROOT / "data" / "raw" / "ETF.xlsx"
RF_FILE = PROJECT_ROOT / "data" / "raw" / "dgs1mo.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

PRICE_SHEET = "Price"
RI_SHEET = "Total return index"

# Each ETF is identified by a keyword in its Datastream name
# (column order differs between the Price and RI sheets).
TICKER_KEYWORDS = {
    "SPY": "S&P 500",
    "EFA": "EAFE",
    "EEM": "EMERGING",
    "IEF": "7-10",
    "LQD": "INV GRADE",
    "TLT": "20+",
    "VNQ": "REAL ESTATE",
    "GLD": "GOLD",
}
TICKERS = list(TICKER_KEYWORDS)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def map_columns_to_tickers(columns):
    """Map Datastream column names to tickers; fail on ambiguous or missing ETFs."""
    mapping = {}
    for col in columns:
        matches = [t for t, kw in TICKER_KEYWORDS.items() if kw in str(col).upper()]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous or unknown column: {col}")
        mapping[col] = matches[0]
    if sorted(mapping.values()) != sorted(TICKERS):
        raise ValueError(f"Expected the 8 ETFs exactly once, got {sorted(mapping.values())}")
    return mapping


def load_datastream_sheet(sheet, path=ETF_FILE):
    """Read one Datastream sheet: Date index, one numeric column per ticker.

    Returns the cleaned frame and a dict of audit counts
    (invalid dates, duplicated dates, non-numeric values per ticker).
    """
    df = pd.read_excel(path, sheet_name=sheet, header=0)
    df = df.rename(columns={df.columns[0]: "Date"})

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    audit = {
        "invalid_dates": int(df["Date"].isna().sum()),
        "duplicated_dates": int(df["Date"].dropna().duplicated().sum()),
    }
    df = df.dropna(subset=["Date"])

    df = df.rename(columns=map_columns_to_tickers(df.columns[1:]))

    non_numeric = {}
    for ticker in TICKERS:
        numeric = pd.to_numeric(df[ticker], errors="coerce")
        non_numeric[ticker] = int((df[ticker].notna() & numeric.isna()).sum())
        df[ticker] = numeric
    audit["non_numeric"] = non_numeric

    return df.set_index("Date").sort_index()[TICKERS], audit


def load_risk_free(path=RF_FILE):
    """Read the FRED DGS1MO series (annualized %, blanks become NaN)."""
    rf = pd.read_csv(path)
    rf.columns = ["Date", "DGS1MO"]
    rf["Date"] = pd.to_datetime(rf["Date"], errors="coerce")
    rf["DGS1MO"] = pd.to_numeric(rf["DGS1MO"], errors="coerce")
    return rf.dropna(subset=["Date"]).set_index("Date").sort_index()["DGS1MO"]


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------
def nyse_sessions(start, end):
    """Official NYSE trading sessions between two dates (inclusive)."""
    schedule = mcal.get_calendar("NYSE").schedule(start_date=start, end_date=end)
    return pd.DatetimeIndex(schedule.index).normalize()


def keep_sessions(df, sessions):
    """Keep only rows whose date is an NYSE session; report dropped and missing dates."""
    dates = df.index.normalize()
    non_sessions = dates.difference(sessions)
    missing_sessions = sessions.difference(dates)
    return df.loc[df.index.isin(sessions)].copy(), non_sessions, missing_sessions


# ---------------------------------------------------------------------------
# Quality checks (detection only, never automatic deletion)
# ---------------------------------------------------------------------------
def zero_runs(series, min_len):
    """Runs of at least min_len consecutive zero returns: list of (start date, length)."""
    z = series.eq(0)
    block = (z != z.shift()).cumsum()
    return [(grp.index[0], len(grp)) for _, grp in series[z].groupby(block[z]) if len(grp) >= min_len]


def extreme_returns(returns, threshold=0.15):
    """Daily returns whose absolute value exceeds the threshold, per ticker."""
    return {t: returns[t][returns[t].abs() > threshold] for t in returns.columns}


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------
def daily_returns(ri, sessions):
    """Simple daily returns from RI, without filling, with a 'regular' flag.

    A return is regular when its two dates are consecutive NYSE sessions;
    irregular returns must not enter daily covariance estimation.
    """
    returns = ri.pct_change(fill_method=None)
    pos = sessions.get_indexer(ri.index)
    returns["regular"] = pd.Series(pos, index=ri.index).diff().eq(1)
    return returns.iloc[1:]   # first date has no previous observation


def month_end_sessions(start, last_data_date):
    """Last NYSE session of each calendar month, up to the end of the last data month."""
    full = nyse_sessions(start, last_data_date + pd.offsets.MonthEnd(0))
    return full.to_series().groupby(full.to_period("M")).max()


def monthly_returns(ri):
    """Monthly returns between common NYSE month-ends.

    Returns (monthly_returns, month_ends, incomplete_final, missing_month_end).
    A month-end missing from the data stays as NaN, so the returns of that
    month and the next month are unavailable. The incomplete final month
    (data ending before its last session) is dropped.
    """
    last_data_date = ri.index.max()
    month_ends = month_end_sessions(ri.index.min(), last_data_date)

    unavailable = month_ends[~month_ends.isin(ri.index)]
    incomplete_final = unavailable[unavailable > last_data_date]
    missing_month_end = unavailable[unavailable <= last_data_date]

    ri_month_end = ri.reindex(month_ends.values)
    ri_month_end.index = month_ends.index

    monthly = ri_month_end.pct_change(fill_method=None).iloc[1:]
    monthly = monthly.drop(index=incomplete_final.index)
    return monthly, month_ends, incomplete_final, missing_month_end


def compounded_monthly(daily):
    """Compound daily returns within each calendar month (consistency check).

    A month is NaN for a ticker as soon as one of its daily returns is missing,
    so the check can never pass on an incomplete series.
    """
    values = daily[TICKERS] if "regular" in daily.columns else daily
    groups = (1 + values).groupby(values.index.to_period("M"))
    compounded = groups.prod() - 1
    complete = groups.count().eq(groups.size(), axis=0)
    return compounded.where(complete)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
def build_clean_dataset(path=ETF_FILE):
    """Load both sheets, keep NYSE sessions and build daily and monthly returns.

    Sessions with a missing or non-positive Price or RI for at least one ETF
    are excluded from the common sample (no interpolation). Their dates are
    returned in "excluded_dates" so the notebook can log them in the quality
    report; the returns spanning them are flagged as irregular.
    """
    price, price_audit = load_datastream_sheet(PRICE_SHEET, path)
    ri, ri_audit = load_datastream_sheet(RI_SHEET, path)
    if price_audit["duplicated_dates"] or ri_audit["duplicated_dates"]:
        raise ValueError("Duplicated dates detected in Datastream sheets")
    if not price.index.equals(ri.index):
        raise ValueError("Price and RI sheets have different dates")

    sessions = nyse_sessions(ri.index.min(), ri.index.max())
    price_clean, _, _ = keep_sessions(price, sessions)
    ri_clean, _, _ = keep_sessions(ri, sessions)

    # Common exclusion rule: drop a session if any ETF is missing or non-positive
    valid = (
        price_clean.notna().all(axis=1)
        & ri_clean.notna().all(axis=1)
        & price_clean.gt(0).all(axis=1)
        & ri_clean.gt(0).all(axis=1)
    )
    excluded_dates = price_clean.index[~valid]
    price_clean = price_clean.loc[valid]
    ri_clean = ri_clean.loc[valid]

    daily = daily_returns(ri_clean, sessions)
    monthly, month_ends, incomplete_final, missing_month_end = monthly_returns(ri_clean)
    return {
        "price": price_clean,
        "ri": ri_clean,
        "daily_returns": daily,
        "monthly_returns": monthly,
        "month_ends": month_ends,
        "incomplete_final": incomplete_final,
        "missing_month_end": missing_month_end,
        "excluded_dates": excluded_dates,
        "sessions": sessions,
        "audit": {"price": price_audit, "ri": ri_audit},
    }


def load_processed():
    """Read the exported clean files (for the backtest and the app)."""
    daily = pd.read_csv(PROCESSED_DIR / "etf_daily_returns.csv", index_col="Date", parse_dates=True)
    monthly = pd.read_csv(PROCESSED_DIR / "etf_monthly_returns.csv", index_col="Month")
    monthly.index = pd.PeriodIndex(monthly.index, freq="M")
    clean = pd.read_csv(PROCESSED_DIR / "etf_daily_clean.csv", index_col="Date", parse_dates=True)
    return clean, daily, monthly
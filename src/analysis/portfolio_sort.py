"""Calendar-time long-short portfolio sort on textual similarity, following
Cohen, Malloy & Nguyen (2020, "Lazy Prices") -- a fundamentally different
test than the pooled cross-sectional correlations/logistic regressions used
everywhere else in this project so far.

Key methodological choices, matched to the paper (see
reports/return_predictability_exploration.md for the full writeup and why
each deviation from the paper was made):
  - Stocks enter a portfolio the month after their filing's disclosure date.
  - Held for `holding_months` months (paper: 3; we also test 12 to match
    this project's existing convention).
  - Portfolios are formed monthly from the trailing `holding_months` months
    of entries (a "vintage" system), so a given calendar month's portfolio
    blends firms that entered at different points in the recent past.
  - Firms are sorted into `n_groups` groups (paper: quintiles; we use
    terciles by default -- our universe is ~111 companies vs. the paper's
    entire US market, so quintiles would leave too few names per group in
    the sparser calendar months) by similarity score, ranked within each
    entry's trailing-window cross-section (not the whole-sample distribution,
    to avoid look-ahead).
  - Long-short = high-similarity ("non-changers") minus low-similarity
    ("changers") portfolio, equal-weighted (value-weighting would need
    shares-outstanding data this project doesn't have -- see limitations).
  - Significance is a t-test on the time series of monthly L/S returns
    (Newey-West with 3 lags) -- this is the correct fix for the repeated-
    observations problem documented in reports/wholenote_multivariate_model.md,
    via a different, well-established route than clustering.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

MARKET = Path("data/raw/market/prices")


def load_monthly_returns() -> tuple[pd.DataFrame, pd.Series]:
    """Monthly buy-and-hold returns per ticker, and the Ibovespa's monthly
    return over the same months, both indexed by month-end Timestamp.
    """
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    prices = prices.set_index("date").sort_index()
    monthly_px = prices.resample("ME").last()
    monthly_ret = monthly_px.pct_change(fill_method=None)

    ibov = pd.read_csv(MARKET / "ibov_index_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date", "IBOV Index": "ibov"})
    ibov["date"] = pd.to_datetime(ibov["date"], format="%m/%d/%Y")
    ibov["ibov"] = pd.to_numeric(ibov["ibov"], errors="coerce")
    ibov = ibov.set_index("date").sort_index()["ibov"]
    ibov_monthly = ibov.resample("ME").last().pct_change()

    return monthly_ret, ibov_monthly


def build_events(sim: pd.DataFrame, filing_dates: pd.DataFrame, ticker_map: pd.DataFrame, date_col: str, period_col: str) -> pd.DataFrame:
    """One row per (company, current-period) similarity pair with its
    disclosure date and resolved ticker -- the raw input to the portfolio
    sort. `filing_dates` must have columns [cd_cvm, <period_col>, filing_date].
    """
    events = sim.merge(filing_dates, left_on=["cd_cvm", period_col], right_on=["cd_cvm", period_col], how="left")
    events = events.merge(ticker_map, on="CD_CVM" if "CD_CVM" in ticker_map.columns else "cd_cvm", how="left") if "CD_CVM" in ticker_map.columns else events
    return events


def run_portfolio_sort(
    events: pd.DataFrame,
    monthly_ret: pd.DataFrame,
    ibov_monthly: pd.Series,
    holding_months: int = 3,
    n_groups: int = 3,
    min_group_size: int = 3,
) -> dict:
    """events must have columns: ticker, entry_month (Timestamp, month-end
    of the month AFTER disclosure), cosine_similarity.
    Returns a dict with the monthly L/S return series, summary stats, and
    diagnostics (avg group sizes, months covered).
    """
    events = events.dropna(subset=["ticker", "entry_month", "cosine_similarity"]).copy()
    events["ticker"] = events["ticker"] + " BS Equity"  # match stock_prices_bloomberg.csv's column naming
    events = events[events["ticker"].isin(monthly_ret.columns)]

    all_months = sorted(monthly_ret.index)
    ls_returns = []
    diagnostics = []

    for i, month in enumerate(all_months):
        window_start = month - pd.DateOffset(months=holding_months)
        active = events[(events["entry_month"] > window_start) & (events["entry_month"] <= month)]
        if len(active) < min_group_size * n_groups:
            continue
        active = active.drop_duplicates(subset=["ticker"], keep="last")  # one position per ticker per month
        try:
            active = active.copy()
            active["group"] = pd.qcut(active["cosine_similarity"], n_groups, labels=False, duplicates="drop")
        except ValueError:
            continue
        n_actual_groups = active["group"].nunique()
        if n_actual_groups < n_groups:
            continue

        month_returns = {}
        for g in range(n_groups):
            tickers = active.loc[active["group"] == g, "ticker"].unique()
            rets = monthly_ret.loc[month, [t for t in tickers if t in monthly_ret.columns]].dropna()
            if len(rets) == 0:
                month_returns[g] = np.nan
            else:
                month_returns[g] = rets.mean()

        high_sim = month_returns[n_groups - 1]  # highest similarity = "non-changers"
        low_sim = month_returns[0]  # lowest similarity = "changers"
        if pd.isna(high_sim) or pd.isna(low_sim):
            continue

        ls_returns.append({
            "month": month,
            "ls_return": high_sim - low_sim,
            "high_sim_return": high_sim,
            "low_sim_return": low_sim,
            "ibov_return": ibov_monthly.get(month, np.nan),
            "n_active": len(active),
        })
        diagnostics.append(len(active))

    if not ls_returns:
        return {"n_months": 0, "error": "no months had enough active positions"}

    ls_df = pd.DataFrame(ls_returns).set_index("month")
    ls_df["ls_return_mkt_adj"] = ls_df["ls_return"]  # L/S is already market-neutral by construction (long minus short)

    mean_ls = ls_df["ls_return"].mean()
    X = np.ones(len(ls_df))
    model = sm.OLS(ls_df["ls_return"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    t_stat = model.tvalues.iloc[0]
    p_value = model.pvalues.iloc[0]

    return {
        "n_months": len(ls_df),
        "avg_n_active": np.mean(diagnostics),
        "mean_monthly_ls_return": mean_ls,
        "annualized_ls_return": (1 + mean_ls) ** 12 - 1,
        "t_stat_newey_west": t_stat,
        "p_value": p_value,
        "mean_high_sim_return": ls_df["high_sim_return"].mean(),
        "mean_low_sim_return": ls_df["low_sim_return"].mean(),
        "ls_series": ls_df,
    }

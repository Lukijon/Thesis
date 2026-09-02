"""Systematic grid search over the portfolio-sort test
(src/analysis/portfolio_sort.py), using only contamination-cleaned /
extraction-reliable data throughout -- see
reports/return_predictability_exploration.md for the full writeup.

Also adds a size-neutralized double sort (first split by firm size, then
by similarity within each size bucket, average the spread across size
buckets) to directly address the size confound found in earlier rounds,
rather than just noting it as a caveat.

Usage:
    python -m src.analysis.portfolio_sort_grid
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.portfolio_sort import load_monthly_returns, run_portfolio_sort

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POC = Path("data/interim/poc")
INTERIM = Path("data/interim")


def attach_tickers(events: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
    tm = ticker_map.rename(columns={"CD_CVM": "cd_cvm"})[["cd_cvm", "ticker"]]
    return events.merge(tm, on="cd_cvm", how="left")


def add_entry_month(events: pd.DataFrame) -> pd.DataFrame:
    events["filing_date"] = pd.to_datetime(events["filing_date"])
    events["entry_month"] = (events["filing_date"] + pd.offsets.MonthBegin(1)).dt.to_period("M").dt.to_timestamp("M")
    return events


def whole_notes_clean_events(ticker_map) -> pd.DataFrame:
    sim = pd.read_csv(POC / "full_notes_similarity_results_VERIFIED.csv")
    fd = pd.read_csv(INTERIM / "dfp_filing_dates.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr"})[["cd_cvm", "year_curr", "filing_date"]]
    events = sim.merge(fd, on=["cd_cvm", "year_curr"], how="left")
    events = add_entry_month(events)
    return attach_tickers(events, ticker_map)


def narrow_annual_reliable_events(ticker_map) -> pd.DataFrame:
    sim = pd.read_csv(POC / "delisted_similarity_results.csv")
    sim = sim[(sim["diagnostic_prev"] == "font_heading") & (sim["diagnostic_curr"] == "font_heading")]
    fd = pd.read_csv(INTERIM / "dfp_filing_dates.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr"})[["cd_cvm", "year_curr", "filing_date"]]
    events = sim.merge(fd, on=["cd_cvm", "year_curr"], how="left")
    events = add_entry_month(events)
    return attach_tickers(events, ticker_map)


def narrow_quarterly_reliable_events(ticker_map) -> pd.DataFrame:
    sim = pd.read_csv(POC / "itr_similarity_results.csv")
    sim = sim[(sim["diagnostic_prev"] == "font_heading") & (sim["diagnostic_curr"] == "font_heading")]
    fd = pd.read_csv(INTERIM / "itr_filing_dates.csv").rename(columns={"CD_CVM": "cd_cvm", "QUARTER_LABEL": "quarter_curr"})[["cd_cvm", "quarter_curr", "filing_date"]]
    events = sim.merge(fd, on=["cd_cvm", "quarter_curr"], how="left")
    events = add_entry_month(events)
    return attach_tickers(events, ticker_map)


def run_size_neutral_sort(events: pd.DataFrame, monthly_ret, ibov_monthly, ctrl: pd.DataFrame,
                            year_col: str, holding_months: int = 12, n_size_buckets: int = 2) -> dict:
    """Double sort: split into size buckets first (using ln_total_assets as
    of the *prior* fiscal year, i.e. known at the time of the event), then
    within each size bucket split into similarity terciles. Long the
    high-similarity minus low-similarity spread *within* each size bucket,
    then average across size buckets -- a standard way (Fama-French style)
    to test whether a characteristic's spread survives once size is held
    roughly constant, without needing a full regression.
    """
    ctrl_small = ctrl[["CD_CVM", "fiscal_year", "ln_total_assets"]].rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": year_col})
    events = events.merge(ctrl_small, on=["cd_cvm", year_col], how="left")
    events = events.dropna(subset=["ln_total_assets"])

    all_spreads = []
    for size_q in range(n_size_buckets):
        lo, hi = events["ln_total_assets"].quantile([size_q / n_size_buckets, (size_q + 1) / n_size_buckets])
        bucket = events[(events["ln_total_assets"] >= lo) & (events["ln_total_assets"] <= hi)]
        r = run_portfolio_sort(bucket, monthly_ret, ibov_monthly, holding_months=holding_months, n_groups=3, min_group_size=2)
        if r.get("n_months", 0) > 5:
            all_spreads.append(r["ls_series"]["ls_return"].rename(f"size_q{size_q}"))

    if not all_spreads:
        return {"n_months": 0, "error": "no size bucket had enough data"}

    combined = pd.concat(all_spreads, axis=1)
    avg_spread = combined.mean(axis=1, skipna=True).dropna()
    import statsmodels.api as sm
    X = np.ones(len(avg_spread))
    model = sm.OLS(avg_spread, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    return {
        "n_months": len(avg_spread),
        "n_size_buckets_used": len(all_spreads),
        "mean_monthly_ls_return": avg_spread.mean(),
        "annualized_ls_return": (1 + avg_spread.mean()) ** 12 - 1,
        "t_stat_newey_west": model.tvalues.iloc[0],
        "p_value": model.pvalues.iloc[0],
    }


def main() -> None:
    ticker_map = build_ticker_map()
    monthly_ret, ibov_monthly = load_monthly_returns()
    ctrl = pd.read_csv(INTERIM / "control_variables.csv")

    scenarios = {
        "whole_annual_CLEAN": (whole_notes_clean_events(ticker_map), "year_curr"),
        "narrow_annual_RELIABLE": (narrow_annual_reliable_events(ticker_map), "year_curr"),
        "narrow_quarterly_RELIABLE": (narrow_quarterly_reliable_events(ticker_map), None),
    }

    print("=== Grid: holding period x number of groups ===")
    results = []
    for scen_name, (events, _) in scenarios.items():
        for holding in [3, 6, 12]:
            for n_groups in [2, 3, 4, 5]:
                r = run_portfolio_sort(events, monthly_ret, ibov_monthly, holding_months=holding, n_groups=n_groups, min_group_size=3)
                row = {k: v for k, v in r.items() if k != "ls_series"}
                row.update({"scenario": scen_name, "holding_months": holding, "n_groups": n_groups})
                results.append(row)
                if r.get("n_months", 0) > 10:
                    flag = " <=====" if r["p_value"] < 0.10 else ""
                    print(f"{scen_name:28s} hold={holding:2d}mo groups={n_groups}  n_months={r['n_months']:3d}  "
                          f"avg_n={r['avg_n_active']:.0f}  ann_LS={r['annualized_ls_return']:+7.1%}  "
                          f"t={r['t_stat_newey_west']:+.2f}  p={r['p_value']:.4f}{flag}")

    print()
    print("=== Size-neutralized double sort (2 size buckets x 3 similarity terciles), 12-month hold ===")
    for scen_name, (events, year_col) in scenarios.items():
        if year_col is None:
            continue  # quarterly control-variable alignment not built; skip for the double sort
        r = run_size_neutral_sort(events, monthly_ret, ibov_monthly, ctrl, year_col, holding_months=12)
        row = dict(r)
        row.update({"scenario": scen_name + "_SIZE_NEUTRAL", "holding_months": 12, "n_groups": 3})
        results.append(row)
        if r.get("n_months", 0) > 0:
            print(f"{scen_name:28s} n_months={r['n_months']:3d}  buckets_used={r.get('n_size_buckets_used')}  "
                  f"ann_LS={r['annualized_ls_return']:+7.1%}  t={r['t_stat_newey_west']:+.2f}  p={r['p_value']:.4f}")
        else:
            print(f"{scen_name}: {r.get('error')}")

    out_path = POC / "portfolio_sort_grid_results.csv"
    pd.DataFrame(results).to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

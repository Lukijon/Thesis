"""Driver: runs the Cohen-Malloy-Nguyen-style portfolio sort
(src/analysis/portfolio_sort.py) across every combination of text scope
(narrow debt-note / whole notes document) and frequency (annual / quarterly
/ combined) already built in this project, plus multiple holding periods.
See reports/return_predictability_exploration.md for the full writeup.

Usage:
    python -m src.analysis.run_portfolio_sorts
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.portfolio_sort import build_events, load_monthly_returns, run_portfolio_sort

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POC = Path("data/interim/poc")
INTERIM = Path("data/interim")


def prep_annual_events(sim_path: str, name_col_year: str = "year_curr") -> pd.DataFrame:
    sim = pd.read_csv(POC / sim_path)
    filing_dates = pd.read_csv(INTERIM / "dfp_filing_dates.csv").rename(
        columns={"CD_CVM": "cd_cvm", "fiscal_year": name_col_year}
    )[["cd_cvm", name_col_year, "filing_date"]]
    events = sim.merge(filing_dates, on=["cd_cvm", name_col_year], how="left")
    events["filing_date"] = pd.to_datetime(events["filing_date"])
    events["entry_month"] = (events["filing_date"] + pd.offsets.MonthBegin(1)).dt.to_period("M").dt.to_timestamp("M")
    return events


def prep_quarterly_events(sim_path: str) -> pd.DataFrame:
    sim = pd.read_csv(POC / sim_path)
    filing_dates = pd.read_csv(INTERIM / "itr_filing_dates.csv").rename(
        columns={"CD_CVM": "cd_cvm", "QUARTER_LABEL": "quarter_curr"}
    )[["cd_cvm", "quarter_curr", "filing_date"]]
    events = sim.merge(filing_dates, on=["cd_cvm", "quarter_curr"], how="left")
    events["filing_date"] = pd.to_datetime(events["filing_date"])
    events["entry_month"] = (events["filing_date"] + pd.offsets.MonthBegin(1)).dt.to_period("M").dt.to_timestamp("M")
    return events


def attach_tickers(events: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
    tm = ticker_map.rename(columns={"CD_CVM": "cd_cvm"})[["cd_cvm", "ticker"]]
    return events.merge(tm, on="cd_cvm", how="left")


def main() -> None:
    ticker_map = build_ticker_map()
    monthly_ret, ibov_monthly = load_monthly_returns()

    scenarios = {
        # delisted_similarity_results.csv already contains BOTH the current-66
        # ("stayed") and historical-46 ("dropped_or_delisted") groups combined
        # -- it is the full-universe annual narrow-note dataset, not an add-on
        # to similarity_results.csv (using both would double-count current-66).
        "narrow_annual": prep_annual_events("delisted_similarity_results.csv"),
        "whole_annual": prep_annual_events("full_notes_similarity_results.csv"),
        "narrow_quarterly": prep_quarterly_events("itr_similarity_results.csv"),
    }

    for name, ev in scenarios.items():
        scenarios[name] = attach_tickers(ev, ticker_map)

    # combined: stack narrow-annual (full universe) with narrow-quarterly
    combined_narrow = pd.concat(
        [scenarios["narrow_annual"], scenarios["narrow_quarterly"]],
        ignore_index=True, sort=False,
    )
    scenarios["combined_narrow_annual_quarterly"] = combined_narrow

    results = []
    for scen_name, events in scenarios.items():
        for holding in [3, 12]:
            for n_groups in [2, 3]:
                r = run_portfolio_sort(events, monthly_ret, ibov_monthly, holding_months=holding, n_groups=n_groups)
                r_summary = {k: v for k, v in r.items() if k != "ls_series"}
                r_summary["scenario"] = scen_name
                r_summary["holding_months"] = holding
                r_summary["n_groups"] = n_groups
                results.append(r_summary)
                if r.get("n_months", 0) > 0:
                    print(f"{scen_name:35s} hold={holding:2d}mo groups={n_groups}  "
                          f"n_months={r['n_months']:3d}  avg_n={r['avg_n_active']:.0f}  "
                          f"ann_LS_ret={r['annualized_ls_return']:+.1%}  t={r['t_stat_newey_west']:+.2f}  p={r['p_value']:.4f}")
                else:
                    print(f"{scen_name:35s} hold={holding:2d}mo groups={n_groups}  -- {r.get('error')}")

    summary_df = pd.DataFrame(results)
    out_path = POC / "portfolio_sort_results.csv"
    summary_df.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

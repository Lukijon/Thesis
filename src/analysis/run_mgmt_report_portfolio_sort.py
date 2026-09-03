"""Portfolio-sort test for the management-report scenario specifically --
missing from portfolio_sort_grid_results.csv (that grid only covers
narrow-note and whole-document text; management report wasn't acquired
yet when it was built). Filling this gap directly answers whether the
clustered-regression result found in test_control_specifications.py
(p=0.03 for management-report returns, see reports/control_specification_test.md)
is corroborated by the more literature-standard portfolio-sort method, or
contradicts it the way the earlier whole-document delisting finding did.

Same grid density as portfolio_sort_grid.py's non-size-neutral scenarios:
holding periods of 3/6/12 months x 2/3/4 groups.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.portfolio_sort import load_monthly_returns, run_portfolio_sort
from src.analysis.run_portfolio_sorts import attach_tickers, prep_annual_events

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POC = Path("data/interim/poc")


def main() -> None:
    ticker_map = build_ticker_map()
    monthly_ret, ibov_monthly = load_monthly_returns()

    events = prep_annual_events("mgmt_report_similarity_results.csv")
    events = attach_tickers(events, ticker_map)
    print(f"{events['ticker'].notna().sum()} mgmt-report events with a resolved ticker (of {len(events)} total)")

    results = []
    for holding in [3, 6, 12]:
        for n_groups in [2, 3, 4]:
            r = run_portfolio_sort(events, monthly_ret, ibov_monthly, holding_months=holding, n_groups=n_groups)
            r_summary = {k: v for k, v in r.items() if k != "ls_series"}
            r_summary["scenario"] = "mgmt_report_annual"
            r_summary["holding_months"] = holding
            r_summary["n_groups"] = n_groups
            results.append(r_summary)
            if r.get("n_months", 0) > 0:
                print(f"hold={holding:2d}mo groups={n_groups}  n_months={r['n_months']:3d}  "
                      f"avg_n={r['avg_n_active']:.0f}  ann_LS={r['annualized_ls_return']:+7.1%}  "
                      f"t={r['t_stat_newey_west']:+.2f}  p={r['p_value']:.4f}")
            else:
                print(f"hold={holding:2d}mo groups={n_groups}  -- {r.get('error')}")

    new_df = pd.DataFrame(results)
    grid_path = POC / "portfolio_sort_grid_results.csv"
    existing = pd.read_csv(grid_path)
    combined = pd.concat([existing, new_df], ignore_index=True, sort=False)
    combined.to_csv(grid_path, index=False)
    print(f"\nAppended {len(new_df)} rows to {grid_path}")


if __name__ == "__main__":
    main()

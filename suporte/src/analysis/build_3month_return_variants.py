"""Builds a 3-month (63-trading-day) counterpart of every annual-frequency
abnormal-return file, to test whether switching the main regression's
forward-return window from 12 months to 3 months (matching Cohen, Malloy &
Nguyen's actual portfolio-sort holding period -- see
reports/return_predictability_exploration.md, this project's own
12-vs-3-month gap was flagged and never actually tested end to end) changes
H1's results.

Reuses the exact same event dates, ticker map, and price data as the
12-month files -- only `window_trading_days` changes (252 -> 63) -- so any
difference in results is attributable to the window length alone, not a
different sample or join.

Narrow-quarterly is deliberately NOT rebuilt here: its return window
(src/analysis/compute_quarterly_abnormal_returns.py, WINDOW_TRADING_DAYS=63)
is already ~3 months by construction (it matches the ITR filing cadence),
so it's already the CMN-comparable case.

Usage:
    python -u -m src.analysis.build_3month_return_variants
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map, compute_returns, load_event_dates

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

WINDOW_3M = 63  # ~1 quarter, matching Cohen-Malloy-Nguyen's actual holding period


def _build(sim_path: Path, out_path: Path, events: pd.DataFrame, ticker_map: pd.DataFrame, label: str) -> None:
    sim = pd.read_csv(sim_path)
    returns = compute_returns(events, ticker_map, window_trading_days=WINDOW_3M)
    merged = sim.merge(returns, on=["cd_cvm", "year_curr"], how="inner")
    merged = merged.drop_duplicates(subset=["cd_cvm", "year_prev", "year_curr"])
    merged.to_csv(out_path, index=False)
    print(f"{label}: {len(sim)} similarity pairs -> {len(merged)} with a computable 3-month abnormal return "
          f"(written: {out_path.name})")


def main() -> None:
    events = load_event_dates()
    ticker_map = build_ticker_map()

    # narrow_annual: same concat of current-66 + historical-46 as
    # compute_abnormal_returns.main()
    core = pd.read_csv(POC / "similarity_results.csv")
    core["poc_group"] = "current_66"
    delisted = pd.read_csv(POC / "delisted_similarity_results.csv")
    delisted["poc_group"] = delisted["group"]
    narrow_sim = pd.concat([core, delisted], ignore_index=True, sort=False)
    narrow_sim_path = POC / "_narrow_annual_sim_tmp.csv"
    narrow_sim.to_csv(narrow_sim_path, index=False)
    _build(narrow_sim_path, POC / "abnormal_returns_poc_3m.csv", events, ticker_map, "narrow_annual")
    narrow_sim_path.unlink()

    _build(POC / "full_notes_similarity_results_VERIFIED.csv", POC / "abnormal_returns_full_notes_VERIFIED_3m.csv",
           events, ticker_map, "whole_notes")
    _build(POC / "mgmt_report_similarity_results.csv", POC / "abnormal_returns_mgmt_report_3m.csv",
           events, ticker_map, "mgmt_report")
    _build(POC / "risk_factors_similarity_results.csv", POC / "abnormal_returns_risk_factors_3m.csv",
           events, ticker_map, "risk_factors")


if __name__ == "__main__":
    main()

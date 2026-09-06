"""Sanity-check counterparts of build_3month_return_variants.py at two more
horizons, both taken directly from the literature-verification pass:

- 3 trading days (index [0, 2], i.e. window_trading_days=2): Brown & Tucker
  (2011)'s own price-reaction window around the 10-K filing.
- 18 months (~378 trading days, 18*21): Cohen, Malloy & Nguyen (2020)'s own
  stated horizon for how long the drift "continues to accrue... without
  reversing."

Same event dates/tickers/prices as every other window variant -- only
window_trading_days changes -- so results are directly comparable.

Usage:
    python -u -m src.analysis.build_extra_window_variants
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map, compute_returns, load_event_dates

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

WINDOWS = {
    "3d": 2,     # [0, +2] trading days, matching Brown & Tucker's CAR window
    "18m": 378,  # ~18 months, matching CMN's stated drift-persistence horizon
}


def _build(sim_path: Path, out_path_tpl: str, events: pd.DataFrame, ticker_map: pd.DataFrame, label: str) -> None:
    sim = pd.read_csv(sim_path)
    for suffix, window in WINDOWS.items():
        returns = compute_returns(events, ticker_map, window_trading_days=window)
        merged = sim.merge(returns, on=["cd_cvm", "year_curr"], how="inner")
        merged = merged.drop_duplicates(subset=["cd_cvm", "year_prev", "year_curr"])
        out_path = POC / out_path_tpl.format(suffix=suffix)
        merged.to_csv(out_path, index=False)
        print(f"{label} [{suffix}]: {len(sim)} similarity pairs -> {len(merged)} with a computable abnormal return "
              f"(written: {out_path.name})")


def main() -> None:
    events = load_event_dates()
    ticker_map = build_ticker_map()

    core = pd.read_csv(POC / "similarity_results.csv")
    core["poc_group"] = "current_66"
    delisted = pd.read_csv(POC / "delisted_similarity_results.csv")
    delisted["poc_group"] = delisted["group"]
    narrow_sim = pd.concat([core, delisted], ignore_index=True, sort=False)
    narrow_sim_path = POC / "_narrow_annual_sim_tmp2.csv"
    narrow_sim.to_csv(narrow_sim_path, index=False)
    _build(narrow_sim_path, "abnormal_returns_poc_{suffix}.csv", events, ticker_map, "narrow_annual")
    narrow_sim_path.unlink()

    _build(POC / "full_notes_similarity_results_VERIFIED.csv", "abnormal_returns_full_notes_VERIFIED_{suffix}.csv",
           events, ticker_map, "whole_notes")
    _build(POC / "mgmt_report_similarity_results.csv", "abnormal_returns_mgmt_report_{suffix}.csv",
           events, ticker_map, "mgmt_report")
    _build(POC / "risk_factors_similarity_results.csv", "abnormal_returns_risk_factors_{suffix}.csv",
           events, ticker_map, "risk_factors")


if __name__ == "__main__":
    main()

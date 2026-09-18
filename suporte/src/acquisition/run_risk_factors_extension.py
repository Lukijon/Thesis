"""Extends run_risk_factors.py's FRE (Fatores de Risco, item 4.1)
acquisition from the original 111-company/2015-2024 scope to the round-7
universe expansion: the same 111 companies' 2010-2014 filings plus the 74
IBX-extra companies' 2010-2025 filings.

Genuinely new downloads (FRE wasn't previously acquired for these
company-years) -- CVM's FRE open-data index is available back to 2010
(confirmed directly against the server, unlike DFP which only goes back to
2010 as well but for a different reason -- both happen to share the same
floor). Expect real network time at CVM's RAD system's paced rate.

Usage:
    python -u -m src.acquisition.run_risk_factors_extension
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.acquisition.cvm_fre import latest_versions, load_fre_index, save_company_year_risk_factors

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/risk_factors")
YEARS = range(2010, 2026)
LOG_PATH = Path("data/interim/risk_factors_extension_log.csv")


def load_universe() -> set[int]:
    current = pd.read_csv("data/interim/ibov_non_financial_universe.csv")
    historical = pd.read_csv("data/interim/ibov_historical_notes_download_log.csv")
    ibx_extra = pd.read_csv("data/interim/ibx_extra_universe.csv", dtype={"CD_CVM": str})
    return (
        set(current["CD_CVM"].astype(int))
        | set(historical["CD_CVM"].astype(int))
        | set(ibx_extra["CD_CVM"].astype(int))
    )


def main() -> None:
    universe = load_universe()
    print(f"{len(universe)} companies in target universe, years {YEARS[0]}-{YEARS[-1]}")

    # Skip company-years already covered by the original run_risk_factors.py
    # acquisition (2015-2024, original 111) -- only fetch what's new.
    already_done = set()
    original_log = Path("data/interim/risk_factors_acquisition_log.csv")
    if already_done_path := original_log:
        if already_done_path.exists():
            prev = pd.read_csv(already_done_path)
            already_done = set(zip(prev["CD_CVM"].astype(int), prev["ANO"] if "ANO" in prev.columns else []))

    log_rows = []
    for year in YEARS:
        index_df = load_fre_index(year, CACHE_DIR)
        latest = latest_versions(index_df, cd_cvm_filter=universe)
        todo = [row for row in latest.itertuples(index=False) if (int(row.CD_CVM), year) not in already_done]
        print(f"\n=== {year}: {len(latest)} companies with an FRE filing, {len(todo)} new ===")
        for i, row in enumerate(todo, start=1):
            result = save_company_year_risk_factors(row.CD_CVM, year, row.ID_DOC, CACHE_DIR, OUT_ROOT)
            result["DENOM_CIA"] = row.DENOM_CIA
            log_rows.append(result)
            status = "OK" if result["found"] else ("ERROR" if result["error"] else "NOT_FOUND")
            if i % 25 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] {row.DENOM_CIA} ({year}) -> {status}")

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, index=False)
    print(f"\n{log_df['found'].sum()}/{len(log_df)} company-years found")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    main()

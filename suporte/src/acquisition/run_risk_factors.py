"""Driver: acquire Risk Factors (FRE item 4.1) for the full 111-company
universe (66 current Ibovespa + 45 historical/delisted), 2015-2024 -- same
scope as every other text source acquired this project. See
src/acquisition/cvm_fre.py's module docstring for the extraction method.

This is genuinely new acquisition (a filing type -- FRE -- not touched
before), unlike the management-report pass which reused already-cached
zips. Expect real network time: up to ~1,100 company-years, each a
multi-MB filing package, paced at CVM's RAD system's existing 2s/request
minimum (src/utils/http.py).

Usage:
    python -u -m src.acquisition.run_risk_factors
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.acquisition.cvm_fre import latest_versions, load_fre_index, save_company_year_risk_factors

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/risk_factors")
YEARS = range(2015, 2025)
LOG_PATH = Path("data/interim/risk_factors_acquisition_log.csv")


def main() -> None:
    universe = set(pd.read_csv("data/interim/poc/delisted_similarity_results.csv")["cd_cvm"].unique())
    print(f"{len(universe)} companies in target universe")

    log_rows = []
    for year in YEARS:
        index_df = load_fre_index(year, CACHE_DIR)
        latest = latest_versions(index_df, cd_cvm_filter=universe)
        print(f"\n=== {year}: {len(latest)} companies with an FRE filing ===")
        for i, row in enumerate(latest.itertuples(index=False), start=1):
            result = save_company_year_risk_factors(row.CD_CVM, year, row.ID_DOC, CACHE_DIR, OUT_ROOT)
            result["DENOM_CIA"] = row.DENOM_CIA
            log_rows.append(result)
            status = "OK" if result["found"] else ("ERROR" if result["error"] else "NOT_FOUND")
            print(f"  [{i}/{len(latest)}] {row.DENOM_CIA} ({year}) -> {status}")

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, index=False)
    print(f"\n{log_df['found'].sum()}/{len(log_df)} company-years found")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    main()

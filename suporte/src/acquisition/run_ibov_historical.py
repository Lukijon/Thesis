"""Download debt-note PDFs for the historical-IBOV addition: companies that
were in the Ibovespa at some point in 2013-2021 but have since dropped out
(delisted, bankrupt, acquired, or fell out on liquidity), which the
original current-members-only IBOV tranche (run_ibov.py) missed entirely.
See src/acquisition/b3_ibov_historical.py for the methodology and its
documented coverage gaps.

Usage:
    python -u -m src.acquisition.run_ibov_historical
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.acquisition.cvm_dfp import build_company_universe
from src.acquisition.cvm_notes import save_company_year_notes

YEARS = list(range(2015, 2025))

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
LOG_PATH = Path("data/interim/ibov_historical_notes_download_log.csv")


def main() -> None:
    cd_cvm_filter = set(NEW_HISTORICAL_CD_CVM)
    universe = build_company_universe(YEARS, CACHE_DIR, cd_cvm_filter=cd_cvm_filter)
    print(f"{universe['CD_CVM'].nunique()}/{len(cd_cvm_filter)} companies have at least one DFP filing 2015-2024")
    print(f"{len(universe)} company-fiscal-year filings to fetch")

    log_rows = []
    for i, (_, row) in enumerate(universe.iterrows(), start=1):
        try:
            result = save_company_year_notes(row["CD_CVM"], row["ANO"], row["ID_DOC"], CACHE_DIR, OUT_ROOT)
        except Exception as exc:  # noqa: BLE001 - keep the batch going, log the failure
            result = {"CD_CVM": row["CD_CVM"], "ANO": row["ANO"], "ID_DOC": row["ID_DOC"], "n_attachments_matched": 0, "match_tier": None, "files": [], "error": str(exc)}
        result["DENOM_CIA"] = row["DENOM_CIA"]
        log_rows.append(result)
        status = "ERROR" if result.get("error") else ("OK" if result["n_attachments_matched"] else "NO MATCH")
        print(f"[{i}/{len(universe)}] {row['DENOM_CIA']} ({row['ANO']}) -> {status}")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, index=False)

    n_ok = (log_df["n_attachments_matched"] > 0).sum()
    print(f"\n{n_ok}/{len(log_df)} company-years yielded a notes PDF.")
    print(log_df["match_tier"].value_counts(dropna=False))
    print(f"\nLog: {LOG_PATH}")


if __name__ == "__main__":
    main()

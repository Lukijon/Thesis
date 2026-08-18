"""Part 1 of the full-scale acquisition: download debt-note PDFs for every
non-financial company currently in the Ibovespa, across the 2015-2024
sample window. The rest of the non-financial B3 universe is part 2 (see
`run_full_universe.py`).

Usage:
    python -m src.acquisition.run_ibov
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.b3_ibov import build_ibov_non_financial_universe
from src.acquisition.cvm_dfp import build_company_universe
from src.acquisition.cvm_notes import save_company_year_notes

YEARS = list(range(2015, 2025))

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
UNIVERSE_OUT = Path("data/interim/ibov_non_financial_universe.csv")
LOG_PATH = Path("data/interim/ibov_notes_download_log.csv")


def main() -> None:
    ibov_universe = build_ibov_non_financial_universe(CACHE_DIR)
    UNIVERSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    ibov_universe.to_csv(UNIVERSE_OUT, index=False)
    print(f"{len(ibov_universe)} non-financial IBOV companies -> {UNIVERSE_OUT}")

    cd_cvm_filter = set(ibov_universe["CD_CVM"])
    universe = build_company_universe(YEARS, CACHE_DIR, cd_cvm_filter=cd_cvm_filter)
    print(f"{len(universe)} company-fiscal-year filings to fetch ({universe['CD_CVM'].nunique()} companies x up to {len(YEARS)} years)")

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
    if "error" in log_df.columns:
        failures = log_df[log_df["error"].notna()]
        if len(failures):
            print(f"\n{len(failures)} failed after retries -- rerun the script (cached filings are skipped) to retry just these:")
            print(failures[["DENOM_CIA", "ANO", "ID_DOC", "error"]].to_string())
    print(f"\nLog: {LOG_PATH}")


if __name__ == "__main__":
    main()

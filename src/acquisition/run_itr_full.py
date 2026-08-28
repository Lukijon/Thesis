"""Quarterly (ITR) acquisition, part 1's full universe: all 66 current
non-financial IBOV constituents plus all 46 historical/delisted companies
found via `b3_ibov_historical.py` -- the same 112-company universe already
covered by the annual DFP pipeline, now at quarterly frequency.

Extends `run_itr_pilot.py`'s 20-company pilot to the full set. Re-includes
those same 20 companies rather than excluding them: `save_company_quarter_notes`
is idempotent and the underlying filing zips are already cached, so
re-processing them just confirms consistency at near-zero extra cost
instead of adding exclusion-logic complexity for little benefit.

Downloads ITR filings for 2015-2024 (Q1/Q2/Q3 each year -- Q4 is covered by
the annual DFP, not ITR). Output lands at
data/raw/itr/<CD_CVM>/<YYYYQn>/notas_explicativas.pdf.

Usage:
    python -u -m src.acquisition.run_itr_full
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.acquisition.cvm_itr import build_quarterly_universe, save_company_quarter_notes

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/itr")
YEARS = list(range(2015, 2025))


def full_universe_cd_cvm() -> set[int]:
    current = pd.read_csv("data/interim/ibov_non_financial_universe.csv")["CD_CVM"].astype(int)
    historical = set(NEW_HISTORICAL_CD_CVM.keys())
    return set(current) | historical


def main() -> None:
    cd_cvm_filter = full_universe_cd_cvm()
    universe = build_quarterly_universe(YEARS, CACHE_DIR, cd_cvm_filter=cd_cvm_filter)
    print(f"{len(universe)} company-quarter rows across {universe['CD_CVM'].nunique()} companies "
          f"(of {len(cd_cvm_filter)} in the target universe -- gaps mean no ITR filing found, e.g. delisted mid-period)")

    log_rows = []
    for i, (_, row) in enumerate(universe.iterrows(), start=1):
        try:
            result = save_company_quarter_notes(
                row["CD_CVM"], row["QUARTER_LABEL"], row["ID_DOC"], CACHE_DIR, OUT_ROOT
            )
        except Exception as exc:
            result = {
                "CD_CVM": row["CD_CVM"], "QUARTER_LABEL": row["QUARTER_LABEL"], "ID_DOC": row["ID_DOC"],
                "n_attachments_matched": 0, "match_tier": None, "files": [], "error": str(exc),
            }
        result["DENOM_CIA"] = row["DENOM_CIA"]
        result["DT_REFER"] = row["DT_REFER"]
        log_rows.append(result)
        status = "ERROR" if result.get("error") else ("OK" if result["n_attachments_matched"] else "NO MATCH")
        print(f"[{i}/{len(universe)}] {row['DENOM_CIA']} ({row['QUARTER_LABEL']}) -> {status}")

    out_csv = Path("data/interim/itr_full_notes_download_log.csv")
    pd.DataFrame(log_rows).to_csv(out_csv, index=False)
    print(f"\nLog written: {out_csv}")


if __name__ == "__main__":
    main()

"""Quarterly (ITR) acquisition pilot: does note text at quarterly frequency
catch a company's deterioration sooner than the annual (DFP) comparison
does? Uses the same 20-company hand-picked set as the original annual POC
(rounds 1-2, `run_poc_tfidf.py`'s original `POC_COMPANIES`) rather than a
fresh company selection, so quarterly results are directly comparable
against an already-established annual baseline for the same companies.

Downloads ITR filings for 2015-2024 (Q1/Q2/Q3 each year -- Q4 is covered by
the annual DFP already downloaded, not by ITR). Output lands at
data/raw/itr/<CD_CVM>/<YYYYQn>/notas_explicativas.pdf, separate from the
annual data/raw/dfp/ tree.

Usage:
    python -u -m src.acquisition.run_itr_pilot
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.cvm_itr import build_quarterly_universe, save_company_quarter_notes

CACHE_DIR = Path("data/raw/dfp/_cache")  # shared with DFP: same CVM cadastral/filing-zip cache
OUT_ROOT = Path("data/raw/itr")
YEARS = list(range(2015, 2025))

# Same 20 companies as the original annual POC's hand-picked set (see
# src/processing/run_poc_tfidf.py git history / reports/poc_note_extraction_findings.md).
PILOT_CD_CVM = {
    4170, 9512, 23264, 3980, 14320, 5410, 20087, 13986, 4820, 2453,
    14443, 8133, 5258, 20915, 20788, 19992, 21881, 17671, 21016, 19739,
}


def main() -> None:
    universe = build_quarterly_universe(YEARS, CACHE_DIR, cd_cvm_filter=PILOT_CD_CVM)
    print(f"{len(universe)} company-quarter rows across {universe['CD_CVM'].nunique()} companies")

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

    out_csv = Path("data/interim/itr_pilot_notes_download_log.csv")
    pd.DataFrame(log_rows).to_csv(out_csv, index=False)
    print(f"\nLog written: {out_csv}")


if __name__ == "__main__":
    main()

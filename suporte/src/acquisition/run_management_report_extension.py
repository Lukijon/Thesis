"""Extends cvm_management_report.py's acquisition (originally 111
companies/2015-2024 only) to the round-7 universe expansion: the same
111-company panel's 2010-2014 filings plus the 74 IBX-extra companies'
2010-2025 filings. Zero new downloads, same as the original script --
every filing's zip is already cached locally from the debt-note
acquisition, this just re-processes those cached zips with the
management-report attachment-selection target.

Usage:
    python -u -m src.acquisition.run_management_report_extension
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.cvm_management_report import OUT_ROOT, save_company_year_management_report

INTERIM = Path("data/interim")
LOG_PATH = INTERIM / "management_report_extension_log.csv"


def main() -> None:
    log_hist = pd.read_csv(INTERIM / "history_extension_notes_download_log.csv")
    log_ibx = pd.read_csv(INTERIM / "ibx_extension_notes_download_log.csv")
    log = pd.concat([log_hist, log_ibx], ignore_index=True)
    log = log[log["n_attachments_matched"] > 0].dropna(subset=["ID_DOC"])
    log["ID_DOC"] = log["ID_DOC"].astype(int)
    print(f"{len(log)} filings to process")

    rows = []
    for i, row in enumerate(log.itertuples(index=False), start=1):
        try:
            result = save_company_year_management_report(row.CD_CVM, row.ANO, row.ID_DOC, OUT_ROOT)
        except Exception as exc:  # noqa: BLE001
            result = {"CD_CVM": str(row.CD_CVM), "ANO": int(row.ANO), "ID_DOC": str(row.ID_DOC), "found": False, "tier": "error", "files": [], "error": str(exc)}
        result["DENOM_CIA"] = row.DENOM_CIA
        rows.append(result)
        if i % 200 == 0 or i == len(log):
            found_so_far = sum(1 for r in rows if r["found"])
            print(f"[{i}/{len(log)}] {found_so_far} found so far")

    out = pd.DataFrame(rows)
    out.to_csv(LOG_PATH, index=False)

    n_found = sum(1 for r in rows if r["found"])
    tier_counts = pd.Series([r["tier"] for r in rows]).value_counts()
    print(f"\n{n_found}/{len(rows)} ({n_found/len(rows):.1%}) management reports found")
    print(tier_counts.to_string())
    print(f"\nLog: {LOG_PATH}")


if __name__ == "__main__":
    main()

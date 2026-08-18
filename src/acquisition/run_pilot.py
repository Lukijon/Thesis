"""Pilot run: validate the CVM acquisition pipeline end-to-end on a small,
known set of non-financial B3 companies before scaling to the full sample.

Usage:
    python -m src.acquisition.run_pilot
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.cvm_dfp import build_company_universe
from src.acquisition.cvm_notes import save_company_year_notes

PILOT_COMPANY_NAME_PATTERNS = [
    "VALE S.A.",
    "PETROBRAS",
    "AMBEV",
    "WEG S.A.",
    "GERDAU S.A.",
    "SUZANO S.A.",
    "LOCALIZA",
    "JBS S.A.",
]
PILOT_YEARS = [2023, 2024]

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
LOG_PATH = Path("data/interim/pilot_notes_download_log.csv")


def main() -> None:
    universe = build_company_universe(PILOT_YEARS, CACHE_DIR)

    pattern = "|".join(PILOT_COMPANY_NAME_PATTERNS)
    pilot = universe[universe["DENOM_CIA"].str.contains(pattern, case=False, na=False, regex=True)]

    found_names = sorted(pilot["DENOM_CIA"].unique())
    print(f"Matched {len(found_names)} companies in the universe:")
    for name in found_names:
        print(f"  - {name}")

    missing = [
        p for p in PILOT_COMPANY_NAME_PATTERNS
        if not any(p.split()[0].upper() in n.upper() for n in found_names)
    ]
    if missing:
        print(f"WARNING: no match found for: {missing}")

    log_rows = []
    for _, row in pilot.iterrows():
        print(f"Fetching {row['DENOM_CIA']} ({row['ANO']}) ...")
        try:
            result = save_company_year_notes(row["CD_CVM"], row["ANO"], row["ID_DOC"], CACHE_DIR, OUT_ROOT)
        except Exception as exc:  # noqa: BLE001 - keep the pilot going, log the failure
            result = {"CD_CVM": row["CD_CVM"], "ANO": row["ANO"], "ID_DOC": row["ID_DOC"], "n_attachments_matched": 0, "files": [], "error": str(exc)}
        result["DENOM_CIA"] = row["DENOM_CIA"]
        log_rows.append(result)
        status = "ERROR" if result.get("error") else ("OK" if result["n_attachments_matched"] else "NO MATCH")
        print(f"  -> {status} ({result['n_attachments_matched']} attachment(s))")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(log_rows).to_csv(LOG_PATH, index=False)

    n_ok = sum(1 for r in log_rows if r["n_attachments_matched"])
    print(f"\n{n_ok}/{len(log_rows)} company-years yielded a notes PDF. Log: {LOG_PATH}")


if __name__ == "__main__":
    main()

"""Extends run_itr_full.py's ITR (quarterly) acquisition from the original
111-company/2015-2024 scope to the round-7 universe expansion: full
185-company universe (111 original + 74 IBX-extra), 2011-2025 (2011 is the
earliest year CVM's ITR open-data archive has -- confirmed directly against
the server; 2010 404s, unlike DFP/FRE which both go back to 2010).

Runs the full 185-company x 2011-2025 sweep in one pass rather than only
the incremental new company-quarters: save_company_quarter_notes is
idempotent and the underlying filing zips for already-covered years
(2015-2024, original 111) are already cached, so re-touching them costs
no new network calls, and this avoids hand-splitting the "new" set the
same way run_itr_full.py already established as the correct pattern for a
full-universe pass.

Usage:
    python -u -m src.acquisition.run_itr_extension
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.acquisition.cvm_itr import build_quarterly_universe, save_company_quarter_notes

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/itr")
YEARS = list(range(2011, 2026))
LOG_PATH = Path("data/interim/itr_extension_log.csv")


def full_universe_cd_cvm() -> set[int]:
    current = pd.read_csv("data/interim/ibov_non_financial_universe.csv")["CD_CVM"].astype(int)
    historical = set(NEW_HISTORICAL_CD_CVM.keys())
    ibx_extra = pd.read_csv("data/interim/ibx_extra_universe.csv", dtype={"CD_CVM": str})["CD_CVM"].astype(int)
    return set(current) | historical | set(ibx_extra)


def main() -> None:
    cd_cvm_filter = full_universe_cd_cvm()
    universe = build_quarterly_universe(YEARS, CACHE_DIR, cd_cvm_filter=cd_cvm_filter)
    print(f"{len(universe)} company-quarter rows across {universe['CD_CVM'].nunique()} companies "
          f"(of {len(cd_cvm_filter)} in the target universe)")

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
        if i % 200 == 0 or i == len(universe):
            n_ok = sum(1 for r in log_rows if r.get("n_attachments_matched", 0))
            print(f"[{i}/{len(universe)}] {n_ok} OK so far")

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, index=False)
    n_ok = (log_df["n_attachments_matched"] > 0).sum()
    print(f"\n{n_ok}/{len(log_df)} company-quarters yielded a notes PDF.")
    print(log_df["match_tier"].value_counts(dropna=False))
    print(f"\nLog: {LOG_PATH}")


if __name__ == "__main__":
    main()

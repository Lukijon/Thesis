"""Extends build_filing_dates.py's dfp_filing_dates.csv (111 companies,
2015-2024 only) to also cover the round-7 universe expansion: the same
111-company panel's 2010-2014 filings (run_history_extension.py) and the
74 IBX-extra companies' 2010-2025 filings (run_ibx_extension.py).

Kept as a separate output file rather than overwriting dfp_filing_dates.csv
-- that file is what the thesis's own H1/H2 pipeline reads, unaffected by
this exploratory extension. Concatenate the two when a script needs the
full combined coverage.

Usage:
    python -u -m src.acquisition.build_filing_dates_extension
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data/raw/dfp/_cache")
INTERIM = Path("data/interim")
YEARS = range(2010, 2026)
OUT_PATH = INTERIM / "dfp_filing_dates_extension.csv"


def load_filing_dates() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        zpath = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
        if not zpath.exists():
            continue
        with zipfile.ZipFile(zpath) as zf:
            with zf.open(f"dfp_cia_aberta_{year}.csv") as f:
                df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
        df = df[df["CATEG_DOC"] == "DFP"][["CD_CVM", "ID_DOC", "DT_REFER", "DT_RECEB"]]
        df["ANO"] = year
        frames.append(df)
    idx = pd.concat(frames, ignore_index=True)
    idx["CD_CVM"] = idx["CD_CVM"].astype(int)
    idx["ID_DOC"] = idx["ID_DOC"].astype(int)
    return idx


def main() -> None:
    filing_dates = load_filing_dates()

    log_hist_ext = pd.read_csv(INTERIM / "history_extension_notes_download_log.csv")
    log_hist_ext = log_hist_ext[log_hist_ext["n_attachments_matched"] > 0].assign(source="history_extension")
    log_ibx = pd.read_csv(INTERIM / "ibx_extension_notes_download_log.csv")
    log_ibx = log_ibx[log_ibx["n_attachments_matched"] > 0].assign(source="ibx_extension")

    logs = pd.concat(
        [log_hist_ext[["CD_CVM", "ANO", "ID_DOC", "DENOM_CIA", "source"]],
         log_ibx[["CD_CVM", "ANO", "ID_DOC", "DENOM_CIA", "source"]]],
        ignore_index=True,
    ).dropna(subset=["ID_DOC"])
    logs["ID_DOC"] = logs["ID_DOC"].astype(int)
    logs["CD_CVM"] = logs["CD_CVM"].astype(int)

    merged = logs.merge(filing_dates, on=["CD_CVM", "ANO", "ID_DOC"], how="left")
    n_missing = merged["DT_RECEB"].isna().sum()
    if n_missing:
        print(f"WARNING: {n_missing}/{len(merged)} filings had no matching DT_RECEB (ID_DOC not found in the cached index)")

    merged = merged.rename(columns={"ANO": "fiscal_year", "DT_REFER": "period_end_date", "DT_RECEB": "filing_date"})
    merged = merged[["CD_CVM", "DENOM_CIA", "fiscal_year", "period_end_date", "filing_date", "ID_DOC", "source"]]
    merged = merged.sort_values(["DENOM_CIA", "fiscal_year"]).reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_PATH, index=False)
    print(f"{len(merged)} company-fiscal-years -> {OUT_PATH}")


if __name__ == "__main__":
    main()

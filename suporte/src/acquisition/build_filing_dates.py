"""Build a reference table of when each acquired debt-note filing actually
became public -- needed for any event-study/abnormal-return work (see
src/analysis/compute_abnormal_returns.py) but not previously persisted
anywhere.

The raw CVM filing index (dfp_cia_aberta_<year>.zip, already cached locally
by the acquisition scripts) carries two distinct dates per filing:
  - DT_REFER: the fiscal period the statements cover (e.g. 2015-12-31) --
    this is what "ANO" in the download logs already reflects.
  - DT_RECEB: the date CVM actually received/published the filing (e.g.
    2016-03-28) -- when the market could have first reacted to it. This is
    the real event date for H1/H1a, and until now it was silently dropped:
    build_company_universe() in cvm_dfp.py never kept it, so it only ever
    existed transiently inside the raw cached zips.

This script joins the two acquisition download logs (current-IBOV +
historical-IBOV) to the raw index on the exact ID_DOC each log recorded
(the specific filing version actually downloaded), restricted to
company-years where a notes PDF was actually matched -- i.e. exactly the
"reports" this repo has, not the full CVM universe.

Usage:
    python -u -m src.acquisition.build_filing_dates
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data/raw/dfp/_cache")
INTERIM = Path("data/interim")
YEARS = range(2015, 2025)
OUT_PATH = INTERIM / "dfp_filing_dates.csv"


def load_filing_dates() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        with zipfile.ZipFile(CACHE_DIR / f"dfp_cia_aberta_{year}.zip") as zf:
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

    log_current = pd.read_csv(INTERIM / "ibov_notes_download_log.csv")
    log_current = log_current[log_current["n_attachments_matched"] > 0].assign(source="current_ibov")
    log_hist = pd.read_csv(INTERIM / "ibov_historical_notes_download_log.csv")
    log_hist = log_hist[log_hist["n_attachments_matched"] > 0].assign(source="historical_ibov")

    logs = pd.concat(
        [log_current[["CD_CVM", "ANO", "ID_DOC", "DENOM_CIA", "source"]],
         log_hist[["CD_CVM", "ANO", "ID_DOC", "DENOM_CIA", "source"]]],
        ignore_index=True,
    ).dropna(subset=["ID_DOC"])
    logs["ID_DOC"] = logs["ID_DOC"].astype(int)

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

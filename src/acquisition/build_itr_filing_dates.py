"""ITR (quarterly) counterpart to `build_filing_dates.py` -- builds a
reference table of when each acquired quarterly filing actually became
public (DT_RECEB), needed for the quarterly abnormal-return checkpoint.
Same rationale: the raw CVM ITR index carries this date, but the
acquisition download logs (`run_itr_pilot.py`/`run_itr_full.py`) never
persisted it.

Usage:
    python -u -m src.acquisition.build_itr_filing_dates
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("data/raw/dfp/_cache")  # shared cache dir with DFP acquisition
INTERIM = Path("data/interim")
YEARS = range(2015, 2025)
OUT_PATH = INTERIM / "itr_filing_dates.csv"


def load_filing_dates() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        zip_path = CACHE_DIR / f"itr_cia_aberta_{year}.zip"
        if not zip_path.exists():
            continue
        with zipfile.ZipFile(zip_path) as zf:
            with zf.open(f"itr_cia_aberta_{year}.csv") as f:
                df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
        df = df[df["CATEG_DOC"] == "ITR"][["CD_CVM", "ID_DOC", "DT_REFER", "DT_RECEB"]]
        frames.append(df)
    idx = pd.concat(frames, ignore_index=True)
    idx["CD_CVM"] = idx["CD_CVM"].astype(int)
    idx["ID_DOC"] = idx["ID_DOC"].astype(int)
    return idx.drop_duplicates(subset=["CD_CVM", "ID_DOC"])


def main() -> None:
    filing_dates = load_filing_dates()

    log = pd.read_csv(INTERIM / "itr_full_notes_download_log.csv")
    log = log[log["n_attachments_matched"] > 0].dropna(subset=["ID_DOC"])
    log["ID_DOC"] = log["ID_DOC"].astype(int)
    log["CD_CVM"] = log["CD_CVM"].astype(int)

    merged = log[["CD_CVM", "QUARTER_LABEL", "ID_DOC", "DENOM_CIA"]].merge(
        filing_dates, on=["CD_CVM", "ID_DOC"], how="left"
    )
    n_missing = merged["DT_RECEB"].isna().sum()
    if n_missing:
        print(f"WARNING: {n_missing}/{len(merged)} filings had no matching DT_RECEB")

    merged = merged.rename(columns={"DT_REFER": "period_end_date", "DT_RECEB": "filing_date"})
    merged = merged[["CD_CVM", "DENOM_CIA", "QUARTER_LABEL", "period_end_date", "filing_date", "ID_DOC"]]
    merged = merged.sort_values(["DENOM_CIA", "QUARTER_LABEL"]).reset_index(drop=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_PATH, index=False)
    print(f"{len(merged)} company-quarters -> {OUT_PATH}")


if __name__ == "__main__":
    main()

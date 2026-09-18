"""Extends the acquired sample backward in time: debt-note PDFs for the
same 111-company fixed panel (66 current Ibovespa + 45 historical/delisted,
data/interim/ibov_non_financial_universe.csv + ibov_historical_notes_download_log.csv)
across fiscal years 2010-2014, on top of the existing 2015-2024 window.

Deliberately the SAME company panel as 2015-2024, not a fresh IBOV-
membership reconstruction for 2010-2014 -- extending the identical set of
companies backward avoids re-opening the survivorship-bias question for
the older years (a separate, much larger project: reconstructing which
companies were in the index a decade ago).

2010 is the earliest year available in this form: CVM's open-data DFP
archive (https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/) starts
at dfp_cia_aberta_2010.zip -- 2004-2009 do not exist in this system at all
(verified directly against the server's own directory listing, not an
assumption). Note also that Bloomberg stock-price coverage
(data/raw/market/prices/stock_prices_bloomberg.csv) only starts
2014-01-01, so fiscal years 2010-2012 (and part of 2013) acquired here
will have debt-note text but no usable return window for H1 without a
separate, later market-data extension -- this script only acquires text,
it does not attempt to compute anything with it.

Usage:
    python -u -m src.acquisition.run_history_extension
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.cvm_dfp import build_company_universe
from src.acquisition.cvm_notes import save_company_year_notes

YEARS = list(range(2010, 2015))

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
CURRENT_UNIVERSE = Path("data/interim/ibov_non_financial_universe.csv")
HISTORICAL_LOG = Path("data/interim/ibov_historical_notes_download_log.csv")
LOG_PATH = Path("data/interim/history_extension_notes_download_log.csv")


def load_panel_cd_cvm() -> set[int]:
    current = pd.read_csv(CURRENT_UNIVERSE)
    historical = pd.read_csv(HISTORICAL_LOG)
    codes = set(current["CD_CVM"].astype(int)) | set(historical["CD_CVM"].astype(int))
    assert len(codes) == 111, f"expected 111 companies, got {len(codes)} -- panel definition changed?"
    return codes


def main() -> None:
    cd_cvm_filter = load_panel_cd_cvm()
    print(f"{len(cd_cvm_filter)}-company fixed panel, years {YEARS[0]}-{YEARS[-1]}")

    universe = build_company_universe(YEARS, CACHE_DIR, cd_cvm_filter=cd_cvm_filter)
    print(f"{len(universe)} company-fiscal-year filings to fetch ({universe['CD_CVM'].nunique()} companies "
          f"x up to {len(YEARS)} years -- not all companies existed/filed for the whole window)")

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

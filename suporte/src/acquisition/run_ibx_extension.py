"""Second universe expansion: debt-note PDFs for the non-financial
companies in ibx.xlsx (a user-supplied Bloomberg export of IBX index
membership, repo root, `IBM_Members` sheet: ID/Name/CNPJ, 245 rows) that
are NOT already in our 111-company Ibovespa panel (66 current +
45 historical/delisted, see run_history_extension.py) -- the "IBX minus
IBOV" set, since IBX is the broader index (IBOV plus more names) the
user asked to expand into. Years 2010-2025, matching the horizon already
established for the IBOV panel (see run_history_extension.py for why 2010
is the earliest year CVM has in this data source, and the Bloomberg-price
market-data caveat for pre-2014 return calculations -- both apply here
too, unchanged).

Matching ibx.xlsx's CNPJ column to a CD_CVM code goes through CVM's own
cadastral registry (cad_cia_aberta.csv, already cached from prior runs),
which is the only reliable key between a Bloomberg ticker/name and a CVM
filer id -- tickers and company names both drift over time (renames,
restructurings), CNPJ doesn't. ~31 of 245 rows don't match (a mix of:
genuinely financial companies correctly excluded by this project's
non-financial scope -- banks, insurers, payment institutions; and a
handful with no CNPJ in the Bloomberg export at all, typically very old
delisted/merged names). Both are expected, not bugs; see main()'s printed
breakdown before trusting the final "extra" count blindly.

Usage:
    python -u -m src.acquisition.run_ibx_extension
"""
from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd

from src.acquisition.cvm_dfp import build_company_universe, is_financial_sector
from src.acquisition.cvm_notes import save_company_year_notes

YEARS = list(range(2010, 2026))

ROOT = Path(__file__).resolve().parents[2]
IBX_XLSX = ROOT / "ibx.xlsx"
CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
CURRENT_UNIVERSE = Path("data/interim/ibov_non_financial_universe.csv")
HISTORICAL_LOG = Path("data/interim/ibov_historical_notes_download_log.csv")
EXTRA_UNIVERSE_OUT = Path("data/interim/ibx_extra_universe.csv")
LOG_PATH = Path("data/interim/ibx_extension_notes_download_log.csv")


def load_ibx_members() -> pd.DataFrame:
    wb = openpyxl.load_workbook(IBX_XLSX, read_only=True, data_only=True)
    ws = wb["IBM_Members"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return pd.DataFrame(rows, columns=["ID", "Name", "CNPJ"])


def resolve_extra_cd_cvm() -> pd.DataFrame:
    """Returns a DataFrame (ID, Name, CNPJ, CD_CVM) of IBX companies not
    already in the 111-company IBOV panel, non-financial only."""
    ibx = load_ibx_members()

    cad = pd.read_csv(CACHE_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str)
    cad = cad.assign(CD_CVM_INT=cad["CD_CVM"].astype(int))
    cad_nonfin = cad[~cad["SETOR_ATIV"].apply(is_financial_sector)]
    cnpj_to_cdcvm = cad_nonfin.drop_duplicates("CNPJ_CIA").set_index("CNPJ_CIA")["CD_CVM_INT"]

    ibx = ibx.copy()
    ibx["CD_CVM"] = ibx["CNPJ"].map(cnpj_to_cdcvm)
    matched = ibx.dropna(subset=["CD_CVM"]).copy()
    matched["CD_CVM"] = matched["CD_CVM"].astype(int)

    existing_111 = (
        set(pd.read_csv(CURRENT_UNIVERSE)["CD_CVM"].astype(int))
        | set(pd.read_csv(HISTORICAL_LOG)["CD_CVM"].astype(int))
    )

    print(f"IBX members: {len(ibx)} rows -> {len(matched)} matched to a non-financial CD_CVM "
          f"({len(ibx) - len(matched)} unmatched: financial companies correctly excluded, or no CNPJ in the export)")

    extra = matched[~matched["CD_CVM"].isin(existing_111)].drop_duplicates("CD_CVM").sort_values("Name")
    print(f"{len(matched) - len(extra)} already in the 111-company IBOV panel; {len(extra)} new companies to acquire")
    return extra


def main() -> None:
    extra = resolve_extra_cd_cvm()
    EXTRA_UNIVERSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    extra.to_csv(EXTRA_UNIVERSE_OUT, index=False)
    print(f"Extra-company list -> {EXTRA_UNIVERSE_OUT}")

    cd_cvm_filter = set(extra["CD_CVM"])
    universe = build_company_universe(YEARS, CACHE_DIR, cd_cvm_filter=cd_cvm_filter)
    print(f"{len(universe)} company-fiscal-year filings to fetch ({universe['CD_CVM'].nunique()} companies "
          f"x up to {len(YEARS)} years, {YEARS[0]}-{YEARS[-1]})")

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

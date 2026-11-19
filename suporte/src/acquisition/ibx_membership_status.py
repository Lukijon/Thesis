"""Determines, for every company in the 185-company sample, whether it is a
CURRENT or HISTORICAL member of the IBX index, using the daily historical
membership matrix the user added to ibx.xlsx (sheet `ibx_members_hist`:
one row per calendar day 2010-01-01..2025-12-31, one column per ticker that
was ever an IBX member in that window, cell = ticker string if a member of
IBX on that date, "#N/A" otherwise).

This supersedes the earlier proxy used in build_thesis_figures_expanded.py,
which assumed (a) all 74 "IBX-extra" companies (never in Ibovespa) are
CURRENT IBX members, and (b) all 45 "historical Ibovespa" companies are no
longer in IBX -- neither holds in the real data: many IBX-extra companies
have since rotated out of the index, and several ex-Ibovespa companies are
still in the broader IBX today. ibx_members_hist provides real historical
IBX composition, so this proxy is no longer necessary for the "current vs.
historical IBX" question -- it's still the only source for "left Ibovespa
specifically" (a distinct, narrower outcome used only by the delisting
check, unaffected by this script).

Matching a company (identified by CD_CVM) to its column(s) in
ibx_members_hist goes through CNPJ, like the rest of the IBX acquisition
pipeline (run_ibx_extension.py) -- but a single CD_CVM can have MULTIPLE
tickers/columns in ibx_members_hist sharing the same CNPJ, one per share
class or post-restructuring rename (e.g. Gerdau: GGBR3 and GGBR4; Suzano:
SUZB5 -> SUZB3 after a 2019 share unification; Rumo: ALLL3/ALLL11 ->
RAIL3/RUMO3). Matching on a single arbitrary ticker per CNPJ silently
picks whichever row happens to come first in the Bloomberg export, which
is frequently a delisted/legacy class -- this misclassified 14 of the 66
current Ibovespa constituents (a logical impossibility, since Ibovespa is
a strict subset of IBX) before this was caught. The fix: collect every
ticker sharing a company's CNPJ (or its 8-digit root, for the handful of
CVM-registry/Bloomberg branch-CNPJ mismatches, e.g. Americanas) and treat
the company as a CURRENT IBX member if ANY of its tickers is still active
on the last available date.

One remaining manual override: SMILES S.A. (CD_CVM 23140) has no CNPJ
match at all (its CVM-registry CNPJ and Bloomberg's "Smiles Fidelidade SA"
CNPJ are unrelated, likely a pre/post spin-off restructuring artifact) --
resolved by name to ticker SMLS3, which is #N/A on the last date, so this
doesn't change its status (it was already known to have left Ibovespa).

Usage:
    python -u -m src.acquisition.ibx_membership_status
"""
from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IBX_XLSX = ROOT / "ibx.xlsx"
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
INTERIM = ROOT / "data" / "interim"

CURRENT_UNIVERSE = INTERIM / "ibov_non_financial_universe.csv"
HISTORICAL_LOG = INTERIM / "ibov_historical_notes_download_log.csv"
EXTRA_UNIVERSE = INTERIM / "ibx_extra_universe.csv"
OUT_PATH = INTERIM / "ibx_current_status.csv"

# CD_CVM 23140 (SMILES S.A.): CNPJ crosswalk fails (see module docstring);
# resolved manually by name to its known ticker.
MANUAL_TICKER_OVERRIDE = {23140: ["SMLS3 BS Equity"]}


def load_ibm_members() -> pd.DataFrame:
    wb = openpyxl.load_workbook(IBX_XLSX, read_only=True, data_only=True)
    ws = wb["IBM_Members"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    ibm = pd.DataFrame(rows, columns=["ID", "Name", "CNPJ"])
    ibm["root"] = ibm["CNPJ"].astype(str).str[:10]
    return ibm


def load_last_membership_row() -> tuple[dict[str, int], list]:
    wb = openpyxl.load_workbook(IBX_XLSX, read_only=True, data_only=True)
    ws = wb["ibx_members_hist"]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    ticker_col = {t: i for i, t in enumerate(header) if i > 0}
    return ticker_col, rows[-1]


def resolve_tickers(cd: int, cnpj: str | None, ibm: pd.DataFrame) -> list[str]:
    if cd in MANUAL_TICKER_OVERRIDE:
        return MANUAL_TICKER_OVERRIDE[cd]
    if cnpj is None:
        return []
    tickers = ibm.loc[ibm["CNPJ"] == cnpj, "ID"].tolist()
    if tickers:
        return tickers
    root = str(cnpj)[:10]
    return ibm.loc[ibm["root"] == root, "ID"].tolist()


def main() -> None:
    cad = pd.read_csv(CACHE_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str)
    cad = cad.assign(CD_CVM_INT=cad["CD_CVM"].astype(int))
    cdcvm_to_cnpj = cad.drop_duplicates("CD_CVM_INT").set_index("CD_CVM_INT")["CNPJ_CIA"]

    ibm = load_ibm_members()
    ticker_col, last_row = load_last_membership_row()

    def is_current_ticker(ticker: str) -> bool:
        col = ticker_col.get(ticker)
        if col is None:
            return False
        val = last_row[col]
        return val is not None and val != "#N/A"

    current_grp = pd.read_csv(CURRENT_UNIVERSE)["CD_CVM"].astype(int)
    hist_grp = pd.read_csv(HISTORICAL_LOG)["CD_CVM"].astype(int).unique()
    extra_grp = pd.read_csv(EXTRA_UNIVERSE, dtype={"CD_CVM": str})["CD_CVM"].astype(int)
    all_cd = sorted(set(current_grp) | set(hist_grp) | set(extra_grp))

    records = []
    for cd in all_cd:
        tickers = resolve_tickers(cd, cdcvm_to_cnpj.get(cd), ibm)
        if not tickers:
            raise ValueError(f"CD_CVM {cd}: no ticker resolved in IBM_Members (add a manual override)")
        status = "atual" if any(is_current_ticker(t) for t in tickers) else "historico"
        records.append({"CD_CVM": cd, "tickers": ";".join(tickers), "status_ibx": status})

    out = pd.DataFrame(records)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    # Sanity check: every current Ibovespa constituent must be a current IBX
    # member (Ibovespa is a strict IBX subset) -- if this ever fails again,
    # a new share-class/rename case needs a manual override above.
    bad = out[out["CD_CVM"].isin(current_grp) & (out["status_ibx"] != "atual")]
    if len(bad):
        raise AssertionError(f"{len(bad)} current-Ibovespa companies resolved as non-current IBX:\n{bad}")

    print(out["status_ibx"].value_counts())
    print(f"\nWritten -> {OUT_PATH}")


if __name__ == "__main__":
    main()

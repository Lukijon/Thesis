"""Builds a company-year panel of the specific "Empréstimos e Financiamentos"
balance-sheet line (CVM's structured chart of accounts, CD_CONTA "2.01.04"
current + "2.02.01" non-current, Balanço Patrimonial Passivo -- confirmed
by direct inspection to already include debêntures as a sub-account of the
same parent line, so no separate debênture code needs to be added).

This is the same precise, item-level debt signal used in
src/analysis/assess_not_found_confidence.py (there, only for the 66
not_found cases) generalized to every company-year in the corpus, so it
can be used as a control variable candidate elsewhere.

Same consolidated-with-individual-fallback convention as
build_control_variables.py: prefer consolidated (_con), fall back to
individual (_ind) for companies that don't file consolidated statements.

Usage:
    python -u -m src.features.build_debt_line_item
"""
from __future__ import annotations

import warnings
import zipfile
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
INTERIM = ROOT / "data" / "interim"

DEBT_CODES = {"2.01.04", "2.02.01"}
YEARS = range(2015, 2025)


def _load_bpp(year: int, consolidation: str) -> pd.DataFrame | None:
    zip_path = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path) as zf:
        name = f"dfp_cia_aberta_BPP_{consolidation}_{year}.csv"
        if name not in zf.namelist():
            return None
        with zf.open(name) as f:
            df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
    sub = df[df["CD_CONTA"].isin(DEBT_CODES)].drop_duplicates(subset=["CD_CVM", "CD_CONTA"])
    sub = sub.assign(VL_CONTA=pd.to_numeric(sub["VL_CONTA"], errors="coerce"))
    return sub.groupby("CD_CVM")["VL_CONTA"].sum()


def main() -> None:
    rows = []
    for year in YEARS:
        con = _load_bpp(year, "con")
        ind = _load_bpp(year, "ind")
        codes = set()
        if con is not None:
            codes |= set(con.index)
        if ind is not None:
            codes |= set(ind.index)
        for cd_padded in codes:
            value = None
            source = None
            if con is not None and cd_padded in con.index:
                value, source = con[cd_padded], "con"
            elif ind is not None and cd_padded in ind.index:
                value, source = ind[cd_padded], "ind"
            rows.append({"cd_cvm": int(cd_padded), "fiscal_year": year, "debt_line_item": value, "fonte": source})

    out = pd.DataFrame(rows)
    out_path = INTERIM / "debt_line_item.csv"
    out.to_csv(out_path, index=False)
    print(f"{len(out)} company-years, {out['cd_cvm'].nunique()} companies, {out['fiscal_year'].nunique()} years")
    print(out["debt_line_item"].describe())
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

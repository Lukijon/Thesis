"""Extends build_debt_line_item.py's debt_line_item.csv (2015-2024 only)
to 2010-2025 -- no company filter needed here (the original script has
none either: CVM's structured BPP data is pulled for every company that
reported the account in a given year, and callers subset to their own
universe downstream), so this is purely a year-range extension.

Usage:
    python -u -m src.features.build_debt_line_item_extension
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.features.build_debt_line_item import _load_bpp

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
OUT_PATH = INTERIM / "debt_line_item_extension.csv"
YEARS = range(2010, 2026)


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
    out.to_csv(OUT_PATH, index=False)
    print(f"{len(out)} company-years, {out['cd_cvm'].nunique()} companies, {out['fiscal_year'].nunique()} years")
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()

"""Build the sample universe: non-financial, B3-listed companies with annual
DFP filings on CVM's open data portal (https://dados.cvm.gov.br), for a given
range of fiscal years.

The open-data CSVs only carry standardized numeric line items (balance
sheet, income statement, etc.) and company identifiers/filing metadata --
the free-text explanatory notes are not in them. This module builds the
list of (company, fiscal year, filing) rows that `cvm_notes.py` then uses
to fetch the full filing package and pull out the notes PDF.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from src.utils.http import get_bytes

CVM_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
CAD_URL = f"{CVM_BASE}/CAD/DADOS/cad_cia_aberta.csv"

# Sector strings in CVM's cadastral data (SETOR_ATIV) that identify financial
# and financial-adjacent companies, excluded per the thesis's non-financial
# sample scope (standard practice: capital structure and disclosure norms
# for banks/insurers/leasing/securitization firms are not comparable to
# non-financial companies).
FINANCIAL_SECTOR_KEYWORDS = [
    "banco",
    "seguradora",
    "corretora",
    "intermediacao financeira",
    "intermediação financeira",
    "arrendamento mercantil",
    "securitizacao",
    "securitização",
    "credito imobiliario",
    "crédito imobiliário",
    "bolsas de valores",
]


def _strip_accents(text: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def is_financial_sector(setor_ativ: str) -> bool:
    if not isinstance(setor_ativ, str) or not setor_ativ:
        return False
    normalized = _strip_accents(setor_ativ).lower()
    return any(_strip_accents(kw).lower() in normalized for kw in FINANCIAL_SECTOR_KEYWORDS)


def load_cadastral(cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Company registry: CNPJ, name, sector (SETOR_ATIV), status, etc."""
    raw = get_bytes(CAD_URL, cache_dir / "cad_cia_aberta.csv", force=force)
    df = pd.read_csv(io.BytesIO(raw), sep=";", encoding="latin1", dtype=str)
    return df


def load_dfp_index(year: int, cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Filing index for one fiscal year: one row per company per DFP/ITR
    document received by CVM, with a LINK_DOC pointing to the full filing.
    """
    url = f"{CVM_BASE}/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
    raw = get_bytes(url, cache_dir / f"dfp_cia_aberta_{year}.zip", force=force)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open(f"dfp_cia_aberta_{year}.csv") as f:
            df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
    df["ANO"] = year
    return df


def build_company_universe(years: list[int], cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """One row per non-financial company per fiscal year, keeping only the
    latest filed version (VERSAO) of the DFP document.
    """
    cadastral = load_cadastral(cache_dir, force=force)
    # CD_CVM isn't consistently zero-padded across CVM's own files (cadastral
    # vs. filing index), so compare as int.
    cadastral = cadastral.assign(CD_CVM_INT=cadastral["CD_CVM"].astype(int))
    non_financial_codes = set(
        cadastral.loc[~cadastral["SETOR_ATIV"].apply(is_financial_sector), "CD_CVM_INT"]
    )
    sector_by_code = cadastral.drop_duplicates("CD_CVM_INT").set_index("CD_CVM_INT")["SETOR_ATIV"]

    yearly_frames = []
    for year in years:
        index_df = load_dfp_index(year, cache_dir, force=force)
        index_df = index_df[index_df["CATEG_DOC"] == "DFP"]
        index_df = index_df.assign(CD_CVM_INT=index_df["CD_CVM"].astype(int))
        index_df = index_df[index_df["CD_CVM_INT"].isin(non_financial_codes)]
        yearly_frames.append(index_df)

    combined = pd.concat(yearly_frames, ignore_index=True)
    combined["VERSAO"] = combined["VERSAO"].astype(int)

    # Keep only the latest submitted version per company per fiscal year.
    combined = combined.sort_values("VERSAO").drop_duplicates(
        subset=["CD_CVM", "DT_REFER"], keep="last"
    )

    combined["SETOR_ATIV"] = combined["CD_CVM_INT"].map(sector_by_code)

    columns = [
        "CD_CVM",
        "CNPJ_CIA",
        "DENOM_CIA",
        "SETOR_ATIV",
        "ANO",
        "DT_REFER",
        "VERSAO",
        "ID_DOC",
        "LINK_DOC",
    ]
    return combined[columns].sort_values(["DENOM_CIA", "ANO"]).reset_index(drop=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the non-financial B3 company/fiscal-year universe from CVM open data.")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--out", type=Path, default=Path("data/interim/cvm_dfp_universe.csv"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/dfp/_cache"))
    args = parser.parse_args()

    years = list(range(args.start_year, args.end_year + 1))
    universe = build_company_universe(years, args.cache_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(args.out, index=False)
    print(f"{len(universe)} company-fiscal-year rows across {universe['CD_CVM'].nunique()} companies -> {args.out}")

"""Resolve the current Ibovespa (IBOV) composition to CVM company codes
(CD_CVM), for use as a first, high-liquidity tranche of the acquisition
sample before scaling to the full non-financial B3 universe.

Two public B3 endpoints (undocumented but stable, widely used by the
Brazilian fintech/data community) are combined:
  - GetPortfolioDay: current IBOV constituents (ticker, short name, weight)
  - GetInitialCompanies: full listed-company registry, which conveniently
    carries `codeCVM` directly -- the same identifier as CVM's CD_CVM -- so
    no fuzzy name matching is needed, just a ticker -> issuer-code lookup
    (a ticker's issuer code is its alphabetic prefix, e.g. "PETR4" -> "PETR").

Note this reflects *today's* IBOV membership, not the historical
composition in each fiscal year of the 2015-2024 sample window -- it's a
convenience slice for staging the download, not a survivorship-bias-free
index reconstruction. That distinction belongs in the analysis stage, not
here.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pandas as pd

from src.acquisition.cvm_dfp import is_financial_sector, load_cadastral
from src.utils.http import get_bytes

B3_BASE = "https://sistemaswebb3-listados.b3.com.br"


def _encode(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


def fetch_ibov_composition(cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Current IBOV constituents: ticker (cod), short name (asset), weight (part)."""
    payload = _encode({"language": "pt-br", "pageNumber": 1, "pageSize": 120, "index": "IBOV", "segment": "1"})
    url = f"{B3_BASE}/indexProxy/indexCall/GetPortfolioDay/{payload}"
    raw = get_bytes(url, cache_dir / "ibov_portfolio.json", force=force)
    data = json.loads(raw)
    return pd.DataFrame(data["results"])[["cod", "asset", "part"]]


def fetch_b3_company_registry(cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Every company listed on B3, with its issuer code, CD_CVM, and CNPJ."""
    cache_path = cache_dir / "b3_listed_companies.json"
    if cache_path.exists() and not force:
        records = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        records = []
        page = 1
        while True:
            payload = _encode({"language": "pt-br", "pageNumber": page, "pageSize": 100})
            url = f"{B3_BASE}/listedCompaniesProxy/CompanyCall/GetInitialCompanies/{payload}"
            data = json.loads(get_bytes(url, timeout=60))
            records.extend(data["results"])
            if page >= data["page"]["totalPages"]:
                break
            page += 1
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    return pd.DataFrame(records)[["issuingCompany", "codeCVM", "cnpj", "companyName"]]


def build_ibov_non_financial_universe(cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Non-financial companies currently in the IBOV, resolved to CD_CVM.

    Columns: COD (ticker), ASSET (B3 short name), CD_CVM, DENOM_CIA, SETOR_ATIV.
    """
    ibov = fetch_ibov_composition(cache_dir, force=force)
    registry = fetch_b3_company_registry(cache_dir, force=force)

    ibov = ibov.assign(issuer_code=ibov["cod"].str.replace(r"\d+$", "", regex=True))
    merged = ibov.merge(registry, left_on="issuer_code", right_on="issuingCompany", how="left")

    unmatched = merged[merged["codeCVM"].isna()]
    if len(unmatched):
        raise ValueError(f"Could not resolve CD_CVM for tickers: {unmatched['cod'].tolist()}")

    merged["CD_CVM"] = merged["codeCVM"].astype(int)
    merged = merged.drop_duplicates("CD_CVM")

    cadastral = load_cadastral(cache_dir, force=force)
    cadastral = cadastral.assign(CD_CVM_INT=cadastral["CD_CVM"].astype(int))
    sector_by_code = cadastral.drop_duplicates("CD_CVM_INT").set_index("CD_CVM_INT")["SETOR_ATIV"]
    merged["SETOR_ATIV"] = merged["CD_CVM"].map(sector_by_code)

    non_financial = merged[~merged["SETOR_ATIV"].apply(is_financial_sector)]

    result = non_financial.rename(columns={"cod": "COD", "asset": "ASSET", "companyName": "DENOM_CIA"})
    return result[["COD", "ASSET", "CD_CVM", "DENOM_CIA", "SETOR_ATIV"]].sort_values("DENOM_CIA").reset_index(drop=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Resolve current IBOV non-financial constituents to CD_CVM.")
    parser.add_argument("--out", type=Path, default=Path("data/interim/ibov_non_financial_universe.csv"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/dfp/_cache"))
    args = parser.parse_args()

    universe = build_ibov_non_financial_universe(args.cache_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(args.out, index=False)
    print(f"{len(universe)} non-financial IBOV companies -> {args.out}")

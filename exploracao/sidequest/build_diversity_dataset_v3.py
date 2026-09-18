"""v3: broadens the outcome side per the explicit ask that a real result
matters more here than another confirmed null. Adds:
  - Market-to-book ratio (a Tobin's Q proxy: market cap / book equity),
    using year-end share price x total shares outstanding
    (fre_cia_aberta_capital_social_*.csv, already downloaded) against
    book equity (already in control_variables.csv / the v2 extension).
    Not tried before this pass.
  - ROA, ROE, and trailing 12-month stock return as additional outcomes
    -- all already computed for the main thesis's control_variables.csv,
    just not yet merged into the diversity analysis. Race-diversity
    against performance specifically is still an open gap per the
    literature verification (only gender-diversity-vs-performance is
    already published for Brazil) -- cost of debt and volatility don't
    exhaust the outcome space the novelty claim covers.
  - A coarse sector bucket (from CVM's cadastral SETOR_ATIV field,
    collapsed from 33 raw categories -- too fragmented for 111 companies
    to use as full dummies -- into ~9 broad groups) as an additional
    control/robustness dimension, motivated directly by v2's finding that
    the workforce-leadership-gender result wasn't explained by size and
    was flagged as plausibly sector-driven but untested.

Usage:
    python -m sidequest.build_diversity_dataset_v3
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
INTERIM = ROOT / "data" / "interim"
OUT_DIR = ROOT / "sidequest"

DIVERSITY_YEARS = [2023, 2024, 2025, 2026]

SECTOR_GROUPS = {
    "Utilities/Energy": ["energia el", "saneamento", "gás", "petróleo"],
    "Commerce/Retail": ["comércio"],
    "Construction/RealEstate": ["construção", "imobiliári"],
    "Industrials/Materials": ["metalurgia", "siderurgia", "extração mineral", "papel e celulose", "máquinas", "químicos"],
    "Consumer/Textile/Food": ["têxtil", "agricultura", "alimentos", "bebidas", "fumo"],
    "Healthcare/Pharma": ["serviços médicos", "farmacêutico"],
    "TransportLogistics": ["transporte", "logística"],
    "TechTelecom": ["comunicação", "telecomunicações", "informática"],
}


def _sector_group(setor: str) -> str:
    if not isinstance(setor, str):
        return "Other"
    s = setor.lower()
    for group, keywords in SECTOR_GROUPS.items():
        if any(kw in s for kw in keywords):
            return group
    return "Other"


def build_sector_map(universe: set[int]) -> pd.DataFrame:
    cad = pd.read_csv(CACHE_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str)
    cad["CD_CVM"] = pd.to_numeric(cad["CD_CVM"], errors="coerce")
    sub = cad[cad["CD_CVM"].isin(universe)][["CD_CVM", "SETOR_ATIV", "CNPJ_CIA"]].drop_duplicates("CD_CVM")
    sub["sector_group"] = sub["SETOR_ATIV"].apply(_sector_group)
    return sub


def build_market_to_book(universe: set[int], cnpj_map: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    prices = prices.set_index("date").sort_index()
    for c in prices.columns:
        prices[c] = pd.to_numeric(prices[c], errors="coerce")

    from src.analysis.compute_abnormal_returns import build_ticker_map
    ticker_map = build_ticker_map().rename(columns={"CD_CVM": "CD_CVM"})

    rows = []
    for year in years:
        zip_path = CACHE_DIR / f"fre_cia_aberta_{year}.zip"
        if not zip_path.exists():
            continue
        z = zipfile.ZipFile(zip_path)
        fname = f"fre_cia_aberta_capital_social_{year}.csv"
        if fname not in z.namelist():
            continue
        cap = pd.read_csv(z.open(fname), sep=";", encoding="latin1")
        cap = cap[cap["Tipo_Capital"] == "Capital Subscrito"]
        cap = cap.merge(cnpj_map[["CD_CVM", "CNPJ_CIA"]], left_on="CNPJ_Companhia", right_on="CNPJ_CIA")
        cap["total_shares"] = cap["Quantidade_Acoes_Ordinarias"].fillna(0) + cap["Quantidade_Acoes_Preferenciais"].fillna(0)
        cap = cap[cap["total_shares"] > 0].drop_duplicates("CD_CVM")

        window = prices.loc[:f"{year}-12-31"].dropna(how="all")
        year_end = window.iloc[-1] if len(window) else None
        if year_end is None:
            continue

        for _, row in cap.iterrows():
            tmap = ticker_map[ticker_map["CD_CVM"] == row["CD_CVM"]]
            if tmap.empty:
                continue
            col = f"{tmap.iloc[0]['ticker']} BS Equity"
            if col not in year_end.index or pd.isna(year_end[col]):
                continue
            rows.append({
                "CD_CVM": row["CD_CVM"], "year": year,
                "market_cap": year_end[col] * row["total_shares"],
                "total_shares": row["total_shares"],
                "share_price_year_end": year_end[col],
            })
    return pd.DataFrame(rows)


def main() -> None:
    universe = set(pd.read_csv(INTERIM / "poc" / "delisted_similarity_results.csv")["cd_cvm"].unique())

    base = pd.read_csv(OUT_DIR / "diversity_analysis_dataset_v2.csv")
    cnpj_map = pd.read_csv(CACHE_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str)
    cnpj_map["CD_CVM"] = pd.to_numeric(cnpj_map["CD_CVM"], errors="coerce")
    cnpj_map = cnpj_map[cnpj_map["CD_CVM"].isin(universe)][["CD_CVM", "CNPJ_CIA"]].drop_duplicates("CD_CVM")

    print("Sector groups...")
    sectors = build_sector_map(universe)
    print(sectors["sector_group"].value_counts())

    print("\nMarket-to-book (Tobin's Q proxy)...")
    mtb = build_market_to_book(universe, cnpj_map, DIVERSITY_YEARS)
    print(f"  {len(mtb)} company-years with computable market cap")

    print("\nROA/ROE/past return...")
    ctrl = pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"fiscal_year": "year"})
    ctrl_2024_25 = pd.DataFrame()
    try:
        from sidequest.build_diversity_dataset_v2 import extend_control_variables
        ctrl_2024_25 = extend_control_variables(universe, [2024, 2025])
        ctrl_2024_25["roe"] = ctrl_2024_25["net_income"] / ctrl_2024_25["total_equity"]
        ctrl_2024_25 = ctrl_2024_25.rename(columns={"fiscal_year": "year"})
    except Exception as exc:
        print("  could not extend controls:", exc)

    perf_cols = ["CD_CVM", "year", "roa", "roe", "past_12m_return"]
    perf = pd.concat([ctrl[perf_cols], ctrl_2024_25[[c for c in perf_cols if c in ctrl_2024_25.columns]]], ignore_index=True)
    perf = perf.drop_duplicates(subset=["CD_CVM", "year"], keep="last")

    full = base.drop(columns=["roa"], errors="ignore")
    full = full.merge(sectors[["CD_CVM", "sector_group"]], on="CD_CVM", how="left")
    full = full.merge(mtb[["CD_CVM", "year", "market_cap"]], on=["CD_CVM", "year"], how="left")
    full = full.merge(perf, on=["CD_CVM", "year"], how="left")

    book_equity = ctrl.rename(columns={"fiscal_year": "year"})[["CD_CVM", "year", "total_equity"]]
    book_equity_ext = ctrl_2024_25[["CD_CVM", "year", "total_equity"]] if "total_equity" in ctrl_2024_25.columns else pd.DataFrame()
    book_equity_all = pd.concat([book_equity, book_equity_ext], ignore_index=True).drop_duplicates(subset=["CD_CVM", "year"], keep="last")
    full = full.merge(book_equity_all, on=["CD_CVM", "year"], how="left")
    full["market_to_book"] = full["market_cap"] / full["total_equity"]
    full.loc[full["total_equity"] <= 0, "market_to_book"] = np.nan  # negative book equity makes the ratio uninterpretable

    out_path = OUT_DIR / "diversity_analysis_dataset_v3.csv"
    full.to_csv(out_path, index=False)
    print(f"\n{len(full)} rows written to {out_path}")
    for col in ["market_to_book", "roa", "roe", "past_12m_return"]:
        print(f"  {col}: {full[col].notna().sum()} non-missing")


if __name__ == "__main__":
    main()

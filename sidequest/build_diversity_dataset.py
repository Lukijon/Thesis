"""Builds the sidequest analysis dataset: board gender/racial diversity
(CVM Resolucao 59/2021 mandatory disclosure, FRE item 7.1, only exists for
FY2022 fiscal-year filings onward -- confirmed empirically, not assumed:
fre_cia_aberta_2022.zip has no declaracao_genero/raca file, 2023 does) for
our existing 111-company universe, paired with two outcome variables not
yet tested in the Brazilian literature for this data (per the literature
scan in sidequest/README.md): a cost-of-debt proxy (despesas financeiras /
passivo total, DRE account 3.06.02, extracted the same way
src/features/build_control_variables.py already does for other DFP line
items) and realized stock-return volatility (annualized std of daily
returns, computed from the price data already on disk).

Zero new downloads: reuses the FRE zips already cached from the Risk
Factors acquisition (data/raw/dfp/_cache/fre_cia_aberta_{2023,2024}.zip)
and the DFP zips already cached from the original debt-note acquisition.

Usage:
    python -m sidequest.build_diversity_dataset   (run from repo root)
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

DIVERSITY_YEARS = [2023, 2024]
COD_ADMIN_CONSELHO = "Conselho de Administração - Efetivos"
COD_ADMIN_DIRETORIA = "Diretoria"


def build_cnpj_map(universe: set[int]) -> pd.DataFrame:
    cad = pd.read_csv(CACHE_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str)
    cad["CD_CVM"] = pd.to_numeric(cad["CD_CVM"], errors="coerce")
    return cad[cad["CD_CVM"].isin(universe)][["CD_CVM", "CNPJ_CIA"]].drop_duplicates()


def _board_pct(df: pd.DataFrame, cols: list[str], numer_cols: list[str], org: str) -> pd.DataFrame:
    sub = df[df["Orgao_Administracao"] == org].copy()
    sub["total"] = sub[cols].sum(axis=1)
    sub["pct"] = sub[numer_cols].sum(axis=1) / sub["total"]
    return sub[["CD_CVM", "total", "pct"]]


def build_diversity_panel(universe: set[int]) -> pd.DataFrame:
    cnpj_map = build_cnpj_map(universe)
    gender_cols = ["Quantidade_Feminino", "Quantidade_Masculino", "Quantidade_Nao_Binario", "Quantidade_Outros"]
    race_cols = ["Quantidade_Amarelo", "Quantidade_Branco", "Quantidade_Preto", "Quantidade_Pardo", "Quantidade_Indigena", "Quantidade_Outros"]

    rows = []
    for year in DIVERSITY_YEARS:
        z = zipfile.ZipFile(CACHE_DIR / f"fre_cia_aberta_{year}.zip")
        g = pd.read_csv(z.open(f"fre_cia_aberta_administrador_declaracao_genero_{year}.csv"), sep=";", encoding="latin1")
        r = pd.read_csv(z.open(f"fre_cia_aberta_administrador_declaracao_raca_{year}.csv"), sep=";", encoding="latin1")
        g = g.merge(cnpj_map, left_on="CNPJ_Companhia", right_on="CNPJ_CIA")
        r = r.merge(cnpj_map, left_on="CNPJ_Companhia", right_on="CNPJ_CIA")

        board_g = _board_pct(g, gender_cols, ["Quantidade_Feminino"], COD_ADMIN_CONSELHO).rename(columns={"total": "board_size", "pct": "pct_female_board"})
        board_r = _board_pct(r, race_cols, ["Quantidade_Preto", "Quantidade_Pardo"], COD_ADMIN_CONSELHO).rename(columns={"total": "board_size_r", "pct": "pct_black_brown_board"})
        exec_g = _board_pct(g, gender_cols, ["Quantidade_Feminino"], COD_ADMIN_DIRETORIA).rename(columns={"total": "exec_size", "pct": "pct_female_exec"})
        exec_r = _board_pct(r, race_cols, ["Quantidade_Preto", "Quantidade_Pardo"], COD_ADMIN_DIRETORIA).rename(columns={"total": "exec_size_r", "pct": "pct_black_brown_exec"})

        m = board_g.merge(board_r[["CD_CVM", "pct_black_brown_board"]], on="CD_CVM", how="outer")
        m = m.merge(exec_g[["CD_CVM", "exec_size", "pct_female_exec"]], on="CD_CVM", how="outer")
        m = m.merge(exec_r[["CD_CVM", "pct_black_brown_exec"]], on="CD_CVM", how="outer")
        m["year"] = year
        rows.append(m)

    panel = pd.concat(rows, ignore_index=True)
    panel = panel[panel["board_size"].fillna(0) > 0].reset_index(drop=True)
    panel["has_black_brown_board"] = (panel["pct_black_brown_board"] > 0).astype(int)
    panel["has_black_brown_exec"] = (panel["pct_black_brown_exec"].fillna(0) > 0).astype(int)
    return panel


def build_cost_of_debt(universe: set[int], years: list[int]) -> pd.DataFrame:
    """despesas_financeiras (DRE 3.06.02) / total_liabilities (already in
    control_variables.csv), by fiscal year. Mirrors
    src/features/build_control_variables.py's extraction pattern exactly."""
    ctrl = pd.read_csv(INTERIM / "control_variables.csv")
    rows = []
    for year in years:
        zip_path = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
        zf = zipfile.ZipFile(zip_path)
        frames = []
        for consolidation in ["con", "ind"]:
            name = f"dfp_cia_aberta_DRE_{consolidation}_{year}.csv"
            if name not in zf.namelist():
                continue
            df = pd.read_csv(zf.open(name), sep=";", encoding="latin1", dtype=str)
            df["CD_CVM_INT"] = df["CD_CVM"].astype(int)
            last_tag = [v for v in df["ORDEM_EXERC"].unique() if isinstance(v, str) and "LTIMO" in v and "PEN" not in v][0]
            df = df[df["ORDEM_EXERC"] == last_tag]
            df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
            df = df[df["CD_CVM_INT"].isin(universe) & (df["CD_CONTA"] == "3.06.02")]
            frames.append(df[["CD_CVM_INT", "VL_CONTA", "DS_CONTA"]].assign(consolidation=consolidation))
        if not frames:
            continue
        combined = pd.concat(frames)
        # prefer consolidated, fall back to individual, per company
        combined = combined.sort_values("consolidation", ascending=False).drop_duplicates("CD_CVM_INT", keep="first")
        combined = combined.rename(columns={"CD_CVM_INT": "CD_CVM", "VL_CONTA": "despesas_financeiras"})
        combined["fiscal_year"] = year
        rows.append(combined[["CD_CVM", "fiscal_year", "despesas_financeiras"]])

    fin = pd.concat(rows, ignore_index=True)
    fin["despesas_financeiras"] = fin["despesas_financeiras"].abs()  # DRE stores expenses as negative
    merged = fin.merge(ctrl[["CD_CVM", "fiscal_year", "total_liabilities"]], on=["CD_CVM", "fiscal_year"], how="left")
    merged["cost_of_debt_proxy"] = merged["despesas_financeiras"] / merged["total_liabilities"]
    return merged


def build_volatility(universe_tickers: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    prices = prices.set_index("date").sort_index()
    for c in prices.columns:
        prices[c] = pd.to_numeric(prices[c], errors="coerce")
    rets = prices.pct_change(fill_method=None)

    rows = []
    for _, row in universe_tickers.iterrows():
        col = f"{row['ticker']} BS Equity"
        if col not in rets.columns:
            continue
        for year in years:
            window = rets.loc[f"{year}-01-01":f"{year}-12-31", col].dropna()
            if len(window) < 100:
                continue
            rows.append({
                "CD_CVM": row["CD_CVM"], "fiscal_year": year,
                "return_volatility": window.std() * np.sqrt(252),
                "n_trading_days": len(window),
            })
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    universe = set(pd.read_csv(INTERIM / "poc" / "delisted_similarity_results.csv")["cd_cvm"].unique())

    print("Building diversity panel...")
    diversity = build_diversity_panel(universe)
    print(f"  {len(diversity)} company-years, {diversity['CD_CVM'].nunique()} companies")

    print("Building cost-of-debt proxy...")
    cod = build_cost_of_debt(universe, DIVERSITY_YEARS)
    print(f"  {cod['cost_of_debt_proxy'].notna().sum()} company-years with a computable proxy")

    print("Building return volatility...")
    from src.analysis.compute_abnormal_returns import build_ticker_map
    ticker_map = build_ticker_map()
    vol = build_volatility(ticker_map, DIVERSITY_YEARS)
    print(f"  {len(vol)} company-years with computable volatility")

    ctrl = pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"fiscal_year": "year"})

    full = diversity.merge(cod.rename(columns={"fiscal_year": "year"})[["CD_CVM", "year", "despesas_financeiras", "cost_of_debt_proxy"]], on=["CD_CVM", "year"], how="left")
    full = full.merge(vol.rename(columns={"fiscal_year": "year"})[["CD_CVM", "year", "return_volatility"]], on=["CD_CVM", "year"], how="left")
    full = full.merge(ctrl[["CD_CVM", "year", "ln_total_assets", "leverage", "roa", "past_12m_return"]], on=["CD_CVM", "year"], how="left")

    out_path = OUT_DIR / "diversity_analysis_dataset.csv"
    full.to_csv(out_path, index=False)
    print(f"\n{len(full)} rows written to {out_path}")
    print(f"  cost_of_debt_proxy available: {full['cost_of_debt_proxy'].notna().sum()}")
    print(f"  return_volatility available: {full['return_volatility'].notna().sum()}")
    print(f"  full controls available: {full[['ln_total_assets','leverage','roa']].notna().all(axis=1).sum()}")


if __name__ == "__main__":
    main()

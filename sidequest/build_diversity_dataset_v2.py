"""Extended version of build_diversity_dataset.py, per the extension plan
in extension_plan.md:
  1. Panel extended 2023-2026 (confirmed available on CVM's portal directly,
     not assumed -- fre_cia_aberta_2025.zip and 2026.zip both exist and
     both carry the same gender/race declaration fields as 2023-2024).
  2. Workforce-leadership diversity added (fre_cia_aberta_empregado_posicao_
     declaracao_{genero,raca}_*.csv, split by Posicao = Lideranca /
     Nao-lideranca) -- hundreds of employees per company vs. the board's
     ~7-person count, so far less zero-inflated.
  3. Cost-of-debt proxy: still despesas_financeiras / total_liabilities
     (DRE 3.06.02, same as v1). The planned refinement (dividing by actual
     structured debt from fre_cia_aberta_obrigacao_*.csv instead of total
     liabilities) turned out NOT to be usable across the full window --
     checked directly, that file and its endividamento sibling only exist
     in the 2023 FRE export, not 2024-2026. Kept the DRE-based proxy for
     consistency across all 4 years rather than mixing methods.
  4. Financial controls extended to fiscal year 2025 (confirmed
     dfp_cia_aberta_2025.zip exists on CVM's portal) via a sidequest-local
     re-run of the same extraction control_variables.csv uses -- the main
     thesis's own data/interim/control_variables.csv is NOT touched, per
     "keep it in the separate folder."

Zero new downloads beyond the one dfp_cia_aberta_2025.zip fetch (needed to
extend controls to match the 2025/2026 diversity snapshots) -- everything
else reuses zips already cached from the Risk Factors and original
debt-note acquisitions.

Usage:
    python -m sidequest.build_diversity_dataset_v2   (run from repo root)
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
FINANCIAL_YEARS_NEEDED = [2024, 2025]  # 2015-2023 already in control_variables.csv
COD_ADMIN_CONSELHO = "Conselho de Administração - Efetivos"
COD_ADMIN_DIRETORIA = "Diretoria"


def build_cnpj_map(universe: set[int]) -> pd.DataFrame:
    cad = pd.read_csv(CACHE_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str)
    cad["CD_CVM"] = pd.to_numeric(cad["CD_CVM"], errors="coerce")
    return cad[cad["CD_CVM"].isin(universe)][["CD_CVM", "CNPJ_CIA"]].drop_duplicates()


def _pct(df: pd.DataFrame, filter_col: str, filter_val: str, cols: list[str], numer_cols: list[str]) -> pd.DataFrame:
    sub = df[df[filter_col] == filter_val].copy()
    sub["total"] = sub[cols].sum(axis=1)
    sub["pct"] = sub[numer_cols].sum(axis=1) / sub["total"]
    return sub[["CD_CVM", "total", "pct"]]


def build_board_diversity(universe: set[int]) -> pd.DataFrame:
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

        board_g = _pct(g, "Orgao_Administracao", COD_ADMIN_CONSELHO, gender_cols, ["Quantidade_Feminino"]).rename(columns={"total": "board_size", "pct": "pct_female_board"})
        board_r = _pct(r, "Orgao_Administracao", COD_ADMIN_CONSELHO, race_cols, ["Quantidade_Preto", "Quantidade_Pardo"]).rename(columns={"total": "board_size_r", "pct": "pct_black_brown_board"})
        exec_g = _pct(g, "Orgao_Administracao", COD_ADMIN_DIRETORIA, gender_cols, ["Quantidade_Feminino"]).rename(columns={"total": "exec_size", "pct": "pct_female_exec"})
        exec_r = _pct(r, "Orgao_Administracao", COD_ADMIN_DIRETORIA, race_cols, ["Quantidade_Preto", "Quantidade_Pardo"]).rename(columns={"total": "exec_size_r", "pct": "pct_black_brown_exec"})

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


def build_leadership_diversity(universe: set[int]) -> pd.DataFrame:
    """Workforce-wide leadership ('Lideranca') racial/gender composition --
    a much larger-N complement to the tiny board-level counts."""
    cnpj_map = build_cnpj_map(universe)
    gender_cols = ["Quantidade_Feminino", "Quantidade_Masculino", "Quantidade_Nao_Binario", "Quantidade_Outros", "Quantidade_Sem_Resposta"]
    race_cols = ["Quantidade_Amarelo", "Quantidade_Branco", "Quantidade_Preto", "Quantidade_Pardo", "Quantidade_Indigena", "Quantidade_Outros", "Quantidade_Sem_Resposta"]

    rows = []
    for year in DIVERSITY_YEARS:
        z = zipfile.ZipFile(CACHE_DIR / f"fre_cia_aberta_{year}.zip")
        g = pd.read_csv(z.open(f"fre_cia_aberta_empregado_posicao_declaracao_genero_{year}.csv"), sep=";", encoding="latin1")
        r = pd.read_csv(z.open(f"fre_cia_aberta_empregado_posicao_declaracao_raca_{year}.csv"), sep=";", encoding="latin1")
        g = g.merge(cnpj_map, left_on="CNPJ_Companhia", right_on="CNPJ_CIA")
        r = r.merge(cnpj_map, left_on="CNPJ_Companhia", right_on="CNPJ_CIA")

        lead_g = _pct(g, "Posicao", "Liderança", gender_cols, ["Quantidade_Feminino"]).rename(columns={"total": "leadership_n", "pct": "pct_female_leadership"})
        lead_r = _pct(r, "Posicao", "Liderança", race_cols, ["Quantidade_Preto", "Quantidade_Pardo"]).rename(columns={"total": "leadership_n_r", "pct": "pct_black_brown_leadership"})

        m = lead_g.merge(lead_r[["CD_CVM", "pct_black_brown_leadership"]], on="CD_CVM", how="outer")
        m["year"] = year
        rows.append(m)

    panel = pd.concat(rows, ignore_index=True)
    return panel[panel["leadership_n"].fillna(0) > 0].reset_index(drop=True)


def extend_control_variables(universe: set[int], years: list[int]) -> pd.DataFrame:
    """Sidequest-local re-run of control_variables.csv's DFP extraction for
    years not yet in the main thesis's file. Does NOT touch
    data/interim/control_variables.csv."""
    ACCOUNTS = {
        "BPA": {"1": "total_assets"},
        "BPP": {"2.01": "current_liabilities", "2.02": "noncurrent_liabilities", "2.03": "total_equity"},
        "DRE": {"3.01": "net_revenue", "3.11": "net_income", "3.06.02": "despesas_financeiras"},
    }

    def last_period_tag(series):
        cands = [v for v in series.unique() if isinstance(v, str) and "LTIMO" in v and "PEN" not in v]
        return cands[0]

    def load_statement(zf, year, statement, consolidation):
        name = f"dfp_cia_aberta_{statement}_{consolidation}_{year}.csv"
        if name not in zf.namelist():
            return None
        df = pd.read_csv(zf.open(name), sep=";", encoding="latin1", dtype=str)
        df["CD_CVM_INT"] = df["CD_CVM"].astype(int)
        df = df[df["ORDEM_EXERC"] == last_period_tag(df["ORDEM_EXERC"])]
        df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
        return df

    rows = []
    for year in years:
        zip_path = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
        if not zip_path.exists():
            continue
        zf = zipfile.ZipFile(zip_path)
        pivots = {}
        for statement, amap in ACCOUNTS.items():
            for consolidation in ["con", "ind"]:
                df = load_statement(zf, year, statement, consolidation)
                if df is None:
                    continue
                df = df[df["CD_CVM_INT"].isin(universe) & df["CD_CONTA"].isin(amap)]
                piv = df.pivot_table(index="CD_CVM_INT", columns="CD_CONTA", values="VL_CONTA", aggfunc="first").rename(columns=amap)
                key = (statement, consolidation)
                pivots[key] = piv
        merged = None
        for consolidation in ["con", "ind"]:
            parts = [pivots[(s, consolidation)] for s in ACCOUNTS if (s, consolidation) in pivots]
            if not parts:
                continue
            combined = parts[0]
            for p in parts[1:]:
                combined = combined.combine_first(p)
            merged = combined if merged is None else merged.combine_first(combined)
        if merged is None:
            continue
        merged["fiscal_year"] = year
        merged = merged.reset_index().rename(columns={"CD_CVM_INT": "CD_CVM"})
        rows.append(merged)

    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if len(out):
        out["total_liabilities"] = out[["current_liabilities", "noncurrent_liabilities"]].sum(axis=1, min_count=1)
        out["ln_total_assets"] = np.log(out["total_assets"].where(out["total_assets"] > 0))
        out["leverage"] = out["total_liabilities"] / out["total_assets"]
        out["roa"] = out["net_income"] / out["total_assets"]
        out["cost_of_debt_proxy"] = out["despesas_financeiras"].abs() / out["total_liabilities"]
    return out


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
            if len(window) < 50:
                continue
            rows.append({"CD_CVM": row["CD_CVM"], "year": year, "return_volatility": window.std() * np.sqrt(252), "n_trading_days": len(window)})
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    universe = set(pd.read_csv(INTERIM / "poc" / "delisted_similarity_results.csv")["cd_cvm"].unique())

    print("Board diversity, 2023-2026...")
    board = build_board_diversity(universe)
    print(f"  {len(board)} company-years, {board['CD_CVM'].nunique()} companies")

    print("Leadership (workforce) diversity, 2023-2026...")
    leadership = build_leadership_diversity(universe)
    print(f"  {len(leadership)} company-years, {leadership['CD_CVM'].nunique()} companies, "
          f"median leadership headcount={leadership['leadership_n'].median():.0f}")

    print("Extending financial controls to FY2024-2025 (sidequest-local, main control_variables.csv untouched)...")
    ctrl_base = pd.read_csv(INTERIM / "control_variables.csv")[["CD_CVM", "fiscal_year", "total_liabilities", "ln_total_assets", "leverage", "roa"]]
    ctrl_ext = extend_control_variables(universe, FINANCIAL_YEARS_NEEDED)
    ctrl_ext_slim = ctrl_ext[["CD_CVM", "fiscal_year", "total_liabilities", "ln_total_assets", "leverage", "roa", "cost_of_debt_proxy"]] if len(ctrl_ext) else pd.DataFrame()

    cod_base_zip = zipfile.ZipFile(CACHE_DIR / "dfp_cia_aberta_2023.zip")  # reuse to get 2023 despesas_financeiras cheaply too, for a consistent cost_of_debt series
    ctrl_2023plus = extend_control_variables(universe, [2023] + FINANCIAL_YEARS_NEEDED)
    cost_of_debt_all = ctrl_2023plus[["CD_CVM", "fiscal_year", "cost_of_debt_proxy"]].rename(columns={"fiscal_year": "year"})

    controls_all = pd.concat([ctrl_base, ctrl_ext_slim], ignore_index=True).drop_duplicates(subset=["CD_CVM", "fiscal_year"], keep="last")
    controls_all = controls_all.rename(columns={"fiscal_year": "year"})

    print("Return volatility, 2023-2026...")
    from src.analysis.compute_abnormal_returns import build_ticker_map
    ticker_map = build_ticker_map()
    vol = build_volatility(ticker_map, DIVERSITY_YEARS)
    print(f"  {len(vol)} company-years with computable volatility")

    full = board.merge(leadership, on=["CD_CVM", "year"], how="left")
    full = full.merge(cost_of_debt_all, on=["CD_CVM", "year"], how="left")
    full = full.merge(vol[["CD_CVM", "year", "return_volatility"]], on=["CD_CVM", "year"], how="left")
    full = full.merge(controls_all[["CD_CVM", "year", "ln_total_assets", "leverage", "roa"]], on=["CD_CVM", "year"], how="left")

    out_path = OUT_DIR / "diversity_analysis_dataset_v2.csv"
    full.to_csv(out_path, index=False)
    print(f"\n{len(full)} rows written to {out_path}")
    print(full.groupby("year").agg(
        n=("CD_CVM", "count"),
        pct_female_board=("pct_female_board", "mean"),
        pct_black_brown_board=("pct_black_brown_board", "mean"),
        pct_black_brown_leadership=("pct_black_brown_leadership", "mean"),
        cost_of_debt=("cost_of_debt_proxy", "count"),
        volatility=("return_volatility", "count"),
    ).round(3))


if __name__ == "__main__":
    main()

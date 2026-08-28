"""Control variables for H1's regression, derived from CVM's *structured*
DFP data -- not the free-text notes. Each annual `dfp_cia_aberta_{year}.zip`
(already cached locally for the note-acquisition pipeline, no new downloads
needed here) bundles per-statement CSVs of standardized numeric line items
alongside the filing index: balance sheet (BPA/BPP), income statement (DRE).
Confirmed by direct inspection of the CVM chart of accounts, not assumed:

    BPA  CD_CONTA "1"     Ativo Total                      (total assets)
    BPP  CD_CONTA "2.01"  Passivo Circulante                (current liabilities)
    BPP  CD_CONTA "2.02"  Passivo Não Circulante            (non-current liabilities)
    BPP  CD_CONTA "2.03"  Patrimônio Líquido Consolidado    (total equity)
    DRE  CD_CONTA "3.01"  Receita de Venda de Bens/Serviços (net revenue)
    DRE  CD_CONTA "3.11"  Lucro/Prejuízo Consolidado         (net income)

Consolidated statements (_con) are used when available (standard practice
for groups with subsidiaries); individual (_ind) is the fallback for
companies that don't file consolidated statements at all.

Derived variables (see TODO.md's control-variable list):
    size        = ln(total assets), ln(net revenue)
    leverage    = (current + non-current liabilities) / total assets
    profitability = net income / total assets (ROA), net income / equity (ROE)
    past_return = trailing 12-month stock return as of fiscal year-end
                  (from the Bloomberg price export already on disk)

Usage:
    python -m src.features.build_control_variables
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path("data/raw/dfp/_cache")
MARKET = Path("data/raw/market/prices")
OUT_PATH = Path("data/interim/control_variables.csv")
YEARS = list(range(2015, 2025))

ACCOUNTS = {
    "BPA": {"1": "total_assets"},
    "BPP": {"2.01": "current_liabilities", "2.02": "noncurrent_liabilities", "2.03": "total_equity"},
    "DRE": {"3.01": "net_revenue", "3.11": "net_income"},
}


def _last_period_tag(series: pd.Series) -> str:
    """ORDEM_EXERC's "ÚLTIMO"/"PENÚLTIMO" values decode with a mangled
    accented character from CVM's source encoding -- match on the
    accent-independent substring instead of the literal string.
    """
    candidates = [v for v in series.unique() if isinstance(v, str) and "LTIMO" in v and "PEN" not in v]
    if not candidates:
        raise ValueError(f"no ÚLTIMO-equivalent tag found in {series.unique()}")
    return candidates[0]


def _load_statement(zf: zipfile.ZipFile, year: int, statement: str, consolidation: str) -> pd.DataFrame | None:
    name = f"dfp_cia_aberta_{statement}_{consolidation}_{year}.csv"
    if name not in zf.namelist():
        return None
    with zf.open(name) as f:
        df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
    df["CD_CVM_INT"] = df["CD_CVM"].astype(int)
    last_tag = _last_period_tag(df["ORDEM_EXERC"])
    df = df[df["ORDEM_EXERC"] == last_tag]
    df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
    return df


def _extract_accounts(df: pd.DataFrame, account_map: dict[str, str], cd_cvm_filter: set[int]) -> pd.DataFrame:
    df = df[df["CD_CVM_INT"].isin(cd_cvm_filter) & df["CD_CONTA"].isin(account_map)]
    pivoted = df.pivot_table(index="CD_CVM_INT", columns="CD_CONTA", values="VL_CONTA", aggfunc="first")
    return pivoted.rename(columns=account_map)


def build_year(year: int, cd_cvm_filter: set[int]) -> pd.DataFrame:
    zip_path = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
    if not zip_path.exists():
        return pd.DataFrame()

    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        for statement, account_map in ACCOUNTS.items():
            con = _load_statement(zf, year, statement, "con")
            ind = _load_statement(zf, year, statement, "ind")
            extracted_con = _extract_accounts(con, account_map, cd_cvm_filter) if con is not None else pd.DataFrame()
            extracted_ind = _extract_accounts(ind, account_map, cd_cvm_filter) if ind is not None else pd.DataFrame()
            # Prefer consolidated; fill gaps (companies with no subsidiaries,
            # so no _con statement at all) from individual.
            combined = extracted_con.combine_first(extracted_ind) if not extracted_con.empty or not extracted_ind.empty else pd.DataFrame()
            frames.append(combined)

    if not frames or all(f.empty for f in frames):
        return pd.DataFrame()

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.join(f, how="outer")
    merged["fiscal_year"] = year
    return merged.reset_index().rename(columns={"CD_CVM_INT": "CD_CVM"})


def add_past_return(df: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Trailing 12-month stock return ending at each fiscal year-end
    (2015-12-31, ..., 2024-12-31) -- a standard control, computed from the
    same Bloomberg export used for the forward abnormal return.
    """
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    prices = prices.set_index("date").sort_index()

    # universe (ibov_non_financial_universe.csv) only covers the current-66
    # companies -- resolving historical/delisted tickers too needs the same
    # B3-live-registry lookup already built for the abnormal-return
    # checkpoint (~30/46 resolve; the rest went private/merged/bankrupt with
    # no tradeable ticker left, a real gap noted elsewhere, not fixed here).
    from src.analysis.compute_abnormal_returns import build_ticker_map

    ticker_map = build_ticker_map()
    cd_to_ticker = dict(zip(ticker_map["CD_CVM"].astype(int), ticker_map["ticker"]))

    def _past_return(row) -> float:
        ticker = cd_to_ticker.get(int(row["CD_CVM"]))
        if ticker is None:
            return np.nan
        col = f"{ticker} BS Equity"
        if col not in prices.columns:
            return np.nan
        year_end = pd.Timestamp(f"{int(row['fiscal_year'])}-12-31")
        series = prices[col].dropna()
        window = series[series.index <= year_end]
        if len(window) < 200:  # need close to a full trailing year of data
            return np.nan
        start = window[window.index >= year_end - pd.Timedelta(days=380)]
        if start.empty:
            return np.nan
        return window.iloc[-1] / start.iloc[0] - 1

    df["past_12m_return"] = df.apply(_past_return, axis=1)
    return df


def main() -> None:
    universe = pd.read_csv("data/interim/ibov_non_financial_universe.csv")
    from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM

    cd_cvm_filter = set(universe["CD_CVM"].astype(int)) | set(NEW_HISTORICAL_CD_CVM.keys())

    yearly = [build_year(y, cd_cvm_filter) for y in YEARS]
    combined = pd.concat([f for f in yearly if not f.empty], ignore_index=True)

    # Found by inspection (TIM S.A. 2024): CVM's own source data occasionally
    # has a filing where the "ÚLTIMO" (current-year) column is populated as
    # a literal 0.0 across every account while "PENÚLTIMO" (prior year) has
    # real values -- an unpopulated/draft filing in CVM's own open data, not
    # an extraction bug. A real operating company never has exactly zero
    # total assets, so treat that as missing rather than trust it silently.
    zero_assets = combined["total_assets"] == 0
    if zero_assets.any():
        print(f"Dropping {zero_assets.sum()} company-year(s) with total_assets == 0 (unpopulated source filing):")
        print(combined.loc[zero_assets, ["CD_CVM", "fiscal_year"]].to_string(index=False))
        combined = combined[~zero_assets].reset_index(drop=True)

    combined["total_liabilities"] = combined["current_liabilities"] + combined["noncurrent_liabilities"]
    combined["leverage"] = combined["total_liabilities"] / combined["total_assets"]
    combined["roa"] = combined["net_income"] / combined["total_assets"]
    combined["roe"] = combined["net_income"] / combined["total_equity"]
    combined["ln_total_assets"] = np.log(combined["total_assets"].clip(lower=1))
    combined["ln_net_revenue"] = np.log(combined["net_revenue"].clip(lower=1))

    combined = add_past_return(combined, universe)

    name_map = dict(zip(universe["CD_CVM"].astype(int), universe["DENOM_CIA"]))
    name_map.update({cd: name for cd, name in NEW_HISTORICAL_CD_CVM.items() if cd not in name_map})
    combined["company_name"] = combined["CD_CVM"].map(name_map)

    cols = [
        "CD_CVM", "company_name", "fiscal_year",
        "total_assets", "net_revenue", "net_income", "total_equity", "total_liabilities",
        "ln_total_assets", "ln_net_revenue", "leverage", "roa", "roe", "past_12m_return",
    ]
    combined = combined[cols].sort_values(["CD_CVM", "fiscal_year"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT_PATH, index=False)

    n_companies = combined["CD_CVM"].nunique()
    n_rows = len(combined)
    coverage = combined[["total_assets", "net_revenue", "net_income", "leverage", "roa", "past_12m_return"]].notna().mean()
    print(f"{n_rows} company-years, {n_companies} companies")
    print("field coverage:")
    print(coverage.to_string())
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()

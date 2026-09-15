"""Extends build_control_variables.py's control_variables.csv (111
companies, 2015-2024 only) to the round-7 universe expansion: the same 111
companies' 2010-2014 years, plus the 74 IBX-extra companies' 2010-2025
years. Same account codes, same consolidated-with-individual-fallback
logic, same derived variables (size, leverage, ROA/ROE, past 12-month
return) -- just a wider company/year scope and the combined (original +
ibx.xlsx) price source for past_12m_return, so the 2010-2013 years aren't
starved of price history the way they would be with stock_prices_bloomberg.csv
alone (see compute_new_universe_returns.py's load_combined_prices).

Kept as a separate output (control_variables_extension.csv) rather than
overwriting control_variables.csv -- that file is what the thesis's own
M0-M3 pipeline reads, untouched by this exploratory expansion. Concatenate
the two (drop_duplicates on cd_cvm/fiscal_year, extension row wins only
where the original has none) for the full combined panel.

Usage:
    python -u -m src.features.build_control_variables_extension
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.compute_new_universe_returns import build_full_ticker_map, load_combined_prices
from src.features.build_control_variables import ACCOUNTS, build_year

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
IBX_EXTRA_UNIVERSE = INTERIM / "ibx_extra_universe.csv"
OUT_PATH = INTERIM / "control_variables_extension.csv"
YEARS = list(range(2010, 2026))


def add_past_return(df: pd.DataFrame, prices: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
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
        if len(window) < 200:
            return np.nan
        start = window[window.index >= year_end - pd.Timedelta(days=380)]
        if start.empty:
            return np.nan
        return window.iloc[-1] / start.iloc[0] - 1

    df["past_12m_return"] = df.apply(_past_return, axis=1)
    return df


def main() -> None:
    original_universe = pd.read_csv(INTERIM / "ibov_non_financial_universe.csv")
    from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM

    ibx_extra = pd.read_csv(IBX_EXTRA_UNIVERSE, dtype={"CD_CVM": str})
    cd_cvm_filter = (
        set(original_universe["CD_CVM"].astype(int))
        | set(NEW_HISTORICAL_CD_CVM.keys())
        | set(ibx_extra["CD_CVM"].astype(int))
    )
    print(f"{len(cd_cvm_filter)}-company universe, years {YEARS[0]}-{YEARS[-1]}")

    yearly = [build_year(y, cd_cvm_filter) for y in YEARS]
    combined = pd.concat([f for f in yearly if not f.empty], ignore_index=True)

    zero_assets = combined["total_assets"] == 0
    if zero_assets.any():
        print(f"Dropping {zero_assets.sum()} company-year(s) with total_assets == 0 (unpopulated source filing)")
        combined = combined[~zero_assets].reset_index(drop=True)

    combined["total_liabilities"] = combined["current_liabilities"] + combined["noncurrent_liabilities"]
    combined["leverage"] = combined["total_liabilities"] / combined["total_assets"]
    combined["roa"] = combined["net_income"] / combined["total_assets"]
    combined["roe"] = combined["net_income"] / combined["total_equity"]
    combined["ln_total_assets"] = np.log(combined["total_assets"].clip(lower=1))
    combined["ln_net_revenue"] = np.log(combined["net_revenue"].clip(lower=1))

    ticker_map = build_full_ticker_map()
    prices = load_combined_prices()
    combined = add_past_return(combined, prices, ticker_map)

    name_map = dict(zip(original_universe["CD_CVM"].astype(int), original_universe["DENOM_CIA"]))
    name_map.update({cd: name for cd, name in NEW_HISTORICAL_CD_CVM.items() if cd not in name_map})
    name_map.update({int(r.CD_CVM): r.Name for r in ibx_extra.itertuples() if int(r.CD_CVM) not in name_map})
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

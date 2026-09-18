"""Builds every control variable needed for the M0-M5 grade
(especificacoes_m0_m5_dissertacao.pdf), beyond what control_variables.csv
and debt_line_item.csv already provide:

  - delta_roa, delta_leverage: year-over-year change (t vs t-1), from
    control_variables.csv.
  - delta_debt: (debt_line_item_t - debt_line_item_t-1) / total_assets_t-1,
    the specific Empréstimos+Financiamentos+Debêntures account
    (src/features/build_debt_line_item.py), normalized by lagged assets.
  - btm: book-to-market = 1 / (price-to-book), from ibov.xlsx's
    px_to_book_value_open sheet, at the trading day at-or-before a given
    reference date (pre-filing, no look-ahead).
  - volatility: std dev of daily stock returns over the trailing 252
    trading days ending strictly before a reference date.
  - amihud_illiquidity: mean(|daily return| / dollar volume) over the same
    trailing 252-day window (Amihud 2002), using ibov.xlsx's px_volume
    (shares) x stock_prices_bloomberg.csv price for dollar volume.

AnalystCoverage (M4) is NOT built here: the only analyst data available
(data/raw/analysts/eps_consensus_bloomberg.csv) is a consensus VALUE
series, with no analyst-count field anywhere in the project's data. M4 is
therefore run with Liquidity only, flagged as partial.

Usage (as a library -- other scripts import build_panel()):
    from src.features.build_m0_m5_controls import build_panel
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
IBOV_XLSX = ROOT / "ibov.xlsx"

VOL_WINDOW = 252
MIN_VOL_OBS = 100


def _load_ibov_sheet(sheet: str) -> pd.DataFrame:
    raw = pd.read_excel(IBOV_XLSX, sheet_name=sheet, header=None)
    tickers = raw.iloc[5, 1:].tolist()
    data = raw.iloc[7:, :].copy()
    data.columns = ["date"] + tickers
    data["date"] = pd.to_datetime(data["date"])
    data = data.dropna(subset=["date"]).set_index("date").sort_index()
    for c in data.columns:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    return data


def load_prices() -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    return prices.set_index("date").sort_index()


def build_fundamentals_panel() -> pd.DataFrame:
    """cd_cvm, fiscal_year -> level + year-over-year change controls."""
    ctrl = pd.read_csv(INTERIM / "control_variables.csv")
    ctrl = ctrl.sort_values(["CD_CVM", "fiscal_year"])
    ctrl["delta_roa"] = ctrl.groupby("CD_CVM")["roa"].diff()
    ctrl["delta_leverage"] = ctrl.groupby("CD_CVM")["leverage"].diff()

    debt = pd.read_csv(INTERIM / "debt_line_item.csv")
    debt = debt.sort_values(["cd_cvm", "fiscal_year"])
    debt["debt_prev"] = debt.groupby("cd_cvm")["debt_line_item"].shift(1)

    m = ctrl.rename(columns={"CD_CVM": "cd_cvm"}).merge(
        debt[["cd_cvm", "fiscal_year", "debt_line_item", "debt_prev"]],
        on=["cd_cvm", "fiscal_year"], how="left",
    )
    assets_prev = ctrl.rename(columns={"CD_CVM": "cd_cvm"})[["cd_cvm", "fiscal_year", "total_assets"]].copy()
    assets_prev["fiscal_year"] = assets_prev["fiscal_year"] + 1
    assets_prev = assets_prev.rename(columns={"total_assets": "total_assets_prev"})
    m = m.merge(assets_prev, on=["cd_cvm", "fiscal_year"], how="left")
    m["delta_debt"] = (m["debt_line_item"] - m["debt_prev"]) / m["total_assets_prev"]

    return m[["cd_cvm", "fiscal_year", "ln_total_assets", "roa", "leverage", "past_12m_return",
              "delta_roa", "delta_leverage", "delta_debt"]]


def _asof_value(series: pd.Series, ref_dates: pd.Series) -> pd.Series:
    """For each ref_date, the series' value at the latest available date
    <= ref_date (no look-ahead)."""
    s = series.dropna().sort_index()
    if s.empty:
        return pd.Series(np.nan, index=ref_dates.index)
    idx = s.index.searchsorted(ref_dates.values, side="right") - 1
    out = np.where(idx >= 0, s.values[np.clip(idx, 0, len(s) - 1)], np.nan)
    return pd.Series(out, index=ref_dates.index)


def build_market_controls(events: pd.DataFrame) -> pd.DataFrame:
    """events needs columns: ticker, window_start (pre-filing reference
    date). Returns btm, volatility, amihud_illiquidity aligned to events'
    index."""
    prices = load_prices()
    btm_sheet = _load_ibov_sheet("px_to_book_value_open")
    vol_sheet = _load_ibov_sheet("px_volume")

    out = pd.DataFrame(index=events.index, columns=["btm", "volatility", "amihud_illiquidity"], dtype=float)
    for ticker, grp in events.groupby("ticker"):
        col = f"{ticker} BS Equity"
        ref_dates = grp["window_start"]

        if col in btm_sheet.columns:
            pb = _asof_value(btm_sheet[col], ref_dates)
            out.loc[grp.index, "btm"] = 1.0 / pb.replace(0, np.nan)

        if col not in prices.columns:
            continue
        px = prices[col].dropna()
        ret = px.pct_change().dropna()

        for idx, ref_date in ref_dates.items():
            window_ret = ret[ret.index < ref_date].tail(VOL_WINDOW)
            if len(window_ret) >= MIN_VOL_OBS:
                out.loc[idx, "volatility"] = window_ret.std()

        if col in vol_sheet.columns:
            dollar_vol = vol_sheet[col] * px
            abs_ret = ret.abs()
            illiq_daily = (abs_ret / dollar_vol.reindex(abs_ret.index)).replace([np.inf, -np.inf], np.nan)
            for idx, ref_date in ref_dates.items():
                window_illiq = illiq_daily[illiq_daily.index < ref_date].tail(VOL_WINDOW).dropna()
                if len(window_illiq) >= MIN_VOL_OBS:
                    out.loc[idx, "amihud_illiquidity"] = window_illiq.mean()

    return out


def build_panel(events: pd.DataFrame) -> pd.DataFrame:
    """events: a dataframe with cd_cvm, year_curr, ticker, window_start
    (datetime) columns -- typically read from an abnormal_returns_alpha_*
    file. Returns events with all M0-M5 control columns appended."""
    events = events.copy()
    events["window_start"] = pd.to_datetime(events["window_start"])

    fund = build_fundamentals_panel()
    events = events.merge(fund, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "fiscal_year"], how="left")

    market = build_market_controls(events)
    events = events.join(market)

    return events


if __name__ == "__main__":
    sample = pd.read_csv(INTERIM / "poc" / "abnormal_returns_alpha_narrow_annual.csv")
    panel = build_panel(sample)
    cols = ["ln_total_assets", "roa", "leverage", "past_12m_return", "delta_roa", "delta_leverage",
            "delta_debt", "btm", "volatility", "amihud_illiquidity"]
    print(panel[cols].describe().round(4))
    print("\nCoverage (non-null):")
    print(panel[cols].notna().sum())

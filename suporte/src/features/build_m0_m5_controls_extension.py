"""Extends build_m0_m5_controls.py's build_panel() to the round-7 universe
expansion: fundamentals (level + year-over-year change controls) from the
extended control_variables_extension.csv / debt_line_item_extension.csv,
and market controls (book-to-market, volatility) from ibov.xlsx AND
ibx.xlsx combined -- ibx.xlsx alone would work for book-to-market/volume
(it's a near-complete superset, see compute_new_universe_returns.py's
load_combined_prices docstring for the verification), but combining both
the same row-level way keeps this consistent with how prices are combined
elsewhere and costs nothing.

amihud_illiquidity (M4, not part of the confirmatory M0-M3 grid) is
deliberately NOT built here -- out of scope for this extension, matching
the original build_m0_m5_controls.py's own M4 caveat.

Usage (as a library):
    from src.features.build_m0_m5_controls_extension import build_panel_extended
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.compute_new_universe_returns import load_combined_prices

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
IBOV_XLSX = ROOT / "ibov.xlsx"
IBX_XLSX = ROOT / "ibx.xlsx"

VOL_WINDOW = 252
MIN_VOL_OBS = 100


def _load_sheet_dynamic(path: Path, sheet: str) -> pd.DataFrame:
    """Same 'DATES' label lookup as compute_new_universe_returns.load_ibx_prices
    -- robust to the two files' differing header-row offsets (confirmed by
    inspection: ibov.xlsx and ibx.xlsx don't share the same number of
    metadata rows before the ticker row, even within ibx.xlsx's own sheets)."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    label_row = raw.index[raw[0] == "DATES"][0]
    tickers = raw.iloc[label_row - 1, 1:].tolist()
    data = raw.iloc[label_row + 1 :, :].copy()
    cols = ["date"] + [t if "BS Equity" in str(t) else f"{t} BS Equity" for t in tickers]
    data.columns = cols
    data["date"] = pd.to_datetime(data["date"])
    data = data.dropna(subset=["date"]).set_index("date").sort_index()
    for c in data.columns:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    return data


def load_combined_sheet(sheet: str) -> pd.DataFrame:
    original = _load_sheet_dynamic(IBOV_XLSX, sheet)
    ibx = _load_sheet_dynamic(IBX_XLSX, sheet)
    return original.combine_first(ibx).sort_index()


def build_fundamentals_panel_extended() -> pd.DataFrame:
    """Same shape as build_m0_m5_controls.build_fundamentals_panel, but
    reading the *_extension.csv files (2010-2025, 185 companies) instead
    of the original 2015-2024/111-company ones."""
    ctrl = pd.read_csv(INTERIM / "control_variables_extension.csv")
    ctrl = ctrl.sort_values(["CD_CVM", "fiscal_year"])
    ctrl["delta_roa"] = ctrl.groupby("CD_CVM")["roa"].diff()
    ctrl["delta_leverage"] = ctrl.groupby("CD_CVM")["leverage"].diff()

    debt = pd.read_csv(INTERIM / "debt_line_item_extension.csv")
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
    s = series.dropna().sort_index()
    if s.empty:
        return pd.Series(np.nan, index=ref_dates.index)
    idx = s.index.searchsorted(ref_dates.values, side="right") - 1
    out = np.where(idx >= 0, s.values[np.clip(idx, 0, len(s) - 1)], np.nan)
    return pd.Series(out, index=ref_dates.index)


def build_market_controls_extended(events: pd.DataFrame) -> pd.DataFrame:
    """events needs columns: ticker, window_start. Returns btm, volatility
    aligned to events' index, using the combined (ibov.xlsx + ibx.xlsx)
    sheets and the combined price source."""
    prices = load_combined_prices()
    btm_sheet = load_combined_sheet("px_to_book_value_open")

    out = pd.DataFrame(index=events.index, columns=["btm", "volatility"], dtype=float)
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

    return out


def build_panel_extended(events: pd.DataFrame) -> pd.DataFrame:
    """events: dataframe with cd_cvm, year_curr, ticker, window_start."""
    events = events.copy()
    events["window_start"] = pd.to_datetime(events["window_start"])

    fund = build_fundamentals_panel_extended()
    events = events.merge(fund, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "fiscal_year"], how="left")

    market = build_market_controls_extended(events)
    events = events.join(market)

    return events


if __name__ == "__main__":
    sample = pd.read_csv(INTERIM / "poc" / "abnormal_returns_alpha_full_expanded_universe.csv")
    panel = build_panel_extended(sample)
    cols = ["ln_total_assets", "roa", "leverage", "past_12m_return", "delta_roa", "delta_leverage",
            "delta_debt", "btm", "volatility"]
    print(panel[cols].describe().round(4))
    print("\nCoverage (non-null):")
    print(panel[cols].notna().sum())

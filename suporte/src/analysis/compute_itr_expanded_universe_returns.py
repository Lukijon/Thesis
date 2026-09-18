"""Quarterly (ITR) counterpart to compute_full_expanded_universe_returns.py:
BHAR ajustado (4-factor alpha model) for the narrow debt note in quarterly
frequency, over the full round-7 expanded universe (185 companies,
2011-2025). Event window is ~1 quarter (63 trading days after the ITR's
CVM disclosure date), matching the ORIGINAL 112-company quarterly
checkpoint's window (compute_quarterly_abnormal_returns.py,
WINDOW_TRADING_DAYS=63) -- not the 12-month window used for the annual
note. This is a deliberate, pre-existing methodological difference
(Sec. 4.2 of the thesis: quarterly is "checagem exploratoria de robustez
de frequencia"), not an inconsistency introduced by this extension.

Usage:
    python -u -m src.analysis.compute_itr_expanded_universe_returns
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_alpha_abnormal_returns import estimate_alpha_model, event_window_residuals, load_factors
from src.analysis.compute_new_universe_returns import build_full_ticker_map, load_combined_prices
from src.analysis.run_m0_m5_grid import M0, M1, M2, M3, _fit_panel
from src.features.build_m0_m5_controls_extension import build_panel_extended

POC = Path("data/interim/poc")
WINDOW_TRADING_DAYS = 63
SIM_CSV = POC / "itr_similarity_results_full_history.csv"
OUT_CSV = POC / "abnormal_returns_alpha_narrow_quarterly_full_expanded_universe.csv"
MODELS = [("M0", M0, "diagnóstico"), ("M1", M1, "baseline"), ("M2", M2, "PRINCIPAL"), ("M3", M3, "robustez econômica")]


def load_event_dates() -> pd.DataFrame:
    filing_dates = pd.read_csv("data/interim/itr_filing_dates_extension.csv")
    return filing_dates.rename(columns={
        "CD_CVM": "cd_cvm", "QUARTER_LABEL": "quarter_curr", "filing_date": "event_date",
    })[["cd_cvm", "quarter_curr", "event_date"]].assign(
        event_date=lambda d: pd.to_datetime(d["event_date"])
    )


def compute_windows(events: pd.DataFrame, ticker_map: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    last_date = prices.index.max()
    rows = []
    events = events.merge(ticker_map, left_on="cd_cvm", right_on="CD_CVM", how="left")
    for row in events.itertuples(index=False):
        if pd.isna(row.event_date) or pd.isna(row.ticker):
            continue
        col = f"{row.ticker} BS Equity"
        if col not in prices.columns:
            continue
        stock = prices[col].dropna()
        stock = stock[stock.index >= row.event_date]
        if stock.empty or len(stock) <= WINDOW_TRADING_DAYS:
            continue
        t0 = stock.index[0]
        t1 = stock.index[WINDOW_TRADING_DAYS]
        if t1 > last_date:
            continue
        rows.append({"cd_cvm": row.cd_cvm, "quarter_curr": row.quarter_curr, "ticker": row.ticker,
                     "window_start": t0, "window_end": t1})
    return pd.DataFrame(rows)


def main() -> None:
    sim = pd.read_csv(SIM_CSV, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    sim["TextChange"] = 1 - sim["cosine_similarity"]
    reliable = sim[(sim["diagnostic_prev"] == "font_heading") & (sim["diagnostic_curr"] == "font_heading")]
    print(f"{len(sim)} total quarterly pairs, {len(reliable)} reliable (font_heading both quarters)")

    ticker_map = build_full_ticker_map()
    events = load_event_dates()
    prices = load_combined_prices()
    windows = compute_windows(events, ticker_map, prices)
    merged = reliable.merge(windows, on=["cd_cvm", "quarter_curr"], how="inner")
    merged = merged.drop_duplicates(subset=["cd_cvm", "quarter_prev", "quarter_curr"])

    factors = load_factors()
    rows = []
    for row in merged.itertuples(index=False):
        col = f"{row.ticker} BS Equity"
        ret = prices[col].dropna().pct_change().dropna()
        est = estimate_alpha_model(ret, factors, row.window_start)
        if est is None:
            continue
        alpha, betas, n_est = est
        eps = event_window_residuals(ret, factors, alpha, betas, row.window_start, row.window_end)
        if eps is None or len(eps) < 20:
            continue
        rows.append({"cd_cvm": row.cd_cvm, "quarter_curr": row.quarter_curr,
                     "year_curr": int(row.quarter_curr[:4]), "ticker": row.ticker,
                     "window_start": row.window_start, "window_end": row.window_end,
                     "TextChange": row.TextChange, "cosine_similarity": row.cosine_similarity,
                     "BHAR_raw": float((1 + eps).prod() - 1)})
    df = pd.DataFrame(rows)
    lo, hi = df["BHAR_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_raw"].clip(lo, hi)
    df.to_csv(OUT_CSV, index=False)
    print(f"{len(df)} observations, {df['cd_cvm'].nunique()} companies -> {OUT_CSV}")

    panel = build_panel_extended(df)
    print("\n=== M0-M3, nota de dívida trimestral, universo expandido (185 empresas, 2011-2025) ===\n")
    grid_rows = []
    for name, controls, status in MODELS:
        r = _fit_panel(panel, "BHAR_ajustado", controls)
        grid_rows.append({"Modelo": name, "Status": status, **r})
        if pd.notna(r["p"]):
            print(f"{name} ({status}): n={r['n']:4d}  n_empresas={r['n_companies']:3d}  "
                  f"beta={r['beta']:+.4f}  se={r['se']:.4f}  p={r['p']:.4f}")
        else:
            print(f"{name} ({status}): n={r['n']:4d} -- insuficiente para estimar")

    out = pd.DataFrame(grid_rows)
    out_path = POC / "m0_m3_narrow_quarterly_expanded_universe_results.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

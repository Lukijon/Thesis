"""Re-runs H1's M2 (principal) specification for the narrow annual debt
note over the expanded universe using the expanding-window (look-ahead-
free) IDF similarity from recompute_similarity_expanding_window_full_
history.py, instead of the full-corpus-fit IDF used everywhere else --
the expanded-universe counterpart of the original 111-company look-ahead
check (Sec. 5.3, "TF-IDF sem informacao futura").

Usage:
    python -u -m src.analysis.run_expanding_window_robustness_expanded_universe
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from src.analysis.compute_alpha_abnormal_returns import estimate_alpha_model, event_window_residuals, load_factors
from src.analysis.compute_new_universe_returns import build_full_ticker_map, compute_windows, load_combined_event_dates, load_combined_prices
from src.analysis.run_m0_m5_grid import M2, _fit_panel
from src.features.build_m0_m5_controls_extension import build_panel_extended

warnings.filterwarnings("ignore")

POC = Path("data/interim/poc")
SIM_CSV = POC / "similarity_results_full_history_expanding.csv"
OUT_CSV = POC / "abnormal_returns_alpha_full_expanded_universe_expanding_idf.csv"


def main() -> None:
    sim = pd.read_csv(SIM_CSV, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    rel = sim[(sim["diagnostic_prev"] == "font_heading") & (sim["diagnostic_curr"] == "font_heading")].copy()
    rel["TextChange"] = 1 - rel["cosine_similarity_expanding"]
    print(f"{len(rel)} reliable pairs (expanding-window IDF)")

    ticker_map = build_full_ticker_map()
    events = load_combined_event_dates()
    prices = load_combined_prices()
    windows = compute_windows(events, ticker_map, prices)
    merged = rel.merge(windows, on=["cd_cvm", "year_curr"], how="inner")

    factors = load_factors()
    rows = []
    for row in merged.itertuples(index=False):
        col = f"{row.ticker} BS Equity"
        if col not in prices.columns:
            continue
        ret = prices[col].dropna().pct_change().dropna()
        est = estimate_alpha_model(ret, factors, row.window_start)
        if est is None:
            continue
        alpha, betas, n_est = est
        eps = event_window_residuals(ret, factors, alpha, betas, row.window_start, row.window_end)
        if eps is None or len(eps) < 20:
            continue
        rows.append({"cd_cvm": row.cd_cvm, "year_curr": row.year_curr, "ticker": row.ticker,
                     "window_start": row.window_start, "window_end": row.window_end,
                     "TextChange": row.TextChange, "BHAR_raw": float((1 + eps).prod() - 1)})
    df = pd.DataFrame(rows)
    lo, hi = df["BHAR_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_raw"].clip(lo, hi)
    df.to_csv(OUT_CSV, index=False)
    print(f"{len(df)} observations -> {OUT_CSV}")

    panel = build_panel_extended(df)
    r = _fit_panel(panel, "BHAR_ajustado", M2)
    print(f"\nM2 (expanding-window IDF): n={r['n']}  n_companies={r['n_companies']}  "
          f"beta={r['beta']:+.4f}  p={r['p']:.4f}")
    print("Compare to M2 (full-corpus IDF, Tabela 5.1): p=0.0173")


if __name__ == "__main__":
    main()

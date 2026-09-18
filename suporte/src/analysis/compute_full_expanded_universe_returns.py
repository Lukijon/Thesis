"""Same BHAR ajustado computation as compute_new_universe_returns.py, but
over the FULL expanded universe's reliable TextChange pairs
(similarity_results_full_history_reliable.csv -- the 111-company/2015-2024
pairs already in the thesis PLUS the round-7 expansion combined), and using
the thesis's own M0 specification (TextChange + company/year fixed effects,
clustered by company -- see run_m0_m5_grid.py's _fit_panel) instead of a
bare bivariate regression, so the result is directly comparable to the
thesis's own Tabela 5.2 M0 row for the narrow annual debt note (n=437,
p=0.211), not just internally consistent.

No control variables (size, ROA, leverage, momentum, deltas) are included
-- those haven't been built for the 74 IBX-extra companies yet, so this is
M0-equivalent only, not M2. Comparing this result to the thesis's M2 row
(p=0.268, with full controls) would not be apples-to-apples; the M0 row is
the right comparison point.

Usage:
    python -u -m src.analysis.compute_full_expanded_universe_returns
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_alpha_abnormal_returns import estimate_alpha_model, event_window_residuals, load_factors
from src.analysis.compute_new_universe_returns import build_full_ticker_map, compute_windows, load_combined_event_dates, load_combined_prices
from src.analysis.run_m0_m5_grid import _fit_panel

POC = Path("data/interim/poc")
SIMILARITY_CSV = POC / "similarity_results_full_history_reliable.csv"
OUT_CSV = POC / "abnormal_returns_alpha_full_expanded_universe.csv"


def build_bhar(sim_path: Path) -> pd.DataFrame:
    sim = pd.read_csv(sim_path, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    sim["TextChange"] = 1 - sim["cosine_similarity"]

    ticker_map = build_full_ticker_map()
    events = load_combined_event_dates()
    prices = load_combined_prices()
    windows = compute_windows(events, ticker_map, prices)
    merged = sim.merge(windows, on=["cd_cvm", "year_curr"], how="inner")

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
                     "TextChange": row.TextChange,
                     "cosine_similarity": row.cosine_similarity, "BHAR_raw": float((1 + eps).prod() - 1)})
    df = pd.DataFrame(rows)
    lo, hi = df["BHAR_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_raw"].clip(lo, hi)
    return df


def main() -> None:
    df = build_bhar(SIMILARITY_CSV)
    df.to_csv(OUT_CSV, index=False)
    print(f"{len(df)} observations, {df['cd_cvm'].nunique()} companies -> {OUT_CSV}")

    headline = _fit_panel(df, "BHAR_ajustado", [])
    print("\n=== M0-equivalent (TextChange + company/year FE, clustered by company) ===")
    print(f"beta={headline['beta']:.4f}  se={headline['se']:.4f}  p={headline['p']:.4f}  "
          f"n={headline['n']}  n_companies={headline['n_companies']}")

    print("\n--- Robustness checks ---")
    degenerate = (df["TextChange"] <= 0.001) | (df["TextChange"] >= 0.999)
    clean = df[~degenerate]
    r_clean = _fit_panel(clean, "BHAR_ajustado", [])
    print(f"Excluding {int(degenerate.sum())} degenerate-similarity pairs: p={r_clean['p']:.4f}  n={r_clean['n']}")

    df_raw = df.rename(columns={"BHAR_ajustado": "BHAR_ajustado_winz", "BHAR_raw": "BHAR_ajustado"})
    r_raw = _fit_panel(df_raw, "BHAR_ajustado", [])
    print(f"Using raw (non-winsorized) BHAR instead: p={r_raw['p']:.4f}")

    worst_p, worst_cd = headline["p"], None
    for cd in df["cd_cvm"].unique():
        sub = df[df["cd_cvm"] != cd]
        r = _fit_panel(sub, "BHAR_ajustado", [])
        if r["p"] > worst_p:
            worst_p, worst_cd = r["p"], cd
    print(f"Leave-one-company-out worst case: p={worst_p:.4f} (dropping cd_cvm={worst_cd})")


if __name__ == "__main__":
    main()

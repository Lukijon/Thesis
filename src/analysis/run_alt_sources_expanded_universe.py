"""Generalizes compute_full_expanded_universe_returns.py (built for the
narrow annual debt note) to the three other DFP/FRE-based text sources --
whole notes, Relatorio da Administracao, Risk Factors -- over the full
round-7 expanded universe (185 companies, 2010-2025), now that
run_alt_sources_full_history_tfidf.py has produced their similarity files.

All three share the same event calendar as the narrow note (DFP disclosure
date, dfp_filing_dates.csv + _extension.csv combined) -- same convention
already used by the ORIGINAL (111-company) pipeline, see
compute_risk_factors_abnormal_returns.py's reuse of load_event_dates().
Quarterly (ITR) is intentionally NOT included here -- acquisition still in
progress, handled separately once it completes.

For each source: builds BHAR ajustado, merges the full M1-M3 control panel
(build_m0_m5_controls_extension.py, source-agnostic), runs the M0-M3 grid,
and -- for any source whose M2 (principal) p-value is below 0.15 -- runs
the same robustness battery used throughout this project (degenerate-
similarity exclusion, raw vs winsorized BHAR, leave-one-company-out).

Usage:
    python -u -m src.analysis.run_alt_sources_expanded_universe
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_alpha_abnormal_returns import estimate_alpha_model, event_window_residuals, load_factors
from src.analysis.compute_new_universe_returns import build_full_ticker_map, compute_windows, load_combined_event_dates, load_combined_prices
from src.analysis.run_m0_m5_grid import M0, M1, M2, M3, _fit_panel
from src.features.build_m0_m5_controls_extension import build_panel_extended

POC = Path("data/interim/poc")

SOURCES = {
    "whole_notes": "full_notes_similarity_results_full_history.csv",
    "mgmt_report": "mgmt_report_similarity_results_full_history.csv",
    "risk_factors": "risk_factors_similarity_results_full_history.csv",
}
MODELS = [("M0", M0, "diagnóstico"), ("M1", M1, "baseline"), ("M2", M2, "PRINCIPAL"), ("M3", M3, "robustez econômica")]


def build_bhar(sim_path: Path, ticker_map, events, prices) -> pd.DataFrame:
    sim = pd.read_csv(sim_path, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    sim["TextChange"] = 1 - sim["cosine_similarity"]

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
    if df.empty:
        return df
    lo, hi = df["BHAR_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_raw"].clip(lo, hi)
    return df


def run_robustness(df: pd.DataFrame) -> None:
    degenerate = (df["TextChange"] <= 0.001) | (df["TextChange"] >= 0.999)
    clean = df[~degenerate]
    r_clean = _fit_panel(clean, "BHAR_ajustado", [])
    print(f"  Excluding {int(degenerate.sum())} degenerate pairs: p={r_clean['p']:.4f}  n={r_clean['n']}")

    df_raw = df.rename(columns={"BHAR_ajustado": "BHAR_ajustado_winz", "BHAR_raw": "BHAR_ajustado"})
    r_raw = _fit_panel(df_raw, "BHAR_ajustado", [])
    print(f"  Raw (non-winsorized) BHAR: p={r_raw['p']:.4f}")

    worst_p, worst_cd = -1.0, None
    for cd in df["cd_cvm"].unique():
        sub = df[df["cd_cvm"] != cd]
        r = _fit_panel(sub, "BHAR_ajustado", [])
        if pd.notna(r["p"]) and r["p"] > worst_p:
            worst_p, worst_cd = r["p"], cd
    print(f"  Leave-one-company-out worst case: p={worst_p:.4f} (dropping cd_cvm={worst_cd})")


def main() -> None:
    ticker_map = build_full_ticker_map()
    events = load_combined_event_dates()
    prices = load_combined_prices()

    all_rows = []
    for name, fname in SOURCES.items():
        print(f"\n=== {name} ({fname}) ===")
        df = build_bhar(POC / fname, ticker_map, events, prices)
        if df.empty:
            print("  No computable observations.")
            continue
        out_path = POC / f"abnormal_returns_alpha_{name}_full_expanded_universe.csv"
        df.to_csv(out_path, index=False)
        print(f"  {len(df)} observations, {df['cd_cvm'].nunique()} companies -> {out_path}")

        panel = build_panel_extended(df)
        m2_p = None
        for m_name, controls, status in MODELS:
            r = _fit_panel(panel, "BHAR_ajustado", controls)
            all_rows.append({"Fonte": name, "Modelo": m_name, "Status": status, **r})
            if pd.notna(r["p"]):
                print(f"  {m_name} ({status}): n={r['n']:4d}  n_empresas={r['n_companies']:3d}  "
                      f"beta={r['beta']:+.4f}  se={r['se']:.4f}  p={r['p']:.4f}")
            else:
                print(f"  {m_name} ({status}): n={r['n']:4d} -- insuficiente para estimar")
            if m_name == "M2":
                m2_p = r["p"]

        if m2_p is not None and pd.notna(m2_p) and m2_p < 0.15:
            print(f"  M2 p={m2_p:.4f} < 0.15 -- running robustness battery:")
            run_robustness(panel)

    out = pd.DataFrame(all_rows)
    out_path = POC / "m0_m3_alt_sources_expanded_universe_results.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

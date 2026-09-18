"""Formalizes and extends Tabela 5.5 (Santos & Coelho 2018-style comparison
-- company-only effect, Hausman-selected FE/RE, robust SEs, alongside this
project's own two-way FE+clustered specification) to the full round-7
expanded universe (185 companies, 2010-2025).

The original table's numbers were produced by an ad hoc, never-committed
script (only its output, santos_coelho_bhar_ajustado.csv, survived,
covering only the FE-company/RE-company/Hausman columns -- the "Ef. fixos
(2 vias)" column's source was undocumented). Reverse-engineered and
verified here before trusting it on new data: _fit_panel(df,
"BHAR_ajustado", ["leverage","roa","past_12m_return"]) reproduces the
2-via column exactly (narrow_annual 12m: p=0.2721 vs. the published 0.272;
18m: p=0.1038 vs. 0.104), and compare_return_windows_santos_coelho_style.
run_one()'s FE/RE/Hausman logic, applied to BHAR_ajustado instead of the
old market-adjusted abnormal_return, reproduces the other three columns
exactly for the same two rows (call with --validate to reprint this
check against the original 111-company data).

18-month BHAR windows for the expanded universe (not built by any earlier
script) are constructed here the same way build_extra_window_variants.py
built them for the original scope: same event dates/ticker map/prices,
window_trading_days=378 instead of 252.

Usage:
    python -u -m src.analysis.run_santos_coelho_expanded_universe [--validate]
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS, RandomEffects
from scipy import stats as scipy_stats

from src.analysis.compute_alpha_abnormal_returns import estimate_alpha_model, event_window_residuals, load_factors
from src.analysis.compute_new_universe_returns import build_full_ticker_map, load_combined_event_dates, load_combined_prices
from src.analysis.run_m0_m5_grid import _fit_panel
from src.features.build_m0_m5_controls_extension import build_fundamentals_panel_extended

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"
CONTROLS = ["leverage", "roa", "past_12m_return"]

SOURCES_EXPANDED = {
    "narrow_annual": POC / "similarity_results_full_history_reliable.csv",
    "whole_notes": POC / "full_notes_similarity_results_full_history.csv",
    "mgmt_report": POC / "mgmt_report_similarity_results_full_history.csv",
    "risk_factors": POC / "risk_factors_similarity_results_full_history.csv",
}
WINDOWS_TRADING_DAYS = {"12m": 252, "18m": 378}


def compute_windows_n(events: pd.DataFrame, ticker_map: pd.DataFrame, prices: pd.DataFrame, window_trading_days: int) -> pd.DataFrame:
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
        if stock.empty or len(stock) <= window_trading_days:
            continue
        t0 = stock.index[0]
        t1 = stock.index[window_trading_days]
        if t1 > last_date:
            continue
        rows.append({"cd_cvm": row.cd_cvm, "year_curr": row.year_curr, "ticker": row.ticker,
                      "window_start": t0, "window_end": t1})
    return pd.DataFrame(rows)


def build_bhar(sim_path: Path, windows: pd.DataFrame, prices: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    sim = pd.read_csv(sim_path, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    sim["TextChange"] = 1 - sim["cosine_similarity"]
    merged = sim.merge(windows, on=["cd_cvm", "year_curr"], how="inner")

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
                     "TextChange": row.TextChange, "BHAR_raw": float((1 + eps).prod() - 1)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    lo, hi = df["BHAR_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_raw"].clip(lo, hi)
    return df


def hausman(fe_res, re_res) -> tuple[float, float]:
    common = [p for p in fe_res.params.index if p in re_res.params.index]
    b_fe, b_re = fe_res.params[common].values, re_res.params[common].values
    v_fe, v_re = fe_res.cov.loc[common, common].values, re_res.cov.loc[common, common].values
    diff, var_diff = b_fe - b_re, v_fe - v_re
    try:
        stat = float(diff @ np.linalg.inv(var_diff) @ diff)
    except np.linalg.LinAlgError:
        stat = float(diff @ np.linalg.pinv(var_diff) @ diff)
    stat = abs(stat)
    p = float(1 - scipy_stats.chi2.cdf(stat, len(common)))
    return stat, p


def run_company_only(df: pd.DataFrame) -> dict:
    cols = ["cd_cvm", "year_curr", "BHAR_ajustado", "TextChange"] + CONTROLS
    d = df.dropna(subset=cols).drop_duplicates(subset=["cd_cvm", "year_curr"]).copy()
    n_companies = d["cd_cvm"].nunique()
    if n_companies < 5 or len(d) < 20:
        return {"n": len(d), "n_companies": n_companies, "fe_p": np.nan, "re_p": np.nan,
                "hausman_p": np.nan, "chosen": "n/a", "chosen_p": np.nan}
    panel_df = d.set_index(["cd_cvm", "year_curr"])
    formula = "BHAR_ajustado ~ 1 + TextChange + " + " + ".join(CONTROLS)

    fe_res = PanelOLS.from_formula(formula + " + EntityEffects", data=panel_df).fit(cov_type="robust")
    re_res = RandomEffects.from_formula(formula, data=panel_df).fit(cov_type="robust")
    hstat, hp = hausman(fe_res, re_res)
    chosen = "FE" if hp < 0.05 else "RE"
    chosen_res = fe_res if chosen == "FE" else re_res
    return {"n": int(fe_res.nobs), "n_companies": n_companies,
            "fe_p": fe_res.pvalues["TextChange"], "re_p": re_res.pvalues["TextChange"],
            "hausman_p": hp, "chosen": chosen, "chosen_p": chosen_res.pvalues["TextChange"]}


def run_two_way(df: pd.DataFrame) -> dict:
    return _fit_panel(df, "BHAR_ajustado", CONTROLS)


def validate() -> None:
    """Reproduces the two published rows (narrow_annual, 12m and 18m) from
    the ORIGINAL 111-company data, both via the 2-way FE column (previously
    undocumented) and the FE/RE/Hausman columns (previously committed to
    santos_coelho_bhar_ajustado.csv), to confirm this script's logic
    matches before trusting it on the expanded universe."""
    ctrl = pd.read_csv(ROOT / "data" / "interim" / "control_variables.csv").rename(
        columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr"})
    for window in ["12m", "18m"]:
        fname = "abnormal_returns_alpha_narrow_annual.csv" if window == "12m" else "abnormal_returns_alpha_narrow_annual_18m.csv"
        df = pd.read_csv(POC / fname)
        df = df.merge(ctrl, on=["cd_cvm", "year_curr"], how="left")
        df["TextChange"] = 1 - df["cosine_similarity"]
        lo, hi = df["alpha_ar_compound"].quantile([0.01, 0.99])
        df["BHAR_ajustado"] = df["alpha_ar_compound"].clip(lo, hi)
        r2 = run_two_way(df)
        rco = run_company_only(df)
        print(f"[validate] narrow_annual {window}: 2-way FE p={r2['p']:.4f}  "
              f"FE-company p={rco['fe_p']:.4f}  RE-company p={rco['re_p']:.4f}  Hausman p={rco['hausman_p']:.4f}")
    print("[validate] Published Tabela 5.5: 12m -> 0.272 / 0.307 / 0.229 / 0.348; 18m -> 0.104 / 0.071 / 0.192 / 0.469\n")


def main() -> None:
    if "--validate" in sys.argv:
        validate()

    ticker_map = build_full_ticker_map()
    events = load_combined_event_dates()
    prices = load_combined_prices()
    factors = load_factors()
    fund = build_fundamentals_panel_extended().rename(columns={"fiscal_year": "year_curr"})

    rows = []
    for name, sim_path in SOURCES_EXPANDED.items():
        for window_label, wdays in WINDOWS_TRADING_DAYS.items():
            windows = compute_windows_n(events, ticker_map, prices, wdays)
            bhar = build_bhar(sim_path, windows, prices, factors)
            if bhar.empty:
                print(f"{name} {window_label}: no computable observations")
                continue
            panel = bhar.merge(fund, on=["cd_cvm", "year_curr"], how="left")

            r2 = run_two_way(panel)
            rco = run_company_only(panel)
            rows.append({"fonte": name, "janela": window_label,
                         "fe2way_p": r2["p"], "fe_p": rco["fe_p"], "re_p": rco["re_p"],
                         "hausman_p": rco["hausman_p"], "chosen": rco["chosen"], "chosen_p": rco["chosen_p"],
                         "n": rco["n"], "n_companies": rco["n_companies"]})
            print(f"{name:15s} {window_label}: 2-way={r2['p']:.4f}  FE={rco['fe_p']:.4f}  RE={rco['re_p']:.4f}  "
                  f"Hausman={rco['hausman_p']:.4f}  escolhido={rco['chosen']}:{rco['chosen_p']:.4f}  "
                  f"n={rco['n']} empresas={rco['n_companies']}")

    out = pd.DataFrame(rows)
    out_path = POC / "santos_coelho_bhar_ajustado_expanded_universe.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

"""H2 scenario battery: does year-over-year textual similarity correlate
with the analyst consensus EPS revision bracketing the same disclosure
event? Mirrors the H1 rigor progression already applied this session
(signed correlation -> magnitude correlation -> clustered-by-company
regression, with and without controls) across every text source/frequency
combination this project has similarity data for:

  narrow_annual     -- debt note only, annual   (delisted_similarity_results.csv)
  narrow_quarterly  -- debt note only, quarterly (itr_similarity_results.csv)
  whole_notes       -- entire notes document, annual (full_notes_similarity_results_VERIFIED.csv)
  mgmt_report       -- Relatorio da Administracao, annual (mgmt_report_similarity_results.csv)

Outcome variable: see compute_eps_revisions.py's module docstring for the
exact definition and its documented caveat (rolling-series noise around
quarter-end rollovers). Controls, where merged: ln_total_assets, leverage,
roa, past_12m_return (same set validated in the H1 whole-document work --
see reports/wholenote_multivariate_model.md).

A portfolio-sort test (the most rigorous H1 method) is deliberately NOT
attempted here -- it's a returns-specific method (calendar-time long-short
portfolios only make sense for a tradeable outcome). Its cross-sectional
analogue used here instead is a similarity-tercile comparison of mean
revision via Kruskal-Wallis, plus the clustered regression, which is the
same standard applied to the delisting checks throughout this session.

Writes data/interim/poc/h2_eps_revision_battery_results.csv (one row per
scenario x filter-cut x test) and prints a compact summary.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.compute_eps_revisions import (
    compute_revisions,
    load_annual_event_dates,
    load_eps_panel,
    load_quarterly_event_dates,
)

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

CONTROL_COLS = ["ln_total_assets", "leverage", "roa", "past_12m_return"]


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year",
    })


def _delisting_group_map() -> pd.DataFrame:
    """cd_cvm -> stayed/dropped, from the narrow-annual scenario (a
    company-level attribute, so any scenario can borrow it by cd_cvm)."""
    g = pd.read_csv(POC / "delisted_similarity_results.csv")[["cd_cvm", "group"]].drop_duplicates("cd_cvm")
    return g


def _clustered_ols(df: pd.DataFrame, formula: str, cluster_col: str):
    model = smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": df[cluster_col]})
    return model


def run_battery(df: pd.DataFrame, label: str, controls: pd.DataFrame | None) -> list[dict]:
    """df must have cosine_similarity, revision_pct, cd_cvm, group columns
    (controls merged in already if available, else None)."""
    results = []
    have = df.dropna(subset=["cosine_similarity", "revision_pct"]).copy()
    n = len(have)
    n_companies = have["cd_cvm"].nunique()
    base = {"scenario": label, "n_pairs": n, "n_companies": n_companies}

    if n < 10:
        results.append({**base, "test": "coverage_too_low"})
        return results

    pearson_r, pearson_p = stats.pearsonr(have["cosine_similarity"], have["revision_pct"])
    spearman_r, spearman_p = stats.spearmanr(have["cosine_similarity"], have["revision_pct"])
    results.append({**base, "test": "signed_pearson", "stat": pearson_r, "p_value": pearson_p})
    results.append({**base, "test": "signed_spearman", "stat": spearman_r, "p_value": spearman_p})

    mag_r, mag_p = stats.pearsonr(have["cosine_similarity"], have["revision_pct"].abs())
    results.append({**base, "test": "magnitude_pearson", "stat": mag_r, "p_value": mag_p})

    m0 = _clustered_ols(have, "revision_pct ~ cosine_similarity", "cd_cvm")
    results.append({**base, "test": "clustered_ols_no_controls",
                     "stat": m0.params["cosine_similarity"], "p_value": m0.pvalues["cosine_similarity"]})

    if controls is not None:
        have_ctrl = have.dropna(subset=CONTROL_COLS)
        if len(have_ctrl) >= 20:
            formula = "revision_pct ~ cosine_similarity + " + " + ".join(CONTROL_COLS)
            m1 = _clustered_ols(have_ctrl, formula, "cd_cvm")
            results.append({**base, "n_pairs": len(have_ctrl), "test": "clustered_ols_with_controls",
                             "stat": m1.params["cosine_similarity"], "p_value": m1.pvalues["cosine_similarity"]})

    try:
        have["tercile"] = pd.qcut(have["cosine_similarity"], 3, labels=["low", "mid", "high"])
        groups = [g["revision_pct"].values for _, g in have.groupby("tercile", observed=True)]
        kw_stat, kw_p = stats.kruskal(*groups)
        means = have.groupby("tercile", observed=True)["revision_pct"].mean()
        results.append({**base, "test": "tercile_kruskal",
                         "stat": kw_stat, "p_value": kw_p,
                         "note": f"low={means.get('low', np.nan):+.4f} mid={means.get('mid', np.nan):+.4f} high={means.get('high', np.nan):+.4f}"})
    except ValueError:
        pass

    if "group" in have.columns and have["group"].nunique() == 2:
        dropped = have.loc[have["group"] == "dropped_or_delisted", "revision_pct"].dropna()
        stayed = have.loc[have["group"] == "stayed", "revision_pct"].dropna()
        if len(dropped) >= 5 and len(stayed) >= 5:
            u_stat, u_p = stats.mannwhitneyu(dropped, stayed)
            results.append({**base, "test": "delisting_mannwhitney_revision",
                             "stat": dropped.mean() - stayed.mean(), "p_value": u_p,
                             "note": f"dropped_mean={dropped.mean():+.4f} stayed_mean={stayed.mean():+.4f} n_dropped={len(dropped)} n_stayed={len(stayed)}"})
            m2 = _clustered_ols(have.assign(is_dropped=(have["group"] == "dropped_or_delisted").astype(int)),
                                 "revision_pct ~ is_dropped", "cd_cvm")
            results.append({**base, "test": "delisting_clustered_revision",
                             "stat": m2.params["is_dropped"], "p_value": m2.pvalues["is_dropped"]})

    return results


def build_scenario(name: str, sim_path: Path, freq: str, group_map: pd.DataFrame,
                    controls: pd.DataFrame, eps_panel: pd.DataFrame, ticker_map: pd.DataFrame,
                    reliable_filter=None) -> dict[str, pd.DataFrame]:
    sim = pd.read_csv(sim_path)

    if freq == "annual":
        events = load_annual_event_dates()
        merged = sim.merge(events, on=["cd_cvm", "year_curr"], how="inner")
        ctrl_year_col = "year_curr"
    else:
        events = load_quarterly_event_dates()
        merged = sim.merge(events, on=["cd_cvm", "quarter_curr"], how="inner")
        merged["ctrl_year_tmp"] = merged["quarter_curr"].str[:4].astype(int)
        ctrl_year_col = "ctrl_year_tmp"

    result = compute_revisions(merged, eps_panel, ticker_map)
    if "group" not in result.columns:
        result = result.merge(group_map, on="cd_cvm", how="left")

    result = result.merge(
        controls.rename(columns={"ctrl_year": "__ctrl_year__"}),
        left_on=["cd_cvm", ctrl_year_col], right_on=["cd_cvm", "__ctrl_year__"], how="left",
    )

    cuts = {"all": result}
    if reliable_filter is not None:
        cuts["reliable_only"] = reliable_filter(result)

    return cuts


def main() -> None:
    ticker_map = build_ticker_map()
    eps_panel = load_eps_panel()
    controls = _load_controls()
    group_map = _delisting_group_map()

    scenarios = {
        "narrow_annual": dict(
            sim_path=POC / "delisted_similarity_results.csv", freq="annual",
            reliable_filter=lambda d: d[(d["diagnostic_prev"] == "font_heading") & (d["diagnostic_curr"] == "font_heading")],
        ),
        "narrow_quarterly": dict(
            sim_path=POC / "itr_similarity_results.csv", freq="quarterly",
            reliable_filter=lambda d: d[(d["diagnostic_prev"] == "font_heading") & (d["diagnostic_curr"] == "font_heading")],
        ),
        "whole_notes": dict(
            sim_path=POC / "full_notes_similarity_results_VERIFIED.csv", freq="annual",
            reliable_filter=lambda d: d[d["both_ok"] == True],  # noqa: E712
        ),
        "mgmt_report": dict(
            sim_path=POC / "mgmt_report_similarity_results.csv", freq="annual",
            reliable_filter=None,
        ),
    }

    all_results = []
    all_frames = {}
    for name, cfg in scenarios.items():
        cuts = build_scenario(name, cfg["sim_path"], cfg["freq"], group_map, controls, eps_panel, ticker_map,
                               reliable_filter=cfg["reliable_filter"])
        for cut_name, df in cuts.items():
            label = f"{name}__{cut_name}"
            all_frames[label] = df
            res = run_battery(df, label, controls)
            all_results.extend(res)
            print(f"\n=== {label} ===")
            for r in res:
                if r["test"] == "coverage_too_low":
                    print(f"  n={r['n_pairs']} -- too few to test")
                    continue
                note = f"  ({r['note']})" if "note" in r else ""
                print(f"  {r['test']:32s} n={r['n_pairs']:4d}  stat={r['stat']:+.4f}  p={r['p_value']:.4f}{note}")

    results_df = pd.DataFrame(all_results)
    out_path = POC / "h2_eps_revision_battery_results.csv"
    results_df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path} ({len(results_df)} rows)")

    for label, df in all_frames.items():
        safe = label.replace("__", "_")
        df.to_csv(POC / f"h2_eps_revision_{safe}.csv", index=False)


if __name__ == "__main__":
    main()

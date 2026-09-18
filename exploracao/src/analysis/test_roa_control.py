"""Direct empirical answer to a specific question: what is ROA's actual
impact on the project's results? Reruns the clustered-regression tests
(H1 return, H1 delisting, H2 revision) across all applicable text sources
under two control specifications -- the thesis's current default
(leverage + roa + past_12m_return) and the same set with ROA dropped
(leverage + past_12m_return only) -- so the effect of ROA specifically can
be read directly, the same way test_control_specifications.py did for size.

Usage:
    python -u -m src.analysis.test_roa_control
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.test_control_specifications import (
    _delisting_group_map,
    _load_controls,
    _merge_controls,
    clustered_ols,
)

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

WITH_ROA = ["leverage", "roa", "past_12m_return"]
NO_ROA = ["leverage", "past_12m_return"]
SPECS = {"atual (c/ ROA)": WITH_ROA, "sem ROA": NO_ROA}


def run_all() -> pd.DataFrame:
    group_map = _delisting_group_map()
    results = []

    return_scenarios = {
        "narrow_annual": (POC / "abnormal_returns_poc.csv", "year_curr"),
        "narrow_quarterly": (POC / "abnormal_returns_itr.csv", "quarter_curr"),
        "whole_notes": (POC / "abnormal_returns_full_notes_VERIFIED.csv", "year_curr"),
        "mgmt_report": (POC / "abnormal_returns_mgmt_report.csv", "year_curr"),
        "risk_factors": (POC / "abnormal_returns_risk_factors.csv", "year_curr"),
    }
    for name, (path, ycol) in return_scenarios.items():
        df = pd.read_csv(path)
        if ycol == "quarter_curr":
            df["ctrl_year"] = df["quarter_curr"].str[:4].astype(int)
            merged = df.merge(_load_controls(), on=["cd_cvm", "ctrl_year"], how="left")
        else:
            merged = _merge_controls(df, ctrl_year_col="year_curr")
        for spec_name, cols in SPECS.items():
            coef, p, n = clustered_ols(merged, "abnormal_return", "cosine_similarity", cols)
            results.append({"family": "H1_return", "scenario": name, "controles": spec_name, "n": n, "coef": coef, "p_valor": p})

    delisting_scenarios = {
        "narrow_annual": POC / "delisted_similarity_results.csv",
        "whole_notes": POC / "full_notes_similarity_results_VERIFIED.csv",
        "mgmt_report": POC / "mgmt_report_similarity_results.csv",
        "risk_factors": POC / "risk_factors_similarity_results.csv",
    }
    for name, path in delisting_scenarios.items():
        df = pd.read_csv(path)
        if "group" not in df.columns:
            df = df.merge(group_map, on="cd_cvm", how="left")
        df["is_dropped"] = (df["group"] == "dropped_or_delisted").astype(int)
        merged = _merge_controls(df, ctrl_year_col="year_curr")
        for spec_name, cols in SPECS.items():
            coef, p, n = clustered_ols(merged, "is_dropped", "cosine_similarity", cols)
            results.append({"family": "H1_delisting", "scenario": name, "controles": spec_name, "n": n, "coef": coef, "p_valor": p})

    h2_scenarios = {
        "narrow_annual": POC / "h2_eps_revision_narrow_annual_all.csv",
        "narrow_quarterly": POC / "h2_eps_revision_narrow_quarterly_all.csv",
        "whole_notes": POC / "h2_eps_revision_whole_notes_all.csv",
        "mgmt_report": POC / "h2_eps_revision_mgmt_report_all.csv",
    }
    for name, path in h2_scenarios.items():
        df = pd.read_csv(path)
        for spec_name, cols in SPECS.items():
            coef, p, n = clustered_ols(df, "revision_pct", "cosine_similarity", cols)
            results.append({"family": "H2_revision", "scenario": name, "controles": spec_name, "n": n, "coef": coef, "p_valor": p})

    return pd.DataFrame(results)


def main() -> None:
    results = run_all()
    out_path = POC / "roa_control_comparison.csv"
    results.to_csv(out_path, index=False)

    pd.set_option("display.width", 160)
    piv = results.pivot_table(index=["family", "scenario"], columns="controles", values="p_valor", aggfunc="first")
    piv = piv[["atual (c/ ROA)", "sem ROA"]]
    print(piv.round(4).to_string())
    print(f"\nWrote {out_path}")

    flips = []
    for (family, scenario), row in piv.iterrows():
        with_roa, no_roa = row["atual (c/ ROA)"], row["sem ROA"]
        if pd.notna(with_roa) and pd.notna(no_roa) and (with_roa < 0.05) != (no_roa < 0.05):
            flips.append((family, scenario, with_roa, no_roa))
    print("\nCenários onde a significância muda ao remover ROA (cruza o limiar de 5%):")
    if flips:
        for f in flips:
            direction = "nao-sig -> sig" if f[3] < 0.05 else "sig -> nao-sig"
            print(f"  {f[0]} / {f[1]}: p(c/ ROA)={f[2]:.4f} -> p(sem ROA)={f[3]:.4f}  [{direction}]")
    else:
        print("  nenhum")


if __name__ == "__main__":
    main()

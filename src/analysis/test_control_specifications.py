"""Direct empirical answer to a specific question: if "size" (ln_total_assets)
is dropped from the control set entirely and only leverage/roa/past_12m_return
are kept, does any scenario tested this session become statistically
relevant that wasn't before? Re-runs the clustered-regression tests for H1
returns, the delisting/survivorship validity check, and H2 EPS revision
under three control specifications -- none, full (ln_total_assets +
leverage + roa + past_12m_return), and no_size (leverage + roa +
past_12m_return) -- across every text source, so the effect of dropping
size can be read directly rather than argued about in the abstract.

All three outcome families reuse already-computed data (no new
acquisition, no new similarity computation): H1 return scenarios read the
abnormal-return CSVs built earlier this session; the delisting check reads
the same similarity CSVs used throughout the project (is_dropped as
outcome, cosine_similarity as predictor -- a linear probability model with
clustered SEs, matching the "similarity coefficient" framing in
reports/wholenote_multivariate_model.md); H2 reads the merged
h2_eps_revision_*_all.csv files from run_h2_scenarios.py, which already
carry the control columns.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

FULL_CONTROLS = ["ln_total_assets", "leverage", "roa", "past_12m_return"]
NO_SIZE_CONTROLS = ["leverage", "roa", "past_12m_return"]
SPECS = {"none": [], "full_with_size": FULL_CONTROLS, "no_size": NO_SIZE_CONTROLS}


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year",
    })


def _delisting_group_map() -> pd.DataFrame:
    return pd.read_csv(POC / "delisted_similarity_results.csv")[["cd_cvm", "group"]].drop_duplicates("cd_cvm")


def _merge_controls(df: pd.DataFrame, ctrl_year_col: str) -> pd.DataFrame:
    controls = _load_controls()
    return df.merge(controls, left_on=["cd_cvm", ctrl_year_col], right_on=["cd_cvm", "ctrl_year"], how="left")


def clustered_ols(df: pd.DataFrame, outcome: str, predictor: str, controls: list[str], cluster_col: str = "cd_cvm"):
    cols = [outcome, predictor, cluster_col] + controls
    have = df.dropna(subset=cols)
    if len(have) < 20 or have[cluster_col].nunique() < 5:
        return None, None, len(have)
    formula = f"{outcome} ~ {predictor}" + "".join(f" + {c}" for c in controls)
    model = smf.ols(formula, data=have).fit(cov_type="cluster", cov_kwds={"groups": have[cluster_col]})
    return model.params[predictor], model.pvalues[predictor], len(have)


def run_all() -> pd.DataFrame:
    group_map = _delisting_group_map()
    results = []

    return_scenarios = {
        "narrow_annual": (POC / "abnormal_returns_poc.csv", "year_curr"),
        "narrow_quarterly": (POC / "abnormal_returns_itr.csv", "quarter_curr"),
        "whole_notes": (POC / "abnormal_returns_full_notes_VERIFIED.csv", "year_curr"),
        "mgmt_report": (POC / "abnormal_returns_mgmt_report.csv", "year_curr"),
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
            results.append({"family": "H1_return", "scenario": name, "controls": spec_name, "n": n, "coef": coef, "p_value": p})

    delisting_scenarios = {
        "narrow_annual": POC / "delisted_similarity_results.csv",
        "whole_notes": POC / "full_notes_similarity_results_VERIFIED.csv",
        "mgmt_report": POC / "mgmt_report_similarity_results.csv",
    }
    for name, path in delisting_scenarios.items():
        df = pd.read_csv(path)
        if "group" not in df.columns:
            df = df.merge(group_map, on="cd_cvm", how="left")
        df["is_dropped"] = (df["group"] == "dropped_or_delisted").astype(int)
        merged = _merge_controls(df, ctrl_year_col="year_curr")
        for spec_name, cols in SPECS.items():
            coef, p, n = clustered_ols(merged, "is_dropped", "cosine_similarity", cols)
            results.append({"family": "H1_delisting", "scenario": name, "controls": spec_name, "n": n, "coef": coef, "p_value": p})

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
            results.append({"family": "H2_revision", "scenario": name, "controls": spec_name, "n": n, "coef": coef, "p_value": p})

    return pd.DataFrame(results)


def main() -> None:
    results = run_all()
    out_path = POC / "control_specification_comparison.csv"
    results.to_csv(out_path, index=False)

    pd.set_option("display.width", 160)
    piv = results.pivot_table(index=["family", "scenario"], columns="controls", values="p_value", aggfunc="first")
    piv = piv[["none", "full_with_size", "no_size"]]
    print(piv.round(4).to_string())
    print(f"\nWrote {out_path}")

    flips = []
    for (family, scenario), row in piv.iterrows():
        if pd.notna(row["full_with_size"]) and pd.notna(row["no_size"]):
            if row["full_with_size"] >= 0.05 and row["no_size"] < 0.05:
                flips.append((family, scenario, row["full_with_size"], row["no_size"]))
    print("\nScenarios where dropping size flips non-significant -> significant:")
    if flips:
        for f in flips:
            print(f"  {f[0]} / {f[1]}: p(with size)={f[2]:.4f} -> p(no size)={f[3]:.4f}")
    else:
        print("  none")


if __name__ == "__main__":
    main()

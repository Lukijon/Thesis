"""Extended test battery for the v2 (4-year, leadership-diversity) dataset.
Same rigor discipline as v1 and the main thesis: simple correlation, then
clustered-by-company OLS with and without controls. Also attempts a
company fixed-effects panel now that there are 4 years instead of 2 --
still thin compared to the main thesis's 10-year panel, so treated as
informative, not definitive.

Usage:
    python -m sidequest.test_diversity_hypotheses_v2
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sidequest" / "diversity_analysis_dataset_v2.csv"
CONTROLS = ["ln_total_assets", "leverage", "roa"]

PREDICTORS = {
    "pct_female_board": "Board: % female",
    "pct_black_brown_board": "Board: % Black/Brown",
    "has_black_brown_board": "Board: has any Black/Brown member (0/1)",
    "pct_female_exec": "Executive board: % female",
    "pct_black_brown_exec": "Executive board: % Black/Brown",
    "pct_female_leadership": "Workforce leadership: % female",
    "pct_black_brown_leadership": "Workforce leadership: % Black/Brown",
}
OUTCOMES = {
    "cost_of_debt_proxy": "Cost of debt proxy",
    "return_volatility": "Return volatility (annualized)",
}


def clustered_ols(df: pd.DataFrame, outcome: str, predictor: str, controls: list[str]):
    cols = [outcome, predictor, "CD_CVM"] + controls
    have = df.dropna(subset=cols)
    if len(have) < 20 or have["CD_CVM"].nunique() < 10:
        return None, None, len(have)
    formula = f"{outcome} ~ {predictor}" + "".join(f" + {c}" for c in controls)
    model = smf.ols(formula, data=have).fit(cov_type="cluster", cov_kwds={"groups": have["CD_CVM"]})
    return model.params[predictor], model.pvalues[predictor], len(have)


def try_fixed_effects(df: pd.DataFrame, outcome: str, predictor: str, controls: list[str]):
    try:
        from linearmodels.panel import PanelOLS
    except ImportError:
        return None, None, None
    cols = ["CD_CVM", "year", outcome, predictor] + controls
    have = df.dropna(subset=cols).drop_duplicates(subset=["CD_CVM", "year"])
    if len(have) < 30 or have["CD_CVM"].nunique() < 10 or have["year"].nunique() < 2:
        return None, None, None
    panel_df = have.set_index(["CD_CVM", "year"])
    formula = f"{outcome} ~ 1 + {predictor} + " + " + ".join(controls) + " + EntityEffects + TimeEffects"
    try:
        mod = PanelOLS.from_formula(formula, data=panel_df)
        res = mod.fit(cov_type="clustered", cluster_entity=True)
        return res.params[predictor], res.pvalues[predictor], int(res.nobs)
    except Exception:
        return None, None, None


def main() -> None:
    df = pd.read_csv(DATA)
    results = []

    for outcome in OUTCOMES:
        print(f"\n=== Outcome: {OUTCOMES[outcome]} ===")
        for predictor in PREDICTORS:
            have = df.dropna(subset=[outcome, predictor])
            if len(have) < 20:
                continue
            r, p = stats.pearsonr(have[predictor], have[outcome])
            coef0, p0, n0 = clustered_ols(df, outcome, predictor, [])
            coef1, p1, n1 = clustered_ols(df, outcome, predictor, CONTROLS)
            fe_coef, fe_p, fe_n = try_fixed_effects(df, outcome, predictor, CONTROLS)
            row = {
                "outcome": outcome, "predictor": predictor, "n_simple": len(have),
                "simple_r": r, "simple_p": p,
                "clustered_no_controls_p": p0, "n_clustered": n0,
                "clustered_with_controls_p": p1, "n_full": n1,
                "fe_coef": fe_coef, "fe_p": fe_p, "fe_n": fe_n,
            }
            results.append(row)
            flag = " <=====" if (p1 is not None and p1 < 0.10) else ""
            fe_str = f"  FE p={fe_p:.3f}" if fe_p is not None else "  FE n/a"
            print(f"  {PREDICTORS[predictor]:38s} n={len(have):3d}  simple r={r:+.3f} (p={p:.3f})  "
                  f"clustered p={p0:.3f}  +ctrl p={p1 if p1 is not None else float('nan'):.3f}{fe_str}{flag}")

    out = pd.DataFrame(results)
    out.to_csv(ROOT / "sidequest" / "diversity_test_results_v2.csv", index=False)
    print(f"\nWrote sidequest/diversity_test_results_v2.csv ({len(out)} rows)")


if __name__ == "__main__":
    main()

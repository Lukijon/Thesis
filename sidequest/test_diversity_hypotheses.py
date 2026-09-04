"""Tests board gender/racial diversity against cost of debt and return
volatility -- the two outcomes not yet covered by the (already fairly
thorough) Brazilian gender-diversity-and-performance literature, and an
outcome family essentially untested for race specifically (see
sidequest/README.md for the literature scan this follows up on).

Same rigor discipline as the main thesis: simple correlation, then
clustered-by-company OLS with and without controls. Company+year fixed
effects are not attempted -- with only 2 fiscal years and board
composition that barely moves year to year for most firms, there is
essentially no within-company variation to identify from (unlike the main
thesis's 5-10-year panels).

Usage:
    python -m sidequest.test_diversity_hypotheses
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sidequest" / "diversity_analysis_dataset.csv"
CONTROLS = ["ln_total_assets", "leverage", "roa"]

PREDICTORS = {
    "pct_female_board": "Board: % female",
    "pct_black_brown_board": "Board: % Black/Brown",
    "has_black_brown_board": "Board: has any Black/Brown member (0/1)",
    "pct_female_exec": "Executive board: % female",
    "pct_black_brown_exec": "Executive board: % Black/Brown",
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
            row = {
                "outcome": outcome, "predictor": predictor, "n_simple": len(have),
                "simple_r": r, "simple_p": p,
                "clustered_no_controls_coef": coef0, "clustered_no_controls_p": p0, "n_clustered": n0,
                "clustered_with_controls_coef": coef1, "clustered_with_controls_p": p1, "n_full": n1,
            }
            results.append(row)
            flag = " <=====" if (p1 is not None and p1 < 0.10) else ""
            print(f"  {PREDICTORS[predictor]:42s} n={len(have):3d}  simple r={r:+.3f} (p={p:.3f})  "
                  f"clustered p={p0:.3f}  clustered+ctrl p={p1 if p1 is not None else float('nan'):.3f}{flag}")

    out = pd.DataFrame(results)
    out.to_csv(ROOT / "sidequest" / "diversity_test_results.csv", index=False)
    print(f"\nWrote sidequest/diversity_test_results.csv ({len(out)} rows)")


if __name__ == "__main__":
    main()

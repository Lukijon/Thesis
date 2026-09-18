"""The calendar-time long-short portfolio sort (src/analysis/portfolio_sort.py)
was originally built and reported (reports/return_predictability_exploration.md,
Secao 5.3) under the OLD market-adjusted-return era of this project, and was
never re-run under the definitive specification adopted in Secao 3.3/3.5
(BHAR ajustado: an out-of-sample residual from a per-stock NEFIN 4-factor
model). The only portfolio-sort result quoted in the thesis (Secao 5.3) is
for a since-discarded mgmt_report finding under that old specification, not
for the narrow debt note under the current one -- a real gap between what
Secao 3.7 ("terceira verificacao") describes as a general check on H1's
identification strategy and what Capitulo 5 actually shows.

This closes that gap the standard way a calendar-time portfolio is made
consistent with a 4-factor abnormal-return model in the asset-pricing
literature: instead of testing the mean of the raw long-short (L-S) return
(portfolio_sort.run_portfolio_sort's approach), the L-S return series is
regressed on the same four NEFIN factors used to build BHAR ajustado
(Rm_minus_Rf, SMB, HML, WML); the regression's intercept is the L-S
portfolio's 4-factor alpha, and its significance (Newey-West HAC, 3 lags,
matching the existing test) is the portfolio-level analog of a significant
BHAR ajustado coefficient. No subtraction of Risk_Free from the L-S return
is needed -- it is already a self-financing, zero-cost combination (long
financed by the short leg), the standard treatment for factor-model tests
of long-short portfolios in this literature (e.g. Fama & French's own
time-series tests of zero-cost portfolios).

Scope: narrow_annual only (delisted_similarity_results_reliable.csv, the
same reliable full-universe sample behind Tabela 5.1's "Nota de divida
(anual)" row) -- this is specifically the gap Secao 3.7 leaves open for the
dissertation's principal text source, not a re-run of the whole
return_predictability_exploration.md grid.

Usage:
    python -u -m src.analysis.run_portfolio_sort_alpha
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.portfolio_sort import load_monthly_returns, run_portfolio_sort
from src.analysis.run_portfolio_sorts import attach_tickers, prep_annual_events

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"
FACTORS_PATH = ROOT / "data" / "raw" / "market" / "factors" / "nefin_factors.csv"
FACTOR_COLS = ["Rm_minus_Rf", "SMB", "HML", "WML"]


def load_monthly_factors() -> pd.DataFrame:
    """Compounds NEFIN's daily factors to month-end, same convention as the
    daily-to-event-window compounding in compute_alpha_abnormal_returns.py."""
    f = pd.read_csv(FACTORS_PATH)
    f["date"] = pd.to_datetime(f["Date"])
    f = f.set_index("date").sort_index()[FACTOR_COLS]
    monthly = (1 + f).resample("ME").prod() - 1
    return monthly


def alpha_test(ls_series: pd.DataFrame, monthly_factors: pd.DataFrame) -> dict:
    df = ls_series[["ls_return"]].join(monthly_factors, how="inner").dropna()
    if len(df) < 12:
        return {"n_months_factor_model": len(df), "error": "too few overlapping months"}
    X = sm.add_constant(df[FACTOR_COLS])
    model = sm.OLS(df["ls_return"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    return {
        "n_months_factor_model": len(df),
        "alpha_monthly": float(model.params["const"]),
        "alpha_annualized": float((1 + model.params["const"]) ** 12 - 1),
        "t_stat_alpha": float(model.tvalues["const"]),
        "p_value_alpha": float(model.pvalues["const"]),
        "beta_mkt": float(model.params["Rm_minus_Rf"]),
        "beta_smb": float(model.params["SMB"]),
        "beta_hml": float(model.params["HML"]),
        "beta_wml": float(model.params["WML"]),
    }


def main() -> None:
    ticker_map = build_ticker_map()
    monthly_ret, ibov_monthly = load_monthly_returns()
    monthly_factors = load_monthly_factors()

    events = prep_annual_events("delisted_similarity_results_reliable.csv")
    events = attach_tickers(events, ticker_map)
    print(f"{events.dropna(subset=['ticker', 'entry_month', 'cosine_similarity']).shape[0]} "
          f"narrow-annual reliable events with ticker + entry month (of {len(events)} total)")

    rows = []
    print("\n=== Raw L-S mean return (original test) vs. 4-factor alpha (BHAR-consistent) ===")
    for holding in [3, 6, 12]:
        for n_groups in [2, 3]:
            r_raw = run_portfolio_sort(events, monthly_ret, ibov_monthly, holding_months=holding, n_groups=n_groups)
            if r_raw.get("n_months", 0) == 0:
                print(f"hold={holding:2d}mo groups={n_groups}  -- {r_raw.get('error')}")
                continue
            r_alpha = alpha_test(r_raw["ls_series"], monthly_factors)
            row = {"scenario": "narrow_annual_reliable", "holding_months": holding, "n_groups": n_groups,
                   "n_months_raw": r_raw["n_months"], "avg_n_active": r_raw["avg_n_active"],
                   "annualized_ls_return_raw": r_raw["annualized_ls_return"],
                   "t_stat_raw_mean": r_raw["t_stat_newey_west"], "p_value_raw_mean": r_raw["p_value"],
                   **r_alpha}
            rows.append(row)
            flag_raw = " <=====" if r_raw["p_value"] < 0.10 else ""
            flag_alpha = " <=====" if r_alpha.get("p_value_alpha", 1) < 0.10 else ""
            print(f"hold={holding:2d}mo groups={n_groups}  n_months={r_raw['n_months']:3d}  avg_n={r_raw['avg_n_active']:.0f}  "
                  f"| raw: ann_LS={r_raw['annualized_ls_return']:+7.1%} t={r_raw['t_stat_newey_west']:+.2f} p={r_raw['p_value']:.4f}{flag_raw}  "
                  f"| alpha: ann_alpha={r_alpha.get('alpha_annualized', float('nan')):+7.1%} "
                  f"t={r_alpha.get('t_stat_alpha', float('nan')):+.2f} p={r_alpha.get('p_value_alpha', float('nan')):.4f}{flag_alpha}")

    out = pd.DataFrame(rows)
    out_path = POC / "portfolio_sort_alpha_narrow_annual.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")

    headline = out[(out["holding_months"] == 12) & (out["n_groups"] == 3)]
    if len(headline):
        h = headline.iloc[0]
        print(f"\nHeadline (12mo, 3 groups, matching BHAR's own horizon): "
              f"n_months={h['n_months_raw']:.0f}, alpha anualizado={h['alpha_annualized']:+.1%}, "
              f"t={h['t_stat_alpha']:+.2f}, p={h['p_value_alpha']:.4f}")


if __name__ == "__main__":
    main()

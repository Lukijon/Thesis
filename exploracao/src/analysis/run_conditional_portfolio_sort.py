"""Bridges the two disagreeing tests from reports/control_specification_test.md:
the management-report *return* clustered regression is significant
(p=0.03) but only once leverage/ROA/past-return are added as controls; the
unconditional portfolio sort (src/analysis/run_mgmt_report_portfolio_sort.py)
is null across all 9 holding-period x group-count combinations. A plain
double sort (bucket on one control, then similarity within it) doesn't
scale to three controls at once without fragmenting the ~50-name monthly
cross-section into empty cells, so this uses the standard alternative for
"control for several continuous characteristics inside a portfolio sort":
characteristic-adjust the returns first, then sort the residual.

Each calendar month, the active firms' realized returns are cross-
sectionally regressed on leverage/ROA/past_12m_return (a fresh OLS fit
every month, no clustering needed -- it's a single month's cross-section);
the residuals -- return with the linear effect of those three controls
removed -- are what gets sorted into similarity groups and long-short'd.
This is the closest a portfolio sort can get to "conditional on
leverage/ROA/past-return", the same conditioning set the regression uses
(size deliberately excluded throughout, per the decision in
control_specification_test.md that it isn't doing meaningful work here).

If the long-short spread on these residual returns is significant, the
regression result is corroborated by an independent method and the
"only shows up conditional on controls" reading holds up as a real,
if bounded, result. If it's still null, the regression result likely
doesn't survive outside that one specification.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.portfolio_sort import load_monthly_returns
from src.analysis.run_portfolio_sorts import attach_tickers, prep_annual_events

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POC = Path("data/interim/poc")
INTERIM = Path("data/interim")
CONTROL_COLS = ["leverage", "roa", "past_12m_return"]
MIN_CROSS_SECTION = 12  # >= 4x the number of regressors (3 controls + intercept), for a stable monthly fit


def run_characteristic_adjusted_sort(
    events: pd.DataFrame,
    monthly_ret: pd.DataFrame,
    ibov_monthly: pd.Series,
    holding_months: int = 12,
    n_groups: int = 3,
    min_group_size: int = 3,
) -> dict:
    """Same active-set/vintage/ranking mechanics as portfolio_sort.run_portfolio_sort,
    except the long-short spread is computed on returns residualized against
    CONTROL_COLS within each month's cross-section, instead of raw returns.
    events must additionally carry CONTROL_COLS (already merged in)."""
    events = events.dropna(subset=["ticker", "entry_month", "cosine_similarity", *CONTROL_COLS]).copy()
    events["ticker"] = events["ticker"] + " BS Equity"
    events = events[events["ticker"].isin(monthly_ret.columns)]

    all_months = sorted(monthly_ret.index)
    ls_returns = []
    diagnostics = []
    months_skipped_thin_cross_section = 0

    for month in all_months:
        window_start = month - pd.DateOffset(months=holding_months)
        active = events[(events["entry_month"] > window_start) & (events["entry_month"] <= month)]
        if len(active) < min_group_size * n_groups:
            continue
        active = active.drop_duplicates(subset=["ticker"], keep="last").copy()

        rets = monthly_ret.loc[month, [t for t in active["ticker"] if t in monthly_ret.columns]].dropna()
        active = active[active["ticker"].isin(rets.index)]
        active["ret"] = active["ticker"].map(rets)

        cross = active.dropna(subset=["ret", *CONTROL_COLS])
        if len(cross) < MIN_CROSS_SECTION:
            months_skipped_thin_cross_section += 1
            continue

        X = sm.add_constant(cross[CONTROL_COLS].astype(float))
        model = sm.OLS(cross["ret"].astype(float), X).fit()
        cross = cross.copy()
        cross["resid_ret"] = model.resid

        try:
            cross["group"] = pd.qcut(cross["cosine_similarity"], n_groups, labels=False, duplicates="drop")
        except ValueError:
            continue
        if cross["group"].nunique() < n_groups:
            continue

        group_means = cross.groupby("group")["resid_ret"].mean()
        high_sim = group_means.get(n_groups - 1)
        low_sim = group_means.get(0)
        if pd.isna(high_sim) or pd.isna(low_sim):
            continue

        ls_returns.append({
            "month": month,
            "ls_return": high_sim - low_sim,
            "high_sim_return": high_sim,
            "low_sim_return": low_sim,
            "ibov_return": ibov_monthly.get(month, np.nan),
            "n_active": len(cross),
        })
        diagnostics.append(len(cross))

    if not ls_returns:
        return {"n_months": 0, "error": "no months had enough active positions with valid controls"}

    ls_df = pd.DataFrame(ls_returns).set_index("month")
    mean_ls = ls_df["ls_return"].mean()
    X = np.ones(len(ls_df))
    model = sm.OLS(ls_df["ls_return"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    return {
        "n_months": len(ls_df),
        "months_skipped_thin_cross_section": months_skipped_thin_cross_section,
        "avg_n_active": np.mean(diagnostics),
        "mean_monthly_ls_return": mean_ls,
        "annualized_ls_return": (1 + mean_ls) ** 12 - 1,
        "t_stat_newey_west": model.tvalues.iloc[0],
        "p_value": model.pvalues.iloc[0],
        "ls_series": ls_df,
    }


def main() -> None:
    ticker_map = build_ticker_map()
    monthly_ret, ibov_monthly = load_monthly_returns()
    ctrl = pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr"})

    events = prep_annual_events("mgmt_report_similarity_results.csv")
    events = attach_tickers(events, ticker_map)
    events = events.merge(ctrl[["cd_cvm", "year_curr", *CONTROL_COLS]], on=["cd_cvm", "year_curr"], how="left")
    print(f"{events.dropna(subset=['ticker', *CONTROL_COLS]).shape[0]} mgmt-report events with ticker + full controls (of {len(events)} total)")

    print("\n=== Characteristic-adjusted sort (residualized on leverage/roa/past_12m_return) ===")
    results = []
    for holding in [3, 6, 12]:
        for n_groups in [2, 3, 4]:
            r = run_characteristic_adjusted_sort(events, monthly_ret, ibov_monthly, holding_months=holding, n_groups=n_groups)
            row = {k: v for k, v in r.items() if k != "ls_series"}
            row.update({"scenario": "mgmt_report_annual_CHAR_ADJUSTED", "holding_months": holding, "n_groups": n_groups})
            results.append(row)
            if r.get("n_months", 0) > 0:
                flag = " <=====" if r["p_value"] < 0.10 else ""
                print(f"hold={holding:2d}mo groups={n_groups}  n_months={r['n_months']:3d}  "
                      f"avg_n={r['avg_n_active']:.0f}  skipped_thin={r['months_skipped_thin_cross_section']:3d}  "
                      f"ann_LS={r['annualized_ls_return']:+7.1%}  t={r['t_stat_newey_west']:+.2f}  p={r['p_value']:.4f}{flag}")
            else:
                print(f"hold={holding:2d}mo groups={n_groups}  -- {r.get('error')}")

    new_df = pd.DataFrame(results)
    grid_path = POC / "portfolio_sort_grid_results.csv"
    existing = pd.read_csv(grid_path)
    combined = pd.concat([existing, new_df], ignore_index=True, sort=False)
    combined.to_csv(grid_path, index=False)
    print(f"\nAppended {len(new_df)} rows to {grid_path}")


if __name__ == "__main__":
    main()

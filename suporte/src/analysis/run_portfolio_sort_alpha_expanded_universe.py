"""Extends run_portfolio_sort_alpha.py's calendar-time long-short
portfolio sort (4-factor alpha version, consistent with BHAR ajustado)
to the full round-7 expanded universe (185 companies, 2010-2025), using
the same reliable narrow-annual sample as Tabela 5.1's "Nota de divida
(anual)" row.

Reuses portfolio_sort.run_portfolio_sort unchanged (it only needs a
monthly-return matrix + an events frame with ticker/entry_month/
cosine_similarity -- both source-agnostic), swapping in the combined
ticker map, combined monthly prices, and combined event dates built for
the rest of the expanded-universe pipeline.

Usage:
    python -u -m src.analysis.run_portfolio_sort_alpha_expanded_universe
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from src.analysis.compute_new_universe_returns import build_full_ticker_map, load_combined_event_dates, load_combined_prices
from src.analysis.portfolio_sort import run_portfolio_sort
from src.analysis.run_portfolio_sort_alpha import alpha_test, load_monthly_factors
from src.analysis.run_portfolio_sorts import attach_tickers

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"
SIM_CSV = POC / "similarity_results_full_history_reliable.csv"


def load_monthly_returns_combined() -> tuple[pd.DataFrame, pd.Series]:
    prices = load_combined_prices()
    monthly_px = prices.resample("ME").last()
    monthly_ret = monthly_px.pct_change(fill_method=None)

    ibov = pd.read_csv(ROOT / "data" / "raw" / "market" / "prices" / "ibov_index_bloomberg.csv",
                        skiprows=[1]).rename(columns={"Unnamed: 0": "date", "IBOV Index": "ibov"})
    ibov["date"] = pd.to_datetime(ibov["date"], format="%m/%d/%Y")
    ibov["ibov"] = pd.to_numeric(ibov["ibov"], errors="coerce")
    ibov = ibov.set_index("date").sort_index()["ibov"]
    ibov_monthly = ibov.resample("ME").last().pct_change()
    return monthly_ret, ibov_monthly


def prep_annual_events_expanded() -> pd.DataFrame:
    sim = pd.read_csv(SIM_CSV, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    events_dates = load_combined_event_dates().rename(columns={"event_date": "filing_date"})
    events = sim.merge(events_dates, on=["cd_cvm", "year_curr"], how="left")
    events["entry_month"] = (events["filing_date"] + pd.offsets.MonthBegin(1)).dt.to_period("M").dt.to_timestamp("M")
    return events


def main() -> None:
    ticker_map = build_full_ticker_map()
    monthly_ret, ibov_monthly = load_monthly_returns_combined()
    monthly_factors = load_monthly_factors()

    events = prep_annual_events_expanded()
    events = attach_tickers(events, ticker_map)
    print(f"{events.dropna(subset=['ticker', 'entry_month', 'cosine_similarity']).shape[0]} "
          f"narrow-annual reliable events with ticker + entry month (of {len(events)} total, expanded universe)")

    rows = []
    print("\n=== Raw L-S mean return (original test) vs. 4-factor alpha (BHAR-consistent) ===")
    for holding in [3, 6, 12]:
        for n_groups in [2, 3]:
            r_raw = run_portfolio_sort(events, monthly_ret, ibov_monthly, holding_months=holding, n_groups=n_groups)
            if r_raw.get("n_months", 0) == 0:
                print(f"hold={holding:2d}mo groups={n_groups}  -- {r_raw.get('error')}")
                continue
            r_alpha = alpha_test(r_raw["ls_series"], monthly_factors)
            row = {"scenario": "narrow_annual_reliable_expanded", "holding_months": holding, "n_groups": n_groups,
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
    out_path = POC / "portfolio_sort_alpha_narrow_annual_expanded_universe.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")

    headline = out[(out["holding_months"] == 12) & (out["n_groups"] == 3)]
    if len(headline):
        h = headline.iloc[0]
        print(f"\nHeadline (12mo, 3 groups, matching BHAR's own horizon): "
              f"n_months={h['n_months_raw']:.0f}, alpha anualizado={h['alpha_annualized']:+.1%}, "
              f"t={h['t_stat_alpha']:+.2f}, p={h['p_value_alpha']:.4f}")

    # Robustness: exclude degenerate-similarity events at the headline setting
    clean_events = events[(events["cosine_similarity"] > 0.001) & (events["cosine_similarity"] < 0.999)]
    n_excluded = len(events) - len(clean_events)
    r_raw_clean = run_portfolio_sort(clean_events, monthly_ret, ibov_monthly, holding_months=12, n_groups=3)
    if r_raw_clean.get("n_months", 0) > 0:
        r_alpha_clean = alpha_test(r_raw_clean["ls_series"], monthly_factors)
        print(f"\nExcluding {n_excluded} degenerate-similarity events (12mo, 3 groups): "
              f"p={r_alpha_clean.get('p_value_alpha', float('nan')):.4f}")


if __name__ == "__main__":
    main()

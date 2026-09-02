"""H2 outcome variable: analyst consensus EPS revision bracketing each
filing's disclosure date, from data/raw/analysts/eps_consensus_bloomberg.csv
(Bloomberg IS_EPS, fpt=Q, ae=E -- a rolling near-term-quarter consensus
snapshot roughly every 3 months, confirmed by the user as "historical
quarterly eps estimation for each quarter").

Measurement choice, stated plainly: this is a ROLLING series (the row's
value is the consensus for whichever quarter Bloomberg treats as "current"
at that date), not a fixed-target-period series re-sampled over time. That
means a pre/post pair bracketing a disclosure date can span a quarter-end
rollover unrelated to the company's own filing -- a source of noise this
measure can't remove. It's the best construct available from what was
exported (no per-target-period history), so it's used as-is and this
caveat should travel with any result built on it, the same way the round-3
"promising, not yet settled" finding and the return-predictability null
results were reported with their own caveats rather than smoothed over.

Revision definition, mirroring how compute_abnormal_returns.py brackets a
forward return window from the same event date:
  - pre_eps  = last consensus snapshot on or before the event date
  - post_eps = first consensus snapshot after the event date, within
    EPS_WINDOW_DAYS (default 140 -- one ~91-day quarterly cycle plus a
    buffer for the occasional skipped/duplicate snapshot date observed in
    the raw export)
  - revision_raw = post_eps - pre_eps
  - revision_pct = revision_raw / |pre_eps|, only where |pre_eps| > 0.01
    (avoids blow-ups from near-zero consensus EPS, which happen for a few
    company-years around losses)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

EPS_WINDOW_DAYS = 140


def load_eps_panel() -> pd.DataFrame:
    """Long-format (ticker, date, eps_est), cleaned and sorted."""
    df = pd.read_csv(RAW / "analysts" / "eps_consensus_bloomberg.csv", skiprows=[1])
    df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    long = df.melt(id_vars="date", var_name="ticker_col", value_name="eps_est")
    long["ticker"] = long["ticker_col"].str.replace(" BS Equity", "", regex=False)
    long["eps_est"] = pd.to_numeric(long["eps_est"], errors="coerce")
    long = long.dropna(subset=["eps_est"]).drop(columns="ticker_col")
    return long.sort_values(["ticker", "date"]).reset_index(drop=True)


def _bracket(series: pd.DataFrame, event_date: pd.Timestamp, window_days: int):
    pre = series[series["date"] <= event_date]
    post = series[(series["date"] > event_date) & (series["date"] <= event_date + pd.Timedelta(days=window_days))]
    if pre.empty or post.empty:
        return None
    pre_row = pre.iloc[-1]
    post_row = post.iloc[0]
    return pre_row["date"], pre_row["eps_est"], post_row["date"], post_row["eps_est"]


def compute_revisions(
    events: pd.DataFrame,
    eps_panel: pd.DataFrame,
    ticker_map: pd.DataFrame,
    event_date_col: str = "event_date",
    window_days: int = EPS_WINDOW_DAYS,
) -> pd.DataFrame:
    """events must carry cd_cvm and event_date_col (plus whatever
    scenario-identifying columns the caller wants preserved). Returns events
    with pre_eps/post_eps/revision_raw/revision_pct columns appended
    (NaN revision where no ticker or no bracketing snapshot pair exists)."""
    merged = events.merge(ticker_map, left_on="cd_cvm", right_on="CD_CVM", how="left")
    panel_by_ticker = {t: g[["date", "eps_est"]].reset_index(drop=True) for t, g in eps_panel.groupby("ticker")}

    pre_dates, pre_epss, post_dates, post_epss = [], [], [], []
    for row in merged.itertuples(index=False):
        ticker = getattr(row, "ticker", None)
        event_date = getattr(row, event_date_col)
        result = None
        if isinstance(ticker, str) and ticker in panel_by_ticker and pd.notna(event_date):
            result = _bracket(panel_by_ticker[ticker], pd.Timestamp(event_date), window_days)
        if result is None:
            pre_dates.append(pd.NaT); pre_epss.append(np.nan)
            post_dates.append(pd.NaT); post_epss.append(np.nan)
        else:
            pd_, pe, qd_, qe = result
            pre_dates.append(pd_); pre_epss.append(pe)
            post_dates.append(qd_); post_epss.append(qe)

    merged["pre_date"] = pre_dates
    merged["pre_eps"] = pre_epss
    merged["post_date"] = post_dates
    merged["post_eps"] = post_epss
    merged["revision_raw"] = merged["post_eps"] - merged["pre_eps"]
    denom = merged["pre_eps"].abs()
    merged["revision_pct"] = np.where(denom > 0.01, merged["revision_raw"] / denom, np.nan)
    return merged


def load_annual_event_dates() -> pd.DataFrame:
    """(cd_cvm, year_curr) -> event_date, same reference table and join key
    compute_abnormal_returns.py uses for H1 (the current fiscal year's CVM
    receipt date)."""
    filing_dates = pd.read_csv(INTERIM / "dfp_filing_dates.csv")
    return filing_dates.rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "year_curr", "filing_date": "event_date",
    })[["cd_cvm", "year_curr", "event_date"]].assign(
        event_date=lambda d: pd.to_datetime(d["event_date"])
    )


def load_quarterly_event_dates() -> pd.DataFrame:
    """(cd_cvm, quarter_curr) -> event_date, from the ITR filing-dates
    reference table."""
    filing_dates = pd.read_csv(INTERIM / "itr_filing_dates.csv")
    return filing_dates.rename(columns={
        "CD_CVM": "cd_cvm", "QUARTER_LABEL": "quarter_curr", "filing_date": "event_date",
    })[["cd_cvm", "quarter_curr", "event_date"]].assign(
        event_date=lambda d: pd.to_datetime(d["event_date"])
    )


def main() -> None:
    """Standalone sanity check: narrow-annual scenario only."""
    sim = pd.read_csv(POC / "delisted_similarity_results.csv")
    events = load_annual_event_dates()
    ticker_map = build_ticker_map()
    eps_panel = load_eps_panel()

    merged_events = sim.merge(events, on=["cd_cvm", "year_curr"], how="inner")
    result = compute_revisions(merged_events, eps_panel, ticker_map)
    result = result.drop_duplicates(subset=["cd_cvm", "year_prev", "year_curr"])

    out_path = POC / "eps_revisions_narrow_annual.csv"
    result.to_csv(out_path, index=False)

    has_rev = result["revision_pct"].notna().sum()
    print(f"{len(result)} narrow-annual similarity pairs; {ticker_map['CD_CVM'].nunique()} companies with a resolved ticker")
    print(f"{has_rev} pairs ({has_rev / len(result):.1%}) have a computable EPS revision")
    have = result.dropna(subset=["revision_pct"])
    if len(have) >= 3:
        pearson = have["cosine_similarity"].corr(have["revision_pct"], method="pearson")
        spearman = have["cosine_similarity"].corr(have["revision_pct"], method="spearman")
        print(f"signed:    pearson r={pearson:+.4f}  spearman rho={spearman:+.4f}")
        mag = have["cosine_similarity"].corr(have["revision_pct"].abs(), method="pearson")
        print(f"magnitude: pearson r={mag:+.4f} (similarity vs |revision|)")


if __name__ == "__main__":
    main()

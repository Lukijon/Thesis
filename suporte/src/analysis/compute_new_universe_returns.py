"""Computes BHAR ajustado (the thesis's definitive H1 dependent variable --
see compute_alpha_abnormal_returns.py and tese/latex/tese_jonathan.tex Secao 3.3)
for the round-7 universe expansion (111-company panel's 2010-2014
extension + 74 IBX-extra companies), then regresses it on TextChange
(1 - cosine similarity) to answer "what's the p-value for the new
universe".

Price data comes from two sources, combined: the original
stock_prices_bloomberg.csv (the 111-company panel's existing, already-
validated source) plus ibx.xlsx's `px_last` sheet -- a user-supplied
export added specifically to close the gap this script first found (only
7/74 IBX-extra tickers were in stock_prices_bloomberg.csv; px_last covers
all 74). Where a ticker exists in both, stock_prices_bloomberg.csv wins
(no reason to prefer the newer, narrower export for companies already
covered by the established one).

Two-stage pipeline, mirroring compute_abnormal_returns.py ->
compute_alpha_abnormal_returns.py: first the simple window/ticker
resolution (event date, first trading day on/after it, 252 trading days
forward), then the 4-factor alpha/BHAR computation on top (252-trading-day
PRE-event estimation window, needs >=100 obs -- this, not ticker coverage
anymore, is the binding constraint for how far back into 2010-2014 this
can actually reach, since Bloomberg price data of either source starts
2010-01-01/2014-01-01 respectively).

Usage:
    python -u -m src.analysis.compute_new_universe_returns
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from src.analysis.compute_abnormal_returns import build_ticker_map as build_original_ticker_map
from src.analysis.compute_alpha_abnormal_returns import (
    FACTOR_COLS,
    estimate_alpha_model,
    event_window_residuals,
    load_factors,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
IBX_XLSX = ROOT / "ibx.xlsx"
WINDOW_TRADING_DAYS = 252

SIMILARITY_CSV = POC / "similarity_results_new_universe_reliable.csv"
IBX_EXTRA_UNIVERSE = INTERIM / "ibx_extra_universe.csv"
OUT_CSV = POC / "abnormal_returns_alpha_new_universe.csv"


def load_original_prices() -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    return prices.set_index("date").sort_index()


def load_ibx_prices() -> pd.DataFrame:
    """ibx.xlsx's `px_last` sheet: a Bloomberg BQL export laid out like
    ibov.xlsx's sheets, but with one fewer header row -- ticker row and
    data start are found by locating the literal 'DATES' label rather than
    hardcoding row offsets, so this doesn't silently misalign if the two
    files' export layouts ever drift apart again.
    """
    raw = pd.read_excel(IBX_XLSX, sheet_name="px_last", header=None)
    label_row = raw.index[raw[0] == "DATES"][0]
    tickers = raw.iloc[label_row - 1, 1:].tolist()  # already suffixed "... BS Equity"
    data = raw.iloc[label_row + 1 :, :].copy()
    data.columns = ["date"] + tickers
    data["date"] = pd.to_datetime(data["date"])
    for c in data.columns:
        if c != "date":
            data[c] = pd.to_numeric(data[c], errors="coerce")
    return data.set_index("date").sort_index()


def load_combined_prices() -> pd.DataFrame:
    """Row-level merge, not column-level: ibx.xlsx's px_last has the same
    values as stock_prices_bloomberg.csv wherever both cover a (ticker,
    date) cell (verified exactly, 0.0 max abs diff across sampled tickers),
    but starts in 2010 instead of 2014 -- for tickers present in both files,
    a column-level "original wins" join (the previous version) silently
    discarded ibx.xlsx's 2010-2013 history for those tickers, which is
    exactly the years the 2010-2014 panel extension needs. combine_first
    takes the original's value per cell where it exists and only falls back
    to ibx.xlsx where the original has nothing -- for the ~8 months at the
    end of stock_prices_bloomberg.csv's range (through 2026-08) that
    ibx.xlsx's export doesn't reach (stops 2026-01), the original still
    wins there too.
    """
    original = load_original_prices()
    ibx = load_ibx_prices()
    combined = original.combine_first(ibx)
    return combined.sort_index()


def build_full_ticker_map() -> pd.DataFrame:
    """Original 111-panel companies via the existing resolution logic, plus
    the 74 IBX-extra companies via ibx.xlsx's own Bloomberg ID (now that
    px_last covers all 74, this is a direct, complete match -- no B3-
    registry fallback needed).
    """
    original_map = build_original_ticker_map()

    ibx_extra = pd.read_csv(IBX_EXTRA_UNIVERSE, dtype={"CD_CVM": str})
    ibx_extra["ticker_guess"] = ibx_extra["ID"].str.replace(" BS Equity", "", regex=False)
    extra_map = pd.DataFrame({"CD_CVM": ibx_extra["CD_CVM"].astype(int), "ticker": ibx_extra["ticker_guess"]})
    print(f"IBX-extra ticker resolution: {len(extra_map)}/{len(ibx_extra)} companies resolved (direct, via ibx.xlsx px_last)")

    return pd.concat([original_map, extra_map], ignore_index=True).drop_duplicates("CD_CVM")


def load_combined_event_dates() -> pd.DataFrame:
    original = pd.read_csv(INTERIM / "dfp_filing_dates.csv")
    extension = pd.read_csv(INTERIM / "dfp_filing_dates_extension.csv")
    combined = pd.concat([original, extension], ignore_index=True).drop_duplicates(["CD_CVM", "fiscal_year"])
    return combined.rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr", "filing_date": "event_date"})[
        ["cd_cvm", "year_curr", "event_date"]
    ].assign(event_date=lambda d: pd.to_datetime(d["event_date"]))


def compute_windows(events: pd.DataFrame, ticker_map: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
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
        if stock.empty or len(stock) <= WINDOW_TRADING_DAYS:
            continue
        t0 = stock.index[0]
        t1 = stock.index[WINDOW_TRADING_DAYS]
        if t1 > last_date:
            continue
        rows.append({"cd_cvm": row.cd_cvm, "year_curr": row.year_curr, "ticker": row.ticker,
                      "window_start": t0, "window_end": t1})
    return pd.DataFrame(rows)


def main() -> None:
    sim = pd.read_csv(SIMILARITY_CSV, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    sim["TextChange"] = 1 - sim["cosine_similarity"]
    print(f"{len(sim)} reliable TextChange pairs in the new universe (input)")

    ticker_map = build_full_ticker_map()
    events = load_combined_event_dates()
    prices = load_combined_prices()
    print(f"Combined price source: {len(prices.columns)} tickers, {prices.index.min().date()} to {prices.index.max().date()}")

    windows = compute_windows(events, ticker_map, prices)
    print(f"{len(windows)} pairs have a resolvable ticker + valid 252-trading-day forward window")

    merged = sim.merge(windows, on=["cd_cvm", "year_curr"], how="inner")
    print(f"{len(merged)} pairs after merging with TextChange (have both text and a price window)")

    factors = load_factors()

    rows = []
    n_dropped_estimation = n_dropped_event = 0
    for row in merged.itertuples(index=False):
        col = f"{row.ticker} BS Equity"
        if col not in prices.columns:
            continue
        ret = prices[col].dropna().pct_change().dropna()

        est = estimate_alpha_model(ret, factors, row.window_start)
        if est is None:
            n_dropped_estimation += 1
            continue
        alpha, betas, n_est = est

        eps = event_window_residuals(ret, factors, alpha, betas, row.window_start, row.window_end)
        if eps is None or len(eps) < 20:
            n_dropped_event += 1
            continue

        rows.append({
            "cd_cvm": row.cd_cvm, "year_curr": row.year_curr, "ticker": row.ticker,
            "TextChange": row.TextChange, "cosine_similarity": row.cosine_similarity,
            "window_start": row.window_start, "window_end": row.window_end,
            "n_est_obs": n_est, "n_event_days": len(eps),
            "BHAR_ajustado_raw": float((1 + eps).prod() - 1),
        })

    df = pd.DataFrame(rows)
    print(f"\n{len(df)} pairs with a computable BHAR ajustado "
          f"({n_dropped_estimation} dropped <100 estimation-window obs, {n_dropped_event} dropped insufficient event-window data)")

    if len(df) < 5:
        print("\nToo few observations for a meaningful regression -- reporting the raw data only.")
        df.to_csv(OUT_CSV, index=False)
        print(f"Written: {OUT_CSV}")
        return

    # Winsorize at 1/99 pct, same convention as the thesis's BHAR ajustado (Secao 3.3)
    lo, hi = df["BHAR_ajustado_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_ajustado_raw"].clip(lo, hi)
    df.to_csv(OUT_CSV, index=False)
    print(f"Written: {OUT_CSV}")

    n_companies = df["cd_cvm"].nunique()
    print(f"\n{len(df)} observations, {n_companies} companies")

    model_pooled = smf.ols("BHAR_ajustado ~ TextChange", data=df).fit(cov_type="HC1")
    print("\n=== Pooled OLS, HC1 robust SE (no clustering -- see note below) ===")
    print(f"beta={model_pooled.params['TextChange']:.4f}  se={model_pooled.bse['TextChange']:.4f}  "
          f"p={model_pooled.pvalues['TextChange']:.4f}  n={int(model_pooled.nobs)}  R2={model_pooled.rsquared:.4f}")

    if n_companies < 10:
        print(f"\nOnly {n_companies} distinct companies -- too few for clustered SEs to be meaningful "
              f"(clustering needs many clusters to be trustworthy); pooled HC1 above is the honest number here.")
        return

    model_clustered = smf.ols("BHAR_ajustado ~ TextChange", data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df["cd_cvm"]}
    )
    headline_p = model_clustered.pvalues["TextChange"]
    print("\n=== OLS, clustered by company (the thesis's standard practice) ===")
    print(f"beta={model_clustered.params['TextChange']:.4f}  se={model_clustered.bse['TextChange']:.4f}  "
          f"p={headline_p:.4f}  n={int(model_clustered.nobs)}  n_companies={n_companies}")

    # Same skepticism discipline applied to every borderline result elsewhere
    # in this project (portfolio-sort degenerate-score check, leave-one-out
    # on the Fatores de Risco delisting finding) -- run it here too rather
    # than reporting a marginal p-value without scrutiny.
    if headline_p < 0.15:
        print("\n--- Robustness checks (p < 0.15, so worth scrutinizing before trusting it) ---")

        degenerate = (df["cosine_similarity"] >= 0.999) | (df["cosine_similarity"] <= 0.001)
        clean = df[~degenerate]
        if degenerate.sum() and clean["cd_cvm"].nunique() >= 10:
            m_clean = smf.ols("BHAR_ajustado ~ TextChange", data=clean).fit(
                cov_type="cluster", cov_kwds={"groups": clean["cd_cvm"]}
            )
            print(f"Excluding {int(degenerate.sum())} degenerate-similarity pairs (>=0.999 or <=0.001): "
                  f"p={m_clean.pvalues['TextChange']:.4f}  n={int(m_clean.nobs)}")

        worst_p = headline_p
        for cd in df["cd_cvm"].unique():
            sub = df[df["cd_cvm"] != cd]
            if sub["cd_cvm"].nunique() < 10:
                continue
            m_loo = smf.ols("BHAR_ajustado ~ TextChange", data=sub).fit(
                cov_type="cluster", cov_kwds={"groups": sub["cd_cvm"]}
            )
            worst_p = max(worst_p, m_loo.pvalues["TextChange"])
        print(f"Leave-one-company-out worst case: p={worst_p:.4f}")


if __name__ == "__main__":
    main()

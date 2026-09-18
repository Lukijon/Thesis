"""Quarterly counterpart to `compute_abnormal_returns.py`: does
quarter-over-quarter debt-note textual change (`itr_similarity_results.csv`,
full 112-company universe) line up with the stock's abnormal return in the
~63 trading days (≈1 quarter) after the note is *disclosed*? Same
market-adjusted (not market-model), simple-by-design approach as the annual
checkpoint -- see that module's docstring for the full rationale, which
applies unchanged here.

Ticker resolution reuses `compute_abnormal_returns.build_ticker_map` (66
current companies map directly; historical/delisted companies resolve via
B3's live registry where possible).

Usage:
    python -u -m src.analysis.compute_quarterly_abnormal_returns
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
WINDOW_TRADING_DAYS = 63  # ~1 quarter


def load_event_dates() -> pd.DataFrame:
    filing_dates = pd.read_csv(INTERIM / "itr_filing_dates.csv")
    return filing_dates.rename(columns={
        "CD_CVM": "cd_cvm", "QUARTER_LABEL": "quarter_curr", "filing_date": "event_date",
    })[["cd_cvm", "quarter_curr", "event_date"]].assign(
        event_date=lambda d: pd.to_datetime(d["event_date"])
    )


def compute_returns(events: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    prices = prices.set_index("date").sort_index()

    ibov = pd.read_csv(MARKET / "ibov_index_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date", "IBOV Index": "ibov"})
    ibov["date"] = pd.to_datetime(ibov["date"], format="%m/%d/%Y")
    ibov["ibov"] = pd.to_numeric(ibov["ibov"], errors="coerce")
    ibov = ibov.set_index("date").sort_index()["ibov"].dropna()

    last_date = ibov.index.max()

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
        if stock.empty:
            continue
        t0 = stock.index[0]
        if len(stock) <= WINDOW_TRADING_DAYS:
            continue
        t1 = stock.index[WINDOW_TRADING_DAYS]
        if t1 > last_date:
            continue

        p0, p1 = stock.iloc[0], stock.loc[t1]
        stock_return = p1 / p0 - 1

        ibov_window = ibov[(ibov.index >= t0) & (ibov.index <= t1)]
        if len(ibov_window) < 2:
            continue
        ibov_return = ibov_window.iloc[-1] / ibov_window.iloc[0] - 1

        rows.append({
            "cd_cvm": row.cd_cvm,
            "quarter_curr": row.quarter_curr,
            "ticker": row.ticker,
            "event_date": row.event_date,
            "window_start": t0,
            "window_end": t1,
            "stock_return": stock_return,
            "ibov_return": ibov_return,
            "abnormal_return": stock_return - ibov_return,
        })
    return pd.DataFrame(rows)


def main() -> None:
    sim = pd.read_csv(POC / "itr_similarity_results.csv")
    events = load_event_dates()
    ticker_map = build_ticker_map()
    returns = compute_returns(events, ticker_map)

    merged = sim.merge(returns, on=["cd_cvm", "quarter_curr"], how="inner")
    merged = merged.drop_duplicates(subset=["cd_cvm", "quarter_prev", "quarter_curr"])

    out_path = POC / "abnormal_returns_itr.csv"
    merged.to_csv(out_path, index=False)

    both_reliable = merged[(merged["diagnostic_prev"] == "font_heading") & (merged["diagnostic_curr"] == "font_heading")]

    print(f"{len(sim)} quarterly note-similarity pairs")
    print(f"{len(merged)} pairs have both a similarity score and a computable ~1-quarter abnormal return\n")

    for label, df in [("All computable pairs", merged), ("Reliable extraction only (font_heading/font_heading)", both_reliable)]:
        if len(df) < 3:
            print(f"{label}: n={len(df)} -- too few to correlate")
            continue
        pearson = df["cosine_similarity"].corr(df["abnormal_return"], method="pearson")
        spearman = df["cosine_similarity"].corr(df["abnormal_return"], method="spearman")
        print(f"{label}: n={len(df)}")
        print(f"  Pearson  r(similarity, abnormal return) = {pearson:.3f}")
        print(f"  Spearman rho(similarity, abnormal return) = {spearman:.3f}")

    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

"""Risk-factors counterpart to `compute_abnormal_returns.py`: joins
`risk_factors_similarity_results.csv` (year-over-year Risk Factors cosine
similarity, src/processing/build_risk_factors_corpus.py) to event dates and
forward market-adjusted returns. Same approach/caveats as the annual
narrow-note checkpoint -- see that module's docstring.

Usage:
    python -u -m src.analysis.compute_risk_factors_abnormal_returns
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.compute_abnormal_returns import build_ticker_map, compute_returns, load_event_dates

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"


def main() -> None:
    sim = pd.read_csv(POC / "risk_factors_similarity_results.csv")
    events = load_event_dates()
    ticker_map = build_ticker_map()
    returns = compute_returns(events, ticker_map)

    merged = sim.merge(returns, on=["cd_cvm", "year_curr"], how="inner")
    merged = merged.drop_duplicates(subset=["cd_cvm", "year_prev", "year_curr"])

    out_path = POC / "abnormal_returns_risk_factors.csv"
    merged.to_csv(out_path, index=False)

    print(f"{len(sim)} risk-factors similarity pairs")
    print(f"{len(merged)} pairs have both a similarity score and a computable 12-month abnormal return\n")

    pearson = merged["cosine_similarity"].corr(merged["abnormal_return"], method="pearson")
    spearman = merged["cosine_similarity"].corr(merged["abnormal_return"], method="spearman")
    print(f"All computable pairs: n={len(merged)}")
    print(f"  Pearson  r(similarity, abnormal return) = {pearson:.3f}")
    print(f"  Spearman rho(similarity, abnormal return) = {spearman:.3f}")
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()

"""Quarterly (ITR) TF-IDF, extended from the 112-company/2015-2024
universe (run_itr_tfidf_full.py) to the full round-7 expanded universe
(185 companies, 2011-2025). Mirrors run_itr_tfidf_full.py's structure
exactly, with an extended name_map (current + historical + IBX-extra,
same pattern as rebuild_sections_cache.py) and a separate output path so
the thesis's own original itr_similarity_results.csv stays untouched.

Usage:
    python -u -m src.processing.run_itr_tfidf_full_history
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.processing.eval_note_locator import load_cached_bookmarks, load_cached_lines
from src.processing.locate_note_section import locate_note_section
from src.processing.run_itr_tfidf_full import compute_similarities
from src.processing.run_poc_tfidf import _clean_for_tfidf  # noqa: F401 (compute_similarities dep)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LINES_CACHE = Path("data/interim/poc/lines_cache")
ITR_SECTIONS = Path("data/interim/poc/itr_sections")
POC_INTERIM = Path("data/interim/poc")
RESULTS_CSV = POC_INTERIM / "itr_similarity_results_full_history.csv"


def _name_map() -> dict[str, str]:
    current = pd.read_csv("data/interim/ibov_non_financial_universe.csv")
    name_map = {f"{int(c):06d}": n for c, n in zip(current["CD_CVM"], current["DENOM_CIA"])}
    for cd, name in NEW_HISTORICAL_CD_CVM.items():
        name_map.setdefault(f"{cd:06d}", name)
    ibx_extra = pd.read_csv("data/interim/ibx_extra_universe.csv", dtype={"CD_CVM": str})
    for row in ibx_extra.itertuples():
        name_map.setdefault(f"{int(row.CD_CVM):06d}", row.Name)
    return name_map


def build_sections() -> pd.DataFrame:
    ITR_SECTIONS.mkdir(parents=True, exist_ok=True)
    name_map = _name_map()
    rows = []
    for cache_path in sorted(LINES_CACHE.glob("itr_*.json")):
        key = cache_path.stem
        m = re.match(r"itr_(\d+)_(\d+Q\d)", key)
        if not m:
            continue
        cd_cvm, quarter = m.group(1), m.group(2)
        if cd_cvm not in name_map:
            continue
        lines = load_cached_lines(key)
        bookmarks = load_cached_bookmarks(key)
        section = locate_note_section(lines, bookmarks=bookmarks)
        rows.append({
            "cd_cvm": cd_cvm, "name": name_map[cd_cvm], "quarter": quarter,
            "diagnostic": section.diagnostic, "heading": section.heading,
            "n_total_lines": len(lines), "text": section.text,
        })
    return pd.DataFrame(rows)


def main() -> None:
    print("Building sections from cached lines (full 185-company expanded universe)...")
    sections = build_sections()
    n_total = len(sections)
    n_found = (sections["text"].str.len() > 0).sum()
    print(f"\n{n_found}/{n_total} company-quarters yielded a non-empty note section")
    print(sections["diagnostic"].value_counts())

    print("\nComputing TF-IDF cosine similarities...")
    results = compute_similarities(sections)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_CSV, index=False)

    print(f"\n{len(results)} quarter-over-quarter pairs computed. Similarity distribution:")
    print(results["cosine_similarity"].describe())
    print(f"\nResults: {RESULTS_CSV}")


if __name__ == "__main__":
    main()

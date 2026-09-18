"""Quarterly (ITR) TF-IDF, extended from the 20-company pilot
(`run_itr_tfidf.py`) to the full 112-company universe (66 current IBOV +
46 historical/delisted) -- the same scope as the annual round-4/5 work.
Also propagates round 5's extraction hardening (bookmarks, same-size
headings, etc.) to the quarterly corpus for the first time, since the
pilot predates that work.

Reuses the raw-lines/bookmarks caches already built for the annual
extraction-tuning work (`eval_note_locator.py`) -- no PDF re-parsing.

Usage:
    python -m src.processing.run_itr_tfidf_full
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.processing.eval_note_locator import load_cached_bookmarks, load_cached_lines
from src.processing.locate_note_section import locate_note_section
from src.processing.run_poc_tfidf import _clean_for_tfidf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LINES_CACHE = Path("data/interim/poc/lines_cache")
ITR_SECTIONS = Path("data/interim/poc/itr_sections")
POC_INTERIM = Path("data/interim/poc")
RESULTS_CSV = POC_INTERIM / "itr_similarity_results.csv"


def _name_map() -> dict[str, str]:
    universe = pd.read_csv("data/interim/ibov_non_financial_universe.csv")
    name_map = {f"{int(c):06d}": n for c, n in zip(universe["CD_CVM"], universe["DENOM_CIA"])}
    for cd, name in NEW_HISTORICAL_CD_CVM.items():
        key = f"{cd:06d}"
        name_map.setdefault(key, name)
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
        out = {
            "cd_cvm": cd_cvm,
            "name": name_map[cd_cvm],
            "quarter": quarter,
            "diagnostic": section.diagnostic,
            "heading": section.heading,
            "n_total_lines": len(lines),
            "text": section.text,
        }
        (ITR_SECTIONS / f"{cd_cvm}_{quarter}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows.append(out)
    return pd.DataFrame(rows)


def compute_similarities(sections: pd.DataFrame) -> pd.DataFrame:
    sections = sections[sections["text"].str.len() > 0].reset_index(drop=True).copy()
    sections["clean_text"] = sections["text"].apply(_clean_for_tfidf)

    vectorizer = TfidfVectorizer(max_df=0.85, min_df=2, max_features=50000)
    tfidf_matrix = vectorizer.fit_transform(sections["clean_text"])

    def _quarter_sort_key(q: str) -> tuple[int, int]:
        year, qtr = q.split("Q")
        return (int(year), int(qtr))

    results = []
    for cd_cvm, group in sections.groupby("cd_cvm"):
        group = group.sort_values("quarter", key=lambda s: s.map(_quarter_sort_key))
        positions = group.index.tolist()
        quarters = group["quarter"].tolist()
        for i in range(1, len(positions)):
            sim = cosine_similarity(tfidf_matrix[positions[i - 1]], tfidf_matrix[positions[i]])[0, 0]
            results.append(
                {
                    "cd_cvm": cd_cvm,
                    "name": group["name"].iloc[0],
                    "quarter_prev": quarters[i - 1],
                    "quarter_curr": quarters[i],
                    "cosine_similarity": round(float(sim), 4),
                    "chars_prev": len(group["text"].iloc[i - 1]),
                    "chars_curr": len(group["text"].iloc[i]),
                    "diagnostic_prev": group["diagnostic"].iloc[i - 1],
                    "diagnostic_curr": group["diagnostic"].iloc[i],
                }
            )
    return pd.DataFrame(results)


def main() -> None:
    print("Building sections from cached lines (full 112-company universe)...")
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

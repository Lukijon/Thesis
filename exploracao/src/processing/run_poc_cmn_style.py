"""Curiosity check requested by the user: rebuild the narrow-debt-note
year-over-year similarity measure using Cohen, Malloy & Nguyen (2020)'s
actual method -- a cosine similarity over RAW term-frequency vectors
(union of terms, plain word counts, no IDF weighting at all) -- instead of
this project's TF-IDF vectors (Brown & Tucker 2011's method, see the
chat/thesis discussion of which paper actually contributes which piece of
the measure).

Verified directly from the "Lazy Prices" NBER working paper text: their
cosine measure is built from term_frequency_vectors of raw word counts,
crediting Hanley & Hoberg (2010) -- no inverse-document-frequency step.

Reuses the exact same cached section text (data/interim/poc/sections/,
shared by run_poc_tfidf.py and run_delisted_analysis.py) and the exact
same cleaning/max_df/min_df settings, swapping only TfidfVectorizer for
CountVectorizer, so the ONLY methodological difference from the project's
main similarity_results.csv/delisted_similarity_results.csv is the
presence/absence of IDF weighting -- everything else (text, vocabulary
filtering, universe) is identical.

Usage:
    python -u -m src.processing.run_poc_cmn_style
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.run_poc_tfidf import POC_COMPANIES, YEARS, _clean_for_tfidf
from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM

POC_INTERIM = Path("data/interim/poc")
SECTIONS_DIR = POC_INTERIM / "sections"
OUT_CSV = POC_INTERIM / "similarity_results_cmn_style.csv"


def _load_cached_sections(companies: dict[str, str], group_label: str) -> pd.DataFrame:
    rows = []
    for cd_cvm in companies:
        for year in YEARS:
            cache_path = SECTIONS_DIR / f"{cd_cvm}_{year}.json"
            if not cache_path.exists():
                continue
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached["group"] = group_label
            rows.append(cached)
    return pd.DataFrame(rows)


def compute_similarities_cmn_style(sections: pd.DataFrame) -> pd.DataFrame:
    sections = sections[sections["text"].str.len() > 0].reset_index(drop=True).copy()
    sections["clean_text"] = sections["text"].apply(_clean_for_tfidf)

    # Same vocabulary filtering as the project's TF-IDF pipeline (max_df/min_df),
    # so the vocabulary itself is identical -- only the weighting (raw counts
    # vs. TF-IDF) differs, isolating that one methodological choice.
    vectorizer = CountVectorizer(max_df=0.85, min_df=2)
    count_matrix = vectorizer.fit_transform(sections["clean_text"])

    results = []
    for cd_cvm, group in sections.groupby("cd_cvm"):
        group = group.sort_values("year")
        positions = group.index.tolist()
        years = group["year"].tolist()
        for i in range(1, len(positions)):
            sim = cosine_similarity(count_matrix[positions[i - 1]], count_matrix[positions[i]])[0, 0]
            results.append({
                "cd_cvm": cd_cvm,
                "name": group["name"].iloc[0],
                "group": group["group"].iloc[0],
                "year_prev": years[i - 1],
                "year_curr": years[i],
                "cosine_similarity_cmn": round(float(sim), 4),
                "diagnostic_prev": group["diagnostic"].iloc[i - 1],
                "diagnostic_curr": group["diagnostic"].iloc[i],
            })
    return pd.DataFrame(results)


def main() -> None:
    current = _load_cached_sections(POC_COMPANIES, "stayed")
    delisted_companies = {f"{cd:06d}": name for cd, name in NEW_HISTORICAL_CD_CVM.items()}
    historical = _load_cached_sections(delisted_companies, "dropped_or_delisted")
    sections = pd.concat([current, historical], ignore_index=True)

    print(f"{len(sections)} cached company-years loaded (shared cache with the TF-IDF pipeline)")
    results = compute_similarities_cmn_style(sections)
    results.to_csv(OUT_CSV, index=False)
    print(f"{len(results)} year-over-year pairs computed (CMN-style, raw term frequency, no IDF)")
    print(results["cosine_similarity_cmn"].describe())
    print(f"\nWritten: {OUT_CSV}")


if __name__ == "__main__":
    main()

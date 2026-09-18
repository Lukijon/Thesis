"""TF-IDF + cosine similarity over the full expanded universe (185
companies -- the original 111-company IBOV panel plus 74 IBX-extra
companies, see run_history_extension.py / run_ibx_extension.py --
2010-2025, not just the original 66-company/2015-2024 scope).

Reads directly from data/interim/poc/sections/, already rebuilt by
rebuild_sections_cache.py from the round-7-hardened lines_cache (corrected
attachment selection + the new elevated-size/non-bold heading rule) -- no
PDF re-parsing here, this script is pure TF-IDF over already-isolated note
text. Run rebuild_sections_cache.py first if locate_note_section.py or the
underlying PDFs changed since the last rebuild.

Deliberately a separate results file from similarity_results.csv (the
original 66-company/2015-2024 scope that run_poc_tfidf.py / the existing
H1/H2 pipeline are built on) rather than overwriting it -- the thesis's
adopted sample and results are unaffected by this extension; this is new
exploratory material for the longer-horizon expansion, not a replacement
for the already-validated confirmatory results.

Usage:
    python -m src.processing.run_full_history_tfidf
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore")

SECTIONS_DIR = Path("data/interim/poc/sections")
RESULTS_CSV = Path("data/interim/poc/similarity_results_full_history.csv")
RELIABLE_CSV = Path("data/interim/poc/similarity_results_full_history_reliable.csv")


def _clean_for_tfidf(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\d.,%]+", " NUM ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_all_sections() -> pd.DataFrame:
    rows = []
    for p in sorted(SECTIONS_DIR.glob("*.json")):
        cached = json.loads(p.read_text(encoding="utf-8"))
        rows.append(cached)
    return pd.DataFrame(rows)


def compute_similarities(sections: pd.DataFrame) -> pd.DataFrame:
    sections = sections[sections["text"].str.len() > 0].reset_index(drop=True).copy()
    sections["clean_text"] = sections["text"].apply(_clean_for_tfidf)

    vectorizer = TfidfVectorizer(max_df=0.85, min_df=2)
    tfidf_matrix = vectorizer.fit_transform(sections["clean_text"])

    results = []
    for cd_cvm, group in sections.groupby("cd_cvm"):
        group = group.sort_values("year")
        positions = group.index.tolist()
        years = group["year"].tolist()
        for i in range(1, len(positions)):
            sim = cosine_similarity(tfidf_matrix[positions[i - 1]], tfidf_matrix[positions[i]])[0, 0]
            results.append({
                "cd_cvm": cd_cvm,
                "name": group["name"].iloc[0],
                "year_prev": years[i - 1],
                "year_curr": years[i],
                "cosine_similarity": round(float(sim), 4),
                "chars_prev": len(group["text"].iloc[i - 1]),
                "chars_curr": len(group["text"].iloc[i]),
                "diagnostic_prev": group["diagnostic"].iloc[i - 1],
                "diagnostic_curr": group["diagnostic"].iloc[i],
            })
    return pd.DataFrame(results)


def main() -> None:
    sections = load_all_sections()
    n_total = len(sections)
    n_found = (sections["text"].str.len() > 0).sum()
    print(f"{n_found}/{n_total} company-years (2010-2025, 185-company universe) yielded a non-empty note section")
    print(sections["diagnostic"].value_counts())
    print(f"Companies: {sections['cd_cvm'].nunique()}; years: {sorted(sections['year'].unique())}")

    print("\nComputing TF-IDF cosine similarities...")
    results = compute_similarities(sections)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_CSV, index=False)

    print(f"\n{len(results)} year-over-year pairs computed across {results['cd_cvm'].nunique()} companies.")
    print("Similarity distribution:")
    print(results["cosine_similarity"].describe())

    reliable = results[(results["diagnostic_prev"] == "font_heading") & (results["diagnostic_curr"] == "font_heading")].reset_index(drop=True)
    print(f"\n{len(reliable)}/{len(results)} pairs ({len(reliable)/len(results):.1%}) have font_heading on both years (the reliable subsample).")
    reliable.to_csv(RELIABLE_CSV, index=False)
    print(f"Reliable-only companies: {reliable['cd_cvm'].nunique()}")
    print("Reliable-only similarity distribution:")
    print(reliable["cosine_similarity"].describe())

    print(f"\nResults (all): {RESULTS_CSV}")
    print(f"Results (reliable only): {RELIABLE_CSV}")


if __name__ == "__main__":
    main()

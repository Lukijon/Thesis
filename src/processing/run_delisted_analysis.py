"""Extends the POC (run_poc_tfidf.py) to the companies found via the
historical-IBOV reconstruction (b3_ibov_historical.py) -- i.e. those that
dropped out of the index or delisted/went bankrupt/got acquired at some
point in 2015-2024, as opposed to the original 20 POC companies, all of
which are still in the index today.

Answers the question that motivated recovering historical IBOV membership
in the first place: is there a difference in debt-note textual change
between companies that stayed in the index and companies that dropped out?

Reuses the same note-locator and TF-IDF approach as the POC, fit as one
shared corpus across both groups so results are directly comparable and
IDF reflects the full cross-sectional boilerplate.

Usage:
    python -u -m src.processing.run_delisted_analysis
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.processing.locate_note_section import locate_note_section
from src.processing.pdf_text import extract_lines
from src.processing.run_poc_tfidf import POC_COMPANIES, YEARS, _clean_for_tfidf

warnings.filterwarnings("ignore")  # pymupdf's fitz-deprecation warning

RAW_ROOT = Path("data/raw/dfp")
POC_INTERIM = Path("data/interim/poc")
SECTIONS_DIR = POC_INTERIM / "sections"
RESULTS_CSV = POC_INTERIM / "delisted_similarity_results.csv"


def extract_all(companies: dict[str, str]) -> pd.DataFrame:
    """Same caching contract as run_poc_tfidf.extract_all: one JSON per
    company-year under SECTIONS_DIR, keyed "{cd_cvm}_{year}.json" -- shared
    with the original POC so a combined TF-IDF fit just globs the directory.
    """
    rows = []
    for cd_cvm, name in companies.items():
        cd_cvm = f"{int(cd_cvm):06d}" if isinstance(cd_cvm, int) else cd_cvm
        for year in YEARS:
            pdf_path = RAW_ROOT / cd_cvm / str(year) / "notas_explicativas.pdf"
            cache_path = SECTIONS_DIR / f"{cd_cvm}_{year}.json"

            if not pdf_path.exists():
                continue

            if cache_path.exists():
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                lines = extract_lines(pdf_path)
                section = locate_note_section(lines)
                cached = {
                    "cd_cvm": cd_cvm,
                    "name": name,
                    "year": year,
                    "diagnostic": section.diagnostic,
                    "heading": section.heading,
                    "n_total_lines": len(lines),
                    "text": section.text,
                }
                cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  {name} ({year}): {section.diagnostic}, {len(section.text)} chars")

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
            results.append(
                {
                    "cd_cvm": cd_cvm,
                    "name": group["name"].iloc[0],
                    "group": group["group"].iloc[0],
                    "year_prev": years[i - 1],
                    "year_curr": years[i],
                    "cosine_similarity": round(float(sim), 4),
                    "chars_prev": len(group["text"].iloc[i - 1]),
                    "chars_curr": len(group["text"].iloc[i]),
                    "diagnostic_prev": group["diagnostic"].iloc[i - 1],
                    "diagnostic_curr": group["diagnostic"].iloc[i],
                }
            )
    return pd.DataFrame(results)


def main() -> None:
    print("Extracting + locating debt notes for delisted/dropped-from-IBOV companies...")
    delisted_companies = {f"{cd:06d}": name for cd, name in NEW_HISTORICAL_CD_CVM.items()}
    delisted_sections = extract_all(delisted_companies)

    print("\nRe-loading original POC (stayed-in-IBOV) companies from cache...")
    stayed_sections = extract_all(POC_COMPANIES)

    delisted_sections["group"] = "dropped_or_delisted"
    stayed_sections["group"] = "stayed"
    combined = pd.concat([stayed_sections, delisted_sections], ignore_index=True)

    n_total = len(combined)
    n_found = (combined["text"].str.len() > 0).sum()
    print(f"\n{n_found}/{n_total} company-years yielded a non-empty note section")
    print(combined.groupby("group")["diagnostic"].value_counts())

    print("\nComputing TF-IDF cosine similarities (shared corpus, both groups)...")
    results = compute_similarities(combined)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_CSV, index=False)

    print(f"\n{len(results)} year-over-year pairs computed.")
    both_reliable = results[(results["diagnostic_prev"] == "font_heading") & (results["diagnostic_curr"] == "font_heading")]
    print(f"\nReliable-only (font_heading/font_heading), by group (n={len(both_reliable)}):")
    print(both_reliable.groupby("group")["cosine_similarity"].describe())
    print(f"\nResults: {RESULTS_CSV}")


if __name__ == "__main__":
    main()

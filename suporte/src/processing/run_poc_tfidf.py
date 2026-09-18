"""POC: does isolating the debt note and comparing it year-over-year with
TF-IDF + cosine similarity produce a sane signal, across the full current
non-financial IBOV universe already downloaded (see .claude/skills/cvm-debt-notes
and the acquisition pipeline in src/acquisition/)?

Originally run (rounds 1-2, see reports/poc_note_extraction_findings.md) on
a hand-picked 20-company sector-diverse subset; extended to the full 66
current non-financial IBOV constituents once the extraction heuristic was
hardened enough to trust at scale. See run_delisted_analysis.py for the
parallel run over historical/delisted (dropped-from-IBOV) companies, which
imports POC_COMPANIES from here so it automatically covers the same set.

This does NOT touch acquisition or download anything new -- it only reads
already-acquired PDFs under data/raw/dfp/.

Usage:
    python -m src.processing.run_poc_tfidf
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.locate_note_section import locate_note_section
from src.processing.pdf_text import extract_lines

warnings.filterwarnings("ignore")  # pymupdf's fitz-deprecation warning

UNIVERSE_CSV = Path("data/interim/ibov_non_financial_universe.csv")


def _load_current_universe() -> dict[str, str]:
    """All current non-financial IBOV constituents (66 as of this writing),
    keyed by zero-padded CD_CVM. Loaded from the universe file rather than
    hardcoded so this stays in sync automatically if that file is refreshed.
    """
    universe = pd.read_csv(UNIVERSE_CSV, dtype={"CD_CVM": str})
    return {
        f"{int(row.CD_CVM):06d}": row.ASSET
        for row in universe.itertuples()
    }


POC_COMPANIES = _load_current_universe()

YEARS = list(range(2015, 2025))
RAW_ROOT = Path("data/raw/dfp")
POC_INTERIM = Path("data/interim/poc")
RESULTS_CSV = POC_INTERIM / "similarity_results.csv"
SECTIONS_DIR = POC_INTERIM / "sections"


def _clean_for_tfidf(text: str) -> str:
    """Whitespace/number normalization for TF-IDF -- keep words, collapse
    the heavy numeric tables into a lighter signal so raw balance figures
    (which change every year almost by definition) don't dominate token
    counts the way real language differences would.
    """
    text = text.lower()
    text = re.sub(r"[\d.,%]+", " NUM ", text)  # collapse numbers/table figures to a single token
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_all() -> pd.DataFrame:
    """Extract + locate the debt note for every company-year in POC_COMPANIES,
    caching per-company-year JSON so re-runs of the similarity step don't
    need to re-parse PDFs.
    """
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for cd_cvm, name in POC_COMPANIES.items():
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
                print(f"  {name} ({year}): {section.diagnostic}, {len(section.text)} chars, heading={section.heading!r}")

            rows.append(cached)

    return pd.DataFrame(rows)


def compute_similarities(sections: pd.DataFrame) -> pd.DataFrame:
    """One row per company per consecutive fiscal-year pair with cosine
    similarity between the two years' isolated note text. TF-IDF is fit
    once across the whole POC corpus so IDF reflects cross-sectional
    boilerplate (the same logic the literature relies on), not just this
    one company's vocabulary.
    """
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
    print("Extracting + locating debt notes...")
    sections = extract_all()

    n_total = len(sections)
    n_found = (sections["text"].str.len() > 0).sum()
    print(f"\n{n_found}/{n_total} company-years yielded a non-empty note section")
    print(sections["diagnostic"].value_counts())

    print("\nComputing TF-IDF cosine similarities...")
    results = compute_similarities(sections)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_CSV, index=False)

    print(f"\n{len(results)} year-over-year pairs computed. Similarity distribution:")
    print(results["cosine_similarity"].describe())
    print(f"\nResults: {RESULTS_CSV}")
    print(f"Per-company-year sections (for spot-checking): {SECTIONS_DIR}/")


if __name__ == "__main__":
    main()

"""POC continuation: does the same note-locator + TF-IDF approach validated
on annual (DFP) notes work on quarterly (ITR) notes -- and does
quarter-over-quarter textual change catch a company's deterioration sooner
than the year-over-year comparison does? This is the motivating question
behind acquiring the ITR pilot (`run_itr_pilot.py`).

Same 20-company hand-picked set as the annual POC's original round-1/2
subset, so results are directly comparable against an established annual
baseline for the exact same companies. Same pipeline code
(`locate_note_section`, `TfidfVectorizer`) as `run_poc_tfidf.py` -- only the
input (quarterly PDFs, quarter-over-quarter pairs including the Q3->Q1
year-boundary pair) differs.

This does NOT touch acquisition or download anything new -- it only reads
already-acquired PDFs under data/raw/itr/.

Usage:
    python -m src.processing.run_itr_tfidf
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.locate_note_section import locate_note_section
from src.processing.pdf_text import extract_lines
from src.processing.run_poc_tfidf import _clean_for_tfidf

warnings.filterwarnings("ignore")  # pymupdf's fitz-deprecation warning

# Same 20 companies as the annual POC's original hand-picked subset (see
# run_poc_tfidf.py git history / reports/poc_note_extraction_findings.md).
PILOT_COMPANIES = {
    "004170": "VALE",
    "009512": "PETROBRAS",
    "023264": "AMBEV",
    "003980": "GERDAU",
    "014320": "USIMINAS",
    "005410": "WEG",
    "020087": "EMBRAER",
    "013986": "SUZANO",
    "004820": "BRASKEM",
    "002453": "CEMIG",
    "014443": "SABESP",
    "008133": "LOJAS RENNER",
    "005258": "RAIA DROGASIL",
    "020915": "MRV",
    "020788": "MARFRIG",
    "019992": "TOTVS",
    "021881": "FLEURY",
    "017671": "TELEFONICA BRASIL",
    "021016": "YDUQS",
    "019739": "LOCALIZA",
}

QUARTERS = [f"{y}Q{q}" for y in range(2015, 2025) for q in (1, 2, 3)]
RAW_ROOT = Path("data/raw/itr")
POC_INTERIM = Path("data/interim/poc")
RESULTS_CSV = POC_INTERIM / "itr_similarity_results.csv"
SECTIONS_DIR = POC_INTERIM / "itr_sections"


def extract_all() -> pd.DataFrame:
    """Extract + locate the debt note for every company-quarter in
    PILOT_COMPANIES, caching per-company-quarter JSON (same contract as
    run_poc_tfidf.extract_all, keyed by quarter label instead of year).
    """
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for cd_cvm, name in PILOT_COMPANIES.items():
        for quarter in QUARTERS:
            pdf_path = RAW_ROOT / cd_cvm / quarter / "notas_explicativas.pdf"
            cache_path = SECTIONS_DIR / f"{cd_cvm}_{quarter}.json"

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
                    "quarter": quarter,
                    "diagnostic": section.diagnostic,
                    "heading": section.heading,
                    "n_total_lines": len(lines),
                    "text": section.text,
                }
                cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  {name} ({quarter}): {section.diagnostic}, {len(section.text)} chars, heading={section.heading!r}")

            rows.append(cached)

    return pd.DataFrame(rows)


def compute_similarities(sections: pd.DataFrame) -> pd.DataFrame:
    """One row per company per consecutive-quarter pair (including the
    Q3->next-year-Q1 year-boundary pair) with cosine similarity between
    the two quarters' isolated note text. TF-IDF fit once across the whole
    quarterly corpus, same rationale as the annual pipeline.
    """
    sections = sections[sections["text"].str.len() > 0].reset_index(drop=True).copy()
    sections["clean_text"] = sections["text"].apply(_clean_for_tfidf)

    vectorizer = TfidfVectorizer(max_df=0.85, min_df=2)
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
    print("Extracting + locating debt notes (quarterly)...")
    sections = extract_all()

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
    print(f"Per-company-quarter sections (for spot-checking): {SECTIONS_DIR}/")


if __name__ == "__main__":
    main()

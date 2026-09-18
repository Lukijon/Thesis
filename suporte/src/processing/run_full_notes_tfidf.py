"""Alternative POC scenario: instead of isolating just the debt note,
compare the *entire* explanatory-notes document year-over-year. This is
closer to how the original "Lazy Prices" literature (Cohen/Malloy/Nguyen)
actually measures textual change -- whole-filing similarity, not a single
isolated section -- and sidesteps the note-*isolation* problem entirely
(no font heuristic, no diagnostic tiers: every filing with extractable text
contributes a score). The tradeoff is precision: a company could show high
whole-document similarity while its debt note specifically changed a lot,
or vice versa, so this is a robustness comparison against the narrow-note
result, not a replacement for it.

Reuses the raw-lines cache built for extraction-heuristic iteration
(`eval_note_locator.py`) -- no PDF re-parsing needed, since the whole
document's text is exactly what's already cached there.

Usage:
    python -m src.processing.run_full_notes_tfidf
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.eval_note_locator import _corpus_pdfs, load_cached_lines

POC_INTERIM = Path("data/interim/poc")
RESULTS_CSV = POC_INTERIM / "full_notes_similarity_results.csv"


def _clean_for_tfidf(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\d.,%]+", " NUM ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_full_texts() -> pd.DataFrame:
    """Whole-document text (all extracted lines joined) per company-year,
    for every DFP filing with a cached lines extraction.
    """
    rows = []
    for key, _ in _corpus_pdfs():
        if not key.startswith("dfp_"):
            continue
        m = re.match(r"dfp_(\d+)_(\d+)", key)
        cd_cvm, year = m.group(1), int(m.group(2))
        cache_path = Path("data/interim/poc/lines_cache") / f"{key}.json"
        if not cache_path.exists():
            continue
        lines = load_cached_lines(key)
        text = "\n".join(l.text for l in lines)
        rows.append({"cd_cvm": cd_cvm, "year": year, "text": text, "chars": len(text), "n_lines": len(lines)})
    return pd.DataFrame(rows)


def compute_similarities(docs: pd.DataFrame) -> pd.DataFrame:
    docs = docs[docs["text"].str.len() > 0].reset_index(drop=True).copy()
    docs["clean_text"] = docs["text"].apply(_clean_for_tfidf)

    vectorizer = TfidfVectorizer(max_df=0.85, min_df=2, max_features=50000)
    tfidf_matrix = vectorizer.fit_transform(docs["clean_text"])

    results = []
    for cd_cvm, group in docs.groupby("cd_cvm"):
        group = group.sort_values("year")
        positions = group.index.tolist()
        years = group["year"].tolist()
        for i in range(1, len(positions)):
            sim = cosine_similarity(tfidf_matrix[positions[i - 1]], tfidf_matrix[positions[i]])[0, 0]
            results.append(
                {
                    "cd_cvm": cd_cvm,
                    "year_prev": years[i - 1],
                    "year_curr": years[i],
                    "cosine_similarity": round(float(sim), 4),
                    "chars_prev": int(group["chars"].iloc[i - 1]),
                    "chars_curr": int(group["chars"].iloc[i]),
                }
            )
    return pd.DataFrame(results)


def main() -> None:
    print("Loading full document text from lines cache...")
    docs = load_full_texts()
    n_total = len(docs)
    n_found = (docs["text"].str.len() > 0).sum()
    print(f"{n_found}/{n_total} company-years with extractable text")

    print("\nComputing whole-document TF-IDF cosine similarities...")
    results = compute_similarities(docs)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_CSV, index=False)

    print(f"\n{len(results)} year-over-year pairs computed. Similarity distribution:")
    print(results["cosine_similarity"].describe())
    print(f"\nResults: {RESULTS_CSV}")


if __name__ == "__main__":
    main()

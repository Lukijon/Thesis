"""Addresses feedback_dissertacao.pdf items 2.5/5.8 (MUITO RECOMENDÁVEL):
the TF-IDF vocabulary and IDF weights used everywhere in this project so
far are fit once on the entire corpus (2015-2024, all companies) --
meaning the representation of a 2016 filing is influenced by word
frequencies observed in 2024 filings, a look-ahead problem in a
prediction study.

This recomputes cosine similarity for the narrow-annual debt note (H1's
core text source) using an expanding-window IDF instead: for a pair
(year_prev, year_curr), the vectorizer is fit only on documents with
year <= year_curr, i.e. only information that would actually have been
available to a market participant at the time of the year_curr filing.
The IDF is refit once per distinct year_curr value (9 fits, 2016-2024),
each time on the full cross-section of companies available through that
year -- preserving the original design's intent (IDF should reflect
genuine cross-sectional boilerplate, not a single company's vocabulary),
just without future years' documents.

Reuses the exact same (cd_cvm, year_prev, year_curr) pairing already in
delisted_similarity_results.csv (including which years ended up paired,
respecting whatever not_found-skipping already happened) -- only the
similarity VALUE for each existing pair is recomputed, so this is an
isolated test of the look-ahead concern, not conflated with any other
methodological question already explored this session.

Usage:
    python -u -m src.processing.recompute_similarity_expanding_window
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.run_poc_tfidf import _clean_for_tfidf

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
SECTIONS_DIR = ROOT / "data" / "interim" / "poc" / "sections"
POC = ROOT / "data" / "interim" / "poc"


def load_all_texts() -> pd.DataFrame:
    rows = []
    for path in SECTIONS_DIR.glob("*.json"):
        cached = json.loads(path.read_text(encoding="utf-8"))
        if not cached.get("text"):
            continue
        rows.append({
            "cd_cvm": int(cached["cd_cvm"]), "year": int(cached["year"]),
            "clean_text": _clean_for_tfidf(cached["text"]),
        })
    return pd.DataFrame(rows)


def main() -> None:
    pairs = pd.read_csv(POC / "delisted_similarity_results.csv")
    texts = load_all_texts()
    text_by_key = {(r.cd_cvm, r.year): r.clean_text for r in texts.itertuples(index=False)}

    print(f"{len(texts)} cached non-empty documents; {len(pairs)} existing pairs to recompute")

    new_sims = {}
    dropped = 0
    for year_curr, group in pairs.groupby("year_curr"):
        window_docs = texts[texts["year"] <= year_curr]
        if len(window_docs) < 20:
            for idx in group.index:
                dropped += 1
            continue
        vectorizer = TfidfVectorizer(max_df=0.85, min_df=2)
        matrix = vectorizer.fit_transform(window_docs["clean_text"])
        doc_index = {(r.cd_cvm, r.year): i for i, r in enumerate(window_docs.itertuples(index=False))}

        for idx, row in group.iterrows():
            key_prev, key_curr = (row["cd_cvm"], row["year_prev"]), (row["cd_cvm"], row["year_curr"])
            if key_prev not in doc_index or key_curr not in doc_index:
                dropped += 1
                continue
            sim = cosine_similarity(matrix[doc_index[key_prev]], matrix[doc_index[key_curr]])[0, 0]
            new_sims[idx] = round(float(sim), 4)

    pairs["cosine_similarity_expanding"] = pairs.index.map(new_sims)
    print(f"{len(new_sims)}/{len(pairs)} pairs recomputed with expanding-window IDF ({dropped} dropped -- "
          f"pair's own text missing from a matching year's cache, shouldn't normally happen)")

    out_path = POC / "delisted_similarity_results_expanding.csv"
    pairs.to_csv(out_path, index=False)
    print(f"Written: {out_path}")

    valid = pairs.dropna(subset=["cosine_similarity_expanding"])
    print("\nComparison, full-corpus IDF vs. expanding-window IDF:")
    print(valid[["cosine_similarity", "cosine_similarity_expanding"]].describe().round(4))
    print("\nCorrelation:", round(valid["cosine_similarity"].corr(valid["cosine_similarity_expanding"]), 4))
    diff = (valid["cosine_similarity"] - valid["cosine_similarity_expanding"]).abs()
    print("Mean absolute difference:", round(diff.mean(), 4), " median:", round(diff.median(), 4),
          " max:", round(diff.max(), 4))


if __name__ == "__main__":
    main()

"""Extends recompute_similarity_expanding_window.py's look-ahead check to
the full round-7 expanded universe (185 companies, 2010-2025). Reuses its
exact logic; only the input pairs file changes (similarity_results_full_
history.csv, the expanded-universe counterpart of delisted_similarity_
results.csv) -- SECTIONS_DIR is already the shared, already-expanded
cache (rebuild_sections_cache.py covers all 185 companies), so
load_all_texts() needs no change at all.

Usage:
    python -u -m src.processing.recompute_similarity_expanding_window_full_history
"""
from __future__ import annotations

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.recompute_similarity_expanding_window import POC, load_all_texts

OUT_PATH = POC / "similarity_results_full_history_expanding.csv"


def main() -> None:
    pairs = pd.read_csv(POC / "similarity_results_full_history.csv", dtype={"cd_cvm": str})
    pairs["cd_cvm"] = pairs["cd_cvm"].astype(int)
    texts = load_all_texts()

    print(f"{len(texts)} cached non-empty documents; {len(pairs)} existing pairs to recompute")

    new_sims = {}
    dropped = 0
    for year_curr, group in pairs.groupby("year_curr"):
        window_docs = texts[texts["year"] <= year_curr]
        if len(window_docs) < 20:
            dropped += len(group)
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
    print(f"{len(new_sims)}/{len(pairs)} pairs recomputed with expanding-window IDF ({dropped} dropped)")

    pairs.to_csv(OUT_PATH, index=False)
    print(f"Written: {OUT_PATH}")

    valid = pairs.dropna(subset=["cosine_similarity_expanding"])
    print("\nComparison, full-corpus IDF vs. expanding-window IDF:")
    print(valid[["cosine_similarity", "cosine_similarity_expanding"]].describe().round(4))
    print("\nCorrelation:", round(valid["cosine_similarity"].corr(valid["cosine_similarity_expanding"]), 4))
    diff = (valid["cosine_similarity"] - valid["cosine_similarity_expanding"]).abs()
    print("Mean absolute difference:", round(diff.mean(), 4), " median:", round(diff.median(), 4),
          " max:", round(diff.max(), 4))


if __name__ == "__main__":
    main()

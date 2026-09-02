# Data-quality correction: wrong-attachment contamination in the whole-document scenario

**Read this before trusting anything in `notebooks/poc_wholenote.ipynb` §6 (the extreme-abnormal-return finding).** That section's headline claim — "the strongest, most robust result in the whole project" — does not survive the investigation documented here. §4-5 (the delisting/bankruptcy correlation) does survive, and is now on firmer footing than before. This file is new, not an edit to the notebook, per your instruction to keep destructive-type corrections separate for your review.

## How this was found

Following up on the "spot-check extreme-return cases" task: the first several real examples read (Magazine Luiza, BRF, Direcional) all turned out to be the same problem — the acquisition pipeline had grabbed the **wrong PDF attachment** for one side of the comparison. Magazine Luiza's 2022 "note" text was actually an earnings-release deck (`MGLU_ER_4T22_POR.pdf` — "ER" = Earnings Release); comparing that to 2021's real financial statements produces near-zero similarity that has nothing to do with the debt note changing.

This is a real bug in `src/acquisition/cvm_notes.py`'s attachment-selection logic: when no attachment has a filename identifying it as the real statements, the code falls back to "largest PDF in the filing," and an earnings-release or management-report PDF can legitimately be the largest file in some years' filings. The existing `NON_STATEMENT_KEYWORDS` exclusion list didn't cover this document type at all.

## How big a problem is it — three progressively better checks

| Check | AR pairs flagged bad | Delisting pairs flagged bad |
|---|---:|---:|
| 1. Earnings-release phrases in first 15 lines | 4.2% (corpus-wide) | — |
| 2. + minimum 200-line extraction length | 9.4% | 8.8% |
| 3. Positive check: requires "Balanço Patrimonial"/"Demonstração do Resultado"/"Notas explicativas às demonstrações" literally present in the first ~400 lines | 43.3% (!) | 44.4% (!) |

**Check 3 is very likely over-flagging**, not a true 44% contamination rate — it doesn't account for filings correctly matched via the `notes_filename_match` tier, which are *supposed* to be an already-isolated notes document with no balance sheet in it at all (by design), so a real, correctly-acquired filing can legitimately fail this check. I did not have time in this pass to build a check that reliably distinguishes "isolated notes file, correctly matched" from "wrong document, incorrectly matched" — that's the real next step (see below), not a solved problem.

Rather than pick one filter and call it final, I'm reporting the range, because the disagreement between filters turns out to be the useful signal:

## The result: one finding is robust, one is not

| | Raw (uncorrected) | Filter 1 | Filter 2 | Filter 3 (strict) |
|---|---:|---:|---:|---:|
| **Delisting correlation, p-value** | 0.0014 | 0.0014* | 0.0044 | **0.0005** |
| **Extreme-AR correlation, p-value** | 0.0236 | **0.1649** | **0.1676** | 0.0512 |

*(Filter 1 was only computed for the AR test in the first pass; the delisting number shown for "Filter 1" is the raw value, not separately re-checked — Filters 2 and 3 are the meaningful comparison for delisting.)*

**The delisting/bankruptcy correlation (§4-5 of the notebook) is real.** It stays significant — actually gets *more* significant, not less — as the contamination filter gets stricter. That's the opposite of what you'd see if the raw result were an artifact of this bug. This finding is more trustworthy after this investigation than before it, not less.

**The extreme-abnormal-return correlation (§6) is not robust.** It swings from significant to not-significant to marginal depending on exactly which pairs get excluded. A real effect doesn't do that; a result that's partly propped up by a specific, identifiable data-quality issue does. **Recommend not presenting §6 as a finding until the acquisition bug is actually fixed and the whole pipeline is re-run on clean data — at that point it may turn out to be real, weak, or gone, and right now there's no way to know which.**

## What was fixed, and what deliberately wasn't

**Fixed (safe, code-only, already applied):** `src/acquisition/cvm_notes.py`'s `NON_STATEMENT_KEYWORDS` now excludes earnings-release filenames (`_ER_`, "earnings release", "release de resultados", "divulgação de resultados"). A new `looks_like_earnings_release_text()` function is ready to use as a content-based check for filings with no useful filename (legacy-era opaque temp-file names) but **is not yet wired into the acquisition path** — see next section for why.

**Deliberately not done in this session:**
- **Did not re-run acquisition against the fixed code.** This would re-select attachments for the ~4-9% of filings currently on `largest_attachment_fallback`, which only needs already-cached zip files (no new downloads) but would change `data/raw/dfp/*/notas_explicativas.pdf` for an unknown-until-run number of companies, and cascade into re-deriving every git-tracked `sections/*.json` file downstream — a bulk change to already-committed results that you should review before it happens, not something to do while you're away.
- **Did not build the "isolated notes file, no balance sheet expected" exception** for the positive-signal check, so Filter 3's 44% number should be read as an upper bound / likely overestimate, not a final rate.
- **Did not check whether this same bug affects the narrow-note or quarterly scenarios.** See `reports/wholenote_cross_scenario_extension.md` for what was checked there instead.

## Recommended next step, when you're back

1. Wire `looks_like_earnings_release_text()` into `select_source_attachments`'s fallback tier (reject a fallback candidate whose first page matches, try the next-largest candidate instead) and build the "isolated notes file" exception for the positive-signal check.
2. Re-run annual acquisition against the already-cached zips (no new downloads) — should be fast, CPU-bound only.
3. Re-derive everything downstream (sections, similarity results, abnormal returns, this notebook) the same way round 5's extraction hardening was propagated — that's a known, already-exercised process, not new work to figure out.
4. Only then decide whether §6 is worth keeping in the thesis narrative.

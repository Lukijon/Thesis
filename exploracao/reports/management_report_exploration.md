# Relatório da Administração (Management Report): acquisition and full test battery

Direct follow-up to `reports/return_predictability_exploration.md`'s recommendation. Acquired Brazil's MD&A-equivalent for the whole universe and ran the complete test battery developed this session (clustered regression, portfolio sort, size-neutralized double sort) against it. **Result: a genuinely different and partly more encouraging pattern than the debt note, but still nothing that clears the full rigor bar for return predictability.** Full detail below.

## Acquisition: 67.2% coverage, zero new downloads

Every filing's zip was already cached locally for the debt-note pipeline, so this was pure re-processing, not new acquisition. Built `src/acquisition/cvm_management_report.py`: for each of the 993 already-downloaded filings, list *every* attachment (not just the one previously kept for notes) and check each one — by filename first, then by first-page content — for the Management Report.

- **667/993 (67.2%) found** — far better than the ~13% a naive filename-only check would give, because most companies file it as its own attachment even when not obviously named (`content_match`: 511; `filename_match`: 156; `not_found`: 326).
- Spot-checked 6 random extractions directly: all real, substantial narrative content (10-68 pages, "Mensagem do Presidente," "Mensagem da Administração," genuine year-in-review commentary) — not junk, not the wrong document.
- Output: `data/raw/dfp_mgmt_report/<CD_CVM>/<ANO>/relatorio_administracao.pdf` (gitignored, same convention as every other raw corpus). Log: `data/interim/management_report_acquisition_log.csv`.
- TF-IDF year-over-year similarity (`src/processing/build_mgmt_report_corpus.py`): 562 pairs, mean 0.79, median 0.85 — a clean, non-degenerate distribution (max 0.97, no exact-1.0 spike, unlike the whole-notes-document scenario's contamination pattern).

## Full test battery, compared against every other text source tried this session

| Test | Debt note (annual) | Whole notes doc | **Management report** |
|---|---:|---:|---:|
| Delisting, raw Mann-Whitney | p=0.24 | p=0.0005 (verified) | **p<0.0001** |
| Delisting, clustered by company, no controls | p=0.49 | p=0.086 | **p=0.039** ✓ |
| Delisting, clustered + full controls | p=0.54 | p=0.54 | p=0.12 |
| Abnormal return, signed correlation | ~0, wrong sign in some cuts | r=-0.02, ns | **r=+0.06, right sign**, p=0.15 |
| Abnormal return, extreme/magnitude test | not robust | not robust (see correction doc) | p=0.065, marginal |
| Portfolio sort, best single-sort result | p=0.14 (degenerate-corrected) | p=0.10 (cleaned) | p=0.43 (best of 9 combos) |
| Portfolio sort, size-neutralized | p=0.14 | not tested (didn't clear single-sort bar) | p=0.46 (best of 3 holds) |

**Reading this honestly:** management-report text is the *only* text source this whole project has tried where a delisting-correlation test survives clustering without any control variables at all (p=0.039) — a genuinely different, better result than debt-note or whole-document text managed. Its return correlation also has the theoretically "correct" sign for the first time (matching Cohen-Malloy-Nguyen's direction, not reversed like the debt-note results). But **the portfolio sort — the more powerful, literature-standard method — shows nothing close to significant for returns**, in either its single-sort or size-neutralized form, across 3/6/12-month holds and 2-4 groups. And the delisting result, promising on its own, does not survive adding the standard financial controls (size, leverage, ROA, past return) together.

## Why the delisting result might be more real than the return result

A plausible, literature-consistent read: management reports narrate a company's *overall* situation (results, strategy, outlook, risk commentary) in a way that plausibly shifts sharply and permanently when a company is heading toward real trouble — which is exactly what "delisted/dropped from the index" captures. Predicting a *forward stock return*, though, needs the text to contain information the market hasn't priced yet, which is a higher bar than "the text changed because the company's situation changed" — the latter could easily be true (and show up in a delisting correlation) even if the market already knew and priced the underlying situation by the time the report was filed. This isn't a proven mechanism, just a reasonable way to hold both results in mind at once rather than treating them as contradictory.

## What this does and doesn't settle

- **Does not vindicate the pivot as "solved."** The core, hardest question this project has been chasing — does textual change predict *future returns* — is still unanswered by management-report text under the most rigorous test tried (portfolio sort).
- **Does add a second, real, different data point**: management-report text behaves differently from debt-note text in a specific, interpretable way (stronger/more robust for delisting, right-signed but not significant for returns), which is itself informative for deciding where to invest further effort.
- **Confirms the literature-based reasoning was directionally right** even though it didn't produce a clean "found it" result: moving toward higher-discretion text did move the numbers in the expected direction (better delisting result, correct-signed return correlation) — just not far enough, yet, to call it a finding.

## Recommendation

1. **Don't treat this as a dead end — the delisting result is worth a proper controlled follow-up** (a full clustered/fixed-effects model built specifically for this text source, not just the screening tests run here), since it's the first result in this whole project to survive clustering without controls.
2. **For returns specifically, the next highest-value move is probably H2 (analyst revision), not a fourth text-scope variant.** Three text sources (debt note, whole document, management report) and two frequencies (annual, quarterly) have now been tried against returns with the same negative result under rigorous testing. Analyst forecast revisions are a different outcome variable entirely, untested all session, with data already in hand — a better use of the next block of time than a fifth cut of the same return-prediction question.
3. If continuing to push on returns with text scope as the lever, the highest-discretion text still untried is **Risk Factors** from the Formulário de Referência — a different CVM filing this project hasn't acquired at all yet (a real new-acquisition project, unlike management report's zero-new-download reuse) — worth knowing it's the theoretically strongest remaining candidate per the literature, but a bigger lift than anything tried today.

## What was not done

- Did not build the "proper" clustered/fixed-effects model for the delisting result specifically (recommended above as the real next step for that result).
- Did not extend management-report acquisition to quarterly (ITR) filings — annual only this pass.
- Did not check management-report data for the same kind of extraction contamination the whole-document scenario had (spot-checked 6 examples, all clean, but that's not the same as a systematic check) — worth doing before leaning on the delisting result further.

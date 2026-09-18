# Risk Factors (Formulário de Referência item 4.1): acquisition and results

Direct follow-up to `panel_model_results.md`'s recommendation ("idea 2"): Risk Factors is the one theoretically-strongest text source this project hadn't tried — Cohen, Malloy and Nguyen (2020) find their strongest textual-change effect specifically in Risk Factors (188bps/month), stronger than MD&A, stronger than footnotes. This required genuinely new acquisition (a CVM filing type — FRE — never touched before), not a reuse of existing downloads.

## Acquisition: 923/978 (94.4%) coverage, new pipeline

`src/acquisition/cvm_fre.py` fetches Formulário de Referência filings from CVM's RAD system and extracts item 4.1. Two real format complications, both confirmed against multiple companies before being trusted as general rules (same discipline as every prior acquisition round):

- **Modern filings** (post-~2021): item 4.1 is CVM's own pre-isolated PDF attachment inside the filing XML, no ambiguity.
- **Legacy filings**: no dedicated attachment — a flat list of ~90 opaquely-named PDF fragments per filing, distinguished only by an internal CVM form-field code (`NumeroQuadroRelacionado`). Found that code `"805"` reliably identifies item 4.1 — confirmed on two unrelated companies (Multiplan, Hypera) before trusting it, since the neighboring "Risco de Mercado" section shares identical opening boilerplate and can't be told apart by content alone.

Also caught a download-corruption issue along the way (the existing zip validator only checks the first 2 bytes, so a truncated large download could get cached as valid) and added a retry-on-corrupt-zip step.

**Result: 923 of 978 attempted company-years succeeded (94.4%)**, consistent across all ten years 2015–2024 (87–101 per year, no systematic era gap) — confirming both extraction paths work robustly at scale, not just in the hand-validated cases. Text extraction from the acquired PDFs succeeded for 922/923 (99.9%). 811 year-over-year similarity pairs computed (`src/processing/build_risk_factors_corpus.py`), mean cosine similarity 0.91, no extraction-artifact contamination found (spot-checked the exact-1.0 cluster — confirmed genuine near-verbatim year-over-year reuse of Risk Factors boilerplate by real companies, not a pipeline bug, unlike the Marcopolo case earlier this session).

## H1 (returns): null, including for this source

Same four-stage rigor progression applied to every other text source:

| Stage | n | p-value |
|---|---:|---:|
| Correlação simples | 696 | 0.226 |
| Agrupado por empresa, s/ controles | 672 | 0.151 |
| Agrupado, c/ controles (sem tamanho) | 672 | 0.308 |
| Efeitos fixos (empresa + ano) | 672 | 0.758 |

**Null at every stage.** This matters: it's the theoretically strongest remaining candidate, tested with the same rigor as everything else, and it doesn't move the needle on H1. Combined with narrow debt note, whole document, and management report — all four text sources now tested, all four null for return predictability under the strictest available method.

## A genuinely new finding: delisting, correctly specified this time

The delisting/survivorship validity check (does textual similarity differ for companies that later left the index) hit the same problem every other source in this project has: the outcome is constant within a company, so pooled/clustered regression conflates cross-sectional and within-company variation, and company fixed effects are mathematically inapplicable (confirmed for management report in `panel_model_results.md` — forcing it produces a machine-precision-zero coefficient with a meaningless p-value).

This time, the right fix was used instead of a workaround: since delisting is inherently a **company-level** question, a **purely cross-sectional regression** — one row per company (n=110), average similarity across all its year-pairs — avoids the repeated-observations problem by construction rather than needing to correct for it after the fact.

| Specification | n | Coefficient | p-value |
|---|---:|---:|---:|
| Sem controles | 110 | -1.19 | 0.121 |
| Com controles (alavancagem, ROA, tamanho), OLS | 110 | -1.45 | **0.030** |
| Com controles, sem tamanho | 110 | -1.01 | 0.157 |
| Com controles, logit | 110 | -8.54 | **0.039** |

Correctly signed (lower similarity → higher probability of leaving the index) and survives real scrutiny: leave-one-company-out (worst case p=0.078, sign never flips), median-instead-of-mean similarity (p=0.033, essentially unchanged), no single company or degenerate score driving it.

**This is the best-supported empirical result this project has produced.** Unlike the management-report near-miss (which depended on clustering and collapsed under fixed effects), there is no sharper test left to apply here — the design already avoids the pseudo-replication problem other findings this session were undone by. It is, however, control-dependent (size specifically does real work here, unlike everywhere else in this project) and small-n (110 companies).

**What this is not**: evidence for H1. It says textual change in Risk Factors correlates with a company's later exit from the index, conditional on fundamentals — a statement about what the measure captures, not about return predictability, which remains null for this source like every other. Delisting has been used throughout this project as a validity check on the text measure, not one of the numbered hypotheses in the pre-projeto.

## Bottom line

Both hypotheses have now been tested against every text source worth trying, including the one the literature says should work best. H1 (returns) is null everywhere, at the highest rigor available, with no exceptions. The one real positive result in the whole project is about delisting, not returns, and is best framed as evidence the text measure is picking up something real about company distress — a finding worth keeping in the dissertation, but not a rescue of the central return-predictability question.

## Update to the dissertation document

`docs/dissertacao_esqueleto.docx` updated: Risk Factors added as a fifth row to the main H1 results table (§4.3), narrative updated to note that even the theoretically strongest source is null, and a new subsection in §4.4 covers the delisting cross-sectional finding with its own table and appropriate caveats.

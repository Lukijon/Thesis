# POC findings: is the TF-IDF debt-note approach viable?

**Scope:** 20 non-financial IBOV companies, hand-picked for sector diversity, drawn from the 613 filings already acquired in part 1 (2015–2024). No new downloads. Code: `src/processing/pdf_text.py`, `src/processing/locate_note_section.py`, `src/processing/run_poc_tfidf.py`. Results: `data/interim/poc/similarity_results.csv`, per-company-year sections in `data/interim/poc/sections/`.

## Bottom line

**The core measurement idea holds up — where extraction is reliable, TF-IDF/cosine similarity on the isolated debt note produces a believable, interpretable signal.** But automated note-*isolation* (finding exactly where the note starts and ends inside a 30–150 page filing) is the weak link, not the similarity measure itself. Roughly half of company-years get a precisely bounded note; the rest fall back to a much less precise method or fail outright. Scaling to the full universe needs the extraction step hardened first — this is a solvable, well-understood problem now, not an open question about whether the approach works.

## 1. Are the PDFs readable?

Yes, essentially always. Of the 200 company-years checked, PyMuPDF extracted real text (not zero characters) from all but the already-known scanned exception (Vibra Energia 2023, flagged during acquisition, not in this 20-company sample). Font-size and bold metadata — needed to tell a real section heading apart from a body-text mention of the same words — is present and usable across every filing checked, including pre-2021 "legacy" CVM filing formats.

## 2. Can the debt note be isolated automatically?

| Diagnostic | Count | Meaning |
|---|---:|---|
| `font_heading` | 86 / 200 (43%) | Found a heading visually distinct from body text (bold + larger font) — the reliable case |
| `regex_only` | 96 / 200 (48%) | No visually distinct heading found; fell back to "last keyword mention, capped at 500 lines" — imprecise |
| `not_found` | 18 / 200 (9%) | No debt-note mention matched at all |

The heuristic (see module docstring in `locate_note_section.py` for the full method) had to be extended several times during this POC to handle real variation across filers:
- Notes titled with a leading number on the same line (`"16 EMPRÉSTIMOS E FINANCIAMENTOS"`, WEG) vs. no number at all (`"Empréstimos e financiamentos"`, Usiminas) vs. the number on its *own* line before the title (also Usiminas).
- Running page headers/footers (e.g. `"WEG S.A."` repeated on every page) that visually resemble headings and have to be filtered out separately from genuine section titles.
- Same-styled sub-captions within the note (e.g. CEMIG's `"Garantias"` subsection) that must *not* be mistaken for the start of the next note.
- Filers that split the disclosure into two adjacent notes — Usiminas has a separate `"Debêntures"` note immediately after `"Empréstimos e financiamentos"`; the thesis scope is the combined debt content, so the locator now merges immediately-adjacent debt-related notes.

Each fix was validated against real, previously-broken cases before moving on (documented inline in the module). Even so, some companies remain unreliable:
- **Vale**: heavily lettered-subsection structure (`"c) Empréstimos e financiamentos"`, `"d) Empréstimos, financiamentos e arrendamentos"`) with no single stable top-level title — extraction ranged from 31 to 5,438 characters across different years for the *same company*, i.e. unstable, not just imprecise.
- **Petrobras, Gerdau, Telefônica, Fleury, Localiza**: mostly `regex_only`, format changes substantially across years within the same company.
- 18 `not_found` cases include some that trace back to an **acquisition-stage** issue, not the locator: Petrobras 2015's `notas_explicativas.pdf` is only 9 pages (a cover document, not the financial statements) — the acquisition pipeline's `largest_attachment_fallback` tier picked the wrong attachment for that specific filing.

## 3. Does the similarity measure make sense?

Full-sample distribution (162 year-pairs): mean 0.60, median 0.77, but with a large mass near 0 and near 1 — a red flag on its own. Restricting to pairs where **both** years got the reliable `font_heading` extraction (64 pairs) tightens this to a much more sensible mean 0.75 / median 0.91, and by company:

| Company | Pairs | Mean similarity | Range |
|---|---:|---:|---|
| WEG | 9 | 0.96 | 0.91 – 0.99 |
| TOTVS | 4 | 0.91 | 0.88 – 0.94 |
| MRV | 3 | 0.90 | 0.76 – 0.98 |
| CEMIG | 9 | 0.89 | 0.82 – 0.95 |
| LOCALIZA | 3 | 0.89 | 0.75 – 0.98 |
| RAIA DROGASIL | 3 | 0.82 | 0.77 – 0.91 |
| USIMINAS | 9 | 0.83 | 0.71 – 0.99 |
| AMBEV, VALE, YDUQS, SABESP(×1) | — | degenerate (see below) | includes 0.0 and/or exact 1.0 |

**Spot-check — a genuine high-similarity pair (WEG 2015→2016, 0.9915):** a real line diff shows the note's structure (BNDES/FINEP covenant clause, currency/rate categories: fixed-rate reais, TJLP-indexed, UFIR-indexed) is identical between years; only balance figures and the reference date change, plus one cosmetic word-order flip in the title. This is exactly the "boilerplate rolled forward with updated numbers" pattern the literature (Lazy Prices, Brown & Tucker) is built on — the measure is correctly reading this as highly similar.

**Spot-check — the exact-1.0 and near-0.0 outliers are extraction artifacts, not signal:**
- Yduqs shows cosine similarity of exactly **1.0000 across four different year-pairs** (2015–2019), all with identical 648-character text. Reading the actual text: it's a generic IFRS accounting-*policy* paragraph ("loans are initially recognized at fair value...") from the significant-accounting-policies note, not the actual debt note — which Yduqs numbers separately ("Nota 11") and which the locator only found in later years (as `regex_only`). The extraction locked onto the wrong, unchanging boilerplate paragraph for those years.
- Vale 2020→2021 and 2021→2022 both show exactly **1.0000** with only **47 characters** each — literally just the heading line itself, no content. Vale 2022→2023 shows **0.0000** because 2022 has the same 47-character non-extraction while 2023 got a real 3,101-character note — comparing "almost nothing" to "something" naturally collapses to near-zero.
- Ambev 2017→2018 (0.0334): 2017 correctly captured the real note (a loan-balance table); 2018's extraction instead grabbed a lettered accounting-policy item, `"(o) Empréstimos e financiamentos"` — which even explicitly cross-references *"(Nota 15 – Empréstimos e financiamentos)"* as the real note it should have found instead.

So: every degenerate score checked traces to a **known, explainable extraction miss**, not a flaw in the similarity measure itself.

## 4. Recommendation

**Go, with a scoped fix before scaling.** The measurement concept is sound and the numbers are interpretable exactly where extraction is reliable. Two concrete next steps before running this across the full non-financial universe:

1. **Harden note isolation for the unreliable ~57% (`regex_only` + `not_found`).** Options, roughly in order of effort: (a) extend the heading heuristic further using patterns seen here (Vale-style lettered subsections need a different "find the enclosing top-level note" strategy); (b) use the DFP's own table of contents / index page, where present, to get exact page ranges per note directly instead of inferring them from font styling; (c) a lightweight LLM pass to locate note boundaries for the residual hard cases, reserved for filers the heuristic can't handle.
2. **Add an automated red-flag check** before trusting any similarity score: exact 1.0/0.0 scores, or notes under some minimum length (e.g. 200 characters), should be auto-flagged for review rather than fed into the analysis silently — this POC found that every such case was a real extraction failure, not a genuine finding.

With those in place, re-running this same 20-company check should show the `font_heading`-only pattern (mean ~0.75–0.90, sensible spread, no degenerate outliers) across the full sample, at which point scaling acquisition (part 2) and building the full pipeline is a reasonable next investment.

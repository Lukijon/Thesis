# POC findings: is the TF-IDF debt-note approach viable?

**Scope (rounds 1–3):** 20 non-financial IBOV companies, hand-picked for sector diversity, drawn from the 613 filings already acquired in part 1 (2015–2024), plus a 36-company subset of the historical/delisted set for the round-3 comparison. **Scope (round 4, §7): the full acquired universe** — all 66 current non-financial IBOV constituents and all 46 historical/delisted companies (993 company-fiscal-years total). No new downloads at any round. Code: `src/processing/pdf_text.py`, `src/processing/locate_note_section.py`, `src/processing/run_poc_tfidf.py`, `src/processing/run_delisted_analysis.py`. Results: `data/interim/poc/similarity_results.csv` and `delisted_similarity_results.csv`, per-company-year sections in `data/interim/poc/sections/`.

**Status: four rounds.** Round 1 (below) established the concept works but flagged note-*isolation* as the weak link. Round 2 (§5) fixed four concrete, generalizable bugs found by chasing the round-1 outliers to ground; the reliable-cohort mean rose from 0.75 to 0.87 and every exact-zero degenerate score disappeared. Round 3 (§6) extended the check to a first cut of the survivorship-bias fix (20 vs. 36 companies): does dropping out of IBOV/delisting correlate with more textual change? Promising at that scale, not yet settled. **Round 4 (§7) reruns everything — extraction and the survivorship-bias comparison — on the complete, unbiased universe** (66 vs. 46 companies, not hand-picked subsets). The extraction picture holds up; the survivorship-bias signal weakens and is no longer statistically significant, which §7 reads honestly rather than downplays.

## Bottom line

**The core measurement idea holds up — where extraction is reliable, TF-IDF/cosine similarity on the isolated debt note produces a believable, interpretable signal.** Automated note-*isolation* (finding exactly where the note starts and ends inside a 30–150 page filing) was the weak link, not the similarity measure itself — round 2 made real progress on it, and round 4 confirms that progress holds at full scale (44% reliable extraction, same rate as the round-2 subset). Roughly 56% of company-years across the whole universe still fall back to a less precise method — hardening that further is now the clear top priority (§7), not revisiting whether the approach works.

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

## 5. Round 2: hardening the extraction heuristic

Following the round-1 recommendation, each remaining degenerate/outlier case was traced to its root cause in the actual PDF (not guessed at) and fixed generally, not patched per-company. Four real bugs found:

1. **Size should dominate the tie-break, not "purity."** The original tie-break picked the *purest*-looking candidate title first, which wrongly penalized legitimate compound titles — Vale's `"Empréstimos, financiamentos e caixa e equivalentes de caixa"` (a combined net-debt note) lost to an unrelated smaller-font subsection for mentioning "caixa." A distinctly larger font reliably marks the true top-level note across every filer checked; purity now only breaks ties *between same-sized* candidates. Fixed Vale's early years and Lojas Renner.
2. **Lettered-subsection markers collide with Portuguese articles.** `"(o) Empréstimos e financiamentos"` (an accounting-policy subsection marker) scored as pure as a real title because "o" ("the") is a legitimate connector word — the letter and the article are indistinguishable by spelling alone. Added an explicit penalty for a leading `(x)`-style marker. Fixed Ambev 2018 and similar years.
3. **Table-of-contents entries look identical to real headings.** Ambev's page-1 index lists every note number and title back-to-back in the same bold/size styling as the real section headings deep in the document — "16" / "EMPRÉSTIMOS E FINANCIAMENTOS" / "17" / "PROVISÕES..." Added a detector for dense runs of consecutive bare-number entries (a real note body never has another top-level number within a handful of lines; a TOC lists all of them in immediate succession) and excluded them from candidacy. Fixed Ambev 2024.
4. **Long compound titles wrap onto a second PDF line at identical styling.** Two separate failures from the same cause: (a) the heading-length cutoff (100 chars) excluded titles like Vale's ~120-character combined net-debt title entirely, leaving only a shorter, wrong lettered subsection to be found instead; (b) even once found, the wrapped continuation line (e.g. `"curto prazo"`) was itself short, bold, same-size, and keyword-free — exactly matching the "next unrelated heading" signal, truncating the section to almost nothing. Loosened the length cutoff and added explicit absorption of same-style continuation lines right after the heading. Fixed Vale 2020–2022 (previously the worst-behaved company in the sample).

**Result**, restricted to pairs where both years got the reliable `font_heading` extraction (still 64 pairs — these fixes corrected *which* text was extracted, not *whether* a font-based heading was found at all):

| | Round 1 | Round 2 |
|---|---:|---:|
| Mean | 0.75 | **0.87** |
| Std dev | 0.34 | **0.17** |
| Min | 0.0000 (artifact) | **0.11** (no more exact-zero artifacts) |
| Vale (worst offender) | 0.42 mean, unstable 31–5,438 chars/year | **0.78 mean**, stable across every year |
| Ambev | 0.30 mean (two wrong-note years) | **0.95 mean** |
| Lojas Renner | 0.54 mean | **0.91 mean** |

Overall extraction-trigger rate barely moved (`font_heading` still 86/200 — these were accuracy fixes, not detection fixes): `regex_only` rose slightly to 99/200 and `not_found` dropped to 15/200 as a side effect of the same fixes recovering a few previously-empty documents.

**Still open, not chased further this round** (diminishing returns for single-company, single-year quirks vs. the four general fixes above):
- Yduqs and Sabesp still show exact-1.0 similarity in some years — a *different* root cause than what was fixed here: the real note simply isn't styled distinctly in those specific years at all, so there's no larger/differently-styled candidate to prefer. This needs either the DFP index-page approach or an LLM fallback (round-1 recommendation, still valid), not another heuristic tweak.
- Suzano 2019 (853 chars, likely related to that year's Fibria merger restructuring the notes) remains a one-off truncation not yet root-caused.

**Updated recommendation:** the extraction heuristic is now meaningfully more trustworthy, but the two round-1 recommendations still stand for the remaining ~57% (`regex_only`/`not_found`) — the DFP-index-page investigation and an automated red-flag check (exact 0/1 similarity, or notes under ~200 characters) before scaling to part 2.

## 6. Round 3: does dropping out of IBOV correlate with textual change?

Part 1's acquisition originally covered only *today's* 66 non-financial IBOV constituents — a real survivorship-bias problem for a thesis about debt-distress signals, since a company that went bankrupt, got acquired, or was delisted mid-sample is exactly the kind most likely to both show large textual change *and* disappear from the index, and would have been entirely absent. That gap is closed (see `src/acquisition/b3_ibov_historical.py`): 36 more companies were found that were IBOV members at some point in 2015–2024 but aren't today — 26 via Internet Archive snapshots of B3's retired portfolio page, 10 more via a user-provided Bloomberg historical-composition export. Several are directly on-theme: Oi, Light, and Rossi Residencial are currently in *recuperação judicial*; MMX Mineração is a bankruptcy estate.

**Method:** the same note-locator and TF-IDF pipeline (`src/processing/run_delisted_analysis.py`) run on these 36 companies (34 with usable filings, 401 year-over-year pairs), compared against the original 20 "stayed" companies from §5, fit as one shared TF-IDF corpus so results are directly comparable.

**Result, reliable (`font_heading`/`font_heading`) pairs only:**

| Group | n | Mean | Median | Std |
|---|---:|---:|---:|---:|
| Dropped / delisted | 104 | 0.742 | 0.866 | 0.288 |
| Stayed in IBOV | 64 | 0.876 | 0.924 | 0.161 |

Mann-Whitney U (dropped < stayed, one-sided): **p = 0.0028**.

**Robustness check — does this survive the same skepticism applied everywhere else in this project?** The dropped/delisted group is newer to the pipeline and hasn't had round-2's hardening, so restricting to pairs where the extracted note length is reasonably consistent across both years (`size_ratio >= 0.5`, a proxy for "the locator found comparable content both times") is a direct test of whether the gap is real or extraction noise:

| Group (size-consistent only) | n | Mean | Median |
|---|---:|---:|---:|
| Dropped / delisted | 81 | 0.859 | 0.905 |
| Stayed in IBOV | 60 | 0.904 | 0.926 |

p rises to **0.068** — the direction holds, but conventional significance doesn't survive the stricter filter. Honest reading: part of the raw gap is genuinely extraction noise specific to this newer company set, not pure signal.

**Two spot-checks, both sides of that honestly:**
- **Grupo Casas Bahia (Via Varejo) 2023→2024 (similarity 0.577, size-consistent):** the actual diff shows real debt restructuring — new debenture issuances (10ª emissão replacing the 8ª), materially changed interest-rate spreads (CDI+4.00%→CDI+1.28% on one line item) — during the company's known 2023–2024 financial distress. This is the pipeline working as intended.
- **MMX Mineração (bankruptcy estate) 2016→2018 (similarity 0.363):** both years captured the generic IFRS accounting-*policy* paragraph again — the same failure mode as the Yduqs artifact in §3 — not real bankruptcy-specific disclosure. A company literally in bankruptcy proceedings is exactly the case where the real note would be most informative, and exactly the case this pipeline currently fails on.

**Recommendation:** promising, not yet settled. Treat as a hypothesis worth pursuing, not a finding to cite yet — extend round-2-style hardening to this 36-company set specifically (distressed filers are the hardest case: irregular formats, mid-restructuring documents, inconsistent filers) before relying on this result in the thesis. Full detail and reproducible numbers in `notebooks/poc_overview.ipynb` §5.

**Update (round 4, §7 below): re-run on the full, unbiased universe instead of this hand-picked subset, the effect weakens and loses significance.** The direction still holds, but the earlier p-values here reflected which companies happened to get picked into each group at least as much as extraction noise in the historical set. See §7.

## 7. Round 4: scaling the whole POC to the full acquired universe

Rounds 1–3 all ran on non-random subsets: 20 hand-picked current-IBOV companies (sector diversity, not randomly drawn) and, for round 3, the first 36 of the 46 historical/delisted companies found by that point. Both choices were reasonable for an early POC, but neither rules out the subset itself driving the results. Round 4 answers the obvious next question — does this hold up on the complete, unbiased universe? — by re-running the identical pipeline (no code changes to the note-locator or TF-IDF step) on:

- **All 66 current non-financial IBOV constituents** (`src/processing/run_poc_tfidf.py`, `POC_COMPANIES` now loaded directly from `data/interim/ibov_non_financial_universe.csv` instead of a hardcoded 20-company dict)
- **All 46 historical/delisted companies** (`src/processing/run_delisted_analysis.py`, unchanged — it already combined `POC_COMPANIES` with the historical set, so expanding the former automatically expanded the comparison)

### 7.1 Extraction reliability holds up at scale

| | Round 2 (20 companies) | Round 4 (66 companies) |
|---|---:|---:|
| Company-years checked | 200 | 613 |
| `font_heading` (reliable) | 43% | 44% |
| `regex_only` | 48% | 46% |
| `not_found` | 9% | 10% |

The reliable-extraction rate is essentially unchanged going from 20 hand-picked companies to the full 66 — a good sign that round 2's fixes generalize rather than having been overfit to the original sample. The reliable-cohort similarity distribution: n=198 pairs, mean 0.77, median 0.89 (versus round 2's n=64, mean 0.87, median 0.92 — somewhat lower and more spread out once smaller, less-followed filers are included, but still a sensible, non-degenerate distribution). 19 of 198 reliable pairs (10%) are still degenerate (≥0.999 or ≤0.001 similarity) — the same known artifact types as rounds 1–2 (static accounting-policy boilerplate, near-empty extractions), now including a few new companies (Marcopolo, Natura) alongside the already-known Yduqs case.

### 7.2 The survivorship-bias signal weakens at full scale — reported honestly

This is the most important round-4 result. Re-running the round-3 comparison (dropped/delisted vs. stayed) on the full 66-vs-46 universe instead of the hand-picked 20-vs-36 subset:

| | Round 3 (20 vs. 36) | Round 4 (66 vs. 46) |
|---|---:|---:|
| Reliable pairs (dropped / stayed) | 104 / 64 | 118 / 198 |
| Mean similarity (dropped / stayed) | 0.742 / 0.876 | 0.749 / 0.767 |
| Mann-Whitney p (raw, one-sided) | **0.0028** | **0.178** |
| Mann-Whitney p (size-consistent ≥0.5) | 0.068 | 0.106 |

The direction is unchanged — dropped/delisted companies still show somewhat lower year-over-year similarity on average, in both cuts — but neither cut reaches conventional significance at full scale, and the raw comparison's p-value moved from clearly significant to clearly not. Round 3's write-up attributed the earlier weakening (0.0028 → 0.068) entirely to extraction noise in the newer, less-hardened historical set. Round 4 shows that explanation was incomplete: even the *stayed* group's mean similarity dropped once it went from 20 hand-picked, well-known, large-cap companies (0.876) to the full 66-company universe including smaller, less-followed filers (0.767) — meaning part of the original gap between groups reflected which companies were picked into each side, not a real stayed-vs-dropped difference. This doesn't kill the survivorship-bias hypothesis (the direction is consistent, and the theoretical logic — distressed companies both change disclosures more and leave the index — is still sound), but it moves the finding from "promising, weakened under one robustness check" to "directionally consistent, not yet a significant one," which is a meaningfully more honest place to be before citing it in the thesis.

The two round-3 spot-checks (Grupo Casas Bahia's real 2023→2024 debt restructuring correctly detected at similarity 0.58; MMX Mineração's bankruptcy-era extraction still failing on generic accounting-policy boilerplate at similarity 0.36) reproduce essentially unchanged at full scale and still illustrate both sides honestly: the pipeline works when extraction succeeds, and still fails on exactly the distressed-filer cases the thesis cares about most.

### 7.3 The H1 pipeline checkpoint, now over the full universe

`src/analysis/compute_abnormal_returns.py` was re-run against the expanded similarity files. Two things changed here independent of the "full universe" scale-up and are worth flagging as bugs found and fixed during this round:

- A diagnostic print in that script mislabeled its ticker-resolution count (it reported "95 of the historical/delisted set" resolved a ticker, which is impossible for a 46-company set — the bug was counting overlap against the wrong reference set). Fixed; the correct, verified number is **30 of 46**.
- The `poc_group` column's `"core_20"` label was renamed to `"current_66"` to match what it now actually contains.

With those fixed, the checkpoint: 676 pairs now have both a similarity score and a computable 12-month abnormal return (up from 297 at the 20/36-company scale). Correlation with the market-adjusted abnormal return remains weak — Pearson r = -0.087 (all computable pairs, n=676), r = -0.120 (reliable-extraction only, n=259) — somewhat stronger than the earlier -0.05/-0.06 but still far from a meaningful relationship, and still expected at this stage: no fundamentals-based controls, a market-adjusted (not market-model) return, and extraction noise still present in over half the universe. This remains a pipeline-completeness result, not a test of H1.

### 7.4 Updated recommendation

The extraction heuristic's reliability generalizes well (7.1) — that's no longer a question worth re-litigating. What changed is the survivorship-bias finding's status: it needs to be described as directional-but-not-yet-significant, not "promising," in any thesis-facing writing until the ~56%-of-universe extraction gap is closed. Concretely, before this line of investigation is citable:

1. Extend round-2-style hardening (DFP index-page parsing, or an LLM fallback for the `regex_only`/`not_found` cases) across the *whole* universe, not another company-specific patch — the round-4 result shows the effect may already be real but is currently underpowered by extraction noise on both sides of the comparison.
2. Add the automated red-flag check recommended since round 1 (exact 0/1 similarity, notes under ~200 characters) so degenerate pairs are caught systematically instead of by manual spot-check.
3. Resolve the 16 historical/delisted companies with no tradeable current ticker (§7.3) — an explicit exclude-vs-proxy decision, not a silent drop — before the H1 checkpoint can claim full-universe coverage on the returns side too.

## 9. Round 5: hardening annual extraction, propagated through the full pipeline

Round 4 named extraction reliability (44% `font_heading` full-universe) as the clear top priority. Round 5 addresses it directly: six candidate fixes were evaluated, four implemented, two investigated and explicitly rejected on evidence. All numbers below are from a full re-run of the 997-filing annual corpus (current-66 + historical-46), measured with a purpose-built harness (`src/processing/eval_note_locator.py`) that caches raw extracted lines once and reruns just the heuristic on each change — letting extraction logic be iterated in seconds instead of re-parsing PDFs every time.

### 9.1 What was fixed, and the measured effect of each

| Stage | `font_heading` | `regex_only` | `not_found` |
|---|---:|---:|---:|
| Round 4 baseline | 43.8% (437/997) | 45.8% | 10.3% |
| + PDF native bookmarks | 44.7% (446/997) | 44.9% | 10.3% |
| + same-size headings (bold, caps or numbered) | 54.2% (540/997) | 35.5% | 10.3% |
| + non-bold caps+numbered, + "debênture" alone | **64.9% (647/997)** | 28.5% | 6.6% |

1. **PDF native bookmarks** (`pdf_text.extract_bookmarks`, `locate_note_section._bookmark_section`). Checked empirically before building anything: only 4.8% of then-unreliable filings had any PDF outline at all, 1.8% (10/559) had one naming the debt note specifically. Implemented anyway since it's essentially free and strictly additive — a bookmark match is more precise than any heuristic, not less.
2. **Same-size headings, bold + (ALL-CAPS or numbered prefix).** The single biggest fix. Direct inspection of persistently-failing companies (Gerdau, Sid Nacional) showed their real note headings — e.g. "NOTA 13 - EMPRÉSTIMOS E FINANCIAMENTOS", "12. EMPRÉSTIMOS, FINANCIAMENTOS E DEBÊNTURES" — are bold and unambiguous but **never larger than body text**, which the original heuristic required unconditionally. This single fix resolved **22 companies that had a 0% reliable-extraction rate across every year checked** — not edge cases, but an entire class of filer the size-only heuristic could never have handled regardless of further tuning.
3. **Non-bold caps+numbered headings.** A further check on the still-failing residual found companies (e.g. Rumo-style filers) whose headings are ALL-CAPS and numbered but **not even bold** — "11. EMPRÉSTIMOS E FINANCIAMENTOS", same size as body, no bold. Requiring *both* signals together (not either alone) keeps this from over-matching ordinary body text, which would be far too permissive as a standalone rule.
4. **"Debênture" as a qualifying keyword on its own.** The original candidacy check required 2 of the 3 keyword stems (empréstimo/financiamento/debênture) in one line. This silently excluded any filer whose combined note is titled plainly "Debêntures" with no "Empréstimos e Financiamentos" in the same heading (found via company 022187). "Debênture" alone is safe to treat as sufficient — unlike "empréstimo" or "financiamento" alone, which also appear in unrelated headings (a cash-flow-statement line "Fluxo de caixa de atividades de financiamento" was the concrete false-positive risk that kept the 2-stem rule in place for those two).

Every fix was validated against the three companies it was diagnosed from, *and* against three already-working controls (WEG, Vale, and the round-2-fixed case) to confirm zero regression, before being counted.

### 9.2 What was investigated and rejected

- **Table-of-contents/index-page detection** — several filers print a literal page index. Checked how often this would actually help before building it: only **1.4% (5/350)** of remaining failures have a body-text TOC region naming a debt note. Not worth the complexity (page-number-to-PDF-page mapping is itself a real source of bugs) for that yield.
- **Following explicit "Nota N" cross-references.** 25.7% (90/350) of remaining failures have text mentioning "Nota N" near a debt keyword — promising on the surface. But checking whether that referenced note is actually *findable and correct* showed only **13/50 (26%) resolve to real content**; the rest latch onto the same bare number N appearing elsewhere in the document as a table value, unrelated footnote, or different cross-reference entirely (concrete false matches: chasing "Nota 12" landed on the number "51.131", "Nota 1" landed on "111" — clearly wrong). Implementing this as designed would silently tag wrong content as high-confidence `font_heading` — a worse outcome than leaving it `regex_only`, since a confidently-wrong "reliable" tag actively misleads downstream analysis rather than just being imprecise. Not implemented.

### 9.3 Residual failures: a shrinking, increasingly idiosyncratic tail

Companies with a 0% reliable-extraction rate (≥3 years checked): **22 → 12 → 5** across the fix sequence. The remaining 5 (012793, 020605, 024848, 025011, 025232) plus a longer tail of low-but-nonzero companies no longer share a common pattern — e.g. Braskem (004820, one of the original 20-company POC set, still only 1/10 reliable) traces to a "Nota 16" cross-reference pointing at real content that genuinely isn't styled as a heading at all in that filer's PDFs. Two of the 5 (009512-Petrobras, 025011) are scanned/image-only PDFs with zero extractable text at all — an OCR problem, not a heuristic one, same as the already-known Vibra Energia 2023 case. Further gains from here likely need per-company overrides rather than more general rules — diminishing returns per unit of effort, not pursued further in this round.

### 9.4 Propagated through the full pipeline

The hardened heuristic was re-run across every downstream artifact, not left as an isolated diagnostic:

- **Current-66 universe** (`similarity_results.csv`): 416/613 (67.9%) `font_heading`, up from 44.0%. Reliable pairs: n=313 (up from 198), mean 0.73, median 0.84 — a mean *slightly lower* than round 4's 0.77 (expected: the newly-recovered filings are exactly the harder, messier cases previously excluded from the reliable pool) but the degenerate-pair rate actually **dropped**, 6.4% (20/313) vs. round 4's 9.6% (19/198), despite far more pairs.
- **Historical/delisted set** (`delisted_similarity_results.csv`): 228/380 (60.0%) `font_heading`, up from 43.2%. Combined reliable pool for the stayed-vs-dropped comparison: n=482 (up from 316). Re-running the Mann-Whitney test: **p = 0.24 raw (was 0.18), p = 0.14 size-consistent (was 0.11)** — still directionally consistent, still not significant. This is a useful negative check in itself: if round 4's non-result had been an artifact of noisy historical-side extraction, substantially more reliable data should have moved the needle toward significance. It didn't move much either way.
- **H1 abnormal-return checkpoint** (`abnormal_returns_poc.csv`): 704 computable pairs (up from 676), 413 reliable (up from 259). Correlations remain trivial: Pearson r = -0.026 (all pairs), -0.084 (reliable only) — both essentially unchanged from round 4's -0.087/-0.120, i.e. still no signal, as expected without controls.
- **Quarterly (ITR) pilot (§8)** has *not* been re-run with round 5's fixes yet — the full historical quarterly download was still in progress when this round completed. The fixes are general (not annual-specific) and should help quarterly extraction too, but quarterly's own new failure mode (MRV's glossary-entry artifact, §8.2) needs its own targeted fix regardless of this round's work.

**Updated recommendation:** annual extraction reliability has moved from "roughly a coin flip" to "solidly majority-case" (68% on the current universe), via general, well-evidenced fixes rather than per-company patching, and every downstream number in this report now reflects that improvement. The remaining ~32% is a genuinely harder, more idiosyncratic tail (scanned PDFs needing OCR, single-company formatting quirks) where further investment should shift from general heuristics to targeted per-company overrides if pursued at all. The survivorship-bias finding (§7) remains the most important open question for the thesis and is now on firmer ground than before — not because it became significant, but because more reliable data confirmed it *isn't*, ruling out "it's just extraction noise" as the explanation for round 4's result.

Motivating idea: an annual-only comparison can leave up to ~12 months between a company's actual deterioration and when that shows up as year-over-year textual change — potentially too coarse to be useful as an early signal. CVM's quarterly filings (ITR — "Informações Trimestrais") carry the same kind of explanatory notes at Q1/Q2/Q3 cadence (Q4 is covered by the annual DFP already in the corpus, not ITR).

**Scope:** the same 20-company hand-picked set as the original annual POC (rounds 1-2), 2015Q1-2024Q3 (600 company-quarters). Deliberately the same companies as the annual baseline, not a fresh selection, so quarterly results are directly comparable rather than confounded by a different sample. Code: `src/acquisition/cvm_itr.py` (acquisition), `src/processing/run_itr_tfidf.py` (extraction + similarity, this section). Results: `data/interim/poc/itr_similarity_results.csv`, sections in `data/interim/poc/itr_sections/`.

**A real structural gotcha found while building acquisition**, worth recording so it isn't re-discovered: ITR filing packages use the same overall shape as DFP (modern XML-embedded attachments; legacy nested-zip for pre-2021 filings) but a *different* attachment tag name (`XmlInformacoesTrimestraisFinanceirasDadosITRAnexoDocumento` vs. DFP's `...DadosDFPAnexoDocumento`) and a different cover-form filename to exclude. The first extraction attempt silently returned zero attachments because of this. `cvm_notes.list_attachments()` was parameterized (`modern_tag`/`modern_exclude`/`legacy_extension`, defaults unchanged so the annual pipeline is unaffected) rather than duplicating the parsing logic; confirmed working against both a modern (2023) and legacy (2016) filing before running the batch acquisition.

### 8.1 Extraction reliability

| | Annual, round 2 (20 companies) | Quarterly, this pilot (20 companies) |
|---|---:|---:|
| Company-periods checked | 200 | 600 |
| `font_heading` (reliable) | 43% | 39% |
| `regex_only` | 48% | 52% |
| `not_found` | 9% | 9% |

Comparable, not a collapse — quarterly filings are extractable at roughly the same rate as annual ones, on the same companies. Reliable-pair similarity: n=184, mean 0.86, median 0.95 (all pairs: n=524, mean 0.64, median 0.86) — a healthy, non-degenerate distribution, similar shape to the annual data.

### 8.2 A new failure mode, not present in the annual data

20 of 184 reliable pairs (11%) are degenerate (≥0.999 or ≤0.001). Ten of those are a single company, **MRV**, locked onto an identical **119-character extraction across eleven consecutive quarter-pairs** (2015-2023) — cosine similarity exactly 1.0000 every time. Reading the actual text: it's a glossary entry defining a financing-source acronym ("SBPE — Sistema Brasileiro de Poupança e Empréstimo — Financiamento bancário que tem como fonte os recursos da poupança"), not the real note — apparently styled like a heading in MRV's quarterly filings specifically. This is a genuinely new artifact type: the annual pipeline's known failure modes (accounting-policy paragraphs, table-of-contents entries, wrapped titles) never included a definitions/glossary entry, because that structure doesn't appear the same way in annual filings.

**SABESP** shows the opposite problem: real but tiny, unstable extractions (115-496 characters, a different fragment each quarter) producing near-zero similarity across all 4 of its reliable pairs — not genuine signal, just noise from grabbing different small fragments each time.

**Spot-check — genuine signal, same pattern as annual (WEG 2023Q1 → 2023Q2, similarity 0.9987):** identical note structure, only the reference date and balance figures change — the same "boilerplate rolled forward" pattern validated in the annual data (§3), now confirmed at quarterly frequency.

### 8.3 Recommendation

The core measurement idea transfers to quarterly frequency — extraction reliability is in the same range as annual, and a genuine case behaves exactly as expected. But **annual-frequency hardening does not automatically cover quarterly failure modes** — MRV's glossary-entry artifact needed its own investigation and would need its own fix (a check against short, definition-style entries, and a per-company stability check that would catch SABESP's instability automatically) before quarterly numbers are trustworthy at scale.

More importantly, **the actual motivating question — does quarterly textual change show up before the corresponding annual change would have — hasn't been tested yet.** This pilot only establishes that quarterly extraction is plausible, not that it catches anything sooner. That test needs known-distress companies (the historical/delisted set from §6 is the natural candidate pool) and a comparison of *when* similarity drops at quarterly vs. annual granularity for the same underlying deterioration event. Also still open: how to splice annual Q4 notes (longer, differently structured) into a mixed quarterly+annual cadence, which is its own design question, not just a data-gap issue.

# Return-predictability exploration: methods tried, what was found, and a recommendation

Answers a direct question: across every reasonable scenario, control, and methodology this project can currently support, is there **any** specification where debt-note (or whole-document) textual change shows a real, defensible relationship with future abnormal returns? Short answer: **no, not yet, with the current text sources** — but the investigation surfaced a concrete, literature-grounded reason why, and a specific, actionable next step. Full detail below; see `reports/SESSION_INDEX_2026-08.md` for how this fits with the rest of this project's open threads.

## What's new here vs. everything tried before

Every prior test in this project (rounds 1-6) used either a simple Pearson/Spearman correlation or a pooled logistic regression on individual company-year pairs. This round adds a fundamentally different, literature-standard method: **the calendar-time long-short portfolio sort** used by Cohen, Malloy & Nguyen (2020, "Lazy Prices") — the thesis's core cited paper. Read the actual paper (NBER working-paper version, extracted and parsed in full, not summarized secondhand) to get the real methodology, which turns out to differ from what this project had been doing in several important ways:

- **Portfolios, not pooled regression.** Each month, rank all currently-held firms into groups by similarity score; go long the most-similar group ("non-changers"), short the least-similar group ("changers"); the spread's own time series is the test statistic. This aggregates away firm-level noise in a way a pooled correlation cannot.
- **Short holding period, monthly rebalancing.** The paper holds each position only **3 months**, not the 12-month buy-and-hold used everywhere in this project. Firms enter the month after disclosure; portfolios roll monthly ("vintages").
- **The effect is not evenly spread across a 10-K.** The paper explicitly decomposes by section: the effect concentrates in **Risk Factors** (strongest: >188bps/month, t=2.76) and **MD&A** (management discretion is high in both) — not footnotes. A companion paper in the same lit review, Amel-Zadeh & Faasse (2016), directly compares MD&A vs. footnotes and finds footnotes react "more slowly and weakly" — real, but structurally weaker. This matters a lot for interpreting a null result on debt-note footnotes specifically (see Recommendation).
- **Announcement-day return is exactly zero** in the paper — the whole point is investors don't react at filing, only gradually afterward. Not independently re-verified here (would need daily-level event-study infrastructure this project doesn't have yet), but worth keeping in mind as a mechanism check for later.

New code: `src/analysis/portfolio_sort.py` (the sort + Newey-West significance engine), `src/analysis/run_portfolio_sorts.py` and `src/analysis/portfolio_sort_grid.py` (drivers across scenarios).

## The scenario grid actually run

| Dimension | Values tried |
|---|---|
| Text scope | Narrow debt-note (reliable-extraction only); whole notes document (contamination-cleaned, see `wholenote_data_quality_correction.md`) |
| Frequency | Annual; quarterly; combined annual+quarterly (validated real calendar-month dispersion first — see below) |
| Holding period | 3, 6, 12 months |
| Number of sort groups | 2 (median split), 3 (terciles), 4, 5 (quintiles, per the paper) |
| Confound handling | Raw; size-neutralized double sort (split by firm size first, then similarity within each size bucket — directly addresses the size confound found in earlier rounds, rather than just noting it) |
| Data-quality handling | Raw; contamination-cleaned (whole-document); extraction-reliable-only (narrow-note); degenerate-score-excluded (exact 0.0/1.0 similarity dropped) |

**On combining annual + quarterly**: checked first whether this is even mechanically sound. Brazilian annual (DFP) filings cluster heavily in Feb-Mar (87% of them), too concentrated on their own for monthly portfolio granularity — but quarterly (ITR) filings spread through May/Aug/Nov, and the combination covers all 12 months with real volume every month. This is exactly the calendar spread the paper's method needs, confirming the combined approach is methodologically sound, not just a data-augmentation convenience.

## What was found, step by step

1. **First pass (uncleaned data): one result looked real.** Whole-document annual, terciles, 12-month hold: t=-2.27, p=0.023. Before reporting it, re-ran on the contamination-cleaned dataset (same one from `wholenote_data_quality_correction.md`) — **the sign flipped and significance vanished** (p=0.10-0.30). Another confirmation that whole-document contamination isn't a minor nuisance; it can manufacture a plausible-looking result from nothing.

2. **Systematic clean-data grid**: of ~30 (scenario × holding × groups) combinations on cleaned/reliable data, exactly two cleared p<0.10 on the first pass: narrow-annual at 12-month/2-3 groups (p≈0.05-0.07) and narrow-quarterly at 3-month/4-5 groups (p≈0.09), with **opposite signs** — annual says "more change → higher future return," quarterly says "more change → lower future return" (matching the paper's direction). An interesting horizon-dependent pattern, but neither cleared conventional significance on its own.

3. **Size-neutralized double sort, narrow-annual**: the 12-month result got *stronger*, not weaker (p=0.022, t=-2.28) — exactly what you'd hope for from a real effect surviving a harder test. It also built monotonically with horizon (t: 0.10 at 3mo → 1.31 at 6mo → 2.28 at 12mo), consistent with a genuinely gradual, "lazy" incorporation story rather than a fluke.

4. **Spot-check before trusting it (the same discipline used throughout this project): read the actual companies in each bucket.** Marcopolo appeared **six times** in the high-similarity ("non-changer") bucket with an exact 1.0000 score — the identical known extraction artifact flagged back in round 4/5 (a static, non-note passage repeating verbatim, not real textual stability). Re-ran the size-neutral sort excluding all degenerate exact-0/1 scores (31 of 481 pairs): **the result weakened back to non-significance** (p=0.14, t=-1.48).

**Net result: nothing survives the full chain of legitimate scrutiny** — data-quality cleaning, extraction-reliability filtering, degenerate-score exclusion, size-neutralization, and proper time-series (not pooled-panel) significance testing, applied together. This is consistent with, and now further confirms, `reports/wholenote_cross_scenario_extension.md`'s earlier conclusion via a completely different method (portfolio sort vs. clustered regression) — two independent statistical approaches agreeing is itself a meaningful result.

## Why, not just whether — the literature gives a real answer

This isn't just "we didn't find it, maybe try more specifications." Cohen/Malloy/Nguyen's own within-paper section breakdown, read directly from the source, says the effect is concentrated in sections where **management has the most discretion** (Risk Factors, MD&A) and is weaker in more formulaic, audited content. A debt note is about as far toward "formulaic and audited" as financial-statement text gets — standardized disclosure of contract terms, indexation, maturity schedules, largely dictated by IFRS/CVM requirements, not managerial narrative choice. Amel-Zadeh & Faasse's direct footnotes-vs-MD&A comparison found exactly this gradient empirically, not just as a stated concern. **The null result on debt-note text specifically is consistent with what the cited literature would predict, not a surprise or a methodological failure.**

## A concrete, evidence-based next step: Relatório da Administração

Brazil's closest regulatory equivalent to the US MD&A is the **Relatório da Administração** (Management Report) — free-form narrative, high managerial discretion, filed alongside the same DFP package already being acquired. Checked how much of this text this project already has, as a byproduct of the attachment-selection work in `wholenote_data_quality_correction.md`: **90 of 991 filings (9.1%) already have Relatório da Administração text captured** (currently mislabeled as noise/excluded, since the acquisition pipeline was built to find the notes, not this). That's not yet enough for its own robust portfolio-sort sample once matched into year-over-year pairs, but it confirms the document is real, present, and already flows through the existing acquisition infrastructure — a dedicated acquisition tier targeting it specifically (the exclusion keyword `"relatorio da administracao"` already exists in `cvm_notes.py`; this would mean *adding* a tier that targets it, not fighting the existing logic) is a small, well-scoped extension, not a new pipeline from scratch.

## Recommendation

1. **Report the current null result as a real, defensible finding, not a failure.** The debt note was tested under a proper literature-standard method (portfolio sort, not just pooled correlation), with contamination controls, reliability filtering, size-neutralization, and a real spot-check that caught a specific false positive before it got reported — that's a thorough, citable robustness chapter regardless of what's tested next. Pair it explicitly with the Amel-Zadeh & Faasse footnotes-vs-MD&A gradient as the theoretical explanation, not just an empirical shrug.
2. **Highest-value next step: acquire Relatório da Administração specifically and re-run the same battery of tests on it.** Directly grounded in where the cited literature's strongest results actually come from, not a guess — and the acquisition path is short given what already exists. This is a bigger scope decision than the narrow-vs-whole-document question in `wholenote_alignment_review.md` (it changes the primary data source, not just how one document is sliced), so it's worth a deliberate conversation, possibly with your advisor, about whether the thesis's "debt note" framing extends to this or whether it becomes a comparison chapter (debt notes vs. management report, testing the discretion-gradient hypothesis directly).
3. **Second, cheaper option: test H2 (analyst EPS consensus revision) against the existing debt-note data.** Never actually run this session — the consensus data is acquired and coverage-checked (`data/raw/analysts/eps_consensus_bloomberg.csv`), and analysts are plausibly more attentive readers of footnote-level text than the broad market is, which the literature doesn't rule out and which this project hasn't tested at all yet.
4. **The horizon-dependent sign flip (§3 above) is worth one sentence as a research note, not a finding** — it didn't survive full scrutiny, but "does the direction of the effect change between short and long holding windows" is a real, testable question for whichever text source ends up being pursued next.

## What this exploration did not do

- Did not build an event-study check of announcement-day returns (the paper's own strongest mechanism evidence) — this project's return data is monthly-resampled from daily prices, which would support it, but wasn't attempted here.
- Did not acquire or test Relatório da Administração as a real sample (recommended above, not started).
- Did not test H2 at all this session.
- Did not attempt value-weighting (would need shares-outstanding data not currently in this project) — used equal-weighting throughout, matching the paper's equal-weight panel (which the paper itself finds slightly weaker than value-weight, so this project's results are if anything a conservative test).
- Did not re-run the same portfolio-sort grid on the combined annual+quarterly dataset with size-neutralization (only the single-sort version was tested there; given neither single-sort component was robust, this was deprioritized, not forgotten).

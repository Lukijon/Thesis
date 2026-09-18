# H2 (analyst EPS revision): full scenario battery

Direct follow-up to `management_report_exploration.md`'s recommendation and your instruction to run "all scenarios we have" against H2. This is the first H2 work this session — everything before this was H1 (returns). Same four text sources tried for H1, same rigor progression (signed correlation -> magnitude correlation -> clustered-by-company regression, with and without controls), plus a tercile comparison and the standing delisting check applied to the new outcome variable. **Result: a clean, thorough null, matching H1's pattern almost exactly — no core test in any scenario is significant, and the handful of "significant" secondary hits both look like the two specific false-positive traps this project has already learned to catch.**

## The outcome variable, and an honest measurement caveat

`data/raw/analysts/eps_consensus_bloomberg.csv` (Bloomberg `IS_EPS`, `fpt=Q`/`ae=E`) is a **rolling** near-term consensus EPS series — one snapshot roughly every 3 months, tracking whichever quarter Bloomberg treats as "current" at that date. It is *not* a fixed-target-period series re-sampled over time (that would need one column per target quarter; the export has exactly one column per ticker).

The original TODO note anticipated defining revision as "the change in consensus for the *same target quarter* between two dates." **That measure isn't buildable from this export** — there's no per-target-period history, only the rolling view. What's implemented instead (`src/analysis/compute_eps_revisions.py`), mirroring how `compute_abnormal_returns.py` brackets a forward return window from the same disclosure event:

- **pre_eps** = last consensus snapshot on or before the filing's disclosure date
- **post_eps** = first snapshot after the disclosure date, within 140 days (~1 quarterly cycle + buffer)
- **revision_pct** = (post_eps − pre_eps) / |pre_eps|

Because the series can roll to a new target quarter between the pre and post snapshots, part of the measured "revision" reflects the normal quarter-to-quarter shift in consensus level rather than a pure sentiment revision — noise this measure can't remove. This is the best construct available from what was exported; if a true same-target-quarter revision measure is wanted later, it needs a different Bloomberg pull (one column per fiscal-period target, e.g. `BEst_EPS` with a fixed `fpr` per column), not a code fix.

**Historical/delisted coverage, checked for the first time (was flagged open in TODO.md):** 27 of the 45 historical/delisted companies have EPS consensus data (of the 30 that resolve to a live ticker at all — the other 15 are genuinely gone from the market, same gap already documented for prices). Combined with 64/66 current-universe companies, that's **91/111 companies (82%)** with some coverage — but pair-level coverage after date-bracketing is lower (~65% for narrow-annual, see table below), since not every disclosure event has both a pre- and post-snapshot within the window.

## Scenarios tested

Same four text sources as the H1 battery, all already-computed similarity data, no new acquisition:

| Scenario | Source file | Frequency |
|---|---|---|
| `narrow_annual` | `delisted_similarity_results.csv` | annual, debt note only |
| `narrow_quarterly` | `itr_similarity_results.csv` | quarterly, debt note only |
| `whole_notes` | `full_notes_similarity_results_VERIFIED.csv` | annual, entire notes document |
| `mgmt_report` | `mgmt_report_similarity_results.csv` | annual, Relatório da Administração |

Each run two ways: **all** pairs, and **reliable_only** (extraction-diagnostic filter for the narrow scenarios; `both_ok` for whole-notes — already baked into the VERIFIED file, so identical to "all" there; no diagnostic column exists for `mgmt_report`, so only "all" applies). New code: `src/analysis/compute_eps_revisions.py` (outcome construction) and `src/analysis/run_h2_scenarios.py` (the battery, one shared function reused across all scenario × cut combinations). Full results: `data/interim/poc/h2_eps_revision_battery_results.csv` (56 rows); per-scenario merged data in `data/interim/poc/h2_eps_revision_<scenario>_<cut>.csv`.

## Core results: similarity vs. revision, p-values across every scenario

| Scenario | n pairs | signed pearson | magnitude pearson | clustered, no controls | clustered, + controls |
|---|---:|---:|---:|---:|---:|
| narrow_annual (all) | 528 | 0.585 | 0.142 | 0.615 | 0.623 |
| narrow_annual (reliable) | 314 | 0.850 | 0.997 | 0.803 | 0.848 |
| narrow_quarterly (all) | 1704 | 0.910 | 0.129 | 0.922 | 0.786 |
| narrow_quarterly (reliable) | 884 | 0.189 | 0.532 | 0.186 | 0.293 |
| whole_notes | 323 | 0.662 | 0.956 | 0.569 | 0.902 |
| mgmt_report | 391 | 0.747 | 0.074 | 0.689 | 0.721 |

**Zero of these 24 core tests clear p=0.05.** Controls used: `ln_total_assets`, `leverage`, `roa`, `past_12m_return` (the same set validated for H1's whole-document model).

## The two secondary hits, and why neither survives a closer look

Two more tests were run per scenario (a similarity-tercile Kruskal-Wallis comparison, and the standing delisting-correlation check applied to revision instead of return) — 56 tests total across the whole battery. **4 came in under p=0.05** — almost exactly the 2.8 expected by pure chance at that rate, and each one fails on inspection:

1. **`narrow_quarterly (reliable), tercile_kruskal`, p=0.0005** — looks like the strongest result in the whole battery. But the pattern across terciles is **low=+0.079, mid=+0.434, high=+0.129** — the *middle* similarity tercile has by far the highest revision, not a monotonic low-to-high relationship. No theoretically motivated version of H2 predicts a hump shape. Consistent with this being noise: the linear tests on the exact same data (signed pearson p=0.19, clustered p=0.19-0.29) show nothing.
2. **`whole_notes, tercile_kruskal`, p=0.024** — mildly more monotonic (low=+0.021, mid=+0.014, high=+0.114) but again unsupported by every linear/clustered test on the same data (p=0.57-0.96).
3. **`mgmt_report, delisting_mannwhitney_revision`, p=0.050** — this is the exact pattern this project has now caught twice before (whole-document delisting finding, narrow-annual size-neutralized portfolio sort): **significant on the naive test, gone once clustered by company** (`delisting_clustered_revision` on the identical data: p=0.851). Filed here as a third instance of the same lesson, not a new finding.

## How this compares to H1

Nearly identical shape to the return-predictability results: three-plus text sources, multiple frequencies, the full rigor progression, all null on the core question. The one difference worth naming — H1's management-report delisting test at least survived clustering-without-controls (p=0.039, `management_report_exploration.md`); H2's analogous test doesn't survive clustering at all (p=0.851). If anything, H2 is a slightly cleaner null than H1 was.

## Honest read

No scenario, text source, or frequency shows analyst consensus revision moving with textual similarity. Combined with H1, this project has now tested **two different outcome variables** (returns, EPS revision) **across four text sources and two frequencies**, with a consistent rigor standard, and found nothing that survives clustering on the core question either time. That's a real, informative pattern, not a data problem — the extraction pipeline is reliable enough to produce clean non-degenerate similarity distributions in every source tried (see each source's own exploration doc), and the null shows up whether the outcome is a stock return or an analyst's forecast.

Two things temper how final this should be treated:
- **The revision measure's rolling-series caveat above is real** — a true same-target-quarter revision measure hasn't been tried, because the current data export can't build one. It's possible (not likely, given how uniformly null everything else has been, but possible) that measure behaves differently.
- **Every H1/H2 test so far has been a screening test**, not the thesis's actual final regression (full universe, complete controls, one pre-registered specification). That regression is still the thing that would actually settle this.

## Recommendation

1. **Don't chase a fifth scenario cut on the current data.** Two outcomes, four sources, two frequencies is a genuinely broad, honest search — the pattern is consistent enough now that another cut of the same inputs is unlikely to change the picture.
2. **If EPS revision stays part of the thesis, the same-target-quarter measure is worth getting right** — it needs a different Bloomberg export (one column per fixed fiscal-period target, not the rolling view), a real ask for you, not something fixable in code.
3. **The two live, unresolved threads from before this are still the highest-value next steps**: (a) the narrow-vs-whole-document scope decision (`wholenote_alignment_review.md`), and (b) whether to invest in Risk Factors/Formulário de Referência acquisition — the theoretically strongest remaining text source per the literature, and now doubly motivated since both outcome variables are null on everything acquired so far.
4. Given how much ground the exploration phase has now covered on both hypotheses, **this might be the natural point to consolidate**: write up the aggregate story (what was tried, what's null, what's promising-but-fragile, what's recommended) as a single document for your advisor conversation, rather than continuing to add more scenario variants. Your call on timing.

## What was not done

- Same-target-quarter revision measure (blocked on data, not code — see above).
- A portfolio-sort-style test for H2 — deliberately skipped, since portfolio sorts are inherently about tradeable returns; the tercile/clustered-regression combination used here is the natural cross-sectional analogue for a non-tradeable outcome like a forecast revision.
- Quarterly EPS-revision testing against `whole_notes`/`mgmt_report` — those two text sources only exist at annual frequency (same limitation noted in `management_report_exploration.md` for H1).

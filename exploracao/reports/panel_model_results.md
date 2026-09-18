# The fixed-effects panel model: the mgmt-report return result doesn't survive it

Direct follow-up to `control_specification_test.md`. That file ended with a recommendation: stop iterating on portfolio-sort variants of the management-report return result and instead build the one proper company+year fixed-effects panel model this project has recommended in every prior report, and let *that* be the real test. This is that test, run across all eight scenarios where it's statistically well-posed (H1 returns and H2 revisions, four text sources each). New code: `src/analysis/run_panel_models.py`. Full results: `data/interim/poc/panel_model_results.csv`.

## The headline result

**The management-report return finding — the most robust result this project had produced, p≈0.03, survived every stress test thrown at it — does not survive company and year fixed effects.**

| Scenario | n | companies | avg years/co. | pooled clustered p | **two-way FE p** |
|---|---:|---:|---:|---:|---:|
| narrow_annual | 671 | 93 | 7.2 | 0.609 | 0.585 |
| narrow_quarterly | 2138 | 94 | 22.7 | 0.987 | 0.826 |
| whole_notes | 411 | 81 | 5.1 | 0.511 | 0.660 |
| **mgmt_report** | 484 | 77 | 6.3 | **0.031** | **0.478** |

The coefficient on similarity goes from +0.258 (pooled) to +0.139 (FE) — same sign, but the standard error widens enough (fewer degrees of freedom, only within-company variation left to work with) that significance disappears entirely. Every other H1 return scenario was already null and stays null.

## What this means, concretely

The panel model asks a sharper question than anything tried before: not "do companies with higher similarity tend to have higher returns" (which is what a pooled comparison asks, clustering or no clustering) but "when a specific company's own similarity moves relative to its own normal level, does that same company's own return move too." Losing significance under that sharper question is consistent with the pooled result having been driven by a **stable, cross-company difference** — some management-report writers are just consistently steadier narrators *and* happen to sit at companies that perform differently, for reasons that have nothing to do with the text itself (industry, typical governance quality, house style) — rather than a genuine within-company signal of the kind the underreaction hypothesis actually needs.

This isn't a case of the test being too conservative to find a real effect. The **poolability F-test** (whether the fixed effects are even doing real work, versus just costing degrees of freedom for nothing) is significant for mgmt_report returns (p=0.007) — meaning there genuinely are systematic company/year differences in the data, and controlling for them is the right thing to do, not overkill. The model isn't destroying signal by being overly strict; it's doing exactly what it's supposed to, and the signal isn't there once it does.

## H2 (revisions): confirms the existing null, nothing new

| Scenario | n | companies | pooled p | **FE p** |
|---|---:|---:|---:|---:|
| narrow_annual | 518 | 88 | 0.603 | 0.919 |
| narrow_quarterly | 1678 | 90 | 0.766 | 0.999 |
| whole_notes | 316 | 73 | 0.854 | 0.866 |
| mgmt_report | 386 | 73 | 0.692 | 0.967 |

None of these were ever significant, pooled or otherwise — the panel model doesn't change the H2 conclusion, it just confirms it under a stricter test too.

## One more thing this caught before it became a mistake

The delisting/survivorship check (is textual change different for companies that later dropped out of the index) was deliberately **not** run through this same two-way FE model, and it's worth being explicit about why rather than silently skipping it: `is_dropped` is constant *within* a company (a company either stayed or dropped for its whole time in the sample — it doesn't flip back and forth year to year). Company fixed effects work by subtracting each company's own average from every variable; for a variable that never varies within a company, that subtraction leaves exactly zero. `run_panel_models.py` actually runs this anyway, on purpose, to show what happens rather than just asserting it: the model reports a coefficient of `7.44e-17` (machine-precision zero) with a p-value of `0.0006` — a number that *looks* highly significant and is completely meaningless, an artifact of testing whether zero differs from zero with a tiny standard error. Reporting that p-value at face value would have been a real, avoidable mistake. Company fixed effects simply don't apply to a time-invariant outcome; this needs a different design (e.g., a single cross-sectional logit on each company's *average* similarity, not a panel) if it's revisited later.

## Where this leaves H1 and H2

Both hypotheses have now been tested via every method built this session, at increasing rigor, converging on the same answer:

1. Simple correlation (rounds 1-5, all null except a few later-debunked cases)
2. Clustered-by-company regression, no controls (mostly null; mgmt_report return was the one exception, p=0.14 — actually not significant at this stage either)
3. Clustered regression, with controls (mgmt_report return becomes significant, p=0.03-0.14 depending on scenario)
4. Portfolio sort, unconditional (mgmt_report return: null, best p=0.43)
5. Portfolio sort, characteristic-adjusted for the same controls (mgmt_report return: still null, best p=0.28, though directionally consistent)
6. **Company + year fixed-effects panel (mgmt_report return: null, p=0.48)**

Every method past step 3 disagrees with step 3. That is about as clear an answer as this kind of empirical search produces: **the one significant result this whole project found was a controls-dependent, cross-sectional pattern that does not survive being asked the sharper within-company question, confirmed two independent ways (portfolio sort and fixed effects).** Both H1 (returns) and H2 (EPS revisions) are null across every text source (narrow debt note, whole document, management report), every frequency (annual, quarterly), and now every method rigor level tried.

## Recommendation

Given the time constraint stated at the start of this thread, I don't think there's a responsible way to keep searching for a return/revision signal in the text sources already acquired — this has now been tested about as thoroughly as it can be, and the answer has been consistent under every method that actually holds up to scrutiny. Two honest paths from here, and this is a real decision, not a technical one I should make unilaterally:

1. **Write up the null as the thesis's actual empirical finding.** A well-documented "textual change in Brazilian debt-note and management-report disclosures does not predict abnormal returns or analyst forecast revisions, tested across N methods of increasing rigor" is a legitimate, defensible accounting/finance thesis result — arguably a *more* interesting one than a marginal p=0.03 would have been, precisely because of how much robustness-checking backs it up. The delisting/survivorship angle (management report, p=0.039 clustered-without-controls, still not tested for the same company-FE degeneracy issue in a valid alternative form) remains a loose partial thread if you want one more angle before closing the book, but it needs a different model design than what's built here.
2. **Pivot the text source, not the method.** Risk Factors (Formulário de Referência) remains the one theoretically-strongest untried source per the literature (Cohen-Malloy-Nguyen's own effect concentrates there) — a real new acquisition project, not a reuse of what's already downloaded, and a bigger lift than anything tried today. Given the stated time constraint, this is probably not realistic to start from scratch now unless there's more runway than "we don't have too long" suggested.

My honest read, given everything tested: option 1 is the pragmatic choice. The search has been genuinely broad and genuinely rigorous, and a well-documented null defended by six converging methods is a stronger thesis than a rushed, undersized new acquisition attempt under time pressure.

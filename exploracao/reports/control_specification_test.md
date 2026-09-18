# Does dropping "size" as a control change anything? And is there a viable finding here?

Direct test of your question: across every clustered-regression test run this session (H1 returns, the delisting/survivorship validity check, H2 revisions — 11 scenario/family combinations), what changes if `ln_total_assets` is dropped from the control set and only `leverage`, `roa`, `past_12m_return` are kept? New code: `src/analysis/test_control_specifications.py`. Full results: `data/interim/poc/control_specification_comparison.csv`.

## Direct answer: dropping size, by itself, doesn't flip anything

None of the 11 scenarios move from non-significant to significant purely by removing size. The closest case is the management-report delisting check: p=0.113 (with size) → p=0.059 (without) — closer, but still short of the conventional 5% bar. Everywhere else, the movement is a rounding error.

Mechanically, this makes sense once you check it: in the management-report data, `ln_total_assets` correlates only weakly with cosine similarity (r=+0.12) and essentially not at all with abnormal return (r=-0.008). Size just isn't doing much confounding here — it isn't a "bad control" suppressing a real effect, it's closer to inert. So "disconsider size going forward" is a reasonable simplification for the model (one fewer control to justify and defend), but it is not, by itself, the thing that would make a null result significant.

## The real finding this check surfaced: management-report returns, with controls, p=0.03

Running this comparison surfaced something that hadn't been tested before: the management-report **return** correlation, *with controls and clustering together*, is significant:

| Spec | n | coefficient on similarity | p-value |
|---|---:|---:|---:|
| clustered, no controls | 504 | — | 0.140 |
| clustered, full controls (incl. size) | 484 | +0.253 | **0.034** |
| clustered, no-size controls | 484 | +0.258 | **0.031** |

Positive and correctly signed (higher similarity → higher subsequent abnormal return, the same direction Cohen-Malloy-Nguyen report). This is a controlled result, not a raw bivariate one — the earlier-reported r=+0.06 (p=0.15) for this scenario (`management_report_exploration.md`) was the simple correlation; adding `leverage`/`roa`/`past_12m_return` as controls is what sharpens it into significance, with or without size in the mix.

**Given this project's history of two false positives this session already (whole-document delisting/extreme-return findings undone by an acquisition bug; a portfolio-sort hit undone by Marcopolo's degenerate score), this got the same spot-check treatment before going anywhere near "here's a finding":**

- **Winsorizing** `abnormal_return` at the 1st/99th percentile: p=0.035 — unchanged.
- **Dropping the 5 most extreme abnormal returns**: p=0.017 — the result gets *stronger*, not weaker (not an outlier artifact).
- **Dropping the one near-degenerate low-similarity observation**: p=0.054 — a real but modest sensitivity, not a collapse.
- **Leave-one-company-out**, refit 77 times (once per company): worst case p=0.068, best case p=0.003, never flips sign, never breaks. No single company is carrying this the way Marcopolo carried the earlier false positive.
- **Spearman rank correlation**, no controls, no clustering at all — the crudest possible check: rho=+0.108, p=0.018. The raw pattern is really there in the data, not an artifact of the regression specification.

This is the most robust result this entire project has produced for the return hypothesis.

## What keeps this from being a settled finding

- **It only shows up once controls are added.** Clustered-with-no-controls is p=0.14. That's a legitimate and expected way for a control variable to work (it's absorbing real confounding variance), not inherently suspicious — but it means there's no raw effect to fall back on if the control choice is challenged.
- **It's one scenario out of eleven tried.** Narrow-note (annual and quarterly) and whole-document returns are still flatly null under the identical specification. This is the theoretically predicted place for an effect to show up first (management report is Brazil's highest-managerial-discretion text among what's been acquired) rather than a random corner of the search grid — which makes it more credible than an arbitrary hit — but "found in the predicted place" is still "found once."
- **The portfolio-sort test does not corroborate it, and this is now checked, not just flagged as a worry.** `src/analysis/run_mgmt_report_portfolio_sort.py` filled the one real gap in the existing grid (management report was never run through the portfolio sort before) across the full 3/6/12-month x 2/3/4-group grid — 9 combinations, matching the density used everywhere else in this project. **Every single one is null**, best case p=0.43 (3-month hold, 2 groups) — including the 2-group/12-month combination specifically chosen to give the coarser, higher-power version of the test the best possible shot. This isn't underpowered binning; it's a real disagreement between the two methods.

**Why they likely disagree, and what it means:** the regression's significance depends entirely on the controls (no-controls clustered p=0.14; only sharpens to p≈0.03 once leverage/ROA/past-return are added). A portfolio sort is structurally univariate — it sorts on similarity alone and can't condition on other variables the way a regression can. So this isn't really "two methods disagreeing about the same effect" — it's more likely that **the effect only exists conditional on leverage/ROA/past-return**, which a raw sort can never see by construction, rather than a marginal, unconditional pattern the market would need to be underreacting to on its own. That's a meaningfully weaker kind of result than an effect that shows up either way: it's real in the data (survived every robustness check above), but it's contingent on a specific model specification rather than a pattern that jumps out of the raw data however you slice it.

## The bridge test: characteristic-adjusted portfolio sort — tried, still doesn't clear significance

Built the direct bridge between the two methods (`src/analysis/run_conditional_portfolio_sort.py`): each calendar month, cross-sectionally regress active firms' realized returns on leverage/ROA/past_12m_return and take the residual — the closest a portfolio sort can get to "conditional on the same controls the regression uses" without fragmenting the ~50-name monthly cross-section into empty double-sort cells. Then sort *those* residuals into similarity groups and long-short as before, across the same 3/6/12-month x 2/3/4-group grid.

| Holding | Groups | ann. L/S spread | t (Newey-West) | p-value |
|---|---:|---:|---:|---:|
| 12mo | 2 | +2.6% | +0.76 | 0.449 |
| 12mo | 3 | +4.8% | +1.09 | **0.276** |
| 12mo | 4 | +5.1% | +0.89 | 0.374 |
| 6mo | best (groups=4) | +5.9% | +0.79 | 0.429 |
| 3mo | best (groups=4) | +7.2% | +0.61 | 0.542 |

**Still null everywhere — best case p=0.276 (12-month hold, 3 groups), the spec that mechanically matches the regression's own 12-month forward-return window.** Two things worth naming precisely, because they point in different directions:

- **It's directionally consistent everywhere.** All 9 combinations show a *positive* long-short spread (high similarity earning more than low similarity), matching the regression's sign, and the best case improved over the unconditional sort's best case (p=0.276 vs. p=0.43). Conditioning on the controls moved the portfolio-sort result closer to the regression's answer, not away from it.
- **It still doesn't get there.** p=0.276 is not evidence by any conventional standard — a Newey-West t-test on ~109 monthly spreads with this much noise needs a much bigger, more consistent effect than what's here.

## How strong would the thesis be looking, honestly

Weaker than my read after the regression robustness checks alone, now that the bridge test is in. What's actually holding up: a clustered cross-sectional regression result (p≈0.03) that is robust to every within-method stress test tried (winsorizing, outlier removal, leave-one-company-out, rank correlation) — that part is real and not an artifact. What did *not* hold up: the hope that an independent, portfolio-based method conditioning on the same controls would confirm it. It moved in the right direction but stayed well short of significance.

Read plainly, this is a **regression-only result**. That's a materially weaker claim than "two different methods agree" — it means the finding depends on the linear-regression functional form and the specific control set, not on something that shows up robustly however the same conditioning information gets used. It's still worth reporting (it's real within its own method, correctly signed, and it's the strongest thing four rounds of searching across two hypotheses and four text sources has produced) — but calling it *the* thesis finding on the strength of one method, after the more literature-standard method twice failed to confirm it (unconditionally and now conditionally), would be overstating what's here.

**Given the time constraint, my honest recommendation: don't spend more of it chasing this specific number.** The next-best move, if you want a real shot at strengthening H1 rather than polishing this one result further, is the standing recommendation this project keeps arriving at from a different angle each time — a proper fixed-effects/panel model (company and year effects) built once, as the actual final specification, rather than another screening test. If that model shows management-report similarity holding up as a significant predictor once effects are absorbed the "right" way, that's a real finding. If it doesn't, the honest, well-supported thesis conclusion is the null this project has now tested from every practical angle: two outcomes, four text sources, two frequencies, and — as of this check — two portfolio-sort specifications, controls-conditional and not.

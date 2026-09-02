# The proper multivariate model — a further, more conservative correction

**Read this after `reports/wholenote_data_quality_correction.md`.** That file established the delisting/bankruptcy correlation (notebook §4-5) survives data-quality contamination checks, unlike the extreme-return finding. This file is a *second*, independent correction: even the delisting finding does not survive a properly specified multivariate model with clustered standard errors. Two different robustness questions, two different answers — read both, don't conflate them.

## The problem with every test run before this one

Every significance test in this project so far — the Mann-Whitney U tests throughout `poc_overview.ipynb` and `poc_wholenote.ipynb` §4, and the one-control-at-a-time logistic screening in §5 — treats each year-over-year **pair** as an independent observation. It isn't. A company with 9 years of filings contributes ~8 pairs, all sharing that company's unobserved characteristics (its typical disclosure style, its baseline riskiness, everything not in the control variables). Treating 487 pairs from 96 companies as 487 independent data points overstates the effective sample size roughly 5x and understates every standard error accordingly. This is a standard panel-data problem (pseudo-replication / non-independence), and the fix is standard too: cluster standard errors by company.

## Results, on the same verified-clean data as the data-quality correction

| Model | n (pairs) | n (companies) | similarity coefficient | p-value (clustered by company) |
|---|---:|---:|---:|---:|
| No controls | 487 | 96 | -1.59 | **0.086** |
| + firm size only | 486 | 96 | -1.03 | 0.337 |
| + size + leverage + ROA + past return | 415 | 82 | -1.06 | 0.538 |

For comparison, the same "no controls" comparison via the simpler (non-clustered) Mann-Whitney test used everywhere else in this project gives p=0.0005 on this same verified data (see the data-quality correction doc) — a **dramatic difference driven entirely by properly accounting for repeated observations per company**, before any control variable is even added.

## What this means

**Neither of `poc_wholenote.ipynb`'s two headline findings survives a properly specified, clustered, fully-controlled model.** The extreme-return finding failed the data-quality check; the delisting finding passes that check but fails this one. Put together honestly: on the current data and current methodology, there is a **real, univariate, uncontrolled association** between whole-document textual change and both delisting risk and extreme returns — but neither one has been shown, at time of writing, to carry information beyond what a company's size, leverage, and profitability already tell you, once the statistics are done in a way that doesn't overstate the sample.

This is not the same as "there's nothing here." It's the honest state of a POC-stage investigation: a real bivariate pattern exists, it survives one class of scrutiny (data quality) and not another (proper controls + clustering), and that's exactly the kind of result that needs the real, final regression — the actual thesis model, not a screening test — to resolve one way or the other. It is *not* ready to be presented as a finding.

## Caveats on this correction itself, for balance

- **82-96 clusters (companies) is on the low side** for the asymptotic properties cluster-robust standard errors rely on (commonly cited rule of thumb: 30-50 minimum, more is better, and precision degrades below ~40-50). This doesn't mean the clustered p-values are wrong, but the exact numbers above shouldn't be treated as more precise than they are — a wild cluster bootstrap or a company-level fixed-effects specification would be a more defensible final approach with this few clusters, and is worth doing before citing any of this externally.
- This was only run on the whole-document scenario. Whether the narrow-note or quarterly scenarios' own findings survive the same clustering correction is checked in `reports/wholenote_cross_scenario_extension.md`.
- Firm size and ROA remain strongly significant throughout every specification (p<0.001 in the full model) — the fundamentals-based distress signal in this data is real and strong; it's specifically the *incremental* value of the text that hasn't been established yet.

# Cross-scenario extension: does any version of the survivorship-bias test survive proper statistics?

Extends `reports/wholenote_multivariate_model.md`'s clustering correction to every similarity scenario built in this project, to answer one question cleanly: **is the "companies that delisted show more textual change" finding real in *any* version of this measurement, once standard errors are clustered by company?**

## Result: no, not in any of the three scenarios tested

| Scenario | n (pairs) | Companies | Mann-Whitney p (uncorrected, as used throughout this project until now) | Logistic, clustered by company, no controls |
|---|---:|---:|---:|---:|
| Narrow debt-note, **annual** (the project's main measure, rounds 1-5) | 482 | 94 | 0.237 | 0.492 |
| Narrow debt-note, **quarterly** (full 112-company universe) | 1,345 | 100 | 0.194 | 0.664 |
| Whole notes document, **annual** (verified-clean subset) | 487 | 96 | **0.0005** | 0.086 |

The narrow-note versions (annual and quarterly) were already not significant under the simple Mann-Whitney test used throughout rounds 1-5 — clustering just makes that more clearly true, no surprise there. **The one version that looked like a real, strong finding — whole-document annual, p=0.0005 on the most carefully verified data — loses significance once clustering is applied, even before any control variable is added** (p=0.086, and it gets weaker still once size/leverage/ROA/past-return are added, per the multivariate-model doc).

## Why this matters more than it might seem

Every p-value cited anywhere else in this project's notebooks and reports for a "stayed vs. dropped/delisted" comparison — `poc_overview.ipynb` §5/§7, `poc_wholenote.ipynb` §4-5 — used the simple (non-clustered) Mann-Whitney test. That was a reasonable default earlier in the project when the question was "does this measurement approach produce a sane, interpretable signal at all," but **it is not the right test for a claim about statistical significance**, because it treats each company's several year-pairs as independent draws when they aren't. This isn't specific to the whole-document scenario — it's a property of the test that was used everywhere, and it means every previously reported "p=0.0028" / "p=0.18" / "p=0.0014" style number in this project should be read as "directionally suggestive, not properly tested for significance" rather than as a real inferential result.

**This is not a reason to conclude H1/the survivorship hypothesis is false.** It's a reason to conclude none of the tests run so far were actually capable of answering the question. A company-level fixed-effects or clustered/panel specification, run once as the real final model (not per-scenario screening), is what would actually answer it.

## What I did not do

- Did not re-run every Mann-Whitney-based number in `poc_overview.ipynb` with clustering — that notebook's own text is left untouched, per your instruction; this file exists so the correction is visible without editing already-written conclusions.
- Did not build the final clustered/fixed-effects panel model that would actually be citable — the numbers above are diagnostic (do simpler tests survive a first, obvious correction), not a finished model.
- Did not check the H1 abnormal-return correlations (§7 of `poc_overview.ipynb`, §6 of `poc_wholenote.ipynb`) for the same clustering issue — same concern almost certainly applies (each company contributes multiple return observations too), and is worth checking with the same method before treating any of those r-values as meaningful either.

## Addendum: the signed H1a-style correlation was checked too

For completeness: the standard signed correlation (similarity vs. raw abnormal return, the H1a-style directional test used throughout `poc_overview.ipynb`) was already not significant on the whole-document verified data (Pearson r=-0.023, p=0.63) even without clustering, and stays non-significant with clustering (OLS, clustered by company: p=0.64). Unlike the delisting finding, clustering doesn't change this particular conclusion — it was already null. Consistent with every prior round's H1a-style result across this whole project.

## Recommended real next step

Before presenting *any* of this project's significance-test results externally: build one proper panel/clustered model (likely a logistic or linear probability model with company clustering, or company fixed effects if the panel is long enough) as the single source of truth for "is textual change associated with distress/returns," applied consistently across scenarios, rather than continuing to produce more one-off Mann-Whitney numbers. Everything currently in the various notebooks should be understood as exploratory/descriptive until that exists.

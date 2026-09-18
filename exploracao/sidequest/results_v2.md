# Extended results (v2): 4-year panel, workforce-leadership diversity, fixed effects

Follow-up to `README.md` and `extension_plan.md` — executed steps 1-5 of the extension plan. New code: `build_diversity_dataset_v2.py`, `test_diversity_hypotheses_v2.py`.

## What changed from v1

- **Panel extended from 2 to 4 fiscal years (2023-2026)**: both 2025 and 2026 FRE data existed on CVM's portal and were pulled directly — 399 company-years, 104 companies (up from 202/103).
- **Added workforce-leadership diversity** (`empregado_posicao_declaracao_{genero,raca}`, split by `Posição = Liderança`): median leadership headcount per company is **723 employees**, versus a board of ~7-8 — a far higher-power measure than the original board-level counts.
- **The planned cost-of-debt refinement did not survive contact with the data.** Checked directly (not assumed): `fre_cia_aberta_obrigacao_*.csv` and its `endividamento` sibling, which would have given a more precise debt denominator, only exist in the 2023 FRE export — absent from 2024, 2025, and 2026. Kept the original DRE-based proxy (`despesas financeiras / passivo total`) for consistency across all 4 years rather than mixing methods across years.
- **Financial controls extended to FY2024-2025** via a sidequest-local re-run of the DFP extraction (confirmed `dfp_cia_aberta_2025.zip` exists on CVM's portal). `data/interim/control_variables.csv` — the main thesis's file — was not touched.
- **A fixed-effects panel test was attempted** (`linearmodels.PanelOLS`, company + year effects, clustered by company) now that 4 years exist — still thin next to the main thesis's 10-year panel, but no longer meaningless the way it would have been with 2 years.

**One descriptive fact worth its own line**: board gender representation rose steadily across the window — 16.5% (2023) → 17.7% (2024) → 19.1% (2025) → 19.6% (2026). Board racial diversity did not show a comparably clean trend (not tabulated here; see the notebook).

## Results: two new near-misses, same fate as everything else this session

| Outcome | Predictor | Simple r (p) | Clustered (p) | +Controls (p) | **Fixed effects (p)** |
|---|---|---:|---:|---:|---:|
| Cost of debt | *(all 7 predictors)* | — | — | — | **null everywhere, nothing close** |
| Return volatility | Board has any Black/Brown | 0.030 | 0.078 | 0.406 | 0.963 |
| Return volatility | **Executive board % Black/Brown** | 0.112 | 0.116 | **0.001** | 0.580 |
| Return volatility | **Workforce leadership % female** | **<0.001** | **0.002** | **0.004** | 0.394 |
| Return volatility | Workforce leadership % Black/Brown | 0.001 | 0.096 | 0.172 | 0.636 |

Full 14-row table: `diversity_test_results_v2.csv`.

**Two results now look like exactly the pattern the main thesis ran into repeatedly** (mgmt-report returns, several delisting checks): not significant naive or clustered, becomes significant once controls are added, then **disappears under company+year fixed effects**:

1. **Executive-board racial diversity → volatility**: null → null → p=0.001 → null. Textbook "controls reveal a cross-company pattern that isn't a within-company effect."
2. **Workforce-leadership gender diversity → volatility**: this one is the more striking case — significant at *every* stage before fixed effects (p<0.001 raw correlation, on 350 observations, holding through clustering and controls) and still fails FE (p=0.394). Checked whether this was the same size confound that explained the v1 board result: **it isn't** — the correlation between leadership-gender-% and firm size is weak and the *wrong sign* to produce this pattern mechanically (r=-0.14). Whatever cross-company factor is driving it (plausibly industry — some sectors run both more female-led leadership teams and structurally different volatility profiles, e.g. retail/services vs. capital-intensive extractive/utility sectors — not confirmed, flagged as the likely mechanism rather than tested) isn't the same one caught in v1.

## Honest bottom line, updated

The extension didn't rescue anything, and — read the right way — that's itself informative. **Every hypothesis tested in this whole session, across two entirely different research questions (textual disclosure change against returns/revisions; board and workforce diversity against cost of debt/volatility), that looked significant under a naive or even a properly-clustered-and-controlled specification, failed once tested against company+year fixed effects.** That's not a coincidence specific to one dataset — it's the same lesson landing twice, in two unrelated empirical settings, which is a stronger argument for taking it seriously than either instance alone.

Cost of debt is a clean, thorough null. Return volatility produced two naive-looking hits, both explained away by the sharpest available test — one by size (v1), one by an unidentified but clearly cross-company factor (v2). Nothing here survives to the level the main thesis would need to call it a finding.

## What this means for the two theses question

See the top-level verdict for the full reasoning — in short, this sidequest is now a well-documented, thoroughly-tested null with a genuinely novel literature contribution (the gap itself, verified adversarially), not a live empirical result to build a thesis around under the current time constraint. The main thesis, despite also being null on its core hypothesis, has a much larger, more mature body of testing (five text sources, two outcomes, six methods, ten years of data) and one real secondary finding (the Risk Factors delisting result) that survives its own sharpest test. That asymmetry matters for a decision that has to be made in weeks, not months.

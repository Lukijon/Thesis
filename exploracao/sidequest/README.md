# Sidequest: a different research question, tested with what's already on hand

Kept deliberately separate from the main thesis (`reports/`, `docs/`) — this is exploratory work on a **different research question**, done in parallel while the main thesis document is under review. Nothing here is part of the H1/H2 debt-note-similarity thesis; it's a response to "find another project question we might be able to answer with what we have."

## The ask

Find a research question that (a) hasn't been done, or hasn't been done recently for Brazil, and (b) can be tested with data already acquired or cheaply acquirable, then actually test it rather than just propose it.

## What we already had sitting unused

While acquiring Risk Factors data this session (see `reports/risk_factors_exploration.md`), the CVM Formulário de Referência (FRE) zip files turned out to contain ~50 other structured data tables per year — governance, executive compensation, related-party transactions, board/employee demographics, audit info, ownership structure — none of it used by the main thesis, all of it already downloaded and cached locally (`data/raw/dfp/_cache/fre_cia_aberta_*.zip`, 2015–2024). Zero new acquisition needed to explore any of it.

## Literature scan

Before picking a direction, ran a broad literature search (Brazilian journals — SciELO, RAE, RAC, RCF, REPeC — plus international sources) across the most promising candidates from that structured data: board/executive gender and racial diversity, executive compensation structure, and related-party transactions. Full detail in `sidequest/literature_scan_notes.md`. Short version:

- **Board gender diversity + firm performance/cost of equity in Brazil**: already well covered, including work as recent as 2025–2026 (Gaio & Stefanelli 2025 on cost of equity; Yoshinaga et al. 2026 on Tobin's Q). Not a gap.
- **Executive compensation structure + performance**: the most crowded of the candidates — already tested against board composition, ESG disclosure, and gender diversity as moderators within the last two years in Brazilian journals. Would need a narrow, specific cut to be defensible as novel.
- **Related-party transactions + cost of capital**: a real, cleaner gap — Brazilian RPT literature exists but clusters on firm value/earnings quality, not cost of capital specifically. Flagged as a good second candidate, not pursued further this pass (see "What wasn't done" below).
- **Racial diversity of boards/leadership + any firm outcome, using the actual mandatory CVM disclosure data**: the clearest gap found. The only existing Brazilian race-and-governance work is a 2022 survey study with a 16% response rate (69 of 442 companies) — nobody has used the real regulatory disclosure (mandatory since Resolução CVM 59/2021, codified in Resolução 80/2022, first appearing in FRE filings in 2023) in a firm-outcome regression. International literature itself flags race/ethnicity as understudied relative to gender. This is the angle pursued below.

**Real constraint carried in from the start**: this disclosure is genuinely new. Confirmed empirically (not assumed) that `fre_cia_aberta_2022.zip` has no gender/race declaration file at all, while `fre_cia_aberta_2023.zip` and `fre_cia_aberta_2024.zip` do. The usable panel is two fiscal years, not ten — ruling out anything like the fixed-effects panel work in the main thesis, and calling for cross-sectional methods with appropriately modest claims.

## What was built

`sidequest/build_diversity_dataset.py` — zero new downloads, all from already-cached FRE and DFP zips:

- **Board and executive-board diversity**: % female and % Black/Brown ("Preto"+"Pardo", the standard Brazilian racial-statistics aggregate), separately for Conselho de Administração and Diretoria, 2023–2024. **101–103 of 111 universe companies covered** — essentially complete.
- **Cost of debt proxy**: `despesas financeiras / passivo total` (DRE account `3.06.02`, extracted the same way `src/features/build_control_variables.py` already pulls other DFP line items).
- **Return volatility**: annualized standard deviation of daily stock returns, computed from the price data already on disk.
- Merged with the existing control variables (size, leverage, ROA).

**A striking descriptive fact before any hypothesis test**: median board racial diversity across the sample is **0%** — more than half of these 100+ major Brazilian listed companies report zero Black or Brown board members, despite Black and Brown Brazilians being roughly 56% of the population (IBGE). This matches the pattern the 2022 survey study found (zero Black board members, ~1% Brown) and confirms the regulatory data isn't an artifact — it's telling the same story as the earlier hand-collected survey, just now with near-complete coverage instead of a 16% response rate.

## Results

Same rigor discipline as the main thesis — simple correlation, then clustered-by-company OLS with and without controls (company+year fixed effects weren't attempted: with only 2 years and board composition that barely moves year to year, there's essentially no within-company variation to identify from).

| Outcome | Predictor | Simple r (p) | Clustered, no controls (p) | Clustered, with controls (p) |
|---|---|---:|---:|---:|
| Cost of debt proxy | Board % female | +0.09 (0.20) | 0.47 | 0.32 |
| Cost of debt proxy | Board % Black/Brown | -0.03 (0.73) | 0.62 | 0.96 |
| Cost of debt proxy | Board has any Black/Brown | -0.08 (0.29) | 0.15 | 0.38 |
| Cost of debt proxy | Executive % female | +0.17 (0.02) | 0.15 | 0.18 |
| Return volatility | Board % Black/Brown | -0.10 (0.19) | 0.14 | 0.60 |
| **Return volatility** | **Board has any Black/Brown** | **-0.15 (0.05)** | **0.020** | **0.24** |

Full table (10 predictor × outcome combinations): `sidequest/diversity_test_results.csv`.

**One result looked real and got the same scrutiny as everything in the main thesis before being trusted.** Companies with at least one Black/Brown board member show meaningfully lower annualized return volatility (34.4% vs. 44.3%, p=0.020 once clustered by company) — and unlike several main-thesis near-misses, this one survives leave-one-company-out (worst case, removing any single company: p=0.037, never loses significance, coefficient never changes sign, checked across all 89 companies in that comparison).

**It does not survive controls, and the reason is precise, not vague.** Adding controls one at a time: `leverage` alone barely moves it (p=0.042), `roa` alone barely moves it (p=0.020) — but `ln_total_assets` alone kills it completely (p=0.346). **Company size fully explains the pattern.** Bigger companies have both more board diversity and lower stock volatility — an entirely mundane confound (larger, more established firms diversify their boards more *and* are simply less volatile stocks), not a diversity effect. This isolation is worth having precisely because it's clean: this is exactly the kind of naive-looking finding a less careful pass would report as "diversity reduces risk."

**Every other combination is null at every stage**, including the executive-board-gender-and-cost-of-debt naive correlation (p=0.016) that disappears once clustered (p=0.15) — the same "significant naive, gone once properly specified" pattern the main thesis ran into repeatedly.

## Honest bottom line

No result here survives full scrutiny. That's a legitimate outcome for a bounded, single-pass exploration with a 2-year panel and ~100 companies — this was never going to have the statistical power of the main thesis's 10-year, 111-company corpus. What this sidequest actually accomplished:

1. **Confirmed a genuine, defensible literature gap**: nobody has tested Brazilian board racial diversity against firm outcomes using the real mandatory disclosure data (as opposed to a 16%-response-rate survey). That gap is now characterized, not just claimed.
2. **Built a reusable, zero-new-acquisition dataset** (`diversity_analysis_dataset.csv`) that could be extended (more outcomes, more years as they become available, or the related-party-transactions angle) without any new downloads.
3. **Found and correctly attributed one real pattern to a confound** rather than either missing it or overselling it — the size-explains-everything result is itself a small, honest piece of evidence about what this new disclosure does and doesn't capture yet, at this sample size.

## What wasn't done

- **Related-party transactions + cost of capital** — the second-ranked candidate from the literature scan, not pursued this pass. The data (`fre_cia_aberta_transacao_parte_relacionada_*.csv`) is already cached and covers the full 2015-2024 window (not gated by the 2021 diversity regulation), so it would support a proper multi-year panel with fixed effects the way the main thesis does — a stronger design than what a 2-year diversity panel can offer. Worth a follow-up pass if this direction is worth continuing.
- **Executive board (Diretoria) as the primary diversity measure, board as secondary** — only the reverse was emphasized here; not expected to change the conclusion given how strongly correlated board and executive diversity are likely to be, but not checked.
- A within-2023-2024 *change* in diversity (does a company that added a Black/Brown board member between the two disclosure years show any subsequent shift in volatility) — genuinely a 2-observation-per-company question, likely underpowered, but conceptually the closest thing to a "does the mandate's effect show up yet" test.
- Extending the diversity panel with 2025 data once it's filed (would double the panel to 3 years).

## Files in this folder

- `build_diversity_dataset.py` — builds `diversity_analysis_dataset.csv` from already-cached FRE + DFP zips.
- `test_diversity_hypotheses.py` — runs the full test battery, writes `diversity_test_results.csv`.
- `board_diversity_panel.csv` — intermediate: just the diversity percentages, before merging outcomes/controls.
- `literature_scan_notes.md` — the first-pass literature scan that picked this angle, including sources.
- `novelty_verification.md` — a second, adversarial pass specifically trying to disprove the novelty claim (it holds up, ~85-90% confidence — see file for the full citation tables and residual uncertainty).
- `extension_plan.md` — what additional data would strengthen this (ranked easy/medium/hard, each checked directly against CVM rather than assumed) and a concrete step-by-step plan if this gets pursued further.
- `results_v2.md` — the extension plan, executed: panel extended to 4 years (2023-2026), workforce-leadership diversity added, fixed-effects panel test attempted. Two new results looked significant through clustering and controls and both failed fixed effects — the same pattern the main thesis found repeatedly, now observed independently in a second dataset.
- `diversity_exploration.ipynb` — the visual walkthrough: diversity trends, the striking zero-median board-race distribution, outcome distributions, and the chart showing both near-misses collapse under fixed effects.
- `build_diversity_dataset_v2.py`, `test_diversity_hypotheses_v2.py`, `diversity_analysis_dataset_v2.csv`, `diversity_test_results_v2.csv` — the extended (v2) build and test code/data.
- `results_v3.md` — a deeper search per the explicit ask that a real result matters more here: added market-to-book, ROA, ROE, and past-return as outcomes, plus a sector control. One predictor (executive-board racial diversity) survived leave-one-out, individual and combined controls, and sector fixed effects — the most robust result in either project this session — before failing a check none of them had needed before: excluding companies with tiny executive boards (where diversity ratios are noisy by construction) collapsed it. Full detail and the reasoning on why fixed effects itself was underpowered here (not decisive, unlike the main thesis) is in this file.
- `build_diversity_dataset_v3.py`, `test_diversity_hypotheses_v3.py`, `diversity_analysis_dataset_v3.csv`, `diversity_test_results_v3.csv` — the v3 build and test code/data.
- `dissertacao_diversidade_esqueleto.docx` — a full ABNT-structured thesis skeleton for this sidequest, matching `docs/dissertacao_esqueleto.docx`'s structure and depth (Introdução, Revisão de Literatura, Metodologia, Resultados — ~4,100 words). Built so this could genuinely stand alongside the main thesis if you choose to pursue it, not just as supporting notes.

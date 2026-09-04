# Where things stand, what to look at, and how to present each paper

Written after exhausting the search for a positive correlation on both projects (see `sidequest/results_v3.md`'s final section for the last, most nuanced attempt). Both are now honestly null. This document is the practical "what do I actually do next" reference — not a thesis deliverable itself.

## 1. The walkthrough: what we actually have

**Main thesis** — textual change in debt-note disclosures vs. stock returns (H1) and analyst forecast revisions (H2). Five text sources tried (narrow debt note, whole notes document, management report, Risk Factors — annual and quarterly where applicable), six methods of increasing rigor (correlation → clustered regression → controls → portfolio sort → fixed effects → a correctly-specified cross-sectional design for the delisting check). Result: **H1 and H2 are null everywhere for return/revision predictability.** One real secondary finding survives: Risk Factors similarity correlates with subsequent index delisting (p=0.030 OLS / p=0.039 logit), robust to leave-one-out — but this is a text-validity signal (does the measure capture distress), not evidence for the core H1 claim.

**Sidequest** — board/executive/workforce-leadership racial and gender diversity vs. firm risk and performance, using CVM's newly-mandatory disclosure data (2023+). A genuine, adversarially-verified literature gap for Brazil. Six outcomes, seven diversity measures, multiple specifications including a fix for fixed effects being underpowered on this data (confirmed: 70% of companies show zero within-company change in executive racial composition across the 4 available years). The single most promising lead — executive board racial diversity vs. return volatility — turned out to be specification-sensitive (p ranges from 0.0007 to 0.20 depending on how a real small-board measurement issue is handled), which is itself the honest finding: not robust enough to build a chapter on.

**Both are now equally "done."** Neither has a bulletproof positive result. The decision between them is about completeness, fit to the deadline, and how defensible the null is — not about which one has a better number.

## 2. Files you should actually care about

Ignore everything else in `data/interim/`, `data/raw/`, and the many intermediate CSVs — those are working files, not reading material. Here's what matters:

**Main thesis:**
| File | What it is |
|---|---|
| `docs/dissertacao_esqueleto.docx` | **The actual submission document.** Introdução, Revisão de Literatura, Metodologia, and Resultados are written (~6,800 words, 6 tables). Conclusão and Resumo/Abstract are deliberately still placeholders. |
| `docs/exame_qualificacao/` | The real Insper qualification-exam guide (PDF) — dates, requirements, defense mechanics. Read this if you haven't closely. |
| `reports/panel_model_results.md` | The single most important supporting report — explains *why* H1/H2 are null even at the strictest test, with the fixed-effects methodology explained clearly. This is your best source for defending the methodology in the oral defense. |
| `reports/risk_factors_exploration.md` | The delisting finding — your one real secondary result. |
| `CLAUDE.md` | Full project history/status if you need to reconstruct any decision or number. |

**Sidequest:**
| File | What it is |
|---|---|
| `sidequest/dissertacao_diversidade_esqueleto.docx` | The parallel submission document, same structure (~4,100 words). |
| `sidequest/README.md` | Entry point — start here if you haven't looked at the sidequest in a while. |
| `sidequest/novelty_verification.md` | The adversarial literature check — your strongest asset if you present this one, since it's a genuinely verified gap. |
| `sidequest/results_v3.md` | The full empirical story, including the final specification-sensitivity finding. |
| `sidequest/diversity_exploration.ipynb` | Visual walkthrough — useful if you want charts for a presentation. |

## 3. Next steps, in order

1. **Decide which thesis to submit.** This is the one thing left that's genuinely yours to decide, not something more testing will resolve — see Section 4 below for what each choice actually asks of you between now and the deadline.
2. **Write the Conclusão and Resumo/Abstract** for whichever document you pick — deliberately left for last, per the exam guide's own instructions, now genuinely the next task.
3. **Fill in the orientador's name and committee details** (marked `[a definir]` throughout).
4. **Create your CV Lattes** (https://lattes.cnpq.br/) — mandatory for approval, unrelated to either paper's content, don't leave it for the last week.
5. **Coordinate with your orientador**: confirm which topic, agree on a defense date inside the 03/08–03/10 window, and get them to schedule it via the Portal do Professor (≥7 days' notice required).
6. **Send the written version to the committee** ≥7 days before the defense date (or earlier if your orientador asks).
7. **Rehearse the 15-minute presentation** — see Section 4's guides below, timed.

## 4. How to present each paper (15 minutes, per the exam guide's own structure: problema + literatura + metodologia + dados + resultados preliminares)

Both guides assume the same total time budget. Adjust the split if your orientador has a preference.

### If presenting the main thesis (debt-note textual change)

**0:00–2:00 — The problem.** State H1 and H2 plainly: does year-over-year textual change in debt disclosures carry information the market is slow to price? Ground it in Cohen-Malloy-Nguyen's "Lazy Prices" finding for the US, and name the Brazilian gap directly (nobody has tested this specific combination — textual change in debt notes vs. return/revision — for Brazil).

**2:00–5:00 — Literature and why this design.** Two sentences each on: information asymmetry/disclosure (Diamond & Verrecchia, Healy & Palepu), limited attention (Hirshleifer, Lim & Teoh), textual change as a signal (Brown & Tucker; Cohen, Malloy & Nguyen), and why debt notes specifically (Amel-Zadeh & Faasse's footnotes-react-slower finding; Schiozer & Albanez confirming Brazilian debt notes carry real contractual information). Don't list papers — say what each one buys you, matching the exam guide's own explicit instruction that citing prior papers isn't enough on its own.

**5:00–9:00 — Methodology, the centerpiece.** This is where you should spend the most time, because it's your strongest material. Walk through the rigor progression as a *narrative*, not a list: naive correlation → the repeated-observations problem you found and fixed with clustering → the deeper omitted-variable concern that motivated company+year fixed effects → the portfolio-sort test as an independent check via a completely different method. Show the equation. State plainly that this progression is what a real identification strategy discussion looks like — it directly answers the exam guide's explicit question ("qual a hipótese de identificação por trás da sua metodologia? existem ameaças razoáveis?").

**9:00–13:00 — Data and results.** Five text sources, ten years, 111 companies. Show Table 1 (correlation → clustered → controls → fixed effects, all five sources). State the result plainly: null everywhere, including the theoretically strongest source (Risk Factors). Then pivot to the one real finding — the delisting result — and spend real time on it: the design problem it solves (company FE can't apply to a time-invariant outcome), the fix (cross-sectional, one row per company), and the robustness (leave-one-out). This is your evidence that the measure captures something real, even though it doesn't answer H1 directly.

**13:00–15:00 — What this means.** Frame the null explicitly as a finding, not an absence of one: two hypotheses, five text sources, six methods of increasing rigor, and a consistent answer. That consistency — not a lucky p-value — is the contribution. Name the one open thread (delisting/text-validity) as a natural extension.

### If presenting the sidequest (board/executive diversity)

**0:00–2:00 — The problem.** State it as a gap-filling exercise: Brazil made board/executive racial and gender composition mandatory disclosure in 2021 — does this newly-available data show any relationship to firm risk or performance? Be upfront that this is exploratory, not a hypothesis carried in from months of prior work — that's an honest framing, not a weakness, given the exam's own emphasis on viability over a fully mature research program.

**2:00–5:00 — Literature, leading with the gap, not the mechanism.** Your strongest card here is the novelty verification, not the theory — spend real time on it. State plainly: gender diversity vs. performance/cost-of-equity is already published for Brazil, including work from 2025–2026, so that's not your gap. Racial diversity tested against *any* firm outcome, using the real regulatory data rather than a 16%-response survey, is undone — verified by a second, adversarial search specifically trying to disprove it. Then briefly note the international comparison (South Africa, Malaysia, Indonesia, the US all have this literature; Brazil, despite better data, doesn't yet) — this is what makes the gap credible, not just unsearched.

**5:00–9:00 — Methodology, and be direct about its limits.** Explain the short panel honestly (disclosure only exists since 2023, confirmed directly against CVM's own files) and what that forces methodologically — a cross-sectional design instead of the fixed-effects approach used in the other thesis, and why (70% of companies show zero within-company change in this window, so fixed effects would be underpowered, not informative). This is a good place to show you understand identification strategy generally, not just in the one setting where your data happens to cooperate.

**9:00–13:00 — Data and results, told as a methodology story.** Lead with the descriptive fact (median board racial diversity: 0%) — it lands on its own, no test needed. Then walk through the search: cost of debt (clean null), then the one candidate that looked real — executive board racial diversity vs. volatility — and the specification-sensitivity that ultimately killed it as a reportable finding (show the table: p=0.0007 raw, down to p=0.20 once the small-board measurement issue is properly handled). Frame this explicitly as the same kind of finding as the main thesis's rigor progression: a result's failure to survive reasonable alternative specifications *is* the result.

**13:00–15:00 — What this means.** A verified gap, real infrastructure, and an honest null with a well-understood reason (small-sample ratio noise in a young dataset, not a lack of effort). Name the natural extension: the panel grows by one more fiscal year every year going forward, and the same small-denominator problem shrinks as boards diversify further — this dataset gets more informative over time in a way the main thesis's ten-year panel already has.

### If you genuinely can't decide before you have to commit

Talk to your orientador with both `docs/dissertacao_esqueleto.docx` and `sidequest/dissertacao_diversidade_esqueleto.docx` in hand — they know the committee and the program's tolerance for a well-documented null far better than this analysis can. The one factor worth naming explicitly in that conversation: the main thesis is a completed research program (five sources, ten years, six methods); the sidequest is a well-executed first pass on a genuinely new question. Both are legitimate qualification-exam submissions. Which one is the better *dissertation* topic for the next several months is a different, bigger question than which one is ready fastest.

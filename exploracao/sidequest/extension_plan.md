# Extension plan: what more we'd need, and the concrete next steps

Direct answers to "what extra data do we need and how easy is it" and "step by step next steps." All feasibility claims below were checked directly against CVM's actual data (not assumed) before being written down.

## What extra data would strengthen this, ranked by how easy it is

### Easy — already downloaded, zero new acquisition, just needs processing

1. **Extend the panel from 2 years to 4.** Confirmed by direct check: `fre_cia_aberta_2025.zip` and `fre_cia_aberta_2026.zip` both already exist on CVM's portal and both contain the gender/race declaration files, same schema as 2023–2024. Pulling them is a one-line change to `sidequest/build_diversity_dataset.py`'s `DIVERSITY_YEARS` list. This roughly doubles the panel and is the single highest-value, lowest-cost improvement available.
2. **A much higher-power diversity measure: workforce leadership, not just the ~7-person board.** `fre_cia_aberta_empregado_posicao_declaracao_raca_*.csv` (already downloaded, same zips) breaks out race/gender by `Posição = Liderança / Não-liderança` for the *entire workforce* — hundreds to thousands of employees per company, versus a board of 6–13 people. The board-level race measure is heavily zero-inflated (median 0%) precisely because the denominator is so small; a leadership-level measure would have real continuous variation and far more statistical power. This is arguably a better primary measure than the board-level one used in the first pass, not just a robustness check.
3. **A more precise cost-of-debt proxy.** The current proxy (`despesas financeiras / passivo total`) divides by *all* liabilities, including non-interest-bearing ones (accounts payable, provisions, etc.) — a real source of noise. `fre_cia_aberta_obrigacao_*.csv` (already downloaded) reports actual structured debt (`Divida_Total`) broken out by maturity bucket and guarantee type. Swapping the denominator to `Divida_Total` is a same-data, more-precise version of the same measure.

### Medium — plausible, same pattern as infrastructure already built this session, but unverified

4. **ISE B3 / IDIVERSA B3 sustainability-index membership**, as an external validity check or control. B3 publishes index composition through the same kind of public endpoint (`GetPortfolioDay`-style) already used successfully for IBOV in `src/acquisition/b3_ibov.py` — very likely the same call works with a different index code. **Not yet tried or confirmed** — flagging as plausible based on precedent, not as a verified fact, per this project's own rule about not trusting a claim until checked.

### Hard — real new acquisition, no existing infrastructure, likely paid/manual

5. **Actual credit ratings or bond-level yield spreads**, for a true cost-of-debt measure instead of a proxy. CVM's open data doesn't carry this. Would need agency data (S&P/Moody's/Fitch — typically paid/licensed) or ANBIMA debenture-market data (public but a genuinely new acquisition pipeline, not a rerun of existing code).
6. **Commercial ESG scores** (Sustainalytics, MSCI, etc.) as an alternative or complementary outcome — same issue, paid/licensed, no existing pipeline.

## Step-by-step next steps

1. **Extend the diversity panel to 2023–2026** using the already-confirmed-available zips (item 1 above). Cheap, immediate, roughly doubles the sample.
2. **Add the workforce-leadership diversity measure** (item 2) alongside the existing board-level one — likely the more statistically meaningful measure given the board's tiny, zero-inflated counts.
3. **Refine the cost-of-debt proxy** using `Divida_Total` instead of total liabilities (item 3) — same effort as the current version, more defensible.
4. **Re-run the full test battery** (`sidequest/test_diversity_hypotheses.py`, extended to the new measures and years) — with 4 years instead of 2, a light fixed-effects or at least a proper clustered panel test becomes more meaningful than it was with 2 years, though still thinner than the main thesis's 10-year panel.
5. **Apply the same stress-testing discipline to anything that comes back significant** — leave-one-company-out, single-control isolation (exactly what caught the size confound in the first pass), alternative measure specifications — before reporting anything as a real finding.
6. **Decide scope with the user before going further**: this sidequest could stay a documented side-note, or — given how clean the novelty gap turned out to be under adversarial verification — could plausibly become a short standalone paper/working-paper draft rather than just a thesis footnote. That's a scope decision worth making deliberately, not by default, especially given the main thesis's own deadline pressure.
7. Only if the result looks genuinely worth pursuing past step 5: consider the "medium" (ISE B3) and "hard" (credit ratings) data as later additions, not prerequisites — the easy tier alone is enough to meaningfully improve on the first pass.

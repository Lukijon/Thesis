# Literature scan: candidate research questions using CVM's structured governance data

Full notes from the literature research pass referenced in `sidequest/README.md`. ~35 searches across Brazilian (SciELO, RAE, RAC, RCF, REPeC) and international (ScienceDirect, Emerald, Wiley, SSRN, Tandfonline) sources.

## Angle 1: Board/executive gender & racial diversity

**Gender — already well covered in Brazil, including very recently:**
- Mastella, Vancin, Perlin & Kirch (2021), *Gender in Management* 36(4) — 150 B3 firms, 2010–2018. Women on boards → positive accounting/market performance; risk effect inconclusive.
- Nisiyama & Nakamura (2018), *RAE* 58(6) — board diversity → higher leverage.
- RAE (SciELO), "Conselho de Administração, Diversidade de Gênero e Monitoramento" — 199 B3 firms, 2011–2018 — gender diversity → lower executive pay, less earnings management.
- Marquez-Cardenas, Gonzalez-Ruiz & Duque-Grisales (2022), *J. Sustainable Finance & Investment* 12(3) — 243 Latin American firms incl. Brazil, 2012–2018 — **null** result.
- **Gaio & Stefanelli (2025)**, *J. Economics, Finance and Administrative Science* 30(60) — B3 firms, 2010–2023, GMM-sys — gender diversity → **significantly lower cost of equity**. Closes off the cost-of-equity version of this question.
- **Yoshinaga, Bellato & Gil (2026)**, *Gender, Work & Organization* — B3 firms 2010–2020, board + executive, Tobin's Q — positive relationship. Brand new.

**Race — thin, and not yet done with real regulatory data:**
- Gouvêa (2022), ECGI Blog — self-administered survey, Jan–May 2021, sent to all 442 listed companies, **only 69 responded (16%)**. Found zero Black board members, 1.05% Brown, zero Black/Brown CEOs/CFOs. Descriptive only, pre-dates the mandatory disclosure this sidequest uses.
- Myers (2003), *Estudos Afro-Asiáticos* — 13-company qualitative case study, old, pre-regulation.
- BAR (Brazilian Administration Review), "Racial Diversity in Organizations: A Framework and Future Research Agenda" — explicitly a research-agenda piece flagging this as understudied, not filling the gap.
- IBGC (March 2024) and Instituto Ethos/IPEC (2024) — institute reports built from the actual Resolução CVM 59/2021 data (confirms the data source is real and minable) but descriptive percentages only, not peer-reviewed regressions against firm outcomes.

**Regulatory timeline** (matters for design): Resolução CVM 59/2021 (amending Instrução 480), now codified as Resolução CVM 80/2022 Annex C item 7.1D. Effective from FRE filings made in 2023. Disability (PCD) disclosure is separate, mandatory only from 2025 (Resolução 198/2024) — outside this dataset's window.

**International mechanism strength**: gender — genuinely mixed/contested at the meta-analytic level (Post & Byron 2015 AMJ meta-analysis; a 2025 meta-analysis both converge on "context-dependent," not universal; Adams & Ferreira 2009 JFE find a *negative* average effect that flips positive only in weakly-governed firms). Cost-of-capital effects specifically are more consistently negative across French/US/MENA/Chinese samples, though endogeneity is a persistent, unresolved concern across the whole literature. Race/ethnicity: a 2025 meta-analysis explicitly flags it as understudied relative to gender — thinner, less robust prior evidence, meaning a race-focused Brazil study is genuinely exploratory rather than testing an established mechanism.

## Angle 2: Executive compensation structure

Most crowded of the three angles in Brazil:
- Grodt, Degenhart, Dal Magro, Ávila & Piccinin (2024), *Revista Contabilidade & Finanças* 35(94) — 81 IBrX-100 firms, 2016–2021 — ESG disclosure moderates/maximizes pay-performance sensitivity (PPS).
- SciELO RCF — board composition reduces PPS when insiders dominate.
- SciELO RAM — governance and PPS, "a new perspective."
- The RAE gender/pay paper above already sits at this intersection.
- Older stream (2010–2016) — consistently mixed/null pay-performance links across several Brazilian samples.
- Emerald *Corporate Governance* 20(7) (~2020) — compensation structure and firm performance in Brazil.

International anchor: Jensen & Murphy (1990) — classic weak PPS finding; Tosi, Werner, Katz & Gomez-Mejia (2000) meta-analysis — firm size explains >40% of CEO pay variance vs. <5% for performance. Cross-country heterogeneity is real (positive in Japan per Kato & Kubo, null in Portugal per Fernandes) — so "does PPS exist, how strong" is legitimately open per-country, but the "governance characteristic X moderates PPS" template has already been run in Brazil with board composition, ESG disclosure, and gender diversity as the moderator within the last ~2 years. A defensible novel cut would need real specificity (e.g., fixed/variable mix by board tier × post-mandate diversity composition), not the general design.

## Angle 3: Related-party transactions (RPTs)

- de Souza, Bortolon & Leal (2020), *Corporate Ownership & Control* 17(3) — 3,790 hand-collected RPT contracts, 2010–2012 — negative RPT–accounting-performance link, null for market value.
- **Flores & Sonza (2021)**, *REPeC* 15(3) — 153 firms, 2010–2017, **already using Formulário de Referência data** — pyramidal ownership shapes RPTs differently for controlling/controlled vs. affiliated relationships; governance mechanisms don't moderate conflicts effectively.
- Silveira, Prado & Sasso (SSRN) — RPT legal strategies, governance, firm value.
- Multiple RPT + earnings management/audit papers (congress proceedings, UFRJ/USP) — a well-worked seam.
- "Shareholding control, ownership concentration, and the value of the Brazilian firm" (ScienceDirect, 2024) — adjacent, couldn't fetch full detail (403).

**Gap assessment**: the Brazilian RPT literature clusters almost entirely on firm value, accounting performance, disclosure quality, and earnings management. **RPTs and cost of capital (debt or equity) specifically looks essentially untested for Brazil.** International precedent exists (GCC-listed firms: RPTs → higher cost of debt, ScienceDirect) and stock-price-crash-risk-from-RPTs is a live, mostly China-centered literature not yet applied to Brazil. Brazil's concentrated/pyramidal ownership (~65% pyramidal structures, ~48% average largest-shareholder stake, per cited sources) makes this a theoretically well-motivated setting — arguably close to the canonical case for the "tunneling" story.

International anchor: Johnson, La Porta, Lopez-de-Silanes & Shleifer (2000), "Tunneling," *AER* — canonical. La Porta et al.'s investor-protection framework fits Brazil directly. The propping-vs-tunneling duality (RPTs can be value-destroying expropriation *or* value-supporting liquidity provision depending on context) means the expected sign isn't a slam dunk — honest, not a weakness, for thesis framing.

## Other candidates checked and set aside

- **Board interlocks/networks** — already fairly saturated for Brazil (multiple papers finding negative-to-nonlinear interlocking-performance links). Low marginal novelty.
- **Audit committee characteristics** — real literature exists, but audit committees are voluntary in Brazil outside financial institutions, so any sample is small and self-selected — a design constraint independent of novelty.
- **Ownership concentration + stock price crash risk** — deep Brazilian literature exists on ownership concentration and firm value/performance, but crash-risk specifically as the outcome is an international (largely China-focused) literature not found applied to Brazil, despite Brazil's structure being a good natural setting. Legitimate gap, more tangential to the data actually inventoried here.
- **Diversity "decoupling"/symbolic compliance** — conceptually appealing (echoes the main thesis's disclosure-vs-substance theme) but hard to operationalize without an independent benchmark of "true" diversity practice distinct from the disclosure itself.
- **Share pledging by controlling shareholders** — zero Brazil literature found, but not confirmed available in FRE's structured fields and not in the data inventory checked. Speculative.
- **Family firm risk/succession** — mostly qualitative/case-study in Brazil, not suited to a structured-data approach. One incidental finding worth noting: female board participation appears to raise volatility specifically *within* family-controlled firms in at least one source found — a possible moderator for future diversity work, not pursued here.

## Sources

- [Board gender diversity: performance and risk of Brazilian firms (Mastella et al. 2021)](https://www.emerald.com/insight/content/doi/10.1108/gm-06-2019-0088/full/html)
- [Board gender diversity and firm performance: evidence from Latin America (Marquez-Cardenas et al. 2022)](https://www.tandfonline.com/doi/full/10.1080/20430795.2021.2017256)
- [Cracking the Glass Ceiling (Yoshinaga et al. 2026)](https://onlinelibrary.wiley.com/doi/10.1111/gwao.70114)
- [Gender diversity and cost of equity capital: evidence from an emerging market (Gaio & Stefanelli 2025)](https://www.emerald.com/jefas/article/30/60/337/1252135/Gender-diversity-and-cost-of-equity-capital)
- [Corporate governance and racial diversity in Brazilian public companies (Gouvêa 2022, ECGI)](https://www.ecgi.global/blog/corporate-governance-and-racial-diversity-brazilian-public-companies)
- [O valor da diversidade racial nas empresas (Myers 2003)](https://www.scielo.br/j/eaa/a/vjBSjLMzqqk6gL5Vd8JKb8K/)
- [IBGC — Pesquisa IBGC analisa diversidade de gênero e raça (2024)](https://www.ibgc.org.br/blog/pesquisa-ibgc-analisa-diversidade-genero-raca)
- [Conselho de Administração, Diversidade de Gênero e Monitoramento (RAE)](https://www.scielo.br/j/rae/a/wMFYsppcq6Nn8ZDXGcsZgSk/)
- [Diversidade do conselho de administração e a estrutura de capital (Nisiyama & Nakamura 2018)](https://www.scielo.br/j/rae/a/khm9KbhLsFGJgVvQfmG8StK/?lang=pt)
- [The stock market's reaction to mandatory ESG disclosure (Del Col Lopes & Jucá 2025)](https://periodicos.ufrn.br/ambiente/article/view/38667)
- [ESG disclosure and pay-performance sensitivity (Grodt et al. 2024)](https://revistas.usp.br/rcf/en/article/view/225578)
- [Related party transactions, disclosure and ownership structure in Brazil (de Souza, Bortolon & Leal 2020)](https://virtusinterpress.org/Related-party-transactions-disclosure-and-ownership-structure-in-Brazil.html)
- [Transações com Partes Relacionadas em estrutura piramidal (Flores & Sonza 2021)](https://www.repec.org.br/repec/article/view/2900)
- [Related party transactions, ownership structures and cost of debt: GCC listed firms](https://www.sciencedirect.com/org/science/article/abs/pii/S1030961623000085)
- [Shareholding control, ownership concentration, and the value of the Brazilian firm (2024)](https://www.sciencedirect.com/science/article/pii/S2214845024000875)
- [Women on Boards and Firm Financial Performance: A Meta-Analysis (Post & Byron 2015)](https://journals.aom.org/doi/10.5465/amj.2013.0319)
- [Gender, ethnic and nationality board diversity and firm performance: a meta-analysis (2025)](https://www.sciencedirect.com/org/science/article/abs/pii/S1472070125000446)
- [Board Interlocking in Brazil (Latin American Business Review 2012)](https://www.tandfonline.com/doi/full/10.1080/10978526.2012.673419)
- [Large blockholders and stock price crash risk: an international study](https://www.sciencedirect.com/science/article/abs/pii/S1044028322001016)

## Ranking (from the research pass)

1. **Racial diversity + cost of debt/risk, using real CVM regulatory data** — cleanest gap, pursued in this sidequest.
2. **Related-party transactions + cost of capital** — good second candidate, not yet pursued (see "What wasn't done" in `README.md`).
3. Executive compensation structure — most crowded; would need a narrow, specific cut to clear the novelty bar.

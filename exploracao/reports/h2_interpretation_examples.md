# H2 interpretation: why more debt-note change goes with *higher* future returns

2026-11-19. Exploratory, for narrative only. The thesis already establishes the effect; nothing here is meant as a formal test.

Data: the expanded-universe panel (1,128 of 1,134 annual debt-note pairs with cached section text in `suporte/data/interim/poc/sections/`). TextChange = 1 − cosine similarity. "New sentences" are the sentences in year t's note that don't appear verbatim (after normalization) in year t−1's note.

## 1. The simple "good-news keywords" theory is not supported

New sentences were flagged for "good" vocabulary (renegotiation, lengthening, prepayment/payoff, new issuance, lower cost) and "bad" vocabulary (waiver, covenant breach, acceleration, reclassification to current, judicial recovery, default). Each family shows up at almost the same rate in high-change and low-change notes. Among high-change notes, those with only "good" terms don't earn more than the others (mean BHAR +2.7%; "only bad" +0.9%, n=17; mixed/neutral +10.9%).

Why, judging from reading the cases below: the *same vocabulary* describes both the problem and its resolution ("covenants were renegotiated", "the BNDES granted a waiver for the breach"). A keyword count can't tell distress from distress being *resolved*.

## 2. The effect lives in the right tail

| TextChange tercile | mean BHAR | median BHAR | share with BHAR > 50% |
|---|---|---|---|
| low change  | −1.3% | −8.6% | 13.6% |
| middle      | −2.7% | −13.5% | 11.7% |
| high change | +7.5% | −5.1% | 18.6% |

The typical high-change firm doesn't do much better. A larger share of them have a big subsequent rally. The top winners in the high-change tercile are mostly firms that had **fallen 50–80% in the prior 12 months** and were highly levered. Fiscal 2015 (window Mar 2016–Mar 2017) is common among them, but it isn't over-represented in the high-change tercile overall (8% vs 9% in the low tercile), and the tercile gap survives dropping 2015 (+4.6% vs −2.0%). Interaction tests (TextChange × past loser / high leverage, M2 controls) put a larger point estimate on past losers (+0.13 extra) but it isn't significant (p = 0.41). So "distressed firms rewriting their debt terms" is a suggestion drawn from the extremes, not a demonstrated channel.

## 3. Narrative examples (raw stock return also high, not just BHAR)

- **Rumo Logística, fiscal 2015** (similarity 0.10; debt balance moved only +3% of assets; raw return over the next 12 months +185%). New text: covenants (net debt/EBITDA) were *renegotiated to 5.5x with all creditors*; the BNDES had *granted a waiver for the covenant breach* at 31/12/2014 and 31/12/2015; a *debt reprofiling* and an ongoing *capitalization* were planned for 1H2016. **Best single example for both H1 and H2.** The balance sheet barely moved, while the note documented a distressed firm finding a way out.
- **Gerdau, fiscal 2015** (similarity 0.70; Δdebt +4.5% of assets; raw +160%). New text: in September 2015 the company *completed the elimination of financial covenants in all of Gerdau S.A.'s contracts*; a potential future breach would trigger a cure period rather than default; it *renewed and reduced* its US$1 billion revolving credit facility. Credit risk fell, and the debt number shows nothing of it.
- **Bradespar, fiscal 2015** (similarity 0.64; raw +256%). New text: a 6th debenture issuance (R$1.26 billion, 105.5% of CDI) whose proceeds *fully repaid* the 5th issuance maturing the same day, i.e. a successful rollover in a closed credit market. Caveat: Bradespar's return is mostly Vale's 2016 rebound, so it's a weaker example.
- **Oi, fiscal 2019** (similarity 0.11; raw +263%). New text: the liabilities subject to judicial recovery were *restructured/novated and remeasured at fair value* (IFRS 9). This shows a completed restructuring. But here the debt balance *did* move a lot (−58% of assets), so it doesn't illustrate "words carry what numbers don't".

Avoid as examples, because the return is an artifact of the model or the market rather than the note: Ambipar 2023 (2024 short squeeze, raw +605%); Nexpe 2022 and Plascar 2012 (raw return ≤ 0 but BHAR > +100%, see section 4); Marfrig 2022 (raw +47% vs BHAR +300%).

## 4. Caveat found along the way: how much of H1 depends on the firm-specific alpha

Firms that crashed during the estimation window get a very negative alpha, so their projected "normal" return is very negative and later stability turns into a large positive BHAR (Nexpe, Plascar, Marfrig above). Re-running the M0–M3 grid with the **raw 12-month stock return** (winsorized 1/99; year fixed effects absorb the market):

| | BHAR ajustado (thesis) | raw return |
|---|---|---|
| M0 | β=+0.160, p=0.014 | β=+0.101, p=0.126 |
| M2 | β=+0.159, p=0.015 | β=+0.089, p=0.188 |
| M3 | β=+0.172, p=0.010 | β=+0.076, p=0.267 |

Same sign, about 55–65% of the magnitude, not significant. The calendar-time portfolio (p = 0.0011) doesn't use firm-specific alphas, so it remains the strongest defense. An examiner could raise this, so it's worth deciding whether the thesis should mention it.

## Suggested narrative (speculative)

In Lazy Prices, firms change their text to obscure bad news, and returns fall. In the Brazilian debt note, large changes seem to appear mostly when a firm *is dealing with* a debt problem: renegotiating covenants, getting waivers, reprofiling, refinancing, completing a restructuring. By the time the note is published, the distress is already priced (prior returns of −50% to −80%). What the note adds is that the problem is being *resolved*, written in technical language that few investors read, and that never shows up in the aggregate debt balance. This would explain both the positive sign (H2 rejected) and the underreaction (H1).

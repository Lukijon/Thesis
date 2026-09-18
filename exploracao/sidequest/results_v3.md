# Extended results (v3): broader outcomes, sector control, and the closest call this project has had

Direct response to "a good correlation matters more here than a null result" — this pass genuinely tried harder, not just re-documented the same null. New outcomes added: market-to-book (Tobin's Q proxy, built from share count × year-end price, not tried before), ROA, ROE, and trailing 12-month stock return. New control: sector group (9 broad categories, collapsed from 33 raw CVM sector codes). New code: `build_diversity_dataset_v3.py`, `test_diversity_hypotheses_v3.py`.

## The full battery: 42 predictor × outcome combinations

One predictor — **executive board % Black/Brown** — showed up as significant across *three different outcomes* (return volatility, market-to-book, trailing return) once controls were added. That's a materially different situation than any single-outcome hit seen so far in either project, and got the deepest scrutiny of anything in this whole session as a result.

## A real methodological catch first: fixed effects is underpowered here, not decisive

Before trusting or dismissing anything, checked whether the company+year fixed-effects test (the main thesis's sharpest tool) is even a fair test for board/executive diversity variables. It isn't: **70 of 100 companies show zero within-company variation in executive board racial composition across all 4 years** — most companies simply never changed their executive racial makeup in this window. Fixed effects can only detect within-company change; with 70% of the sample contributing none, a null FE result here means "underpowered," not "debunked" — a real, important difference from the main thesis, where 10 years of genuine year-to-year textual change gave fixed effects real teeth.

**The fix**: the same one that worked for the main thesis's Risk Factors delisting finding — a purely cross-sectional design (one row per company, company-level averages), which sidesteps the low-variation problem by construction instead of needing power it doesn't have.

## The closest call: executive board racial diversity vs. return volatility

Cross-sectional test (n=91 companies): **p=0.029 without controls, p=0.0007 with controls** — positive coefficient (more diverse executive boards, on average, associated with *higher* volatility, not lower). Then stress-tested exactly like every other near-miss this session:

| Check | Result |
|---|---|
| Leave-one-company-out (91 refits) | Worst case p=0.021, never loses significance, never flips sign |
| Each control added individually | All three (size, leverage, ROA) keep it significant alone |
| Median instead of mean | p=0.0020, essentially unchanged |
| Sector-group dummies added | p=0.0003 -- gets *stronger* |

By every check this project has used before, this should have been the strongest result of the entire session — stronger than the Risk Factors delisting finding, stronger than the mgmt-report return result, surviving checks that killed both of those.

**It didn't survive the next one.** Executive boards in this sample are small (median 5 members, some as few as 1-2) and racial-diversity percentages computed on small denominators produce noisy extreme values almost by construction — a 7-person board with one Black/Brown member reads as a "typical" 14%, but a 2-person board with one member reads as an extreme-looking 50%. Excluding companies with fewer than 5 executive-board members (57 of 91 remain): **the result collapses to p=0.197**, and the coefficient shrinks by two-thirds (+0.65 to +0.19).

This is a genuinely important catch, and a different failure mode than anything found before this session: leave-one-out only checks whether *one* company drives a result. Here, several small-denominator companies were each contributing noisy ratios in a way that no single removal would expose — it took a targeted, denominator-quality-motivated exclusion to find it, the same instinct that caught the wrong-attachment contamination and the Marcopolo degenerate score earlier in this project, applied to a new kind of data-quality problem.

## Everything else: null, same pattern as v1/v2

- Cost of debt: null across all 7 predictors, no exceptions.
- Market-to-book and ROA/ROE: the same executive-diversity predictor showed marginal hits (p≈0.03-0.04) in the panel specification, but given the volatility result -- the strongest of the three -- didn't survive the denominator check, these weren't pursued further; they're the same predictor and almost certainly the same artifact.
- Board-level and workforce-leadership diversity: nothing new against the four added outcomes.

## Follow-up: does a softer fix (instead of hard exclusion) rescue it?

Hard-excluding small executive boards is the crudest possible fix -- it throws away 37% of the sample along with the noise. Three more surgical alternatives were tried, all legitimate, none of them a "make the problem go away" move:

| Specification | n | Coefficient | p-value |
|---|---:|---:|---:|
| Ratio, unweighted OLS (baseline) | 91 | +0.648 | 0.0007 |
| Ratio, WLS weighted by executive-board size | 91 | +0.430 | 0.0074 |
| Ratio, WLS weighted by (board size)² | 91 | +0.300 | 0.0325 |
| Raw count + board size as separate regressors (no pre-built ratio) | 91 | +0.072 (count) | 0.0322 |
| Ratio, hard-restricted to boards ≥5 members | 57 | +0.192 | 0.1973 |

**This is a more honest, more complicated picture than "it's just noise."** The two softer corrections (downweighting instead of dropping, and letting count and denominator enter separately instead of pre-dividing them) both keep the result marginally significant, just weaker than the raw version. Only the hard exclusion kills it outright -- and the point estimate itself, not just its precision, shrinks by two-thirds under that specification (0.65 to 0.19), which is a bigger change than sample-size loss alone would produce.

**Read plainly: the result is specification-sensitive, not specification-proof.** It swings from p=0.0007 down to p=0.20 depending on which defensible way of handling the small-board measurement issue is used, without ever clearly settling on one side. A genuinely robust finding shouldn't move that much across reasonable alternative treatments of the same underlying problem -- this is the same kind of instability, in miniature, that killed the main thesis's management-report result once tested against fixed effects. It doesn't fully vindicate "it's an artifact," and it doesn't rescue "it's real" either. The fair characterization is: unresolved, fragile, and not something to build a thesis chapter around as currently specified.

## Honest verdict on this pass

A real, thorough search happened here -- 6 outcomes, 7 predictors, sector controls, a properly-specified cross-sectional design built specifically to give underpowered fixed effects a fair alternative, and the deepest stress-testing this project has applied to any single result. **Nothing survived.** The one candidate that cleared every bar this project has used before was caught by a bar this project hadn't needed to use before (small-denominator ratio noise) -- which says the bar was worth having, not that the search wasn't serious.

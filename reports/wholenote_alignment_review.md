# Alignment review: whole-document POC vs. the approved pre-projeto

Written while re-reading `docs/pre-projeto.docx` in full for the first time this session, before building on top of `notebooks/poc_wholenote.ipynb`. Two things in the pre-projeto directly bear on how that notebook's findings should be framed, and one of them is a real tension I'm not resolving on my own — flagging both here rather than silently editing already-written conclusions.

## 1. The "bidirectional" finding is not a new hypothesis — it's H1, tested correctly for the first time

The pre-projeto states H1 explicitly without a direction, **on purpose**, and says so in so many words:

> "H1: as alterações textuais entre exercícios nas notas de empréstimos, financiamentos e debêntures estão associadas ao retorno anormal futuro das ações... Optou-se por manter essa hipótese sem direção definida de propósito. Uma mudança grande no texto pode ser notícia ruim, como quebra de covenant ou dificuldade de refinanciamento, mas também pode ser notícia boa, como alongamento de prazo, redução de taxa ou quitação de dívida. Não dá pra assumir de antemão que mudança sempre significa notícia ruim."

H1a (the directional, Lazy-Prices-style hypothesis — more change → lower future return) is explicitly marked **"opcional, exploratória"** and secondary, conditional on the change turning out to be concentrated in bad news.

Every correlation computed in this project before `poc_wholenote.ipynb` §6 — including the ones in `poc_overview.ipynb` — was a **signed** correlation (Pearson/Spearman between similarity and raw abnormal return). That's a test of H1a, not H1. It was never labeled that way, and H1a was never meant to be the primary test. **§6's extreme-return / magnitude test is the first time this project has actually tested H1 as specified.** It should be described that way going forward: this is H1, tested properly, not a new "H1b."

**Action taken:** the new analysis added in this session (§8–§10 of `poc_wholenote.ipynb`) uses "H1 (magnitude/bidirectional test)" instead of "H1b." I did not rewrite §6's original "candidate H1b" language where it already existed — that text is left as-is with a short note pointing here, since editing an already-written conclusion without your sign-off is exactly the kind of change you asked me to flag rather than make silently. Worth a five-minute cleanup pass once you're back to make the notebook internally consistent.

## 2. Real tension, not resolved here: the pre-projeto argues *for* the narrow note, *against* the whole document

This is the one that needs your judgment call. The pre-projeto's justification section explicitly argues for the narrow debt note as the unit of analysis, citing a specific Brazilian study:

> "No Brasil, Schiozer e Albanez mostram, com coleta manual em milhares de notas de empréstimos e financiamentos de empresas da B3, que essas notas carregam informação contratual concreta sobre covenants, o que reforça que vale a pena tratar essa nota especificamente, **e não o documento inteiro**, como unidade de análise."

That's a direct, citable, already-in-the-document argument against exactly the pivot `poc_wholenote.ipynb` makes. It's a good argument — a whole-document measure mixes in accounting-policy boilerplate, unrelated notes (PP&E, taxes, related parties, etc.), and picks up disclosure-style changes that have nothing to do with debt. The whole-document approach's *stronger empirical results* don't make that theoretical concern go away; if anything, a whole-document effect that's stronger than the narrow-note effect is a little suspicious on its own terms — it could mean the measure is picking up something more diffuse (general disclosure-quality or reporting-style change) rather than the debt-specific mechanism the thesis is actually about.

**This is not something I should decide.** Options as I see them, for you to weigh when you're back:
- **(a) Keep the narrow note as the primary/thesis-defining measure**, per the approved pre-projeto, and present the whole-document result as a supplementary/robustness angle — "the effect is not confined to the debt note, it shows up at the whole-filing level too," which is actually a fine, defensible framing that doesn't require abandoning Schiozer & Albanez's argument.
- **(b) Promote whole-document to co-primary or primary**, and rewrite the justification section to argue for it — defensible too, since Amel-Zadeh & Faasse (already cited in the pre-projeto!) explicitly compare MD&A vs. footnote-level text and find footnote-level change predicts returns, which is actually a whole-vs-narrow precedent already sitting in your own lit review, cutting the other way from Schiozer & Albanez.
- **(c) Both, formally**, as two parallel measures with their own results sections — more work, most complete, matches how this session already produced parallel narrow/whole/quarterly pipelines.

I'd lean toward (a) or (c) if asked, since it doesn't require walking back an already-written, professor-facing justification, but this is genuinely your call, not mine to make by editing the pre-projeto or reframing the notebook's headline unilaterally.

## What I did *not* touch

- `docs/pre-projeto.docx` — read only, not edited.
- `notebooks/poc_wholenote.ipynb`'s existing §1–§7 conclusions — left exactly as written. New analysis this session is appended as new sections, not merged into or replacing the existing narrative.
- No claim in this project has been walked back or softened based on this review — this file exists so the tension is visible, not so it gets quietly resolved in one direction.

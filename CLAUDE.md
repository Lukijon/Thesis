# Project context for Claude

Read this first. It's a working summary of a long, iterative session — status, decisions, and the things that would otherwise get rediscovered the hard way. `README.md` is the user-facing overview; this file is oriented at picking work back up quickly.

## What this is

A Brazilian accounting/finance master's thesis (Insper MPE22 program; see `privado/pre-projeto.docx`): does year-over-year textual change in the "empréstimos, financiamentos e debêntures" (loans/financing/debentures) note of Brazilian companies' annual financial statements predict future abnormal stock returns (H1/H1a) and analyst EPS forecast revisions (H2)? Measured via TF-IDF + cosine similarity between consecutive fiscal years' note text, following Cohen/Malloy/Nguyen ("Lazy Prices") and Brown & Tucker.

The user is doing the actual academic work; this repo is the data/code side plus the thesis document itself. Thesis-facing content (README, the thesis text) is in Portuguese to match; code, comments, and commit messages are in English.

## Where things stand

**The empirical work is done; the project is now in thesis-writing/editing mode.** Two hypotheses were tested across four text sources (originally five — the ITR/quarterly debt note was removed from scope in September 2026, see below) and six rigor levels (correlation, clustered regression with/without controls, tercile comparison, delisting check, fixed-effects panel, calendar-time portfolio sort). Full empirical narrative, round by round, lives in `exploracao/reports/*.md` if historical detail is ever needed — it's not reproduced here anymore since it's no longer the active work.

**The headline result**: on the expanded 185-company universe (2010–2025), year-over-year textual change in the *annual* debt note is associated with future abnormal returns, significant at 5% across the full M0–M3 control grid (M2, the pre-specified main specification: β=0.156, p=0.017), corroborated by a calendar-time portfolio sort (p=0.0011) and the Santos & Coelho (2018) panel design (p=0.043–0.080). This is the dissertation's single pre-specified confirmatory test for H1. The other three text sources (whole notes, Relatório da Administração, Fatores de Risco) are specificity/generalization checks, not independent confirmatory tests of the same hypothesis — none show the same pattern. H2 (analyst EPS revision) is a clean null across the whole grid, on the original 111-company universe (EPS consensus data hasn't been re-pulled for the 74 IBX-extra companies).

**Recent structural decisions on the thesis text (September 2026), in order:**
1. Repo reorganized into `tese/` (deliverable), `suporte/` (data+code), `exploracao/` (POCs/superseded work), `privado/` (gitignored, local-only advisor material) — see Repo map below.
2. Resumo/Abstract rewritten in a direct, "Utilizando X, mostramos que Y" style per advisor feedback and the Lazy Prices paper's example; universe described via IBX only (every Ibovespa company is already in IBX, so naming both is redundant — but this only applies to *describing the total universe*, not to methodology that is genuinely IBOV-specific, see below).
3. The Benjamini-Hochberg multiple-testing correction was removed entirely, alongside reframing the annual debt note as the dissertation's one pre-specified confirmatory test and the other sources as specificity/generalization checks rather than a "family" of independent tests — this reframing is what made dropping the correction defensible rather than arbitrary.
4. Text sources reduced from five to four: the ITR (quarterly debt note) was removed completely — text, tables (`tab:sample`, `tab:h1`, `tab:h1_m2_detalhe`, `tab:h2`, `tab:h2_detalhe`), and the two figures that included it (`similarity_by_source.png`, `extraction_reliability.png`, regenerated via `suporte/src/analysis/build_thesis_figures_expanded.py`). Rationale: a quarterly filing's effect is economically distinct from the annual sources and had no clean rationale for sitting alongside them.
5. Chapter 1 (Introdução) revised to match the Resumo's tone: precise IBX-based universe description instead of vague "listadas na B3"; trimmed a paragraph that fully re-argued material Chapter 2 (Referencial Teórico) already covers in depth, deferring to it instead (the same "leaner where it's not about the result" logic as the Resumo rewrite).
6. Audited every remaining "Ibovespa"/"IBOV" mention across text, tables, and figure legends (the PNGs themselves, not just the `.tex` source — matplotlib text doesn't show up in a text grep). Most are legitimate and methodologically load-bearing, *not* redundant with IBX: the sample's three groups (current/historical Ibovespa constituents vs. IBX-extra) were built using Ibovespa's own historical composition (reconstructed from B3 web-archive snapshots — no equivalent historical IBX reconstruction exists), and the delisting/survivorship check's outcome variable is specifically "saiu do Ibovespa" (a more selective, rotating index than IBX, so a real distress signal). But found and fixed one genuine factual bug in the process: "Fontes de dados" and the descriptive-stats section attributed H1's dependent variable and the past-return control to Bloomberg *Ibovespa* price data — checking the actual code (`compute_alpha_abnormal_returns.py`, `build_control_variables.py`) showed the current abnormal return is a four-factor NEFIN-model residual and the past-return control is a raw stock return; Ibovespa index price isn't used by either (it's loaded in `portfolio_sort.py` only as an unused diagnostic column). Corrected the text to match what the code actually computes.
7. Per explicit advisor guidance ("ser direto ao ponto, seguir o estilo de papers de economia, não material acadêmico genérico"): Hipóteses section restructured to state H1/H1a as plain, back-to-back statements first, with the direction/exploratory-hypothesis discussion moved to a paragraph after both; Section 1.2 ("Estrutura da dissertação", a chapter-by-chapter roadmap) removed entirely — it only restated the table of contents in prose, a common ABNT convention but absent from the economics papers (Lazy Prices included) this thesis otherwise follows stylistically.

**Still pending**: Conclusão is a placeholder (deliberately, per the exam guide's own "write it last" instruction) — this is the main remaining piece of actual writing. Beyond that, thesis text/editing work tends to arrive incrementally (a section at a time, often triggered by rereading against the advisor's feedback or the Lazy Prices example) rather than as a single remaining task list.

## Repo map

```
tese/latex/tese_jonathan.tex   the actual submission document (ABNT, compiles via MiKTeX: pdflatex → bibtex → pdflatex → pdflatex)
tese/latex/figures/            thesis figures, regenerated by suporte/src/analysis/build_thesis_figures_expanded.py
suporte/src/acquisition/       CVM + B3 data acquisition (see .claude/skills/cvm-debt-notes/SKILL.md for the full playbook)
suporte/src/processing/        PDF text extraction, note-section isolation, TF-IDF scripts
suporte/src/analysis/          abnormal-return models, M0-M3 grid, robustness batteries, thesis figure generation
suporte/src/features/          control-variable construction (size, leverage, ROA, momentum, etc.)
suporte/data/raw/dfp/          acquired debt-note PDFs, one folder per CD_CVM/fiscal year (gitignored, local-only -- see below)
suporte/data/raw/dfp/_cache/   raw CVM filing zips -- gitignored, multi-GB locally, freely re-derivable, never needs backing up
suporte/data/raw/market/       Bloomberg-derived data (gitignored -- see licensing note below)
suporte/data/interim/          manifest/log CSVs (tracked) + suporte/data/interim/poc/ (POC intermediates + results, tracked)
suporte/data/interim/dfp_filing_dates.csv   real CVM disclosure date per acquired filing (event date for return calcs)
exploracao/notebooks/poc_overview.ipynb   the POC narrative with real charts and text evidence, executed in place
exploracao/reports/            narrative writeups (markdown) for every closed-out exploration round -- the full empirical history
privado/                       gitignored, local-only: advisor feedback/transcripts, the institutional exam guide, the Lazy Prices
                                reference paper, the old pre-expansion LaTeX draft, the pre-projeto, a presentation guide
```

**Reorganized 2026-09-18** from a flatter layout (`src/`, `data/`, `docs/latex/main.tex`) into the structure above. **All `python -m src.<...>` commands must be run with CWD set to `suporte/`** — that's where `src/` and `data/` sit relative to each other. A handful of scripts moved to `exploracao/src/` (explicitly superseded, per their own docstrings, or one-off/exploratory) still import `from src.analysis...` and would need `PYTHONPATH` pointed at `suporte/` to run again — they're not part of the active pipeline, so this wasn't fixed.

## Non-obvious things worth knowing before touching acquisition code

Full detail lives in `.claude/skills/cvm-debt-notes/SKILL.md` and in code docstrings (`suporte/src/acquisition/cvm_notes.py`, `suporte/src/acquisition/b3_ibov_historical.py`, `suporte/src/processing/locate_note_section.py`) — don't re-derive these from scratch:

- CVM filings come in two structurally different formats depending on year (pre/post ~2021); `cvm_notes.list_attachments` handles both.
- `save_company_year_notes` normalizes pandas/numpy types before JSON serialization — numpy.int64 isn't JSON-serializable and this bit us once.
- CVM's RAD system throttles under rapid-fire requests; downloads are paced (`suporte/src/utils/http.py`).
- B3's live composition API only returns *today's* IBOV membership — no historical date parameter exists. Historical membership was reconstructed from Internet Archive snapshots of B3's retired portfolio page (26 companies) plus a user-provided Bloomberg export (10 more companies) — see `b3_ibov_historical.py` for the full methodology and its documented residual gaps. There is no equivalent historical reconstruction for IBX (the broader index) — this matters when describing the sample's group structure, see point 6 above.
- The note-locator (`locate_note_section.py`) uses font-size/bold heuristics, not plain regex — necessary because the same keywords appear in tables of contents, body prose, and subsection captions, not just the real heading. It's been hardened across seven rounds against specific failure modes (see the module docstring); when you find a new one, fix it generally and re-run the eval harness (`eval_note_locator.py`) to confirm no regression.
- A background download that looks stalled often isn't — Python's stdout buffers heavily when not a TTY. Check `suporte/data/raw/dfp/_cache/*.zip` mtimes before assuming a hang. Always launch long acquisition runs with `python -u`.
- The current H1 dependent variable is a four-factor (NEFIN: MKT/SMB/HML/WML) alpha-residual model, computed in `suporte/src/analysis/compute_alpha_abnormal_returns.py` — it supersedes an older Ibovespa-only, no-beta market-adjusted return method. If you see "Ibovespa" attributed to the abnormal-return calculation anywhere, that's stale; verify against this file before trusting it (see point 6 above for a real instance of this bug).

## Data/git conventions

- **Raw acquired PDFs (`suporte/data/raw/dfp/`) are gitignored, local-only — do not track or push them.** They were briefly tracked via git-lfs and pushed to GitHub, then reversed: history was rewritten with `git-filter-repo` to strip them and force-pushed. The files themselves are safe on disk, just not in git. Don't `git lfs track` these again without asking — that's exactly what got reversed.
- `suporte/data/raw/dfp/_cache/` (raw CVM zips) and `suporte/data/raw/market/` + `suporte/data/raw/analysts/` (Bloomberg-derived data — redistribution-restricted under Bloomberg's license) are **gitignored**, never commit these regardless of size.
- Small manifest/log CSVs under `suporte/data/interim/` are tracked; bulk intermediate caches generally aren't, except `suporte/data/interim/poc/` which is small enough (~5MB) to keep for reproducibility.
- `privado/` is entirely gitignored (see `.gitignore` for the full rationale) — never move anything out of it into a tracked location without checking first.
- **Force-pushes / history rewrites**: only ever done once, explicitly requested by the user. Don't do this again without the same kind of explicit, specific request.
- After any edit to `tese/latex/tese_jonathan.tex`, recompile before committing: from `tese/latex/`, `pdflatex -interaction=nonstopmode tese_jonathan.tex` → `bibtex tese_jonathan` → `pdflatex ...` (×2), confirm 0 undefined references, then delete build artifacts (`*.aux *.log *.out *.toc *.bbl *.blg missfont.log compile_log_*.txt bibtex_log.txt`) before `git add` — the compiled `tese_jonathan.pdf` is the only build output that's tracked.

## How this user likes to work

- **Verify findings against the real underlying data/code before trusting a number or a claim in the text.** This applies as much to thesis prose now as it did to empirical results earlier — a methodology description that sounds plausible ("Ibovespa is the benchmark") can be stale relative to what the code actually does; check before asserting, the way the Ibovespa-price bug above was caught by reading `compute_alpha_abnormal_returns.py`, not by trusting the existing sentence.
- Report honest caveats and negative/mixed results plainly rather than smoothing them over.
- For genuinely large or costly/hard-to-reverse actions (big new downloads, force-pushes, major restructuring), check in briefly before proceeding — but don't over-ask for routine continuations of already-agreed-on work.
- Prefers concrete numbers and real examples over descriptions ("here's the actual diff" beats "the text changed").
- **Writing style, per the advisor's explicit instruction**: direct, assertive, results-first where appropriate (e.g. lead paragraphs with "Utilizando X, mostramos que Y" rather than "este estudo investiga se..."); follow the register of an economics paper (Lazy Prices is the standing example) rather than generic ABNT/academic boilerplate. In practice this has meant: cutting sections whose only function is restating the table of contents or re-arguing points made in full elsewhere in the document; trimming sample/universe descriptions to the minimum precise statement (name the actual index, no unnecessary breakdowns) rather than exhaustive detail, in framing paragraphs — full detail still belongs in the dedicated data chapter; bolding short lead-in phrases ("A pergunta, formalmente:", "O resultado principal, em uma frase:") that orient the reader before a dense paragraph.
- Frequently asks a question first ("é realmente necessário?", "porque está diferente?") before deciding on an edit — treat these as genuine requests for your honest assessment, not rhetorical, and give a direct recommendation; the user will confirm ("sim") before you act on anything structural.
- Session-management pattern: this project runs long, editing-heavy sessions against a single large `.tex` file, which gets expensive — when the user says a session is "pesada" and they're starting fresh, the priority is making sure this file (and README's Status section) reflects current reality so the next session doesn't need to re-derive it from `git log`.

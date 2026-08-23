# Project context for Claude

Read this first. It's a working summary of a long, iterative session — status, decisions, and the things that would otherwise get rediscovered the hard way. `README.md` is the user-facing overview; this file is oriented at picking work back up quickly.

## What this is

A Brazilian accounting/finance master's thesis (see `docs/pre-projeto.docx`): does year-over-year textual change in the "empréstimos, financiamentos e debêntures" (loans/financing/debentures) note of Brazilian companies' annual financial statements predict future abnormal stock returns (H1/H1a) and analyst EPS forecast revisions (H2)? Measured via TF-IDF + cosine similarity between consecutive fiscal years' note text, following Cohen/Malloy/Nguyen ("Lazy Prices") and Brown & Tucker.

The user is doing the actual academic work; this repo is the data/code side. Thesis-facing content (README, TODO, pre-projeto) is in Portuguese to match; code, comments, and commit messages are in English.

## Status (see README.md "Status" section for the checklist)

- **Acquisition part 1: done.** 993 company-fiscal-year debt-note PDFs, 2015–2024, for 111 non-financial companies — the 66 *current* Ibovespa constituents plus 45 more found via a historical-IBOV reconstruction (`src/acquisition/b3_ibov_historical.py`) to fix survivorship bias. Includes Americanas S.A. (added in a second, corrective Bloomberg pass — see that file's docstring point 3 for a real process gap worth reading before trusting a "we checked X" claim at face value). All present locally on disk; **not tracked in git** (see Data/git conventions below — this was tried via git-lfs and reversed).
- **POC: done, three rounds**, all in `notebooks/poc_overview.ipynb` + `reports/poc_note_extraction_findings.md`:
  1. Does the TF-IDF idea hold up at all? Yes, where extraction is reliable.
  2. Hardened the note-extraction heuristic (4 real bugs fixed) — reliable-cohort mean similarity 0.75 → 0.87.
  3. Extended to 36 of the (now 45) historical-IBOV companies: dropped-from-IBOV/delisted companies show more textual change than companies that stayed, but the effect weakens under a stricter robustness check (p=0.0028 → p=0.068) — **promising, not yet settled**, needs the same hardening work extended to that company set before it's citable. This ran *before* the 10-company corrective addition (Americanas et al. — see acquisition note above), so the quantitative §5/§6 comparison in the notebook doesn't include them yet; PDFs are downloaded and ready, just not run through `run_delisted_analysis.py` yet.
- **Not started:** acquisition part 2 (rest of the non-financial B3 universe, ~756 more companies — see `src/acquisition/cvm_dfp.py build_company_universe` with no `cd_cvm_filter`), re-running the delisted-company POC analysis with the 10 newly-added companies, Bloomberg market/fundamentals/analyst data, control variables, abnormal returns, regressions.
- **Outstanding asks of the user:** see `TODO.md` — market data, control variables, and analyst consensus (all Bloomberg).

## Repo map

```
src/acquisition/   CVM + B3 data acquisition (see .claude/skills/cvm-debt-notes/SKILL.md for the full playbook)
src/processing/    PDF text extraction, note-section isolation, TF-IDF POC scripts
src/analysis/      empty — where regressions/hypothesis tests will go
src/features/      empty — where control-variable construction will go
data/raw/dfp/      acquired debt-note PDFs, one folder per CD_CVM/fiscal year (gitignored, local-only -- see below)
data/raw/dfp/_cache/  raw CVM filing zips -- gitignored, 8.6GB+ locally, freely re-derivable, never needs backing up
data/raw/market/   Bloomberg-derived data (gitignored — see licensing note below)
data/interim/      manifest/log CSVs (tracked) + data/interim/poc/ (POC intermediates + results, tracked)
notebooks/poc_overview.ipynb   the POC narrative with real charts and text evidence, executed in place
reports/           narrative writeups (markdown)
```

## Non-obvious things worth knowing before touching acquisition code

Full detail lives in `.claude/skills/cvm-debt-notes/SKILL.md` and in code docstrings (`src/acquisition/cvm_notes.py`, `src/acquisition/b3_ibov_historical.py`, `src/processing/locate_note_section.py`) — don't re-derive these from scratch:

- CVM filings come in two structurally different formats depending on year (pre/post ~2021); `cvm_notes.list_attachments` handles both.
- `save_company_year_notes` normalizes pandas/numpy types before JSON serialization — numpy.int64 isn't JSON-serializable and this bit us once.
- CVM's RAD system throttles under rapid-fire requests; downloads are paced (`src/utils/http.py`).
- B3's live composition API only returns *today's* IBOV membership — no historical date parameter exists. Historical membership was reconstructed from Internet Archive snapshots of B3's retired portfolio page (26 companies) plus a user-provided Bloomberg export (10 more companies) — see `src/acquisition/b3_ibov_historical.py` for the full methodology and its documented residual gaps.
- The note-locator (`locate_note_section.py`) uses font-size/bold heuristics, not plain regex — necessary because the same keywords appear in tables of contents, body prose, and subsection captions, not just the real heading. It's been hardened against several specific failure modes (see the module docstring); when you find a new one, fix it generally and re-run the POC to confirm no regression, the way round 2 did.
- A background download that looks stalled often isn't — Python's stdout buffers heavily when not a TTY. Check `data/raw/dfp/_cache/*.zip` mtimes before assuming a hang. Always launch long acquisition runs with `python -u`.

## Data/git conventions

- **Raw acquired PDFs (`data/raw/dfp/`) are gitignored, local-only — do not track or push them.** They were briefly tracked via git-lfs and pushed to GitHub, then reversed: history was rewritten with `git-filter-repo` to strip them (see the commit around "Add CLAUDE.md" in `git log` for where this happened) and force-pushed. The files themselves were restored to disk afterward from the still-populated local LFS object store (`.git/lfs/objects` retains blobs even after they're untracked, until explicitly pruned) — they're safe on disk, just not in git anymore. `.gitattributes` no longer declares any LFS-tracked paths. If you're tempted to `git lfs track` these again, don't without asking — that's exactly what got reversed.
- `data/raw/dfp/_cache/` (raw CVM zips) and `data/raw/market/` + `data/raw/analysts/` (Bloomberg-derived data — redistribution-restricted under Bloomberg's license) are **gitignored**, never commit these regardless of size.
- Small manifest/log CSVs under `data/interim/` are tracked; bulk intermediate caches generally aren't, except `data/interim/poc/` which is small enough (~5MB) to keep for reproducibility.
- **Force-pushes / history rewrites**: only ever done once so far, explicitly requested by the user to remove the PDFs above. Don't do this again without the same kind of explicit, specific request — it's about as destructive as git gets.

## How this user likes to work (learned this session, not guessed)

- **Verify findings against the real underlying data before trusting a number.** Repeatedly, an aggregate stat (a similarity score, a "current members" list) turned out to hide an artifact (wrong PDF section captured, survivorship bias) that only showed up by reading actual text or checking a concrete example. Default to that level of skepticism on this project — it's been right every time so far.
- Report honest caveats and negative/mixed results plainly (e.g. the round-3 "promising, not yet settled" finding) rather than smoothing them over.
- For genuinely large or costly/hard-to-reverse actions (big new downloads, force-pushes, spending significant new effort in a new direction), check in briefly before proceeding rather than assuming — but don't over-ask for routine continuations of already-agreed-on work. When in doubt about what belongs in a push, ask rather than assume — a mid-flight correction here is exactly what led to the history rewrite documented above.
- Prefers concrete numbers and real examples over descriptions ("here's the actual diff" beats "the text changed").

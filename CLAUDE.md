# Project context for Claude

Read this first. It's a working summary of a long, iterative session — status, decisions, and the things that would otherwise get rediscovered the hard way. `README.md` is the user-facing overview; this file is oriented at picking work back up quickly.

## What this is

A Brazilian accounting/finance master's thesis (see `docs/pre-projeto.docx`): does year-over-year textual change in the "empréstimos, financiamentos e debêntures" (loans/financing/debentures) note of Brazilian companies' annual financial statements predict future abnormal stock returns (H1/H1a) and analyst EPS forecast revisions (H2)? Measured via TF-IDF + cosine similarity between consecutive fiscal years' note text, following Cohen/Malloy/Nguyen ("Lazy Prices") and Brown & Tucker.

The user is doing the actual academic work; this repo is the data/code side. Thesis-facing content (README, TODO, pre-projeto) is in Portuguese to match; code, comments, and commit messages are in English.

## Status (see README.md "Status" section for the checklist)

- **Acquisition part 1: done.** 993 company-fiscal-year debt-note PDFs, 2015–2024, for 111 non-financial companies — the 66 *current* Ibovespa constituents plus 45 more found via a historical-IBOV reconstruction (`src/acquisition/b3_ibov_historical.py`) to fix survivorship bias. Includes Americanas S.A. (added in a second, corrective Bloomberg pass — see that file's docstring point 3 for a real process gap worth reading before trusting a "we checked X" claim at face value). All present locally on disk; **not tracked in git** (see Data/git conventions below — this was tried via git-lfs and reversed).
- **POC: done, five rounds**, all in `notebooks/poc_overview.ipynb` + `reports/poc_note_extraction_findings.md`:
  1. Does the TF-IDF idea hold up at all? Yes, where extraction is reliable.
  2. Hardened the note-extraction heuristic (4 real bugs fixed) — reliable-cohort mean similarity 0.75 → 0.87, on a hand-picked 20-company subset.
  3. Extended to 36 of the 45-46 historical-IBOV companies known at the time: dropped-from-IBOV/delisted companies show more textual change than companies that stayed, but the effect weakens under a stricter robustness check (p=0.0028 → p=0.068) on that subset.
  4. **Scaled rounds 2-3 to the full universe** (all 66 current IBOV companies + all 46 historical/delisted, 993 company-years total, no more hand-picked subsets): `run_poc_tfidf.py`'s `POC_COMPANIES` now loads all 66 current companies from `data/interim/ibov_non_financial_universe.csv` instead of a hardcoded 20; `run_delisted_analysis.py` picks this up automatically. Extraction reliability holds up at scale (44% `font_heading`, same as the round-2 subset) — but the survivorship-bias signal from round 3 **weakens further and loses significance** at full scale (p=0.178 raw, p=0.106 size-consistent), because part of round 3's result reflected which companies got hand-picked, not just extraction noise as previously assumed. Also fixed a ticker-resolution diagnostic bug in `src/analysis/compute_abnormal_returns.py` found during this pass (was reporting an impossible count) and re-ran it: 676 pairs now have a computable abnormal return (up from 297), correlation still weak (r ≈ -0.09 to -0.12).
  5. **Hardened annual extraction itself** (`src/processing/locate_note_section.py`), directly answering round 4's "extraction is the top priority" finding: four targeted fixes (PDF bookmarks; same-size bold headings with caps/numbering; non-bold caps+numbered headings; "debênture" alone as a qualifying keyword), each found by inspecting real failing PDFs and validated against known-good controls. Pushed full-universe `font_heading` from 44% → **65%** (997 filings); resolved 22 companies that previously had a 0% reliable rate down to 5. Two more ideas (table-of-contents detection, "Nota N" cross-reference following) were empirically checked and explicitly rejected — low yield (1.4%) for the former, unacceptable false-positive rate (only 26% of matches resolve correctly) for the latter. Propagated through the whole pipeline: survivorship-bias result unchanged in substance (p=0.24 raw / p=0.14 size-consistent, still directionally consistent, still not significant, now on a much larger reliable sample — a useful confirmation that round 4's result wasn't just extraction noise), H1 checkpoint correlations still trivial (r ≈ -0.03 to -0.08). New iteration harness for this work: `src/processing/eval_note_locator.py` (caches raw PDF lines once, reruns just the heuristic on each change — full-corpus eval in seconds instead of re-parsing 997 PDFs every time). Full detail in `reports/poc_note_extraction_findings.md` §9. **Not yet propagated to the quarterly (ITR) pilot** (§8) — pending the full historical quarterly download finishing.
- **Not started:** acquisition part 2 (rest of the non-financial B3 universe, ~756 more companies — see `src/acquisition/cvm_dfp.py build_company_universe` with no `cd_cvm_filter`), fundamentals/control-variable data, analyst-consensus data, the real (full-universe, controlled) regressions.
- **Market data: received and verified.** `data/raw/market/prices/stock_prices_bloomberg.csv` (153 tickers, daily `PX_LAST`, 2014–2026) + `ibov_index_bloomberg.csv` (Ibovespa daily level, same period) — all 66 current-universe tickers covered; 9 tickers are stale pre-rename duplicates that resolve `#N/A` (e.g. EMBR3→EMBJ3, MRFG3→MBRF3, CCRO3→MOTV3) but the current-name column has full data, so use the current B3 ticker per company when mapping to CD_CVM. Of the ~45 historical/delisted companies, ~40 resolve to a current tradeable ticker (via B3's live registry); the rest (Souza Cruz, MMX, Fibria, etc.) are genuinely gone from the market (went private/merged/bankrupt) — a real gap, not a data bug. See `TODO.md` for full notes.
- **First H1 checkpoint: done, pipeline runs end-to-end over the full universe, no signal yet (expected).** `src/acquisition/build_filing_dates.py` builds `data/interim/dfp_filing_dates.csv` (993 rows — the actual CVM disclosure date per filing, `DT_RECEB`, which existing acquisition code had silently discarded). `src/analysis/compute_abnormal_returns.py` uses that to compute a market-adjusted (stock minus Ibovespa buy-and-hold, no beta) 12-month abnormal return per company-year and correlates it against POC note similarity — see `poc_overview.ipynb` §7. 676 pairs computable (up from 297 pre-round-4); correlation is still weak (r ≈ -0.09 to -0.12), the expected result without controls, not a finding against H1a; this only proves the pipeline is wired correctly end to end.
- **Outstanding asks of the user:** see `TODO.md` — fundamentals/control variables and analyst consensus (both Bloomberg).
- **Natural next step:** either keep chasing the shrinking, increasingly per-company-specific tail of extraction failures (5 companies still at 0% reliable, diminishing returns per fix now), propagate round 5's hardening to the quarterly pilot once its download finishes, or get fundamentals/control variables from the user so §7's abnormal-return checkpoint can become a real, controlled test. All legitimate; ask the user which they'd rather prioritize rather than assuming.

## Repo map

```
src/acquisition/   CVM + B3 data acquisition (see .claude/skills/cvm-debt-notes/SKILL.md for the full playbook)
src/processing/    PDF text extraction, note-section isolation, TF-IDF POC scripts
src/analysis/      compute_abnormal_returns.py (POC-scale H1 checkpoint); full regressions/hypothesis tests still to come
src/features/      empty — where control-variable construction will go
data/raw/dfp/      acquired debt-note PDFs, one folder per CD_CVM/fiscal year (gitignored, local-only -- see below)
data/raw/dfp/_cache/  raw CVM filing zips -- gitignored, 8.6GB+ locally, freely re-derivable, never needs backing up
data/raw/market/   Bloomberg-derived data (gitignored — see licensing note below)
data/interim/      manifest/log CSVs (tracked) + data/interim/poc/ (POC intermediates + results, tracked)
data/interim/dfp_filing_dates.csv   real CVM disclosure date per acquired filing (event date for return calcs)
data/interim/poc/abnormal_returns_poc.csv   POC-scale market-adjusted abnormal return per similarity pair
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

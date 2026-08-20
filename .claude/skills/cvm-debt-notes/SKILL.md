---
name: cvm-debt-notes
description: Download debt-note ("empréstimos, financiamentos e debêntures") PDFs from CVM's DFP filings for Brazilian non-financial B3 companies. Use when acquiring more companies or years for the thesis corpus, retrying failed downloads, extending past the current IBOV-only sample, or debugging the CVM acquisition pipeline (rate limiting, legacy filing formats, malformed responses).
---

# CVM debt-notes acquisition

Pulls the "notas explicativas de empréstimos, financiamentos e debêntures" out of
companies' annual DFP filings on CVM's open-data portal, for the thesis corpus
(see `README.md` for the research question). The pipeline already exists in
`src/acquisition/` — this skill is about how to *run* and *extend* it, plus the
non-obvious things that broke in practice so you don't rediscover them.

## What's already built

- `src/acquisition/cvm_dfp.py` — `build_company_universe(years, cache_dir,
  cd_cvm_filter=None)`: resolves CVM's open-data indexes into one row per
  non-financial company per fiscal year (excludes banks/insurers/leasing/
  securitization by sector keyword). `cd_cvm_filter` restricts to a specific
  set of CD_CVM codes.
- `src/acquisition/b3_ibov.py` — `build_ibov_non_financial_universe(cache_dir)`:
  resolves the *current* Ibovespa composition (via B3's public
  GetPortfolioDay/GetInitialCompanies endpoints) to CD_CVM codes, filtered to
  non-financial. This is how "part 1" (already done) was scoped.
- `src/acquisition/cvm_notes.py` — `save_company_year_notes(cd_cvm, ano,
  id_doc, cache_dir, out_root)`: downloads one company-year's filing package
  and extracts the PDF attachment(s) most likely to contain the debt note
  (tiered filename matching, see docstring in that file for the strategy and
  why it's tiered).
- `src/acquisition/run_ibov.py` — the part-1 driver script, already run to
  completion (613/613 non-financial IBOV constituents, 2015–2024).
- `src/utils/http.py` — `get_bytes(...)`: shared download helper with
  on-disk caching, retries with exponential backoff, and optional request
  pacing (`min_interval`/`pace_key`) to avoid CVM's rate limiting.

Output lands at `data/raw/dfp/<CD_CVM>/<ANO>/notas_explicativas.pdf` (+
`attachment_meta.json` recording which attachment was picked and why). The
raw filing zips CVM serves are cached at `data/raw/dfp/_cache/` — that
cache is git-ignored (multi-GB, trivially re-fetchable from CVM any time);
the extracted PDFs are tracked via **git-lfs** (see `.gitattributes`) so
they survive beyond this machine.

## Running it for a new batch (e.g. part 2: the rest of the B3 universe)

Don't reuse `run_ibov.py` as-is — write a small new driver script following
its exact shape, swapping the universe source. Minimal pattern:

```python
from pathlib import Path
import pandas as pd
from src.acquisition.cvm_dfp import build_company_universe
from src.acquisition.cvm_notes import save_company_year_notes

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
YEARS = list(range(2015, 2025))

# No cd_cvm_filter => full non-financial universe. Pass a set of CD_CVM ints
# to restrict (e.g. `set(ibov_universe["CD_CVM"]) ^ full_set` to get
# "everything except IBOV" and avoid re-downloading part 1).
universe = build_company_universe(YEARS, CACHE_DIR)

log_rows = []
for i, (_, row) in enumerate(universe.iterrows(), start=1):
    try:
        result = save_company_year_notes(row["CD_CVM"], row["ANO"], row["ID_DOC"], CACHE_DIR, OUT_ROOT)
    except Exception as exc:
        result = {"CD_CVM": row["CD_CVM"], "ANO": row["ANO"], "ID_DOC": row["ID_DOC"], "n_attachments_matched": 0, "match_tier": None, "files": [], "error": str(exc)}
    result["DENOM_CIA"] = row["DENOM_CIA"]
    log_rows.append(result)
    print(f"[{i}/{len(universe)}] {row['DENOM_CIA']} ({row['ANO']}) -> {'ERROR' if result.get('error') else ('OK' if result['n_attachments_matched'] else 'NO MATCH')}")

pd.DataFrame(log_rows).to_csv("data/interim/<batch_name>_notes_download_log.csv", index=False)
```

Save the driver as `src/acquisition/run_<batch_name>.py` so it's reusable and
diffable, not a one-off shell snippet.

**Always launch full-universe runs with unbuffered output and in the
background**: `python -u -m src.acquisition.run_<batch_name>`. Without `-u`,
stdout buffers for many minutes when redirected to a file — a long silent
gap looks like a hang but usually isn't (see Gotchas). Check progress with
`grep -c " -> OK$"` / `ERROR$` / `NO MATCH$"` on the output file rather than
assuming silence means trouble.

**Resuming is cheap and safe.** `download_filing_zip` checks the on-disk
cache before hitting the network, and `save_company_year_notes` always
re-derives its output from the (possibly cached) zip. Just rerun the same
driver — already-fetched company-years fly through from cache; only new
ones actually hit the network. No need to track "where it left off"
manually.

## Retrying a single failed item

Look up its CD_CVM/ANO/ID_DOC from the batch's log CSV (`data/interim/*_notes_download_log.csv`,
rows where `error` is non-null), then:

```python
from pathlib import Path
from src.acquisition.cvm_notes import save_company_year_notes
result = save_company_year_notes(cd_cvm, ano, id_doc, Path("data/raw/dfp/_cache"), Path("data/raw/dfp"))
```

This does **not** update the log CSV (that only happens at the end of a full
driver run) — patch the corresponding row's `n_attachments_matched`/
`match_tier`/`error` columns by hand afterward if you want the log to stay
accurate, or just rerun the full driver (cheap, see above).

## Validating a batch

A successful download doesn't guarantee the right content was extracted
(tiered filename matching can pick the wrong attachment for an unusual
filer). Spot-check with:

```python
import glob, re, warnings
import fitz  # pymupdf
warnings.filterwarnings("ignore")

for path in glob.glob("data/raw/dfp/*/*/notas_explicativas*.pdf"):
    doc = fitz.open(path)
    full = "".join(p.get_text() for p in doc)
    hit = bool(re.search(r"(?i)financiamentos|empr[eé]stimos|deb[eê]ntures", full))
    if not hit:
        print("MISSING?", path, "pages=", len(doc), "chars=", len(full))
```

An empty `full` (0 chars) despite the PDF opening fine means it's a
scanned/image-only document (happened once, Vibra Energia 2023) — it's
still the correct source file, just needs OCR at the text-processing stage,
not a re-download.

## Gotchas already paid for (don't re-debug these)

- **Pre-~2021 filings use a completely different package format.** Modern
  filings have one top-level XML (`XmlDemonstracoesFinanceiras`) with
  attachments inline. Legacy ones bury a `.dfp` file that is *itself* a
  nested ZIP containing `AnexoDocumento.xml`, with opaque internal temp-path
  attachment names (no descriptive filename to match against — falls back
  to largest-attachment). Already handled in `cvm_notes.list_attachments`;
  don't assume a "download failure" on old years is rate limiting.
- **numpy.int64 isn't JSON-serializable.** Pandas row values (e.g. `ANO`)
  passed into `save_company_year_notes` are normalized to plain `str`/`int`
  internally — if you write a new driver that constructs its own metadata
  dicts from DataFrame rows, do the same or `json.dumps` will raise.
- **CVM's RAD filing endpoint throttles under sustained rapid-fire
  requests.** `download_filing_zip` already paces requests (2s minimum
  gap) and retries with exponential backoff. If you see a cluster of
  `ERROR`s, first check whether it's genuinely rate limiting (retry a
  failed item standalone after a pause — if it succeeds instantly, it was
  throttling) before assuming something is broken.
- **A silent gap in the output log is not necessarily a hang.** Python
  buffers stdout in large chunks when it isn't a terminal. Always run with
  `python -u` for anything you'll monitor. If you forgot and progress looks
  stalled, check `data/raw/dfp/_cache/*.zip` mtimes before killing the
  process — new files landing there mean it's still working even if the
  log hasn't flushed.
- **Company sector filtering** (`cvm_dfp.is_financial_sector`) is
  keyword-based over CVM's free-text `SETOR_ATIV` field (excludes "banco",
  "seguradora", "corretora", "intermediação financeira", "arrendamento
  mercantil", "securitização", "crédito imobiliário", "bolsas de valores").
  If a new batch pulls in an unexpected financial-adjacent company, extend
  `FINANCIAL_SECTOR_KEYWORDS` rather than hand-filtering the universe.

## Committing new data

The extracted PDFs are tracked via git-lfs (`.gitattributes` already
configures `data/raw/dfp/**/*.pdf`). After a batch completes:

```bash
git add data/raw/dfp/<new company folders> data/interim/<batch>_notes_download_log.csv
git commit -m "..."
```

Check `git lfs status` before committing to confirm new PDFs are routed
through LFS, not committed as regular (huge) git blobs. Don't `git push`
without checking with the user first — GitHub's free LFS quota is 1GB/month
and this corpus is already well past that; whether/when to push is a
standing decision, not a default action.

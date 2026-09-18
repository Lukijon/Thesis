"""Round 7 of note-extraction hardening (2026-09): re-runs attachment
selection for every filing that used the risky `largest_attachment_fallback`
tier, now that `select_source_attachments` content-filters that tier against
Relatorio da Administracao / earnings-release boilerplate (see
cvm_notes.looks_like_management_report_text's docstring for how this was
found -- a corpus-wide scan after expanding to 185 companies turned up 202
filings, ~10% of the whole corpus, where the wrong document had been picked
for years, including long-known low-reliability companies like Braskem).

Uses only already-cached filing zips (force=False) -- no new downloads, this
is a pure re-selection pass over data already on disk. Overwrites
notas_explicativas.pdf + attachment_meta.json in place for any filing whose
pick changes; leaves it untouched (same bytes rewritten) if the fix agrees
with the original pick.

Usage:
    python -u -m src.acquisition.rerun_fallback_selection
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd

from src.acquisition.cvm_notes import save_company_year_notes

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp")
LOG_PATH = Path("data/interim/fallback_rerun_log.csv")


def find_targets() -> list[tuple[str, int, str]]:
    """(cd_cvm, ano, id_doc) for every filing whose current metadata shows
    the risky fallback tier."""
    targets = []
    for meta_path in glob.glob(str(OUT_ROOT / "*" / "*" / "attachment_meta.json")):
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        if meta.get("match_tier") == "largest_attachment_fallback":
            targets.append((meta["CD_CVM"], meta["ANO"], meta["ID_DOC"]))
    return targets


def main() -> None:
    targets = find_targets()
    print(f"{len(targets)} filings to re-select (previously largest_attachment_fallback)")

    rows = []
    for i, (cd_cvm, ano, id_doc) in enumerate(targets, start=1):
        try:
            result = save_company_year_notes(cd_cvm, ano, id_doc, CACHE_DIR, OUT_ROOT, force=False)
            new_tier = result["match_tier"]
        except Exception as exc:  # noqa: BLE001 - log and continue
            new_tier = f"ERROR: {exc}"
        rows.append({"CD_CVM": cd_cvm, "ANO": ano, "ID_DOC": id_doc, "new_tier": new_tier})
        if i % 200 == 0 or i == len(targets):
            print(f"  [{i}/{len(targets)}]")

    log_df = pd.DataFrame(rows)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_df.to_csv(LOG_PATH, index=False)

    print("\nOutcome breakdown:")
    print(log_df["new_tier"].value_counts())
    n_changed = (log_df["new_tier"] == "largest_attachment_fallback_content_filtered").sum()
    n_all_flagged = (log_df["new_tier"] == "largest_attachment_fallback_all_flagged").sum()
    print(f"\n{n_changed} filings had their attachment pick changed by the content filter.")
    print(f"{n_all_flagged} filings had every candidate flagged as wrong-content (kept the largest anyway).")
    print(f"\nLog: {LOG_PATH}")


if __name__ == "__main__":
    main()

"""Reconcile Cox 2014 (source_id 740435e0-2577-4691-baa4-77cc09e904e9)
across notebook_covariate files so they match SCREENING_LOG_FINAL.csv
(exclude_review, not_for_extraction).
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COX_SID = "740435e0-2577-4691-baa4-77cc09e904e9"

PRIMARY = ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv"
ALL_SOURCES = ROOT / "notebook_covariates" / "notebook_covariates_all_sources_geoaugmented.csv"
MISSINGNESS = ROOT / "notebook_covariates" / "notebook_covariate_missingness_primary_geoaugmented.csv"
REMAINING = ROOT / "notebook_covariates" / "notebook_covariate_remaining_queue_primary_geoaugmented.csv"


def drop_row_by_sid(path: Path) -> int:
    rows = list(csv.DictReader(path.open(newline="")))
    fields = list(rows[0].keys()) if rows else []
    kept = [r for r in rows if r.get("source_id") != COX_SID]
    dropped = len(rows) - len(kept)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(kept)
    return dropped


def patch_final_status(path: Path) -> int:
    rows = list(csv.DictReader(path.open(newline="")))
    fields = list(rows[0].keys()) if rows else []
    patched = 0
    for r in rows:
        if r.get("source_id") == COX_SID:
            if r.get("final_status") != "exclude_review":
                r["final_status"] = "exclude_review"
                r["extraction_readiness"] = "not_for_extraction"
                patched += 1
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return patched


def main() -> None:
    drops_primary = drop_row_by_sid(PRIMARY)
    drops_miss = drop_row_by_sid(MISSINGNESS)
    drops_remain = drop_row_by_sid(REMAINING)
    patches_all = patch_final_status(ALL_SOURCES)
    print(f"Dropped Cox 2014 from {PRIMARY.name}: {drops_primary}")
    print(f"Dropped Cox 2014 from {MISSINGNESS.name}: {drops_miss}")
    print(f"Dropped Cox 2014 from {REMAINING.name}: {drops_remain}")
    print(f"Patched final_status in {ALL_SOURCES.name}: {patches_all}")


if __name__ == "__main__":
    main()

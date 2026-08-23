#!/usr/bin/env python3
"""Build a genus-level coral taxonomy lookup from WoRMS.

This script intentionally handles taxonomy only. Trait values such as skeletal
porosity can be added to the lookup with their own provenance and will be
preserved on refresh.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_COVARIATES = ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv"
LOOKUP = ROOT / "notebook_covariates" / "taxon_trait_lookup.csv"
SUMMARY = ROOT / "notebook_covariates" / "TAXON_TRAIT_LOOKUP_SUMMARY.md"
WORMS_BASE = "https://www.marinespecies.org/rest/AphiaRecordsByName"

FIELDS = [
    "genus_raw",
    "genus",
    "worms_aphia_id",
    "worms_status",
    "worms_valid_name",
    "worms_valid_aphia_id",
    "family",
    "order",
    "class",
    "phylum",
    "taxonomy_source",
    "taxonomy_lookup_status",
    "skeletal_porosity",
    "skeletal_porosity_source",
    "skeletal_porosity_status",
    "notes",
]

PRESERVE_FIELDS = [
    "skeletal_porosity",
    "skeletal_porosity_source",
    "skeletal_porosity_status",
    "notes",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def relpath(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def extract_genera(rows: list[dict[str, str]]) -> list[str]:
    genera: set[str] = set()
    for row in rows:
        text = clean(row.get("species", ""))
        for part in re.split(r",|;|\band\b|/|\(|\)", text):
            match = re.match(r"\s*([A-Z][A-Za-z-]+)\b", part.strip())
            if match:
                genera.add(match.group(1))
    return sorted(genera)


def worms_records_by_name(name: str, timeout: int) -> list[dict[str, object]]:
    url = f"{WORMS_BASE}/{urllib.parse.quote(name)}?like=false&marine_only=true"
    request = urllib.request.Request(url, headers={"User-Agent": "coral-regeneration-meta-analysis/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, list) else []


def select_coral_record(records: list[dict[str, object]]) -> dict[str, object] | None:
    genus_records = [record for record in records if clean(record.get("rank", "")).lower() == "genus"]
    candidates = genus_records or records

    def score(record: dict[str, object]) -> tuple[int, int, int, int]:
        order = clean(record.get("order", "")).lower()
        class_name = clean(record.get("class", "")).lower()
        phylum = clean(record.get("phylum", "")).lower()
        status = clean(record.get("status", "")).lower()
        return (
            1 if order == "scleractinia" else 0,
            1 if class_name == "hexacorallia" else 0,
            1 if phylum == "cnidaria" else 0,
            1 if status == "accepted" else 0,
        )

    if not candidates:
        return None
    return max(candidates, key=score)


def build_lookup_rows(
    genera: list[str],
    existing_rows: list[dict[str, str]],
    timeout: int,
    pause_seconds: float,
) -> list[dict[str, str]]:
    existing_by_raw = {clean(row.get("genus_raw", "")): row for row in existing_rows}
    rows: list[dict[str, str]] = []
    for genus in genera:
        preserved = existing_by_raw.get(genus, {})
        out = {field: "" for field in FIELDS}
        out["genus_raw"] = genus
        try:
            record = select_coral_record(worms_records_by_name(genus, timeout=timeout))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            out["taxonomy_lookup_status"] = "worms_query_failed"
            out["notes"] = f"WoRMS query failed: {exc}"
            record = None
        if record:
            out.update(
                {
                    "genus": clean(record.get("valid_name", "")) or clean(record.get("scientificname", "")),
                    "worms_aphia_id": clean(record.get("AphiaID", "")),
                    "worms_status": clean(record.get("status", "")),
                    "worms_valid_name": clean(record.get("valid_name", "")),
                    "worms_valid_aphia_id": clean(record.get("valid_AphiaID", "")),
                    "family": clean(record.get("family", "")),
                    "order": clean(record.get("order", "")),
                    "class": clean(record.get("class", "")),
                    "phylum": clean(record.get("phylum", "")),
                    "taxonomy_source": f"{WORMS_BASE}/{urllib.parse.quote(genus)}?like=false&marine_only=true",
                    "taxonomy_lookup_status": "worms_scleractinia_match"
                    if clean(record.get("order", "")).lower() == "scleractinia"
                    else "worms_non_scleractinia_match_review",
                }
            )
        else:
            out["genus"] = genus
            out["taxonomy_lookup_status"] = out["taxonomy_lookup_status"] or "worms_no_match"
        for field in PRESERVE_FIELDS:
            if clean(preserved.get(field, "")):
                out[field] = preserved[field]
        if not clean(out.get("skeletal_porosity_status", "")):
            out["skeletal_porosity_status"] = "not_in_taxon_lookup"
        rows.append(out)
        if pause_seconds > 0:
            time.sleep(pause_seconds)
    return rows


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    matched = sum(1 for row in rows if row.get("taxonomy_lookup_status") == "worms_scleractinia_match")
    family = sum(1 for row in rows if clean(row.get("family", "")))
    porosity = sum(1 for row in rows if clean(row.get("skeletal_porosity", "")))
    lines = [
        "# Taxon Trait Lookup Summary",
        "",
        "Generated by `python3 tools/build_taxon_trait_lookup.py`.",
        "",
        "## Current Result",
        "",
        f"- genus rows: {len(rows)}",
        f"- WoRMS Scleractinia matches: {matched}",
        f"- rows with family: {family}",
        f"- rows with skeletal porosity: {porosity}",
        "",
        "## Files",
        "",
        f"- `{relpath(LOOKUP)}`",
        "",
        "## Notes",
        "",
        "- Taxonomy is queried from the WoRMS Aphia REST API and filtered to coral-like records before selecting a match.",
        "- Skeletal porosity is not supplied by WoRMS. Any values in those columns must come from a separate trait source and are preserved during refresh.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covariates", type=Path, default=PRIMARY_COVARIATES)
    parser.add_argument("--lookup", type=Path, default=LOOKUP)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--pause-seconds", type=float, default=0.2)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    genera = extract_genera(read_csv(args.covariates))
    rows = build_lookup_rows(genera, read_csv(args.lookup), timeout=args.timeout, pause_seconds=args.pause_seconds)
    write_csv(args.lookup, rows)
    write_summary(args.summary, rows)
    print(f"Wrote {relpath(args.lookup)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

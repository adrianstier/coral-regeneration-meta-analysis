#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


APPROX_FIELDS = [
    "latitude_approx",
    "longitude_approx",
    "approx_coordinate_basis",
    "approx_coordinate_confidence",
    "approx_location_notes",
]

EXACT_REPAIR_FIELDS = [
    "depth_min_m",
    "depth_max_m",
    "growth_form",
    "tissue_type",
    "area_mm2",
    "temperature_c",
    "sample_size",
]


def normalize(value: str | None) -> str:
    return (value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_note(row: dict[str, str], field: str, tag: str) -> None:
    note = normalize(row.get(field))
    if tag not in note:
        row[field] = f"{note} {tag}".strip()


def worker_confirms_exact_coords(repair: dict[str, str]) -> bool:
    note = normalize(repair.get("approx_location_notes")).lower()
    return (
        "exact coordinates reported in source" in note
        or "exact coordinates were reported in the source" in note
        or "exact coordinates already exist in the source/current manifest" in note
        or "exact coordinates are reported in the paper" in note
    )


def ensure_location_fields(row: dict[str, str]) -> None:
    for field in [
        "latitude_approx",
        "longitude_approx",
        "approx_coordinate_basis",
        "approx_coordinate_confidence",
        "approx_location_notes",
        "latitude_best",
        "longitude_best",
        "best_coordinate_basis",
        "best_coordinate_confidence",
        "location_row_id",
    ]:
        row.setdefault(field, "")


def ensure_cov_fields(row: dict[str, str]) -> None:
    for field in [
        "latitude_approx",
        "longitude_approx",
        "approx_coordinate_basis",
        "approx_coordinate_confidence",
        "approx_location_notes",
        "latitude_best",
        "longitude_best",
        "best_coordinate_basis",
        "best_coordinate_confidence",
    ]:
        row.setdefault(field, "")


def reconcile_exact_vs_approx(row: dict[str, str]) -> None:
    exact_lat = normalize(row.get("latitude"))
    exact_lon = normalize(row.get("longitude"))
    exact_basis = normalize(row.get("coordinate_basis"))
    approx_lat = normalize(row.get("latitude_approx"))
    approx_lon = normalize(row.get("longitude_approx"))

    if exact_lat and exact_lon and exact_basis != "reported_exact":
        if not approx_lat and not approx_lon:
            row["latitude_approx"] = exact_lat
            row["longitude_approx"] = exact_lon
            row["approx_coordinate_basis"] = exact_basis or "inferred_from_locality"
            row["approx_coordinate_confidence"] = normalize(row.get("coordinate_confidence")) or "low"
            append_note(row, "approx_location_notes", "[migrated from mixed non-exact coordinate columns]")
        row["latitude"] = ""
        row["longitude"] = ""

    exact_lat = normalize(row.get("latitude"))
    exact_lon = normalize(row.get("longitude"))
    approx_lat = normalize(row.get("latitude_approx"))
    approx_lon = normalize(row.get("longitude_approx"))

    if exact_lat and exact_lon:
        row["latitude_best"] = exact_lat
        row["longitude_best"] = exact_lon
        row["best_coordinate_basis"] = "reported_exact"
        row["best_coordinate_confidence"] = "high"
    elif approx_lat and approx_lon:
        row["latitude_best"] = approx_lat
        row["longitude_best"] = approx_lon
        row["best_coordinate_basis"] = normalize(row.get("approx_coordinate_basis"))
        row["best_coordinate_confidence"] = normalize(row.get("approx_coordinate_confidence"))
    else:
        row["latitude_best"] = ""
        row["longitude_best"] = ""
        row["best_coordinate_basis"] = ""
        row["best_coordinate_confidence"] = ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-csv", required=True)
    parser.add_argument("--primary-csv", required=True)
    parser.add_argument("--all-sources-csv", required=True)
    parser.add_argument("--queue-csv", required=True)
    parser.add_argument("--agent-csvs", nargs="+", required=True)
    parser.add_argument("--output-location", required=True)
    parser.add_argument("--output-primary", required=True)
    parser.add_argument("--output-all-sources", required=True)
    parser.add_argument("--output-audit", required=True)
    args = parser.parse_args()

    location_rows = read_csv(Path(args.location_csv))
    primary_rows = read_csv(Path(args.primary_csv))
    all_rows = read_csv(Path(args.all_sources_csv))
    queue_rows = read_csv(Path(args.queue_csv))
    queue_by_id = {row["location_row_id"]: row for row in queue_rows}

    repairs: dict[str, dict[str, str]] = {}
    for csv_path in args.agent_csvs:
        for row in read_csv(Path(csv_path)):
            repairs[row["location_row_id"]] = row

    location_audit: list[dict[str, str]] = []

    for idx, row in enumerate(location_rows, start=1):
        ensure_location_fields(row)
        row_id = f"loc_{idx:03d}"
        row["location_row_id"] = row_id
        repair = repairs.get(row_id)
        if repair:
            if worker_confirms_exact_coords(repair) and normalize(row.get("latitude")) and normalize(row.get("longitude")):
                row["coordinate_basis"] = "reported_exact"
                row["coordinate_confidence"] = "high"
                append_note(row, "location_notes", "[worker confirmed existing coordinates are exact]")
            changed_fields: list[str] = []
            for field in APPROX_FIELDS:
                incoming = normalize(repair.get(field))
                if incoming and not normalize(row.get(field)):
                    row[field] = incoming
                    changed_fields.append(field)
            if normalize(repair.get("approx_location_notes")):
                append_note(row, "approx_location_notes", normalize(repair["approx_location_notes"]))
            if changed_fields:
                location_audit.append(
                    {
                        "location_row_id": row_id,
                        "source_id": row.get("source_id", ""),
                        "paper_title": row.get("paper_title", ""),
                        "changed_location_fields": "; ".join(changed_fields),
                        "approx_basis": normalize(row.get("approx_coordinate_basis")),
                        "approx_confidence": normalize(row.get("approx_coordinate_confidence")),
                    }
                )
        reconcile_exact_vs_approx(row)

    location_by_source: dict[str, list[dict[str, str]]] = {}
    for row in location_rows:
        location_by_source.setdefault(row["source_id"], []).append(row)

    for rows in (primary_rows, all_rows):
        for row in rows:
            ensure_cov_fields(row)
            locs = location_by_source.get(row["source_id"], [])
            exact = next((loc for loc in locs if normalize(loc.get("latitude")) and normalize(loc.get("longitude"))), None)
            approx = next((loc for loc in locs if normalize(loc.get("latitude_approx")) and normalize(loc.get("longitude_approx"))), None)
            chosen = exact or approx
            if chosen:
                row["latitude_approx"] = normalize(chosen.get("latitude_approx"))
                row["longitude_approx"] = normalize(chosen.get("longitude_approx"))
                row["approx_coordinate_basis"] = normalize(chosen.get("approx_coordinate_basis"))
                row["approx_coordinate_confidence"] = normalize(chosen.get("approx_coordinate_confidence"))
                row["approx_location_notes"] = normalize(chosen.get("approx_location_notes"))
                row["latitude_best"] = normalize(chosen.get("latitude_best"))
                row["longitude_best"] = normalize(chosen.get("longitude_best"))
                row["best_coordinate_basis"] = normalize(chosen.get("best_coordinate_basis"))
                row["best_coordinate_confidence"] = normalize(chosen.get("best_coordinate_confidence"))

    primary_by_source = {row["source_id"]: row for row in primary_rows}
    for repair in repairs.values():
        source_id = repair.get("source_id", "")
        prow = primary_by_source.get(source_id)
        if not prow:
            continue
        for field in EXACT_REPAIR_FIELDS:
            if not normalize(prow.get(field)) and normalize(repair.get(field)):
                prow[field] = repair[field]
                append_note(prow, "notes", f"[approx georef pass exact repair: {field}]")

    primary_by_source = {row["source_id"]: row for row in primary_rows}
    for row in all_rows:
        replacement = primary_by_source.get(row["source_id"])
        if replacement:
            for field in EXACT_REPAIR_FIELDS + [
                "latitude_approx",
                "longitude_approx",
                "approx_coordinate_basis",
                "approx_coordinate_confidence",
                "approx_location_notes",
                "latitude_best",
                "longitude_best",
                "best_coordinate_basis",
                "best_coordinate_confidence",
            ]:
                row[field] = replacement.get(field, row.get(field, ""))

    write_csv(Path(args.output_location), location_rows, list(location_rows[0].keys()))
    write_csv(Path(args.output_primary), primary_rows, list(primary_rows[0].keys()))
    write_csv(Path(args.output_all_sources), all_rows, list(all_rows[0].keys()))
    write_csv(
        Path(args.output_audit),
        location_audit,
        ["location_row_id", "source_id", "paper_title", "changed_location_fields", "approx_basis", "approx_confidence"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

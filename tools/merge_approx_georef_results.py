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

LOCATION_EXTRA_FIELDS = [
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
]

COV_EXTRA_FIELDS = [
    "latitude_approx",
    "longitude_approx",
    "approx_coordinate_basis",
    "approx_coordinate_confidence",
    "approx_location_notes",
    "latitude_best",
    "longitude_best",
    "best_coordinate_basis",
    "best_coordinate_confidence",
    "location_count",
    "location_merge_status",
]

LOCATION_AUDIT_FIELDS = [
    "location_row_id",
    "source_id",
    "paper_title",
    "changed_location_fields",
    "approx_basis",
    "approx_confidence",
]

QUEUE_VALIDATION_FIELDS = [
    ("source_id", ("source_id",), "source_id"),
    ("location_raw", ("location_raw",), "location_raw"),
    ("site_name", ("site_name",), "site_name"),
    ("country_territory", ("country_territory",), "country_territory"),
    ("water_body", ("water_body",), "water_body"),
    ("current_latitude", ("current_latitude", "latitude"), "current_latitude"),
    ("current_longitude", ("current_longitude", "longitude"), "current_longitude"),
    ("current_coordinate_basis", ("current_coordinate_basis", "coordinate_basis"), "current_coordinate_basis"),
    (
        "current_coordinate_confidence",
        ("current_coordinate_confidence", "coordinate_confidence"),
        "current_coordinate_confidence",
    ),
]


def normalize(value: str | None) -> str:
    return (value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    return read_csv_with_fieldnames(path)[0]


def read_csv_with_fieldnames(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def merge_fieldnames(fieldnames: list[str], rows: list[dict[str, str]], extras: list[str] | None = None) -> list[str]:
    merged = list(fieldnames)
    for field in extras or []:
        if field not in merged:
            merged.append(field)
    for row in rows:
        for field in row:
            if field not in merged:
                merged.append(field)
    return merged


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
    for field in LOCATION_EXTRA_FIELDS:
        row.setdefault(field, "")


def ensure_cov_fields(row: dict[str, str]) -> None:
    for field in COV_EXTRA_FIELDS:
        row.setdefault(field, "")


def reconcile_exact_vs_approx(row: dict[str, str]) -> None:
    exact_lat = normalize(row.get("latitude"))
    exact_lon = normalize(row.get("longitude"))
    exact_basis = normalize(row.get("coordinate_basis"))
    approx_lat = normalize(row.get("latitude_approx"))
    approx_lon = normalize(row.get("longitude_approx"))

    if exact_lat and exact_lon and exact_basis != "reported_exact":
        if not (approx_lat and approx_lon):
            row["latitude_approx"] = exact_lat
            row["longitude_approx"] = exact_lon
            row["approx_coordinate_basis"] = exact_basis or "inferred_from_locality"
            row["approx_coordinate_confidence"] = normalize(row.get("coordinate_confidence")) or "low"
            if approx_lat or approx_lon:
                append_note(
                    row,
                    "approx_location_notes",
                    "[replaced partial approximate coordinate with migrated complete non-exact coordinate pair]",
                )
            else:
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


def validate_unique_ids(rows: list[dict[str, str]], field: str, label: str) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        row_id = normalize(row.get(field))
        if not row_id:
            raise ValueError(f"{label} contains a row without {field}")
        if row_id in by_id:
            raise ValueError(f"{label} contains duplicate {field}: {row_id}")
        by_id[row_id] = row
    return by_id


def first_available_value(row: dict[str, str], fields: tuple[str, ...]) -> str:
    for field in fields:
        if field in row:
            return normalize(row.get(field))
    return ""


def validate_against_queue(row_id: str, row: dict[str, str], queue_row: dict[str, str], label: str) -> None:
    mismatches: list[str] = []
    for label_field, row_fields, queue_field in QUEUE_VALIDATION_FIELDS:
        current = first_available_value(row, row_fields)
        queued = normalize(queue_row.get(queue_field))
        if current != queued:
            mismatches.append(f"{label_field}: current={current!r}, queued={queued!r}")
    if mismatches:
        raise ValueError(f"{label} does not match queue row {row_id}: " + "; ".join(mismatches))


def load_repairs(agent_csvs: list[str], queue_by_id: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    repairs: dict[str, dict[str, str]] = {}
    for csv_path in agent_csvs:
        for row in read_csv(Path(csv_path)):
            row_id = normalize(row.get("location_row_id"))
            if not row_id:
                raise ValueError(f"{csv_path} contains a repair row without location_row_id")
            if row_id in repairs:
                raise ValueError(f"Duplicate repair for {row_id} in {csv_path}")
            queue_row = queue_by_id.get(row_id)
            if queue_row is None:
                raise ValueError(f"{csv_path} contains repair {row_id}, which is not present in the queue CSV")
            validate_against_queue(row_id, row, queue_row, f"repair file {csv_path}")
            row["source_id"] = normalize(row.get("source_id"))
            repairs[row_id] = row
    return repairs


def location_pair(row: dict[str, str]) -> tuple[str, str, str, str] | None:
    lat = normalize(row.get("latitude_best")) or normalize(row.get("latitude_approx")) or normalize(row.get("latitude"))
    lon = normalize(row.get("longitude_best")) or normalize(row.get("longitude_approx")) or normalize(row.get("longitude"))
    if not (lat and lon):
        return None
    basis = (
        normalize(row.get("best_coordinate_basis"))
        or normalize(row.get("approx_coordinate_basis"))
        or normalize(row.get("coordinate_basis"))
    )
    confidence = (
        normalize(row.get("best_coordinate_confidence"))
        or normalize(row.get("approx_coordinate_confidence"))
        or normalize(row.get("coordinate_confidence"))
    )
    return lat, lon, basis, confidence


def choose_source_location(locs: list[dict[str, str]]) -> tuple[dict[str, str] | None, str]:
    candidates = [loc for loc in locs if location_pair(loc)]
    if not candidates:
        return None, "no_location_coordinates"
    unique_pairs = {location_pair(loc) for loc in candidates}
    if len(locs) == 1:
        return candidates[0], "single_location_propagated"
    if len(candidates) == len(locs) and len(unique_pairs) == 1:
        return candidates[0], "multiple_locations_same_coordinates_propagated"
    return None, "multiple_locations_not_collapsed"


def clear_cov_location_summary(row: dict[str, str]) -> None:
    for field in [
        "latitude_approx",
        "longitude_approx",
        "approx_coordinate_basis",
        "approx_coordinate_confidence",
        "latitude_best",
        "longitude_best",
        "best_coordinate_basis",
        "best_coordinate_confidence",
    ]:
        row[field] = ""


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

    location_rows, location_fieldnames = read_csv_with_fieldnames(Path(args.location_csv))
    primary_rows, primary_fieldnames = read_csv_with_fieldnames(Path(args.primary_csv))
    all_rows, all_fieldnames = read_csv_with_fieldnames(Path(args.all_sources_csv))
    queue_rows = read_csv(Path(args.queue_csv))
    queue_by_id = validate_unique_ids(queue_rows, "location_row_id", "queue CSV")

    repairs = load_repairs(args.agent_csvs, queue_by_id)

    location_audit: list[dict[str, str]] = []
    applied_repair_ids: set[str] = set()

    for idx, row in enumerate(location_rows, start=1):
        ensure_location_fields(row)
        row_id = f"loc_{idx:03d}"
        row["location_row_id"] = row_id
        queue_row = queue_by_id.get(row_id)
        if queue_row is not None:
            validate_against_queue(row_id, row, queue_row, "location CSV")
        repair = repairs.get(row_id)
        if repair:
            applied_repair_ids.add(row_id)
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

    missing_repair_ids = sorted(set(repairs) - applied_repair_ids)
    if missing_repair_ids:
        raise ValueError("Repair IDs were not found in the current location CSV: " + ", ".join(missing_repair_ids))

    location_by_source: dict[str, list[dict[str, str]]] = {}
    for row in location_rows:
        location_by_source.setdefault(normalize(row.get("source_id")), []).append(row)

    for rows in (primary_rows, all_rows):
        for row in rows:
            ensure_cov_fields(row)
            locs = location_by_source.get(normalize(row.get("source_id")), [])
            row["location_count"] = str(len(locs))
            chosen, merge_status = choose_source_location(locs)
            row["location_merge_status"] = merge_status
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
            else:
                clear_cov_location_summary(row)
                if merge_status == "multiple_locations_not_collapsed":
                    append_note(row, "approx_location_notes", "[multiple location rows; coordinates retained in location manifest only]")
                else:
                    append_note(row, "approx_location_notes", "[no location coordinates available in location manifest]")

    primary_by_source = {normalize(row.get("source_id")): row for row in primary_rows}
    for repair in repairs.values():
        source_id = normalize(repair.get("source_id"))
        prow = primary_by_source.get(source_id)
        if not prow:
            continue
        for field in EXACT_REPAIR_FIELDS:
            if not normalize(prow.get(field)) and normalize(repair.get(field)):
                prow[field] = repair[field]
                append_note(prow, "notes", f"[approx georef pass exact repair: {field}]")

    primary_by_source = {normalize(row.get("source_id")): row for row in primary_rows}
    for row in all_rows:
        replacement = primary_by_source.get(normalize(row.get("source_id")))
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
                "location_count",
                "location_merge_status",
            ]:
                row[field] = replacement.get(field, row.get(field, ""))

    write_csv(Path(args.output_location), location_rows, merge_fieldnames(location_fieldnames, location_rows, LOCATION_EXTRA_FIELDS))
    write_csv(Path(args.output_primary), primary_rows, merge_fieldnames(primary_fieldnames, primary_rows, COV_EXTRA_FIELDS))
    write_csv(Path(args.output_all_sources), all_rows, merge_fieldnames(all_fieldnames, all_rows, COV_EXTRA_FIELDS))
    write_csv(
        Path(args.output_audit),
        location_audit,
        LOCATION_AUDIT_FIELDS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

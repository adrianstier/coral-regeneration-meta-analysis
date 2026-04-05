#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


REPAIR_FIELDS = [
    "location_raw",
    "latitude_raw",
    "longitude_raw",
    "depth_min_m",
    "depth_max_m",
    "growth_form",
    "tissue_type",
    "area_mm2",
    "temperature_c",
    "sample_size",
]

TRACKED_MISSING_FIELDS = [
    "missing_location_raw",
    "missing_coords_latlon",
    "missing_depth",
    "missing_growth_form",
    "missing_tissue_type",
    "missing_area_mm2",
    "missing_temperature_c",
    "missing_sample_size",
]

LOCATION_FIELDS = [
    "source_id",
    "paper_title",
    "location_raw",
    "location_standardized",
    "site_name",
    "reef_or_bay",
    "island_or_coast",
    "country_territory",
    "water_body",
    "latitude",
    "longitude",
    "depth_min_m",
    "depth_max_m",
    "location_type",
    "coordinate_basis",
    "coordinate_confidence",
    "location_notes",
]


def normalize(value: str | None) -> str:
    return (value or "").strip()


def dms_to_decimal(text: str) -> str:
    raw = normalize(text)
    if not raw:
        return ""
    for old, new in [
        ("′′", '"'),
        ("''", '"'),
        ("″", '"'),
        ("“", '"'),
        ("”", '"'),
        ("′", "'"),
        ("’", "'"),
        ("`", "'"),
        ("º", "°"),
        ("◦", "°"),
    ]:
        raw = raw.replace(old, new)

    m = re.search(
        r"(?P<deg>-?\d+(?:\.\d+)?)\s*°?\s*"
        r"(?:(?P<min>\d+(?:\.\d+)?)\s*'?\s*)?"
        r"(?:(?P<sec>\d+(?:\.\d+)?)\s*\"?\s*)?"
        r"(?P<hem>[NSEW])?$",
        raw,
        flags=re.I,
    )
    if not m:
        return raw if re.fullmatch(r"-?\d+(?:\.\d+)?", raw) else ""

    deg = float(m.group("deg"))
    minutes = float(m.group("min") or 0)
    seconds = float(m.group("sec") or 0)
    hem = (m.group("hem") or "").upper()
    decimal = abs(deg) + minutes / 60 + seconds / 3600
    if deg < 0:
        decimal *= -1
    if hem in {"S", "W"}:
        decimal *= -1
    return f"{decimal:.6f}"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_note(row: dict[str, str], note_field: str, tag: str) -> None:
    note = normalize(row.get(note_field, ""))
    if tag not in note:
        row[note_field] = f"{note} {tag}".strip()


def merge_worker_repairs(
    base_rows: list[dict[str, str]],
    worker_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], Counter, dict[str, Counter]]:
    out_rows = [dict(row) for row in base_rows]
    by_source = {row["source_id"]: row for row in out_rows}
    audit_rows: list[dict[str, str]] = []
    field_counter: Counter[str] = Counter()
    worker_counter: dict[str, Counter] = defaultdict(Counter)

    for wr in worker_rows:
        source_id = wr.get("source_id", "")
        if source_id not in by_source:
            continue
        base = by_source[source_id]
        changed_fields: list[str] = []

        for field in REPAIR_FIELDS:
            if not normalize(base.get(field, "")) and normalize(wr.get(field, "")):
                base[field] = wr[field]
                changed_fields.append(field)
                field_counter[field] += 1

        if not normalize(base.get("latitude", "")) and normalize(base.get("latitude_raw", "")):
            decimal = dms_to_decimal(base["latitude_raw"])
            if decimal:
                base["latitude"] = decimal
                changed_fields.append("latitude")
                field_counter["latitude"] += 1

        if not normalize(base.get("longitude", "")) and normalize(base.get("longitude_raw", "")):
            decimal = dms_to_decimal(base["longitude_raw"])
            if decimal:
                base["longitude"] = decimal
                changed_fields.append("longitude")
                field_counter["longitude"] += 1

        worker_note = normalize(wr.get("repair_notes", ""))
        if worker_note:
            append_note(base, "notes", f"[agent repair: {worker_note}]")

        if changed_fields:
            worker_id = normalize(wr.get("repair_batch_id", "")) or "unknown_worker"
            worker_counter[worker_id]["rows_changed"] += 1
            for field in changed_fields:
                worker_counter[worker_id][field] += 1
            audit_rows.append(
                {
                    "source_id": source_id,
                    "paper_title": base.get("paper_title", ""),
                    "worker_batch_id": worker_id,
                    "worker_status": normalize(wr.get("repair_status", "")),
                    "changed_fields": "; ".join(changed_fields),
                    "worker_notes": worker_note,
                }
            )

    return out_rows, audit_rows, field_counter, worker_counter


def normalize_coordinate_pairs(rows: list[dict[str, str]], note_field: str) -> None:
    tag = "[coordinate cleanup: partial one-sided coordinate removed from decimal columns]"
    for row in rows:
        lat = normalize(row.get("latitude", ""))
        lon = normalize(row.get("longitude", ""))
        if bool(lat) ^ bool(lon):
            row["latitude"] = ""
            row["longitude"] = ""
            append_note(row, note_field, tag)


def replace_primary_rows(
    all_rows: list[dict[str, str]],
    primary_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    primary_by_id = {row["source_id"]: row for row in primary_rows}
    out: list[dict[str, str]] = []
    for row in all_rows:
        replacement = primary_by_id.get(row["source_id"])
        out.append(dict(replacement) if replacement else dict(row))
    return out


def build_missingness_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    missing_rows: list[dict[str, str]] = []
    for row in rows:
        missing = {
            "source_id": row["source_id"],
            "paper_title": row["paper_title"],
            "missing_location_raw": "1" if not normalize(row.get("location_raw", "")) else "0",
            "missing_coords_latlon": "0"
            if normalize(row.get("latitude", "")) and normalize(row.get("longitude", ""))
            else "1",
            "missing_depth": "1"
            if not (normalize(row.get("depth_min_m", "")) or normalize(row.get("depth_max_m", "")))
            else "0",
            "missing_growth_form": "1" if not normalize(row.get("growth_form", "")) else "0",
            "missing_tissue_type": "1" if not normalize(row.get("tissue_type", "")) else "0",
            "missing_area_mm2": "1" if not normalize(row.get("area_mm2", "")) else "0",
            "missing_temperature_c": "1" if not normalize(row.get("temperature_c", "")) else "0",
            "missing_sample_size": "1" if not normalize(row.get("sample_size", "")) else "0",
        }
        missing_rows.append(missing)
    return missing_rows


def remaining_queue(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        if any(row[field] == "1" for field in TRACKED_MISSING_FIELDS):
            issue_count = sum(1 for field in TRACKED_MISSING_FIELDS if row[field] == "1")
            remaining = dict(row)
            remaining["remaining_issue_count"] = str(issue_count)
            out.append(remaining)
    return out


def preferred(existing: str, incoming: str) -> str:
    return existing if normalize(existing) else normalize(incoming)


def derive_basis(row: dict[str, str]) -> tuple[str, str]:
    if normalize(row.get("latitude", "")) and normalize(row.get("longitude", "")):
        if normalize(row.get("latitude_raw", "")) or normalize(row.get("longitude_raw", "")):
            return "reported_exact", "high"
        return "inferred_from_locality", "medium"
    if normalize(row.get("location_raw", "")):
        return "reported_site_name", "medium"
    return "not_yet_resolved", "low"


def merge_location_rows(location_rows: list[dict[str, str]], cov_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cov_by_id = {
        row["source_id"]: row
        for row in cov_rows
        if row.get("source_id") and row.get("notebook_covariate_status") == "parsed"
    }
    seen_sources: set[str] = set()
    merged: list[dict[str, str]] = []

    for row in location_rows:
        out = {field: row.get(field, "") for field in LOCATION_FIELDS}
        cov = cov_by_id.get(row.get("source_id", ""))
        if cov:
            seen_sources.add(row["source_id"])
            out["paper_title"] = preferred(out["paper_title"], cov.get("paper_title", ""))
            out["location_raw"] = preferred(out["location_raw"], cov.get("location_raw", ""))
            out["site_name"] = preferred(out["site_name"], cov.get("site_name", ""))
            out["country_territory"] = preferred(out["country_territory"], cov.get("country_territory", ""))
            out["water_body"] = preferred(out["water_body"], cov.get("water_body", ""))
            out["latitude"] = preferred(out["latitude"], cov.get("latitude", ""))
            out["longitude"] = preferred(out["longitude"], cov.get("longitude", ""))
            out["depth_min_m"] = preferred(out["depth_min_m"], cov.get("depth_min_m", ""))
            out["depth_max_m"] = preferred(out["depth_max_m"], cov.get("depth_max_m", ""))
            if not normalize(out.get("location_type", "")):
                out["location_type"] = "field_site"
            basis, conf = derive_basis(cov)
            out["coordinate_basis"] = preferred(out["coordinate_basis"], basis)
            out["coordinate_confidence"] = preferred(out["coordinate_confidence"], conf)
            append_note(out, "location_notes", "Notebook covariate final merge")
        merged.append(out)

    for source_id, cov in cov_by_id.items():
        if source_id in seen_sources:
            continue
        basis, conf = derive_basis(cov)
        merged.append(
            {
                "source_id": source_id,
                "paper_title": cov.get("paper_title", ""),
                "location_raw": cov.get("location_raw", ""),
                "location_standardized": "",
                "site_name": cov.get("site_name", ""),
                "reef_or_bay": "",
                "island_or_coast": "",
                "country_territory": cov.get("country_territory", ""),
                "water_body": cov.get("water_body", ""),
                "latitude": cov.get("latitude", ""),
                "longitude": cov.get("longitude", ""),
                "depth_min_m": cov.get("depth_min_m", ""),
                "depth_max_m": cov.get("depth_max_m", ""),
                "location_type": "field_site" if normalize(cov.get("location_raw", "")) else "unknown",
                "coordinate_basis": basis,
                "coordinate_confidence": conf,
                "location_notes": "Notebook covariate final merge",
            }
        )

    return merged


def count_nonblank(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if normalize(row.get(field, "")))


def count_latlon(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if normalize(row.get("latitude", "")) and normalize(row.get("longitude", "")))


def write_summary(
    path: Path,
    base_primary: list[dict[str, str]],
    final_primary: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
    field_counter: Counter,
    worker_counter: dict[str, Counter],
    remaining_rows: list[dict[str, str]],
    location_rows: list[dict[str, str]],
) -> None:
    base_missing = build_missingness_rows(base_primary)
    final_missing = build_missingness_rows(final_primary)

    lines: list[str] = []
    lines.append("# Notebook Covariate Finalization Summary")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- Base repaired primary rows: {len(base_primary)}")
    lines.append(f"- Final primary rows: {len(final_primary)}")
    lines.append(f"- Worker rows with actual merged changes: {len(audit_rows)}")
    lines.append("")
    lines.append("## Worker Merge Gains")
    if audit_rows:
        for field in [
            "location_raw",
            "latitude_raw",
            "longitude_raw",
            "latitude",
            "longitude",
            "depth_min_m",
            "depth_max_m",
            "growth_form",
            "tissue_type",
            "area_mm2",
            "temperature_c",
            "sample_size",
        ]:
            if field_counter[field]:
                lines.append(f"- `{field}`: +{field_counter[field]}")
    else:
        lines.append("- No new worker repairs were merged.")
    lines.append("")
    lines.append("## Missingness Before -> After")
    for field in TRACKED_MISSING_FIELDS:
        before = sum(1 for row in base_missing if row[field] == "1")
        after = sum(1 for row in final_missing if row[field] == "1")
        lines.append(f"- `{field}`: {before} -> {after} (resolved {before - after})")
    lines.append("")
    lines.append("## Final Primary Coverage")
    lines.append(f"- `location_raw`: {count_nonblank(final_primary, 'location_raw')}/{len(final_primary)}")
    lines.append(f"- decimal coordinate pairs: {count_latlon(final_primary)}/{len(final_primary)}")
    lines.append(
        f"- depth: {sum(1 for row in final_primary if normalize(row.get('depth_min_m', '')) or normalize(row.get('depth_max_m', '')))}/{len(final_primary)}"
    )
    lines.append(f"- `growth_form`: {count_nonblank(final_primary, 'growth_form')}/{len(final_primary)}")
    lines.append(f"- `tissue_type`: {count_nonblank(final_primary, 'tissue_type')}/{len(final_primary)}")
    lines.append(f"- `area_mm2`: {count_nonblank(final_primary, 'area_mm2')}/{len(final_primary)}")
    lines.append(f"- `temperature_c`: {count_nonblank(final_primary, 'temperature_c')}/{len(final_primary)}")
    lines.append(f"- `sample_size`: {count_nonblank(final_primary, 'sample_size')}/{len(final_primary)}")
    lines.append("")
    lines.append("## Location Manifest")
    lines.append(f"- rows: {len(location_rows)}")
    lines.append(f"- with locality text: {count_nonblank(location_rows, 'location_raw')}/{len(location_rows)}")
    lines.append(f"- with coordinate pairs: {count_latlon(location_rows)}/{len(location_rows)}")
    lines.append(
        f"- with depth: {sum(1 for row in location_rows if normalize(row.get('depth_min_m', '')) or normalize(row.get('depth_max_m', '')))}/{len(location_rows)}"
    )
    basis_counts = Counter(normalize(row.get("coordinate_basis", "")) for row in location_rows)
    for basis in ["reported_exact", "reported_site_name", "inferred_from_locality", "not_yet_resolved"]:
        if basis_counts[basis]:
            lines.append(f"- `{basis}`: {basis_counts[basis]}")
    lines.append("")
    lines.append("## Worker Contribution Detail")
    if worker_counter:
        for worker_id in sorted(worker_counter):
            counter = worker_counter[worker_id]
            lines.append(f"- `{worker_id}`: {counter['rows_changed']} rows changed")
    else:
        lines.append("- No worker changes recorded.")
    lines.append("")
    lines.append("## Remaining Queue")
    lines.append(f"- remaining primary rows with at least one unresolved tracked field: {len(remaining_rows)}")
    lines.append("- The remaining queue is dominated by true nonreporting, especially exact coordinates, single study-level temperatures, and lesion areas.")
    lines.append("- `Cox - 2014 - Corallivory The Coral’s Point of View.pdf` remains in the queue only because it is still mislabeled as primary upstream.")
    lines.append("")
    lines.append("## Files")
    lines.append("- `notebook_covariates_primary_final.csv`")
    lines.append("- `notebook_covariates_all_sources_final.csv`")
    lines.append("- `notebook_covariate_missingness_primary_final.csv`")
    lines.append("- `notebook_covariate_remaining_queue_primary_final.csv`")
    lines.append("- `study_location_metadata_enriched_final.csv`")
    lines.append("- `agent_worker_merge_audit.csv`")

    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-primary", required=True)
    parser.add_argument("--base-all-sources", required=True)
    parser.add_argument("--worker-csvs", nargs="+", required=True)
    parser.add_argument("--base-location", required=True)
    parser.add_argument("--output-primary", required=True)
    parser.add_argument("--output-all-sources", required=True)
    parser.add_argument("--output-missingness", required=True)
    parser.add_argument("--output-remaining", required=True)
    parser.add_argument("--output-location", required=True)
    parser.add_argument("--output-summary", required=True)
    parser.add_argument("--output-audit", required=True)
    args = parser.parse_args()

    base_primary = load_csv(Path(args.base_primary))
    base_all_sources = load_csv(Path(args.base_all_sources))
    base_location = load_csv(Path(args.base_location))

    worker_rows: list[dict[str, str]] = []
    for path in args.worker_csvs:
        worker_rows.extend(load_csv(Path(path)))

    final_primary, audit_rows, field_counter, worker_counter = merge_worker_repairs(base_primary, worker_rows)
    normalize_coordinate_pairs(final_primary, "notes")

    final_all_sources = replace_primary_rows(base_all_sources, final_primary)
    normalize_coordinate_pairs(final_all_sources, "notes")

    missing_rows = build_missingness_rows(final_primary)
    remaining_rows = remaining_queue(missing_rows)

    final_location = merge_location_rows(base_location, final_all_sources)
    normalize_coordinate_pairs(final_location, "location_notes")

    write_csv(Path(args.output_primary), final_primary, list(final_primary[0].keys()))
    write_csv(Path(args.output_all_sources), final_all_sources, list(final_all_sources[0].keys()))
    write_csv(Path(args.output_missingness), missing_rows, list(missing_rows[0].keys()))
    write_csv(
        Path(args.output_remaining),
        remaining_rows,
        list(remaining_rows[0].keys()),
    )
    write_csv(Path(args.output_location), final_location, LOCATION_FIELDS)
    write_csv(
        Path(args.output_audit),
        audit_rows,
        ["source_id", "paper_title", "worker_batch_id", "worker_status", "changed_fields", "worker_notes"],
    )
    write_summary(
        Path(args.output_summary),
        base_primary,
        final_primary,
        audit_rows,
        field_counter,
        worker_counter,
        remaining_rows,
        final_location,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

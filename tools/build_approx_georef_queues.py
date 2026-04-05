#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def normalize(value: str | None) -> str:
    return (value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def classify_region(row: dict[str, str]) -> str:
    text = " | ".join(
        [
            normalize(row.get("location_raw")),
            normalize(row.get("site_name")),
            normalize(row.get("country_territory")),
            normalize(row.get("water_body")),
        ]
    ).lower()

    if any(k in text for k in ["eilat", "red sea", "israel", "saudi", "mediterranean", "portugal"]):
        return "eastern_region"
    if any(
        k in text
        for k in [
            "moorea",
            "hawaii",
            "kaneohe",
            "guam",
            "okinawa",
            "australia",
            "philippines",
            "rangiroa",
            "oahu",
            "french polynesia",
            "oceanário",
            "oceanario",
        ]
    ):
        return "pacific_region"
    return "caribbean_region"


def build_exact_missing_map(primary_rows: list[dict[str, str]]) -> dict[str, str]:
    issue_map: dict[str, str] = {}
    issue_fields = [
        "missing_location_raw",
        "missing_coords_latlon",
        "missing_depth",
        "missing_growth_form",
        "missing_tissue_type",
        "missing_area_mm2",
        "missing_temperature_c",
        "missing_sample_size",
    ]
    for row in primary_rows:
        issues = [field for field in issue_fields if normalize(row.get(field)) == "1"]
        issue_map[row["source_id"]] = "; ".join(issues)
    return issue_map


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-csv", required=True)
    parser.add_argument("--remaining-primary-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    location_rows = read_csv(Path(args.location_csv))
    remaining_primary = read_csv(Path(args.remaining_primary_csv))
    issue_map = build_exact_missing_map(remaining_primary)

    targets: list[dict[str, str]] = []
    for idx, row in enumerate(location_rows, start=1):
        has_loc = bool(normalize(row.get("location_raw")))
        has_exact = bool(normalize(row.get("latitude"))) and bool(normalize(row.get("longitude")))
        exact_basis = normalize(row.get("coordinate_basis"))
        if not has_loc:
            continue
        if has_exact and exact_basis == "reported_exact":
            continue

        targets.append(
            {
                "location_row_id": f"loc_{idx:03d}",
                "source_id": normalize(row.get("source_id")),
                "paper_title": normalize(row.get("paper_title")),
                "location_raw": normalize(row.get("location_raw")),
                "site_name": normalize(row.get("site_name")),
                "country_territory": normalize(row.get("country_territory")),
                "water_body": normalize(row.get("water_body")),
                "current_latitude": normalize(row.get("latitude")),
                "current_longitude": normalize(row.get("longitude")),
                "current_coordinate_basis": exact_basis,
                "current_coordinate_confidence": normalize(row.get("coordinate_confidence")),
                "needs_approx_georef": "1",
                "has_mixed_nonexact_current_coords": "1" if has_exact and exact_basis != "reported_exact" else "0",
                "remaining_exact_missing_fields": issue_map.get(normalize(row.get("source_id")), ""),
                "region_bucket": classify_region(row),
            }
        )

    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in targets:
        buckets[row["region_bucket"]].append(row)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_path = output_dir / "approx_georef_queue_all.csv"
    fieldnames = list(targets[0].keys()) if targets else [
        "location_row_id",
        "source_id",
        "paper_title",
        "location_raw",
        "site_name",
        "country_territory",
        "water_body",
        "current_latitude",
        "current_longitude",
        "current_coordinate_basis",
        "current_coordinate_confidence",
        "needs_approx_georef",
        "has_mixed_nonexact_current_coords",
        "remaining_exact_missing_fields",
        "region_bucket",
    ]

    with all_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(targets)

    name_map = {
        "caribbean_region": "agent_georef_queue_1.csv",
        "pacific_region": "agent_georef_queue_2.csv",
        "eastern_region": "agent_georef_queue_3.csv",
    }
    for bucket, rows in buckets.items():
        path = output_dir / name_map[bucket]
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(all_path)
    print(f"target_rows={len(targets)}")
    for bucket in ["caribbean_region", "pacific_region", "eastern_region"]:
        print(f"{bucket}={len(buckets.get(bucket, []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

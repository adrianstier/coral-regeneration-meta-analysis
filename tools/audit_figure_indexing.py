#!/usr/bin/env python3
"""Audit figure/table digitization indexing against local source files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENING_LOG = ROOT / "data" / "screening" / "SCREENING_LOG_FINAL.csv"
LITERATURE_MAP = ROOT / "data" / "literature" / "LITERATURE_MAP.csv"
DIGITIZATION_QUEUE = ROOT / "pipeline" / "DIGITIZATION_FIGURE_QUEUE.csv"
FIGURE_SOURCE_REVIEW = ROOT / "digitization" / "source_review" / "FIGURE_SOURCE_REVIEW.csv"
FIGURE_SOURCE_REVIEW_VALIDATED = ROOT / "digitization" / "source_review" / "FIGURE_SOURCE_REVIEW_VALIDATED.csv"
FIGURE_CANDIDATE_AUDIT = ROOT / "digitization" / "source_review" / "FIGURE_CANDIDATE_AUDIT.csv"
FIGURE_QUEUE_AUDIT = ROOT / "digitization" / "source_review" / "FIGURE_QUEUE_AUDIT_STATUS.csv"
SOURCE_PAGE_RENDER_MANIFEST = ROOT / "digitization" / "figures" / "SOURCE_PAGE_RENDER_MANIFEST.csv"
FIGURE_VISUAL_REAUDIT = ROOT / "digitization" / "source_review" / "FIGURE_VISUAL_REAUDIT.csv"
FIGURE_CROP_MANIFEST = ROOT / "digitization" / "figures" / "FIGURE_CROP_MANIFEST.csv"
FIGURE_INDEX_AUDIT = ROOT / "digitization" / "figures" / "FIGURE_INDEX_AUDIT.csv"
FIGURE_INDEX_SUMMARY = ROOT / "digitization" / "figures" / "FIGURE_INDEX_AUDIT_SUMMARY.md"
SOURCE_PAGE_DIR = ROOT / "digitization" / "figures" / "source_pages"
CROP_REVIEW_DIR = ROOT / "digitization" / "figures" / "crop_review"
DIGITIZED_DATA_DIR = ROOT / "digitization" / "data"


AUDIT_FIELDS = [
    "severity",
    "check",
    "object_type",
    "object_id",
    "detail",
    "expected",
    "observed",
    "path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return token or "candidate"


def add_issue(
    issues: list[dict[str, str]],
    severity: str,
    check: str,
    object_type: str,
    object_id: str,
    detail: str,
    expected: str = "",
    observed: str = "",
    path: str = "",
) -> None:
    issues.append(
        {
            "severity": severity,
            "check": check,
            "object_type": object_type,
            "object_id": object_id,
            "detail": detail,
            "expected": expected,
            "observed": observed,
            "path": path,
        }
    )


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_count(path: Path) -> str:
    if not path.exists():
        return ""
    proc = subprocess.run(
        ["pdfinfo", str(path)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return ""
    for line in proc.stdout.splitlines():
        if line.lower().startswith("pages:"):
            return line.split(":", 1)[1].strip()
    return ""


def parse_int(value: str) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def candidate_descriptors(value: str) -> list[str]:
    return [clean(item) for item in str(value or "").split("|") if clean(item)]


def parse_candidate_descriptor(descriptor: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(?P<kind>[^:]+):(?P<label>.+):p(?P<page>\d+)$", descriptor)
    if not match:
        return None
    return match.group("kind"), match.group("label"), match.group("page")


def image_size(path: Path) -> tuple[int | None, int | None, str]:
    if not path.exists():
        return None, None, "missing_file"
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
        return width, height, "ok"
    except Exception as exc:  # pragma: no cover - defensive for corrupt images.
        return None, None, f"image_error: {clean(exc)[:120]}"


def parse_crop_box(value: str) -> tuple[int, int, int, int] | None:
    parts = [part.strip() for part in str(value or "").split(",")]
    if len(parts) != 4:
        return None
    parsed = [parse_int(part) for part in parts]
    if any(part is None for part in parsed):
        return None
    x, y, width, height = parsed
    assert x is not None and y is not None and width is not None and height is not None
    return x, y, width, height


def rows_by_key(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(key, "")].append(row)
    return grouped


def first_by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key, "")}


def collect_source_ids(*row_groups: list[dict[str, str]]) -> set[str]:
    source_ids: set[str] = set()
    for rows in row_groups:
        for row in rows:
            source_id = row.get("source_id", "")
            if source_id:
                source_ids.add(source_id)
    return source_ids


def audit_prefixes(issues: list[dict[str, str]], source_ids: set[str]) -> None:
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for source_id in source_ids:
        by_prefix[source_id[:8]].append(source_id)
    for prefix, ids in sorted(by_prefix.items()):
        if len(set(ids)) > 1:
            add_issue(
                issues,
                "error",
                "source_id_prefix_collision",
                "source_id_prefix",
                prefix,
                "The first 8 characters of source_id are not unique, so figure/page filenames are ambiguous.",
                "one source_id per prefix",
                " | ".join(sorted(set(ids))),
            )


def audit_queue(
    issues: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    screening_rows: list[dict[str, str]],
    literature_rows: list[dict[str, str]],
) -> dict[str, str]:
    pdf_hashes: dict[str, str] = {}
    screening_by_source = first_by_key(screening_rows, "source_id")
    literature_by_source = first_by_key(literature_rows, "source_id")
    queue_by_id = rows_by_key(queue_rows, "queue_id")
    for queue_id, rows in sorted(queue_by_id.items()):
        if not queue_id:
            add_issue(issues, "error", "missing_queue_id", "queue_row", "", "Digitization queue row has no queue_id.")
        if len(rows) > 1:
            add_issue(
                issues,
                "error",
                "duplicate_queue_id",
                "queue_id",
                queue_id,
                "Digitization queue_id must be unique.",
                "1 row",
                str(len(rows)),
            )

    seen_source_response: dict[tuple[str, str], str] = {}
    for row in queue_rows:
        queue_id = row.get("queue_id", "")
        source_id = row.get("source_id", "")
        response_type = row.get("response_type", "")
        local_rel = row.get("local_relpath", "")
        expected_queue_id = f"DIG-{source_id[:8]}-{response_type}" if source_id and response_type else ""
        if expected_queue_id and queue_id != expected_queue_id:
            add_issue(
                issues,
                "error",
                "queue_id_format",
                "queue_id",
                queue_id,
                "queue_id does not match the source_id-prefix/response indexing rule.",
                expected_queue_id,
                queue_id,
            )
        source_response = (source_id, response_type)
        if source_id and response_type and source_response in seen_source_response:
            add_issue(
                issues,
                "error",
                "duplicate_source_response",
                "queue_id",
                queue_id,
                "More than one digitization queue row exists for the same source_id and response_type.",
                seen_source_response[source_response],
                queue_id,
            )
        seen_source_response[source_response] = queue_id

        screening = screening_by_source.get(source_id)
        if not screening:
            add_issue(
                issues,
                "error",
                "queue_source_missing_from_screening",
                "queue_id",
                queue_id,
                "Digitization queue source_id is not present in SCREENING_LOG_FINAL.csv.",
                path=DIGITIZATION_QUEUE.relative_to(ROOT).as_posix(),
            )
        else:
            if screening.get("final_status") != "include_primary":
                add_issue(
                    issues,
                    "error",
                    "queue_source_not_primary",
                    "queue_id",
                    queue_id,
                    "Digitization queue row is not tied to an include_primary screening record.",
                    "include_primary",
                    screening.get("final_status", ""),
                )
            screening_rel = screening.get("local_relpath", "")
            if screening_rel and local_rel and screening_rel != local_rel:
                add_issue(
                    issues,
                    "error",
                    "queue_screening_path_mismatch",
                    "queue_id",
                    queue_id,
                    "Queue local_relpath differs from SCREENING_LOG_FINAL.csv.",
                    screening_rel,
                    local_rel,
                )
        literature = literature_by_source.get(source_id)
        if literature:
            literature_rel = literature.get("local_relpath", "")
            if literature_rel and local_rel and literature_rel != local_rel:
                add_issue(
                    issues,
                    "error",
                    "queue_literature_map_path_mismatch",
                    "queue_id",
                    queue_id,
                    "Queue local_relpath differs from LITERATURE_MAP.csv.",
                    literature_rel,
                    local_rel,
                )

        pdf_path = ROOT / local_rel if local_rel else ROOT
        exists = bool(local_rel) and pdf_path.exists()
        declared_available = row.get("source_file_status") == "local_pdf_available"
        if declared_available and not exists:
            add_issue(
                issues,
                "error",
                "queue_pdf_missing",
                "queue_id",
                queue_id,
                "Queue row declares local_pdf_available but the local file does not exist.",
                "existing local PDF",
                local_rel,
                local_rel,
            )
        if exists and row.get("source_file_status") != "local_pdf_available":
            add_issue(
                issues,
                "error",
                "queue_pdf_status_mismatch",
                "queue_id",
                queue_id,
                "Queue row does not declare local_pdf_available even though the file exists.",
                "local_pdf_available",
                row.get("source_file_status", ""),
                local_rel,
            )
        if exists and local_rel not in pdf_hashes:
            pdf_hashes[local_rel] = file_sha256(pdf_path)
    return pdf_hashes


def audit_source_review(
    issues: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    validated_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    pdf_hashes: dict[str, str],
) -> dict[str, str]:
    queue_ids = {row.get("queue_id", "") for row in queue_rows}
    page_counts: dict[str, str] = {}
    for local_rel in pdf_hashes:
        page_counts[local_rel] = pdf_page_count(ROOT / local_rel)

    if len(source_rows) != len(validated_rows):
        add_issue(
            issues,
            "error",
            "source_review_validated_row_count",
            "file_pair",
            "FIGURE_SOURCE_REVIEW.csv",
            "Validated figure-source review should preserve raw review row count.",
            str(len(source_rows)),
            str(len(validated_rows)),
        )

    for row in source_rows:
        queue_id = row.get("queue_id", "")
        local_rel = row.get("local_relpath", "")
        if queue_id not in queue_ids:
            add_issue(
                issues,
                "error",
                "source_review_queue_missing",
                "queue_id",
                queue_id,
                "Source-review row does not have a matching digitization queue row.",
            )
        actual_hash = pdf_hashes.get(local_rel, "")
        stored_hash = row.get("pdf_sha256", "")
        if actual_hash and stored_hash and stored_hash != actual_hash:
            add_issue(
                issues,
                "error",
                "source_review_pdf_hash_mismatch",
                "queue_id",
                queue_id,
                "Stored source-review PDF hash differs from the current local PDF.",
                actual_hash,
                stored_hash,
                local_rel,
            )
        actual_pages = page_counts.get(local_rel, "")
        stored_pages = row.get("pdf_page_count", "")
        if actual_pages and stored_pages and actual_pages != stored_pages:
            add_issue(
                issues,
                "error",
                "source_review_page_count_mismatch",
                "queue_id",
                queue_id,
                "Stored source-review PDF page count differs from current local PDF.",
                actual_pages,
                stored_pages,
                local_rel,
            )
        page = parse_int(row.get("candidate_page", ""))
        count = parse_int(actual_pages or stored_pages)
        if page is not None and count is not None and (page < 1 or page > count):
            add_issue(
                issues,
                "error",
                "source_review_candidate_page_out_of_range",
                "queue_id",
                queue_id,
                "Candidate page is outside the source PDF page range.",
                f"1..{count}",
                str(page),
                local_rel,
            )
    return page_counts


def audit_queue_audit(
    issues: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
    queue_audit_rows: list[dict[str, str]],
    candidate_audit_rows: list[dict[str, str]],
) -> None:
    queue_ids = {row.get("queue_id", "") for row in queue_rows}
    audit_by_queue = rows_by_key(queue_audit_rows, "queue_id")
    for queue_id in sorted(queue_ids):
        rows = audit_by_queue.get(queue_id, [])
        if not rows:
            add_issue(
                issues,
                "error",
                "queue_missing_audit_status",
                "queue_id",
                queue_id,
                "Digitization queue row has no FIGURE_QUEUE_AUDIT_STATUS row.",
            )
        elif len(rows) > 1:
            add_issue(
                issues,
                "error",
                "queue_duplicate_audit_status",
                "queue_id",
                queue_id,
                "Digitization queue row has multiple FIGURE_QUEUE_AUDIT_STATUS rows.",
                "1 row",
                str(len(rows)),
            )
    for row in queue_audit_rows:
        queue_id = row.get("queue_id", "")
        if queue_id not in queue_ids:
            add_issue(
                issues,
                "error",
                "audit_status_queue_missing",
                "queue_id",
                queue_id,
                "FIGURE_QUEUE_AUDIT_STATUS row does not have a matching digitization queue row.",
            )
        descriptors = candidate_descriptors(row.get("recommended_candidates", ""))
        expected_count = parse_int(row.get("recommended_candidate_count", ""))
        if expected_count is not None and expected_count != len(descriptors):
            add_issue(
                issues,
                "error",
                "recommended_candidate_count_mismatch",
                "queue_id",
                queue_id,
                "recommended_candidate_count does not match the number of pipe-separated descriptors.",
                str(len(descriptors)),
                str(expected_count),
            )
        for descriptor in descriptors:
            parsed = parse_candidate_descriptor(descriptor)
            if parsed is None:
                add_issue(
                    issues,
                    "error",
                    "recommended_candidate_descriptor_parse",
                    "queue_id",
                    queue_id,
                    "Recommended candidate descriptor does not parse as type:label:pN.",
                    "type:label:pN",
                    descriptor,
                )
        status = row.get("queue_audit_status", "")
        if status in {"needs_followup_review", "no_valid_candidate_found", "blocked_missing_pdf"}:
            add_issue(
                issues,
                "warning",
                f"queue_{status}",
                "queue_id",
                queue_id,
                "Queue row is not ready for crop-to-data extraction.",
                "audited_candidate_available",
                status,
            )

    for row in candidate_audit_rows:
        if row.get("coverage_status") == "extra_or_stale_audit_candidate":
            add_issue(
                issues,
                "warning",
                "extra_or_stale_candidate_audit",
                "queue_id",
                row.get("queue_id", ""),
                "Candidate audit row no longer matches a raw candidate key.",
                "matched_base_candidate",
                row.get("coverage_status", ""),
                row.get("audit_file", ""),
            )
        if row.get("audit_key_status") != "valid_status":
            add_issue(
                issues,
                "error",
                "invalid_candidate_audit_key",
                "queue_id",
                row.get("queue_id", ""),
                "Candidate audit row has an invalid status or incomplete key.",
                "valid_status",
                row.get("audit_key_status", ""),
                row.get("audit_file", ""),
            )


def expected_source_page_path(source_id: str, page: str) -> str:
    page_int = parse_int(page)
    if not source_id or page_int is None:
        return ""
    return f"digitization/figures/source_pages/{source_id[:8]}__page-{page_int:03d}.png"


def audit_render_manifest(
    issues: list[dict[str, str]],
    render_rows: list[dict[str, str]],
    queue_audit_rows: list[dict[str, str]],
    page_counts: dict[str, str],
) -> None:
    expected_render_keys = {
        (row.get("queue_id", ""), descriptor)
        for row in queue_audit_rows
        for descriptor in candidate_descriptors(row.get("recommended_candidates", ""))
    }
    render_keys = {(row.get("queue_id", ""), row.get("candidate_descriptor", "")) for row in render_rows}
    for key in sorted(expected_render_keys - render_keys):
        add_issue(
            issues,
            "error",
            "recommended_candidate_missing_render_row",
            "queue_candidate",
            " :: ".join(key),
            "Recommended candidate has no source-page render manifest row.",
        )
    for key in sorted(render_keys - expected_render_keys):
        add_issue(
            issues,
            "warning",
            "render_row_without_recommended_candidate",
            "queue_candidate",
            " :: ".join(key),
            "Render manifest row does not match a current recommended candidate.",
        )

    seen_paths = set()
    for row in render_rows:
        queue_id = row.get("queue_id", "")
        descriptor = row.get("candidate_descriptor", "")
        parsed = parse_candidate_descriptor(descriptor)
        if parsed is None:
            add_issue(
                issues,
                "error",
                "render_candidate_descriptor_parse",
                "queue_id",
                queue_id,
                "Render candidate descriptor does not parse as type:label:pN.",
                "type:label:pN",
                descriptor,
            )
        else:
            kind, label, page = parsed
            if kind != row.get("candidate_type", "") or label != row.get("candidate_label", "") or page != row.get("pdf_page", ""):
                add_issue(
                    issues,
                    "error",
                    "render_descriptor_column_mismatch",
                    "queue_id",
                    queue_id,
                    "Parsed candidate_descriptor differs from explicit render-manifest columns.",
                    f"{kind}|{label}|{page}",
                    f"{row.get('candidate_type', '')}|{row.get('candidate_label', '')}|{row.get('pdf_page', '')}",
                )
        local_rel = row.get("local_relpath", "")
        page = row.get("pdf_page", "")
        page_int = parse_int(page)
        page_count = parse_int(page_counts.get(local_rel, ""))
        if page_int is not None and page_count is not None and (page_int < 1 or page_int > page_count):
            add_issue(
                issues,
                "error",
                "render_page_out_of_range",
                "queue_id",
                queue_id,
                "Render page is outside the source PDF page range.",
                f"1..{page_count}",
                str(page_int),
                local_rel,
            )
        expected_path = expected_source_page_path(row.get("source_id", ""), page)
        observed_path = row.get("source_page_render", "")
        if expected_path and observed_path != expected_path:
            add_issue(
                issues,
                "error",
                "source_page_render_path_mismatch",
                "queue_id",
                queue_id,
                "Source-page render path does not follow source prefix/page indexing.",
                expected_path,
                observed_path,
                observed_path,
            )
        if observed_path:
            seen_paths.add(observed_path)
            image_path = ROOT / observed_path
            width, height, status = image_size(image_path)
            if status != "ok":
                add_issue(
                    issues,
                    "error",
                    "source_page_render_file_problem",
                    "queue_id",
                    queue_id,
                    "Source-page render image is missing or unreadable.",
                    "readable PNG",
                    status,
                    observed_path,
                )
            elif width is not None and height is not None and (width <= 0 or height <= 0):
                add_issue(
                    issues,
                    "error",
                    "source_page_render_bad_dimensions",
                    "queue_id",
                    queue_id,
                    "Source-page render image has invalid dimensions.",
                    "positive width and height",
                    f"{width}x{height}",
                    observed_path,
                )
        if row.get("render_status") not in {"rendered", "already_rendered"}:
            add_issue(
                issues,
                "error",
                "render_status_not_available",
                "queue_id",
                queue_id,
                "Render manifest row is not available for visual audit/cropping.",
                "rendered or already_rendered",
                row.get("render_status", ""),
                observed_path,
            )

    if SOURCE_PAGE_DIR.exists():
        referenced_paths = {ROOT / path for path in seen_paths if path}
        for png in sorted(SOURCE_PAGE_DIR.glob("*.png")):
            if png not in referenced_paths:
                add_issue(
                    issues,
                    "warning",
                    "unreferenced_source_page_png",
                    "file",
                    relpath(png),
                    "Source-page PNG is not referenced by SOURCE_PAGE_RENDER_MANIFEST.csv.",
                    path=relpath(png),
                )


def audit_visual_reaudit(
    issues: list[dict[str, str]],
    visual_rows: list[dict[str, str]],
    render_rows: list[dict[str, str]],
    candidate_audit_rows: list[dict[str, str]],
) -> None:
    render_keys = {(row.get("queue_id", ""), row.get("candidate_descriptor", "")) for row in render_rows}
    accepted_visual_keys = set()
    for row in visual_rows:
        if row.get("reaudit_row_type") != "accepted_visual_candidate":
            continue
        key = (row.get("queue_id", ""), row.get("candidate_descriptor", ""))
        accepted_visual_keys.add(key)
        if key not in render_keys:
            add_issue(
                issues,
                "error",
                "accepted_visual_missing_render",
                "queue_candidate",
                " :: ".join(key),
                "Accepted visual candidate has no render manifest row.",
            )
        image_path = ROOT / row.get("source_page_render", "")
        width, height, status = image_size(image_path)
        if status != "ok":
            add_issue(
                issues,
                "error",
                "visual_source_image_problem",
                "queue_id",
                row.get("queue_id", ""),
                "Visual reaudit source image is missing or unreadable.",
                "readable PNG",
                status,
                row.get("source_page_render", ""),
            )
        else:
            if row.get("image_width") and str(width) != row.get("image_width"):
                add_issue(
                    issues,
                    "error",
                    "visual_image_width_mismatch",
                    "queue_id",
                    row.get("queue_id", ""),
                    "Visual reaudit image_width differs from actual PNG width.",
                    str(width),
                    row.get("image_width", ""),
                    row.get("source_page_render", ""),
                )
            if row.get("image_height") and str(height) != row.get("image_height"):
                add_issue(
                    issues,
                    "error",
                    "visual_image_height_mismatch",
                    "queue_id",
                    row.get("queue_id", ""),
                    "Visual reaudit image_height differs from actual PNG height.",
                    str(height),
                    row.get("image_height", ""),
                    row.get("source_page_render", ""),
                )
        if row.get("visual_reaudit_status") != "source_page_image_verified":
            add_issue(
                issues,
                "error",
                "accepted_visual_not_verified",
                "queue_id",
                row.get("queue_id", ""),
                "Accepted visual candidate is not source-page verified.",
                "source_page_image_verified",
                row.get("visual_reaudit_status", ""),
                row.get("source_page_render", ""),
            )

    for key in sorted(render_keys - accepted_visual_keys):
        add_issue(
            issues,
            "error",
            "render_missing_accepted_visual",
            "queue_candidate",
            " :: ".join(key),
            "Render manifest row has no accepted visual reaudit row.",
        )

    rejected_audit_count = sum(1 for row in candidate_audit_rows if row.get("audit_status") == "remove")
    retained_rejected_count = sum(1 for row in visual_rows if row.get("reaudit_row_type") == "retained_caption_rejected")
    if rejected_audit_count != retained_rejected_count:
        add_issue(
            issues,
            "error",
            "retained_rejected_count_mismatch",
            "file_pair",
            "FIGURE_CANDIDATE_AUDIT.csv",
            "Rejected caption-audit rows should be retained in FIGURE_VISUAL_REAUDIT.csv.",
            str(rejected_audit_count),
            str(retained_rejected_count),
        )


def concrete_data_path(path_value: str) -> bool:
    value = clean(path_value)
    return bool(value) and "<" not in value and ">" not in value


def audit_crop_manifest(
    issues: list[dict[str, str]],
    crop_rows: list[dict[str, str]],
    visual_rows: list[dict[str, str]],
) -> dict[str, int]:
    visual_keys = {
        (row.get("queue_id", ""), row.get("candidate_descriptor", ""))
        for row in visual_rows
        if row.get("reaudit_row_type") == "accepted_visual_candidate"
    }
    crop_keys = set()
    crop_paths = Counter(row.get("crop_path", "") for row in crop_rows if row.get("crop_path", ""))
    final_paths = Counter(
        row.get("final_clip_path", "")
        for row in crop_rows
        if row.get("crop_row_type") == "accepted_visual_candidate" and row.get("final_clip_path", "")
    )
    concrete_data_paths = 0
    missing_concrete_data_paths = 0

    for crop_path, count in sorted(crop_paths.items()):
        if count > 1:
            add_issue(
                issues,
                "error",
                "duplicate_crop_path",
                "crop_path",
                crop_path,
                "Crop proposal paths must be unique.",
                "1 row",
                str(count),
                crop_path,
            )
    for final_path, count in sorted(final_paths.items()):
        if count > 1:
            add_issue(
                issues,
                "warning",
                "duplicate_final_clip_path_rule",
                "final_clip_path",
                final_path,
                "Multiple crop rows share the same final clip path rule; reviewer must disambiguate panel/page before saving final clips.",
                "1 row or distinct panel paths",
                str(count),
                final_path,
            )

    for row in crop_rows:
        if row.get("crop_row_type") != "accepted_visual_candidate":
            continue
        key = (row.get("queue_id", ""), row.get("candidate_descriptor", ""))
        crop_keys.add(key)
        if key not in visual_keys:
            add_issue(
                issues,
                "error",
                "crop_missing_visual_row",
                "queue_candidate",
                " :: ".join(key),
                "Accepted crop row has no accepted visual reaudit row.",
            )
        expected_prefix = f"digitization/figures/crop_review/{row.get('source_id', '')[:8]}__{safe_token(row.get('response_type', ''))}__"
        crop_path = row.get("crop_path", "")
        if row.get("crop_status") == "auto_crop_proposal_created":
            if not crop_path:
                add_issue(
                    issues,
                    "error",
                    "auto_crop_missing_path",
                    "queue_id",
                    row.get("queue_id", ""),
                    "Auto crop row is missing crop_path.",
                    "crop_review PNG path",
                )
            elif not crop_path.startswith(expected_prefix):
                add_issue(
                    issues,
                    "error",
                    "crop_path_prefix_mismatch",
                    "queue_id",
                    row.get("queue_id", ""),
                    "Crop path does not follow source prefix/response indexing.",
                    expected_prefix,
                    crop_path,
                    crop_path,
                )
            width = parse_int(row.get("source_page_width", ""))
            height = parse_int(row.get("source_page_height", ""))
            source_path = ROOT / row.get("source_page_render", "")
            actual_width, actual_height, source_status = image_size(source_path)
            if source_status == "ok":
                width = actual_width or width
                height = actual_height or height
            box = parse_crop_box(row.get("crop_box_xywh", ""))
            if box is None:
                add_issue(
                    issues,
                    "error",
                    "crop_box_parse",
                    "queue_id",
                    row.get("queue_id", ""),
                    "Crop box does not parse as x,y,width,height.",
                    "x,y,width,height",
                    row.get("crop_box_xywh", ""),
                    crop_path,
                )
            else:
                x, y, crop_width, crop_height = box
                if crop_width <= 0 or crop_height <= 0:
                    add_issue(
                        issues,
                        "error",
                        "crop_box_nonpositive",
                        "queue_id",
                        row.get("queue_id", ""),
                        "Crop box has non-positive width or height.",
                        "positive width and height",
                        row.get("crop_box_xywh", ""),
                        crop_path,
                    )
                if width is not None and height is not None and (x < 0 or y < 0 or x + crop_width > width or y + crop_height > height):
                    add_issue(
                        issues,
                        "error",
                        "crop_box_out_of_bounds",
                        "queue_id",
                        row.get("queue_id", ""),
                        "Crop box extends outside the source-page image.",
                        f"within {width}x{height}",
                        row.get("crop_box_xywh", ""),
                        crop_path,
                    )
            if crop_path:
                crop_file = ROOT / crop_path
                crop_width, crop_height, crop_status = image_size(crop_file)
                if crop_status != "ok":
                    add_issue(
                        issues,
                        "error",
                        "crop_file_problem",
                        "queue_id",
                        row.get("queue_id", ""),
                        "Crop proposal file is missing or unreadable.",
                        "readable PNG",
                        crop_status,
                        crop_path,
                    )
                elif crop_width is not None and crop_height is not None:
                    box = parse_crop_box(row.get("crop_box_xywh", ""))
                    if box is not None and (crop_width != box[2] or crop_height != box[3]):
                        add_issue(
                            issues,
                            "error",
                            "crop_file_dimension_mismatch",
                            "queue_id",
                            row.get("queue_id", ""),
                            "Crop proposal image dimensions differ from crop_box_xywh.",
                            f"{box[2]}x{box[3]}",
                            f"{crop_width}x{crop_height}",
                            crop_path,
                        )
        data_path = row.get("digitized_data_path", "")
        if concrete_data_path(data_path):
            concrete_data_paths += 1
            if not (ROOT / data_path).exists():
                missing_concrete_data_paths += 1
                add_issue(
                    issues,
                    "error",
                    "digitized_data_path_missing",
                    "queue_id",
                    row.get("queue_id", ""),
                    "Crop manifest references a concrete digitized data path that does not exist.",
                    "existing CSV",
                    data_path,
                    data_path,
                )

    for key in sorted(visual_keys - crop_keys):
        add_issue(
            issues,
            "error",
            "accepted_visual_missing_crop",
            "queue_candidate",
            " :: ".join(key),
            "Accepted visual candidate has no crop manifest row.",
        )

    if CROP_REVIEW_DIR.exists():
        referenced_paths = {ROOT / row.get("crop_path", "") for row in crop_rows if row.get("crop_path", "")}
        for png in sorted(CROP_REVIEW_DIR.glob("*.png")):
            if png not in referenced_paths:
                add_issue(
                    issues,
                    "warning",
                    "unreferenced_crop_review_png",
                    "file",
                    relpath(png),
                    "Crop-review PNG is not referenced by FIGURE_CROP_MANIFEST.csv.",
                    path=relpath(png),
                )

    concrete_files_on_disk = list(DIGITIZED_DATA_DIR.glob("*.csv")) if DIGITIZED_DATA_DIR.exists() else []
    referenced_data_paths = {ROOT / row.get("digitized_data_path", "") for row in crop_rows if concrete_data_path(row.get("digitized_data_path", ""))}
    for data_file in sorted(concrete_files_on_disk):
        if data_file not in referenced_data_paths:
            add_issue(
                issues,
                "warning",
                "unreferenced_digitized_data_csv",
                "file",
                relpath(data_file),
                "Digitized-data CSV is not referenced by FIGURE_CROP_MANIFEST.csv.",
                path=relpath(data_file),
            )

    return {
        "concrete_digitized_data_paths": concrete_data_paths,
        "missing_concrete_digitized_data_paths": missing_concrete_data_paths,
        "digitized_data_files_on_disk": len(concrete_files_on_disk),
    }


def counter_table(counter: Counter[str], label: str) -> str:
    lines = [f"| {label} | Count |", "| --- | ---: |"]
    if not counter:
        lines.append("| `none` | 0 |")
        return "\n".join(lines)
    for key, count in sorted(counter.items()):
        lines.append(f"| `{key}` | {count} |")
    return "\n".join(lines)


def issue_table(issues: list[dict[str, str]]) -> str:
    if not issues:
        return "No indexing issues were detected."
    lines = ["| Severity | Check | Count |", "| --- | --- | ---: |"]
    counts = Counter((row["severity"], row["check"]) for row in issues)
    for (severity, check), count in sorted(counts.items(), key=lambda item: (item[0][0], item[0][1])):
        lines.append(f"| `{severity}` | `{check}` | {count} |")
    return "\n".join(lines)


def build_summary(stats: dict[str, object], issues: list[dict[str, str]]) -> str:
    severity_counts = Counter(row["severity"] for row in issues)
    queue_status_counts = stats.get("queue_status_counts", Counter())
    render_status_counts = stats.get("render_status_counts", Counter())
    crop_status_counts = stats.get("crop_status_counts", Counter())
    crop_review_counts = stats.get("crop_review_counts", Counter())
    extractability_counts = stats.get("extractability_counts", Counter())
    assert isinstance(queue_status_counts, Counter)
    assert isinstance(render_status_counts, Counter)
    assert isinstance(crop_status_counts, Counter)
    assert isinstance(crop_review_counts, Counter)
    assert isinstance(extractability_counts, Counter)
    return "\n".join(
        [
            "# Figure Index Audit Summary",
            "",
            "Generated by `python3 tools/audit_figure_indexing.py`.",
            "",
            "## Scope",
            "",
            f"- Digitization queue rows: {stats['digitization_queue_rows']}",
            f"- Unique digitization queue IDs: {stats['unique_queue_ids']}",
            f"- Raw figure-source review rows: {stats['figure_source_review_rows']}",
            f"- Validated figure-source review rows: {stats['figure_source_review_validated_rows']}",
            f"- Figure queue audit rows: {stats['figure_queue_audit_rows']}",
            f"- Source-page render rows: {stats['source_page_render_rows']}",
            f"- Accepted visual candidates: {stats['accepted_visual_candidates']}",
            f"- Retained rejected caption rows: {stats['retained_rejected_caption_rows']}",
            f"- Crop-manifest rows: {stats['crop_manifest_rows']}",
            f"- Auto crop proposals: {stats['auto_crop_proposals']}",
            f"- Concrete digitized-data paths referenced: {stats['concrete_digitized_data_paths']}",
            f"- Digitized-data CSV files on disk: {stats['digitized_data_files_on_disk']}",
            "",
            "## Issue Counts",
            "",
            f"- Errors: {severity_counts.get('error', 0)}",
            f"- Warnings: {severity_counts.get('warning', 0)}",
            "",
            issue_table(issues),
            "",
            "## Queue Status",
            "",
            counter_table(queue_status_counts, "Queue audit status"),
            "",
            "## Render And Crop Status",
            "",
            counter_table(render_status_counts, "Render status"),
            "",
            counter_table(crop_status_counts, "Crop status"),
            "",
            counter_table(crop_review_counts, "Crop review status"),
            "",
            counter_table(extractability_counts, "Extractability class"),
            "",
            "## Interpretation",
            "",
            "- `error` rows are structural mismatches in source IDs, paths, pages, hashes, renders, crops, or concrete data-file references.",
            "- `warning` rows are unresolved review/indexing states that can be legitimate work remaining, but should not enter pooled extraction.",
            "- Crop-review PNGs are proposals. They are not final clipped panels until `panel_label`, `final_clip_path`, `digitized_data_path`, units, variance, sample size, digitizer, reviewer, and QA status are filled.",
            "",
        ]
    )


def run_audit() -> tuple[list[dict[str, str]], dict[str, object]]:
    screening_rows = read_csv(SCREENING_LOG)
    literature_rows = read_csv(LITERATURE_MAP)
    queue_rows = read_csv(DIGITIZATION_QUEUE)
    source_rows = read_csv(FIGURE_SOURCE_REVIEW)
    validated_rows = read_csv(FIGURE_SOURCE_REVIEW_VALIDATED)
    candidate_audit_rows = read_csv(FIGURE_CANDIDATE_AUDIT)
    queue_audit_rows = read_csv(FIGURE_QUEUE_AUDIT)
    render_rows = read_csv(SOURCE_PAGE_RENDER_MANIFEST)
    visual_rows = read_csv(FIGURE_VISUAL_REAUDIT)
    crop_rows = read_csv(FIGURE_CROP_MANIFEST)

    issues: list[dict[str, str]] = []
    source_ids = collect_source_ids(
        screening_rows,
        literature_rows,
        queue_rows,
        source_rows,
        validated_rows,
        queue_audit_rows,
        render_rows,
        visual_rows,
        crop_rows,
    )
    audit_prefixes(issues, source_ids)
    pdf_hashes = audit_queue(issues, queue_rows, screening_rows, literature_rows)
    page_counts = audit_source_review(issues, source_rows, validated_rows, queue_rows, pdf_hashes)
    audit_queue_audit(issues, queue_rows, queue_audit_rows, candidate_audit_rows)
    audit_render_manifest(issues, render_rows, queue_audit_rows, page_counts)
    audit_visual_reaudit(issues, visual_rows, render_rows, candidate_audit_rows)
    data_stats = audit_crop_manifest(issues, crop_rows, visual_rows)

    stats: dict[str, object] = {
        "digitization_queue_rows": len(queue_rows),
        "unique_queue_ids": len({row.get("queue_id", "") for row in queue_rows if row.get("queue_id", "")}),
        "figure_source_review_rows": len(source_rows),
        "figure_source_review_validated_rows": len(validated_rows),
        "figure_queue_audit_rows": len(queue_audit_rows),
        "source_page_render_rows": len(render_rows),
        "accepted_visual_candidates": sum(1 for row in visual_rows if row.get("reaudit_row_type") == "accepted_visual_candidate"),
        "retained_rejected_caption_rows": sum(1 for row in visual_rows if row.get("reaudit_row_type") == "retained_caption_rejected"),
        "crop_manifest_rows": len(crop_rows),
        "auto_crop_proposals": sum(1 for row in crop_rows if row.get("crop_status") == "auto_crop_proposal_created"),
        "queue_status_counts": Counter(row.get("queue_audit_status", "") for row in queue_audit_rows),
        "render_status_counts": Counter(row.get("render_status", "") for row in render_rows),
        "crop_status_counts": Counter(row.get("crop_status", "") for row in crop_rows),
        "crop_review_counts": Counter(row.get("crop_review_status", "") for row in crop_rows),
        "extractability_counts": Counter(row.get("extractability_class", "") for row in crop_rows),
        **data_stats,
    }
    return issues, stats


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=FIGURE_INDEX_AUDIT)
    parser.add_argument("--summary", type=Path, default=FIGURE_INDEX_SUMMARY)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warnings are present.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    issues, stats = run_audit()
    write_csv(args.audit_csv, AUDIT_FIELDS, issues)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(build_summary(stats, issues), encoding="utf-8")
    error_count = sum(1 for row in issues if row["severity"] == "error")
    warning_count = sum(1 for row in issues if row["severity"] == "warning")
    print(f"Wrote figure index audit to {args.audit_csv.relative_to(ROOT)}")
    print(f"Wrote figure index summary to {args.summary.relative_to(ROOT)}")
    print(f"Errors: {error_count}")
    print(f"Warnings: {warning_count}")
    if error_count:
        return 1
    if args.strict and warning_count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

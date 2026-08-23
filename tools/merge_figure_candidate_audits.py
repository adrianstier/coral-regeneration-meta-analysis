#!/usr/bin/env python3
"""Merge independent figure/table candidate audits into review artifacts."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVIEW_DIR = ROOT / "digitization" / "source_review"
DEFAULT_BASE_REVIEW = SOURCE_REVIEW_DIR / "FIGURE_SOURCE_REVIEW.csv"
DEFAULT_AUDIT_DIR = SOURCE_REVIEW_DIR / "agent_audits"
DEFAULT_OUTPUT_DIR = SOURCE_REVIEW_DIR

AUDIT_STATUSES = {
    "keep",
    "replace",
    "remove",
    "blocked_missing_pdf",
    "needs_manual_visual_review",
}

AUDIT_COLUMNS = [
    "source_id",
    "paper_title",
    "response_type",
    "queue_id",
    "original_candidate_rank",
    "original_candidate_type",
    "original_candidate_label",
    "original_candidate_page",
    "audit_status",
    "corrected_candidate_type",
    "corrected_candidate_label",
    "corrected_candidate_page",
    "corrected_candidate_text",
    "reason",
    "needs_manual_visual_review",
    "evidence_method",
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


def clean(value: str | None) -> str:
    return " ".join(str(value or "").split())


def candidate_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("source_id", ""),
        row.get("response_type", ""),
        row.get("queue_id", ""),
        row.get("candidate_rank") or row.get("original_candidate_rank", ""),
        clean(row.get("candidate_label") or row.get("original_candidate_label", "")),
        row.get("candidate_page") or row.get("original_candidate_page", ""),
    )


def reviewable_candidate(row: dict[str, str]) -> bool:
    return row.get("review_status") == "candidate_review_needed"


def normalized_audit_row(row: dict[str, str], audit_file: Path) -> dict[str, str]:
    out = {column: row.get(column, "") for column in AUDIT_COLUMNS}
    out["audit_file"] = str(audit_file.relative_to(ROOT))
    status = out.get("audit_status", "").strip()
    out["audit_status"] = status
    out["audit_key_status"] = "valid_status" if status in AUDIT_STATUSES else "invalid_status"
    if not out.get("original_candidate_rank") and status != "replace":
        out["audit_key_status"] = "missing_candidate_rank"
    return out


def load_audits(audit_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not audit_dir.exists():
        return rows
    for path in sorted(audit_dir.glob("figure_candidate_audit_agent*.csv")):
        for row in read_csv(path):
            rows.append(normalized_audit_row(row, path))
    return rows


def audit_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("source_id", ""),
        row.get("response_type", ""),
        row.get("queue_id", ""),
        row.get("original_candidate_rank", ""),
        clean(row.get("original_candidate_label", "")),
        row.get("original_candidate_page", ""),
    )


def validated_status(base_row: dict[str, str], audits: list[dict[str, str]]) -> str:
    if base_row.get("review_status") == "blocked_missing_local_pdf":
        return "blocked_missing_pdf"
    if not reviewable_candidate(base_row):
        return base_row.get("review_status", "")
    if not audits:
        return "pending_agent_review"
    statuses = {row.get("audit_status", "") for row in audits}
    if "replace" in statuses:
        return "candidate_replacement_available"
    if "remove" in statuses:
        return "candidate_rejected"
    if "needs_manual_visual_review" in statuses:
        return "needs_manual_visual_review"
    if statuses == {"keep"}:
        return "candidate_verified"
    return "audit_conflict"


def combine_unique(rows: list[dict[str, str]], field: str) -> str:
    values = []
    seen = set()
    for row in rows:
        value = clean(row.get(field, ""))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return " | ".join(values)


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def build_validated_rows(
    base_rows: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    audits_by_key: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in audit_rows:
        audits_by_key[audit_key(row)].append(row)

    base_keys = {candidate_key(row) for row in base_rows if reviewable_candidate(row)}
    audited_keys = set(audits_by_key)
    missing_keys = base_keys - audited_keys
    extra_keys = audited_keys - base_keys

    validated_rows: list[dict[str, object]] = []
    for row in base_rows:
        key = candidate_key(row)
        matching_audits = audits_by_key.get(key, [])
        audit_status = combine_unique(matching_audits, "audit_status")
        validated_rows.append(
            {
                **row,
                "audit_status": audit_status,
                "validated_review_status": validated_status(row, matching_audits),
                "corrected_candidate_type": combine_unique(matching_audits, "corrected_candidate_type"),
                "corrected_candidate_label": combine_unique(matching_audits, "corrected_candidate_label"),
                "corrected_candidate_page": combine_unique(matching_audits, "corrected_candidate_page"),
                "corrected_candidate_text": combine_unique(matching_audits, "corrected_candidate_text"),
                "audit_reason": combine_unique(matching_audits, "reason"),
                "needs_manual_visual_review_after_audit": combine_unique(matching_audits, "needs_manual_visual_review"),
                "audit_evidence_method": combine_unique(matching_audits, "evidence_method"),
                "audit_file": combine_unique(matching_audits, "audit_file"),
            }
        )

    merged_audits: list[dict[str, object]] = []
    for row in audit_rows:
        key = audit_key(row)
        coverage = "matched_base_candidate"
        if key in extra_keys:
            coverage = "extra_or_stale_audit_candidate"
        elif key in missing_keys:
            coverage = "missing_from_audit"
        merged_audits.append({**row, "coverage_status": coverage})

    summary = {
        "base_review_rows": len(base_rows),
        "base_candidate_rows": len(base_keys),
        "audit_rows": len(audit_rows),
        "matched_candidate_rows": len(base_keys & audited_keys),
        "missing_candidate_rows": len(missing_keys),
        "extra_audit_rows": len(extra_keys),
        "duplicate_audit_keys": sum(1 for rows in audits_by_key.values() if len(rows) > 1),
        "audit_status_counts": Counter(row.get("audit_status", "") for row in audit_rows),
        "validated_status_counts": Counter(row.get("validated_review_status", "") for row in validated_rows),
        "audit_key_status_counts": Counter(row.get("audit_key_status", "") for row in audit_rows),
        "missing_by_source": Counter(key[0] for key in missing_keys),
        "extra_by_source": Counter(key[0] for key in extra_keys),
    }
    return validated_rows, merged_audits, summary


def candidate_rank(row: dict[str, object]) -> int:
    try:
        return int(str(row.get("candidate_rank") or "999999"))
    except ValueError:
        return 999999


def candidate_descriptor(row: dict[str, object]) -> str:
    candidate_type = clean(str(row.get("corrected_candidate_type") or row.get("candidate_type") or "candidate"))
    label = clean(str(row.get("corrected_candidate_label") or row.get("candidate_label") or ""))
    page = clean(str(row.get("corrected_candidate_page") or row.get("candidate_page") or ""))
    if not label or label == "no_valid_candidate_found":
        return ""
    return f"{candidate_type}:{label}:p{page}" if page else f"{candidate_type}:{label}"


def candidate_text(row: dict[str, object]) -> str:
    return clean(str(row.get("corrected_candidate_text") or row.get("candidate_text") or ""))


def row_has_candidate(row: dict[str, object]) -> bool:
    return str(row.get("validated_review_status", "")) in {"candidate_verified", "candidate_replacement_available"}


def build_queue_summary_rows(validated_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in validated_rows:
        grouped[str(row.get("queue_id", ""))].append(row)

    summary_rows: list[dict[str, object]] = []
    for queue_id, rows in sorted(grouped.items(), key=lambda item: item[0]):
        first = rows[0]
        status_counts = Counter(str(row.get("validated_review_status", "")) for row in rows)
        candidate_rows = [row for row in rows if str(row.get("review_status", "")) == "candidate_review_needed"]
        recommended: list[str] = []
        recommended_texts: list[str] = []
        seen = set()
        for row in sorted(rows, key=candidate_rank):
            if not row_has_candidate(row):
                continue
            descriptor = candidate_descriptor(row)
            if not descriptor or descriptor in seen:
                continue
            seen.add(descriptor)
            recommended.append(descriptor)
            text = candidate_text(row)
            if text:
                recommended_texts.append(f"{descriptor} :: {text}")

        rejected = []
        for row in sorted(rows, key=candidate_rank):
            if str(row.get("validated_review_status", "")) != "candidate_rejected":
                continue
            descriptor = f"{row.get('candidate_type', '')}:{row.get('candidate_label', '')}:p{row.get('candidate_page', '')}"
            rejected.append(clean(descriptor))

        if status_counts.get("blocked_missing_pdf"):
            queue_status = "blocked_missing_pdf"
            action = "Retrieve the source PDF before selecting figure/table candidates."
        elif recommended:
            queue_status = "audited_candidate_available"
            action = "Confirm panel/axis details visually, then clip from recommended candidate(s)."
        elif candidate_rows and len(candidate_rows) == status_counts.get("candidate_rejected", 0):
            queue_status = "no_valid_candidate_found"
            action = "Do not clip this response from figures/tables unless a later full-text review finds non-caption evidence."
        else:
            queue_status = "needs_followup_review"
            action = "Resolve pending, conflicting, or incomplete audit status before clipping."

        manual_visual_review = any(truthy(str(row.get("needs_manual_visual_review_after_audit", ""))) for row in rows)
        if manual_visual_review and queue_status == "audited_candidate_available":
            action = "Visually confirm rendered PDF page before clipping; OCR found only partial or in-text evidence."

        summary_rows.append(
            {
                "queue_id": queue_id,
                "queue_audit_status": queue_status,
                "source_id": first.get("source_id", ""),
                "paper_title": first.get("paper_title", ""),
                "response_type": first.get("response_type", ""),
                "source_file_status": first.get("source_file_status", ""),
                "local_relpath": first.get("local_relpath", ""),
                "candidate_rows_reviewed": len(candidate_rows),
                "verified_candidate_rows": status_counts.get("candidate_verified", 0),
                "replacement_candidate_rows": status_counts.get("candidate_replacement_available", 0),
                "rejected_candidate_rows": status_counts.get("candidate_rejected", 0),
                "blocked_rows": status_counts.get("blocked_missing_pdf", 0),
                "recommended_candidate_count": len(recommended),
                "recommended_candidates": "|".join(recommended),
                "recommended_candidate_text": " || ".join(recommended_texts),
                "rejected_original_candidates": "|".join(rejected),
                "needs_manual_visual_review": "yes" if manual_visual_review else "no",
                "recommended_action": action,
            }
        )
    return summary_rows


def counter_table(counter: Counter[str], label: str) -> str:
    lines = [f"| {label} | Count |", "| --- | ---: |"]
    if not counter:
        lines.append("| `none` | 0 |")
        return "\n".join(lines)
    for key, count in sorted(counter.items()):
        lines.append(f"| `{key}` | {count} |")
    return "\n".join(lines)


def build_summary(summary: dict[str, object]) -> str:
    audit_status_counts = summary["audit_status_counts"]
    validated_status_counts = summary["validated_status_counts"]
    audit_key_status_counts = summary["audit_key_status_counts"]
    missing_by_source = summary["missing_by_source"]
    extra_by_source = summary["extra_by_source"]
    queue_status_counts = summary.get("queue_status_counts", Counter())
    manual_visual_review_queue_count = summary.get("manual_visual_review_queue_count", 0)
    assert isinstance(audit_status_counts, Counter)
    assert isinstance(validated_status_counts, Counter)
    assert isinstance(audit_key_status_counts, Counter)
    assert isinstance(missing_by_source, Counter)
    assert isinstance(extra_by_source, Counter)
    assert isinstance(queue_status_counts, Counter)

    return "\n".join(
        [
            "# Figure Candidate Audit Summary",
            "",
            "Generated by `python3 tools/merge_figure_candidate_audits.py`.",
            "",
            f"- Base review rows: {summary['base_review_rows']}",
            f"- Base candidate rows needing review: {summary['base_candidate_rows']}",
            f"- Agent audit rows: {summary['audit_rows']}",
            f"- Matched candidate rows: {summary['matched_candidate_rows']}",
            f"- Missing candidate rows: {summary['missing_candidate_rows']}",
            f"- Extra/stale audit keys: {summary['extra_audit_rows']}",
            f"- Duplicate audit keys: {summary['duplicate_audit_keys']}",
            f"- Queue rows with manual visual-review flags: {manual_visual_review_queue_count}",
            "",
            counter_table(audit_status_counts, "Agent audit status"),
            "",
            counter_table(validated_status_counts, "Validated review status"),
            "",
            counter_table(queue_status_counts, "Queue audit status"),
            "",
            counter_table(audit_key_status_counts, "Audit key status"),
            "",
            "## Missing Audit Coverage By Source",
            "",
            counter_table(missing_by_source, "Source ID"),
            "",
            "## Extra Or Stale Audit Keys By Source",
            "",
            counter_table(extra_by_source, "Source ID"),
            "",
            "## Use",
            "",
            "- Treat `FIGURE_QUEUE_AUDIT_STATUS.csv` as the clipping worklist after independent audit.",
            "- Use `FIGURE_SOURCE_REVIEW_VALIDATED.csv` for row-level candidate evidence, corrections, and rejection reasons.",
            "- Rows marked `candidate_replacement_available` need the corrected label/page confirmed visually before clipping.",
            "- Rows marked `candidate_rejected` should not be clipped unless a later reviewer adds a replacement.",
            "- Rows marked `pending_agent_review`, if present, were not covered by the agent audit and still need review.",
            "",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-review", type=Path, default=DEFAULT_BASE_REVIEW)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    base_rows = read_csv(args.base_review)
    audit_rows = load_audits(args.audit_dir)
    if not base_rows:
        raise SystemExit(f"Missing or empty base review file: {args.base_review}")

    validated_rows, merged_audits, summary = build_validated_rows(base_rows, audit_rows)
    queue_rows = build_queue_summary_rows(validated_rows)
    summary["queue_status_counts"] = Counter(row.get("queue_audit_status", "") for row in queue_rows)
    summary["manual_visual_review_queue_count"] = sum(1 for row in queue_rows if row.get("needs_manual_visual_review") == "yes")
    base_fields = list(base_rows[0].keys())
    validated_fields = base_fields + [
        "audit_status",
        "validated_review_status",
        "corrected_candidate_type",
        "corrected_candidate_label",
        "corrected_candidate_page",
        "corrected_candidate_text",
        "audit_reason",
        "needs_manual_visual_review_after_audit",
        "audit_evidence_method",
        "audit_file",
    ]
    audit_fields = AUDIT_COLUMNS + ["audit_file", "audit_key_status", "coverage_status"]
    queue_fields = [
        "queue_id",
        "queue_audit_status",
        "source_id",
        "paper_title",
        "response_type",
        "source_file_status",
        "local_relpath",
        "candidate_rows_reviewed",
        "verified_candidate_rows",
        "replacement_candidate_rows",
        "rejected_candidate_rows",
        "blocked_rows",
        "recommended_candidate_count",
        "recommended_candidates",
        "recommended_candidate_text",
        "rejected_original_candidates",
        "needs_manual_visual_review",
        "recommended_action",
    ]

    write_csv(args.output_dir / "FIGURE_SOURCE_REVIEW_VALIDATED.csv", validated_fields, validated_rows)
    write_csv(args.output_dir / "FIGURE_CANDIDATE_AUDIT.csv", audit_fields, merged_audits)
    write_csv(args.output_dir / "FIGURE_QUEUE_AUDIT_STATUS.csv", queue_fields, queue_rows)
    (args.output_dir / "FIGURE_CANDIDATE_AUDIT_SUMMARY.md").write_text(build_summary(summary), encoding="utf-8")

    print(f"Wrote merged figure candidate audit artifacts to {args.output_dir.relative_to(ROOT)}")
    print(f"Base candidate rows: {summary['base_candidate_rows']}")
    print(f"Agent audit rows: {summary['audit_rows']}")
    print(f"Missing candidate rows: {summary['missing_candidate_rows']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

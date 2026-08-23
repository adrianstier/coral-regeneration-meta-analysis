#!/usr/bin/env python3
"""Build a second-layer visual audit over rendered figure/table source pages."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVIEW_DIR = ROOT / "digitization" / "source_review"
FIGURE_DIR = ROOT / "digitization" / "figures"
SOURCE_PAGE_MANIFEST = FIGURE_DIR / "SOURCE_PAGE_RENDER_MANIFEST.csv"
CAPTION_AUDIT = SOURCE_REVIEW_DIR / "FIGURE_CANDIDATE_AUDIT.csv"
VISUAL_REAUDIT = SOURCE_REVIEW_DIR / "FIGURE_VISUAL_REAUDIT.csv"
VISUAL_REAUDIT_SUMMARY = SOURCE_REVIEW_DIR / "FIGURE_VISUAL_REAUDIT_SUMMARY.md"


VISUAL_REAUDIT_FIELDS = [
    "reaudit_row_type",
    "visual_reaudit_status",
    "crop_readiness",
    "extractability_class",
    "queue_id",
    "source_id",
    "paper_title",
    "response_type",
    "candidate_descriptor",
    "candidate_type",
    "candidate_label",
    "pdf_page",
    "source_page_render",
    "render_status",
    "image_width",
    "image_height",
    "image_nonblank",
    "candidate_text",
    "caption_audit_status",
    "caption_rejection_reason",
    "original_candidate_type",
    "original_candidate_label",
    "original_candidate_page",
    "audit_file",
    "recommended_action",
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


def image_metadata(path: Path) -> tuple[str, str, str]:
    if not path.exists():
        return "", "", "missing_file"
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as image:
            width, height = image.size
            stat = ImageStat.Stat(image.convert("L"))
            extrema = image.convert("L").getextrema()
            nonblank = "yes" if stat.stddev and stat.stddev[0] > 1 and extrema[0] != extrema[1] else "no"
            return str(width), str(height), nonblank
    except Exception as exc:  # pragma: no cover - defensive for corrupt image files.
        return "", "", f"image_error: {clean(exc)[:120]}"


def extractability_class(candidate_type: str, candidate_text: str) -> str:
    text = candidate_text.lower()
    numeric_terms = [
        "mean",
        "rate",
        "percent",
        "%",
        "se",
        "sd",
        "standard error",
        "standard deviation",
        "error bars",
        "n =",
        "anova",
        "regression",
        "mortality",
        "survival",
        "growth",
        "area",
        "average",
        "averaged",
        "cumulative",
        "fecundity",
        "function of time",
        "g cm",
        "probability",
        "proportion",
        "weight",
    ]
    visual_terms = [
        "representative image",
        "representative images",
        "photograph",
        "photographs",
        "photo",
        "histolog",
        "micrograph",
        "time series photographs",
        "images showing",
    ]
    has_numeric = any(term in text for term in numeric_terms)
    has_visual = any(term in text for term in visual_terms)
    if candidate_type == "table":
        return "table_transcription_candidate"
    if has_numeric and has_visual:
        return "mixed_visual_quantitative_candidate"
    if has_numeric:
        return "quantitative_plot_candidate"
    if has_visual:
        return "photo_or_mechanism_candidate"
    return "visual_review_needed"


def accepted_row_status(row: dict[str, str], width: str, height: str, nonblank: str) -> tuple[str, str]:
    if row.get("render_status") not in {"rendered", "already_rendered"}:
        return "render_not_available", "cannot_crop_until_page_render_exists"
    if nonblank != "yes":
        return "source_page_image_problem", "inspect_or_rerender_source_page"
    if not width or not height:
        return "source_page_image_problem", "inspect_or_rerender_source_page"
    return "source_page_image_verified", "ready_for_manual_crop_or_table_transcription"


def build_visual_reaudit_rows(
    render_rows: list[dict[str, str]],
    caption_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in render_rows:
        render_relpath = row.get("source_page_render", "")
        width, height, nonblank = image_metadata(ROOT / render_relpath) if render_relpath else ("", "", "missing_render_path")
        visual_status, crop_readiness = accepted_row_status(row, width, height, nonblank)
        extractability = extractability_class(row.get("candidate_type", ""), row.get("candidate_text", ""))
        out.append(
            {
                "reaudit_row_type": "accepted_visual_candidate",
                "visual_reaudit_status": visual_status,
                "crop_readiness": crop_readiness,
                "extractability_class": extractability,
                "queue_id": row.get("queue_id", ""),
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "response_type": row.get("response_type", ""),
                "candidate_descriptor": row.get("candidate_descriptor", ""),
                "candidate_type": row.get("candidate_type", ""),
                "candidate_label": row.get("candidate_label", ""),
                "pdf_page": row.get("pdf_page", ""),
                "source_page_render": render_relpath,
                "render_status": row.get("render_status", ""),
                "image_width": width,
                "image_height": height,
                "image_nonblank": nonblank,
                "candidate_text": row.get("candidate_text", ""),
                "caption_audit_status": "accepted",
                "recommended_action": row.get(
                    "next_action",
                    "Crop exact figure/table panel from rendered source page before digitization.",
                ),
            }
        )

    for row in caption_rows:
        if row.get("audit_status") != "remove":
            continue
        out.append(
            {
                "reaudit_row_type": "retained_caption_rejected",
                "visual_reaudit_status": "caption_rejected_retained",
                "crop_readiness": "do_not_crop_from_caption_audit",
                "extractability_class": "not_a_valid_visual_candidate",
                "queue_id": row.get("queue_id", ""),
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "response_type": row.get("response_type", ""),
                "candidate_type": row.get("corrected_candidate_type") or row.get("original_candidate_type", ""),
                "candidate_label": row.get("corrected_candidate_label") or row.get("original_candidate_label", ""),
                "pdf_page": row.get("corrected_candidate_page") or row.get("original_candidate_page", ""),
                "caption_audit_status": row.get("audit_status", ""),
                "caption_rejection_reason": row.get("reason", ""),
                "original_candidate_type": row.get("original_candidate_type", ""),
                "original_candidate_label": row.get("original_candidate_label", ""),
                "original_candidate_page": row.get("original_candidate_page", ""),
                "audit_file": row.get("audit_file", ""),
                "recommended_action": "Retain as rejected evidence; do not crop unless a later reviewer overturns the caption audit.",
            }
        )
    return out


def counter_table(counter: Counter[str], label: str) -> str:
    lines = [f"| {label} | Count |", "| --- | ---: |"]
    if not counter:
        lines.append("| `none` | 0 |")
        return "\n".join(lines)
    for key, value in sorted(counter.items()):
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def build_summary(rows: list[dict[str, object]]) -> str:
    row_type_counts = Counter(clean(row.get("reaudit_row_type", "")) for row in rows)
    status_counts = Counter(clean(row.get("visual_reaudit_status", "")) for row in rows)
    crop_counts = Counter(clean(row.get("crop_readiness", "")) for row in rows)
    extractability_counts = Counter(clean(row.get("extractability_class", "")) for row in rows)
    render_problem_rows = [
        row
        for row in rows
        if row.get("reaudit_row_type") == "accepted_visual_candidate"
        and row.get("visual_reaudit_status") != "source_page_image_verified"
    ]
    return "\n".join(
        [
            "# Figure Visual Reaudit Summary",
            "",
            "Generated by `python3 tools/build_figure_visual_reaudit.py`.",
            "",
            f"- Total reaudit rows: {len(rows)}",
            f"- Accepted visual candidates reaudit rows: {row_type_counts.get('accepted_visual_candidate', 0)}",
            f"- Retained rejected caption rows: {row_type_counts.get('retained_caption_rejected', 0)}",
            f"- Accepted visual candidates with render/image problems: {len(render_problem_rows)}",
            "",
            counter_table(row_type_counts, "Row type"),
            "",
            counter_table(status_counts, "Visual reaudit status"),
            "",
            counter_table(crop_counts, "Crop readiness"),
            "",
            counter_table(extractability_counts, "Extractability class"),
            "",
            "## Rules",
            "",
            "- Accepted visual candidates are source-page verified, not final crops.",
            "- Retained rejected caption rows stay in the audit so rejected evidence is traceable.",
            "- Do not pool figure-derived values until exact crop path, panel, axes, units, variance, sample-size source, and digitized/transcribed data are recorded.",
            "",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-page-manifest", type=Path, default=SOURCE_PAGE_MANIFEST)
    parser.add_argument("--caption-audit", type=Path, default=CAPTION_AUDIT)
    parser.add_argument("--output", type=Path, default=VISUAL_REAUDIT)
    parser.add_argument("--summary", type=Path, default=VISUAL_REAUDIT_SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    render_rows = read_csv(args.source_page_manifest)
    caption_rows = read_csv(args.caption_audit)
    if not render_rows:
        raise SystemExit(f"Missing or empty source page manifest: {args.source_page_manifest}")
    if not caption_rows:
        raise SystemExit(f"Missing or empty caption audit: {args.caption_audit}")

    rows = build_visual_reaudit_rows(render_rows, caption_rows)
    write_csv(args.output, VISUAL_REAUDIT_FIELDS, rows)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(build_summary(rows), encoding="utf-8")

    print(f"Wrote figure visual reaudit to {args.output.relative_to(ROOT)}")
    print(f"Accepted visual candidates: {sum(row['reaudit_row_type'] == 'accepted_visual_candidate' for row in rows)}")
    print(f"Retained rejected caption rows: {sum(row['reaudit_row_type'] == 'retained_caption_rejected' for row in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

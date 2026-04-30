#!/usr/bin/env python3
"""Create reproducible crop proposals from the figure visual reaudit."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVIEW_DIR = ROOT / "digitization" / "source_review"
FIGURE_DIR = ROOT / "digitization" / "figures"
VISUAL_REAUDIT = SOURCE_REVIEW_DIR / "FIGURE_VISUAL_REAUDIT.csv"
SOURCE_PAGE_MANIFEST = FIGURE_DIR / "SOURCE_PAGE_RENDER_MANIFEST.csv"
CROP_REVIEW_DIR = FIGURE_DIR / "crop_review"
CROP_MANIFEST = FIGURE_DIR / "FIGURE_CROP_MANIFEST.csv"
CROP_SUMMARY = FIGURE_DIR / "FIGURE_CROP_SUMMARY.md"


CROP_FIELDS = [
    "crop_row_type",
    "crop_status",
    "crop_review_status",
    "extractability_class",
    "queue_id",
    "source_id",
    "paper_title",
    "response_type",
    "candidate_descriptor",
    "candidate_type",
    "candidate_label",
    "pdf_page",
    "local_relpath",
    "source_page_render",
    "source_page_width",
    "source_page_height",
    "crop_path",
    "crop_box_xywh",
    "crop_method",
    "caption_locator_status",
    "panel_label",
    "final_clip_path",
    "digitized_data_path",
    "axis_units_status",
    "variance_sample_size_status",
    "caption_text",
    "rejection_reason",
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


def safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return token or "candidate"


def normalized_label(value: str) -> str:
    text = value.lower().replace("fig.", "figure").replace("fig ", "figure ")
    return re.sub(r"[^a-z0-9]+", "", text)


def source_manifest_by_candidate(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row.get("queue_id", ""), row.get("candidate_descriptor", "")): row
        for row in rows
        if row.get("queue_id") and row.get("candidate_descriptor")
    }


def run_pdftotext_bbox(pdf_path: Path, page: str) -> tuple[str, str]:
    proc = subprocess.run(
        ["pdftotext", "-bbox", "-f", page, "-l", page, str(pdf_path), "-"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return "", clean(proc.stderr)
    return proc.stdout, ""


def parse_bbox_lines(bbox_html: str) -> tuple[float, float, list[dict[str, object]]]:
    if not bbox_html.strip():
        return 0.0, 0.0, []
    try:
        root = ET.fromstring(bbox_html)
    except ET.ParseError:
        return 0.0, 0.0, []
    page = root.find(".//{*}page")
    if page is None:
        return 0.0, 0.0, []
    page_width = float(page.attrib.get("width", "0") or 0)
    page_height = float(page.attrib.get("height", "0") or 0)
    words = []
    for word in page.findall(".//{*}word"):
        text = "".join(word.itertext())
        if not clean(text):
            continue
        words.append(
            {
                "text": text,
                "x_min": float(word.attrib["xMin"]),
                "y_min": float(word.attrib["yMin"]),
                "x_max": float(word.attrib["xMax"]),
                "y_max": float(word.attrib["yMax"]),
            }
        )
    words.sort(key=lambda item: (float(item["y_min"]), float(item["x_min"])))
    lines: list[list[dict[str, object]]] = []
    for word in words:
        y_mid = (float(word["y_min"]) + float(word["y_max"])) / 2
        for line in reversed(lines[-8:]):
            line_y_mid = sum((float(w["y_min"]) + float(w["y_max"])) / 2 for w in line) / len(line)
            if abs(y_mid - line_y_mid) <= 4:
                line.append(word)
                break
        else:
            lines.append([word])

    out = []
    for line in lines:
        line.sort(key=lambda item: float(item["x_min"]))
        text = clean(" ".join(str(word["text"]) for word in line))
        out.append(
            {
                "text": text,
                "norm": normalized_label(text),
                "x_min": min(float(word["x_min"]) for word in line),
                "y_min": min(float(word["y_min"]) for word in line),
                "x_max": max(float(word["x_max"]) for word in line),
                "y_max": max(float(word["y_max"]) for word in line),
            }
        )
    return page_width, page_height, out


def caption_start_lines(lines: list[dict[str, object]]) -> list[dict[str, object]]:
    out = []
    for line in lines:
        norm = str(line.get("norm", ""))
        if norm.startswith("figure") or norm.startswith("table"):
            out.append(line)
    return out


def line_column(line: dict[str, object], page_width: float) -> str:
    x_min = float(line.get("x_min", 0))
    x_max = float(line.get("x_max", 0))
    if x_min < page_width * 0.25 and x_max > page_width * 0.75:
        return "full"
    center = (x_min + x_max) / 2
    if center < page_width * 0.48:
        return "left"
    if center > page_width * 0.52:
        return "right"
    return "full"


def find_caption_line(
    lines: list[dict[str, object]],
    candidate_label: str,
) -> tuple[str, dict[str, object] | None]:
    target = normalized_label(candidate_label)
    if not target:
        return "missing_candidate_label", None
    starts = caption_start_lines(lines)
    for line in starts:
        norm = str(line.get("norm", ""))
        if norm.startswith(target) or target in norm[: max(len(target) + 12, 20)]:
            return "caption_bbox_found", line
    for line in lines:
        norm = str(line.get("norm", ""))
        if norm.startswith(target) or target in norm[: max(len(target) + 12, 20)]:
            return "label_bbox_found_not_caption_start", line
    return "caption_bbox_not_found", None


def image_content_bbox(image_path: Path, region: tuple[int, int, int, int] | None = None) -> tuple[int, int, int, int]:
    from PIL import Image

    with Image.open(image_path) as image:
        gray = image.convert("L")
        width, height = gray.size
        if region is None:
            region = (0, 0, width, height)
        x0, y0, x1, y1 = region
        x0 = max(0, min(x0, width - 1))
        x1 = max(x0 + 1, min(x1, width))
        y0 = max(0, min(y0, height - 1))
        y1 = max(y0 + 1, min(y1, height))
        crop = gray.crop((x0, y0, x1, y1))
        mask = crop.point(lambda pixel: 255 if pixel < 245 else 0)
        content = mask.getbbox()
        if content is None:
            return x0, y0, x1, y1
        left, top, right, bottom = content
        pad = 18
        return (
            max(0, x0 + left - pad),
            max(0, y0 + top - pad),
            min(width, x0 + right + pad),
            min(height, y0 + bottom + pad),
        )


def proposal_region(
    image_path: Path,
    page_width: float,
    page_height: float,
    lines: list[dict[str, object]],
    caption_line: dict[str, object] | None,
) -> tuple[str, tuple[int, int, int, int]]:
    from PIL import Image

    with Image.open(image_path) as image:
        image_width, image_height = image.size
    if not caption_line or page_width <= 0 or page_height <= 0:
        return "page_content_bbox_fallback", image_content_bbox(image_path)

    scale_x = image_width / page_width
    scale_y = image_height / page_height
    column = line_column(caption_line, page_width)
    if column == "left":
        x0_pdf, x1_pdf = page_width * 0.04, page_width * 0.52
    elif column == "right":
        x0_pdf, x1_pdf = page_width * 0.46, page_width * 0.96
    else:
        x0_pdf, x1_pdf = page_width * 0.04, page_width * 0.96

    starts = [line for line in caption_start_lines(lines) if line_column(line, page_width) == column]
    caption_y = float(caption_line["y_min"])
    prev_y = max([float(line["y_min"]) for line in starts if float(line["y_min"]) < caption_y - 3], default=None)
    next_y = min([float(line["y_min"]) for line in starts if float(line["y_min"]) > caption_y + 3], default=None)
    content_top = page_height * 0.04
    content_bottom = page_height * 0.96
    if prev_y is None:
        y0_pdf = content_top
    else:
        y0_pdf = (prev_y + caption_y) / 2
    if next_y is None:
        y1_pdf = content_bottom
    else:
        y1_pdf = (caption_y + next_y) / 2
    y0_pdf = min(y0_pdf, float(caption_line["y_min"]) - 40)
    y1_pdf = max(y1_pdf, float(caption_line["y_max"]) + 40)
    x0 = int(x0_pdf * scale_x)
    x1 = int(x1_pdf * scale_x)
    y0 = int(max(0, y0_pdf) * scale_y)
    y1 = int(min(page_height, y1_pdf) * scale_y)
    tightened = image_content_bbox(image_path, (x0, y0, x1, y1))
    return "caption_segment_content_bbox", tightened


def crop_image(source_path: Path, crop_path: Path, box: tuple[int, int, int, int]) -> None:
    from PIL import Image

    crop_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image.crop(box).save(crop_path)


def crop_filename(row: dict[str, str], sequence: int) -> str:
    source = row.get("source_id", "")[:8] or "source"
    response = safe_token(row.get("response_type", "response"))
    kind = safe_token(row.get("candidate_type", "candidate"))
    label = safe_token(row.get("candidate_label", "label"))
    page = safe_token(row.get("pdf_page", "page"))
    return f"{source}__{response}__{kind}-{label}__page-{page}__crop-{sequence:03d}.png"


def final_clip_path(row: dict[str, str]) -> str:
    source = row.get("source_id", "")[:8] or "source"
    response = safe_token(row.get("response_type", "response"))
    kind = safe_token(row.get("candidate_type", "candidate"))
    label = safe_token(row.get("candidate_label", "label"))
    return f"digitization/figures/{source}__{response}__{kind}-{label}_panel-<panel>.png"


def data_path_rule(row: dict[str, str]) -> str:
    source = row.get("source_id", "")[:8] or "source"
    response = safe_token(row.get("response_type", "response"))
    kind = safe_token(row.get("candidate_type", "candidate"))
    label = safe_token(row.get("candidate_label", "label"))
    return f"digitization/data/{source}__{response}__{kind}-{label}_panel-<panel>.csv"


def build_crop_rows(
    visual_rows: list[dict[str, str]],
    source_manifest_rows: list[dict[str, str]],
    write_crops: bool = True,
) -> list[dict[str, object]]:
    source_lookup = source_manifest_by_candidate(source_manifest_rows)
    bbox_cache: dict[tuple[str, str], tuple[float, float, list[dict[str, object]], str]] = {}
    sequence_by_base: defaultdict[str, int] = defaultdict(int)
    out: list[dict[str, object]] = []

    for row in visual_rows:
        if row.get("reaudit_row_type") != "accepted_visual_candidate":
            out.append(
                {
                    "crop_row_type": "retained_caption_rejected",
                    "crop_status": "retained_rejected_not_cropped",
                    "crop_review_status": "do_not_crop_from_caption_audit",
                    "extractability_class": row.get("extractability_class", ""),
                    "queue_id": row.get("queue_id", ""),
                    "source_id": row.get("source_id", ""),
                    "paper_title": row.get("paper_title", ""),
                    "response_type": row.get("response_type", ""),
                    "candidate_type": row.get("candidate_type", ""),
                    "candidate_label": row.get("candidate_label", ""),
                    "pdf_page": row.get("pdf_page", ""),
                    "rejection_reason": row.get("caption_rejection_reason", ""),
                    "recommended_action": "Retained for traceability; do not crop unless caption audit is overturned.",
                }
            )
            continue

        key = (row.get("queue_id", ""), row.get("candidate_descriptor", ""))
        source_row = source_lookup.get(key, {})
        local_relpath = source_row.get("local_relpath", "")
        source_page_render = row.get("source_page_render", "")
        source_path = ROOT / source_page_render
        pdf_page = row.get("pdf_page", "")
        pdf_path = ROOT / local_relpath
        caption_status = "caption_bbox_not_checked"
        method = "not_cropped"
        box = (0, 0, 0, 0)
        page_width = 0.0
        page_height = 0.0
        lines: list[dict[str, object]] = []
        if source_path.exists() and pdf_path.exists() and pdf_page:
            bbox_key = (local_relpath, pdf_page)
            if bbox_key not in bbox_cache:
                bbox_html, bbox_error = run_pdftotext_bbox(pdf_path, pdf_page)
                if bbox_error:
                    bbox_cache[bbox_key] = (0.0, 0.0, [], bbox_error)
                else:
                    parsed_width, parsed_height, parsed_lines = parse_bbox_lines(bbox_html)
                    bbox_cache[bbox_key] = (parsed_width, parsed_height, parsed_lines, "")
            page_width, page_height, lines, bbox_error = bbox_cache[bbox_key]
            if bbox_error:
                caption_status = f"pdftotext_bbox_failed: {bbox_error[:120]}"
            else:
                caption_status, caption_line = find_caption_line(lines, row.get("candidate_label", ""))
                method, box = proposal_region(source_path, page_width, page_height, lines, caption_line)
        elif not source_path.exists():
            caption_status = "source_page_render_missing"
        elif not pdf_path.exists():
            caption_status = "local_pdf_missing"
        else:
            caption_status = "pdf_page_missing"

        crop_relpath = ""
        crop_status = "crop_proposal_not_created"
        if source_path.exists() and box[2] > box[0] and box[3] > box[1]:
            base = f"{row.get('source_id', '')[:8]}__{safe_token(row.get('response_type', ''))}"
            sequence_by_base[base] += 1
            crop_relpath = str((CROP_REVIEW_DIR / crop_filename(row, sequence_by_base[base])).relative_to(ROOT))
            if write_crops:
                crop_image(source_path, ROOT / crop_relpath, box)
            crop_status = "auto_crop_proposal_created"

        x0, y0, x1, y1 = box
        out.append(
            {
                "crop_row_type": "accepted_visual_candidate",
                "crop_status": crop_status,
                "crop_review_status": "needs_human_crop_box_qa",
                "extractability_class": row.get("extractability_class", ""),
                "queue_id": row.get("queue_id", ""),
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "response_type": row.get("response_type", ""),
                "candidate_descriptor": row.get("candidate_descriptor", ""),
                "candidate_type": row.get("candidate_type", ""),
                "candidate_label": row.get("candidate_label", ""),
                "pdf_page": pdf_page,
                "local_relpath": local_relpath,
                "source_page_render": source_page_render,
                "source_page_width": row.get("image_width", ""),
                "source_page_height": row.get("image_height", ""),
                "crop_path": crop_relpath,
                "crop_box_xywh": f"{x0},{y0},{x1 - x0},{y1 - y0}" if crop_relpath else "",
                "crop_method": method,
                "caption_locator_status": caption_status,
                "panel_label": "all_unverified",
                "final_clip_path": final_clip_path(row),
                "digitized_data_path": data_path_rule(row),
                "axis_units_status": "not_checked",
                "variance_sample_size_status": "not_checked",
                "caption_text": row.get("candidate_text", ""),
                "recommended_action": "Review crop proposal against source page; adjust crop box and panel label before treating as a final clip.",
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
    crop_row_type = Counter(clean(row.get("crop_row_type", "")) for row in rows)
    crop_status = Counter(clean(row.get("crop_status", "")) for row in rows)
    crop_review_status = Counter(clean(row.get("crop_review_status", "")) for row in rows)
    extractability = Counter(clean(row.get("extractability_class", "")) for row in rows)
    caption_locator = Counter(clean(row.get("caption_locator_status", "")) for row in rows if row.get("caption_locator_status"))
    return "\n".join(
        [
            "# Figure Crop Summary",
            "",
            "Generated by `python3 tools/build_figure_crop_manifest.py`.",
            "",
            f"- Total crop-manifest rows: {len(rows)}",
            f"- Auto crop proposals: {crop_status.get('auto_crop_proposal_created', 0)}",
            f"- Retained rejected rows not cropped: {crop_status.get('retained_rejected_not_cropped', 0)}",
            "",
            counter_table(crop_row_type, "Crop row type"),
            "",
            counter_table(crop_status, "Crop status"),
            "",
            counter_table(crop_review_status, "Crop review status"),
            "",
            counter_table(extractability, "Extractability class"),
            "",
            counter_table(caption_locator, "Caption locator status"),
            "",
            "## Rules",
            "",
            "- Files under `digitization/figures/crop_review/` are reproducible crop proposals, not final QA-passed clips.",
            "- Every proposed crop is marked `needs_human_crop_box_qa` until a reviewer confirms the exact panel/table boundary, axes, units, variance, and sample-size source.",
            "- Rows marked `retained_rejected_not_cropped` preserve rejected evidence and remain outside the crop queue.",
            "",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-reaudit", type=Path, default=VISUAL_REAUDIT)
    parser.add_argument("--source-page-manifest", type=Path, default=SOURCE_PAGE_MANIFEST)
    parser.add_argument("--crop-manifest", type=Path, default=CROP_MANIFEST)
    parser.add_argument("--summary", type=Path, default=CROP_SUMMARY)
    parser.add_argument("--no-write-crops", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    visual_rows = read_csv(args.visual_reaudit)
    source_manifest_rows = read_csv(args.source_page_manifest)
    if not visual_rows:
        raise SystemExit(f"Missing or empty visual reaudit: {args.visual_reaudit}")
    if not source_manifest_rows:
        raise SystemExit(f"Missing or empty source page manifest: {args.source_page_manifest}")
    rows = build_crop_rows(visual_rows, source_manifest_rows, write_crops=not args.no_write_crops)
    write_csv(args.crop_manifest, CROP_FIELDS, rows)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(build_summary(rows), encoding="utf-8")
    print(f"Wrote figure crop manifest to {args.crop_manifest.relative_to(ROOT)}")
    print(f"Crop manifest rows: {len(rows)}")
    print(f"Auto crop proposals: {sum(row['crop_status'] == 'auto_crop_proposal_created' for row in rows)}")
    print(f"Retained rejected rows: {sum(row['crop_status'] == 'retained_rejected_not_cropped' for row in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

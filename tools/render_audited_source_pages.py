#!/usr/bin/env python3
"""Render audited source PDF pages for figure/table clipping review."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE_AUDIT = ROOT / "digitization" / "source_review" / "FIGURE_QUEUE_AUDIT_STATUS.csv"
FIGURE_DIR = ROOT / "digitization" / "figures"
SOURCE_PAGE_DIR = FIGURE_DIR / "source_pages"
MANIFEST = FIGURE_DIR / "SOURCE_PAGE_RENDER_MANIFEST.csv"


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


def safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return token or "candidate"


def parse_candidate_descriptor(descriptor: str) -> tuple[str, str, str]:
    match = re.match(r"^(?P<kind>[^:]+):(?P<label>.+):p(?P<page>\d+)$", descriptor)
    if not match:
        return "", "", ""
    return match.group("kind"), match.group("label"), match.group("page")


def candidate_text_by_descriptor(row: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in row.get("recommended_candidate_text", "").split(" || "):
        if " :: " not in item:
            continue
        descriptor, text = item.split(" :: ", 1)
        out[descriptor] = text
    return out


def source_page_path(source_id: str, page: str) -> Path:
    return SOURCE_PAGE_DIR / f"{source_id[:8]}__page-{int(page):03d}.png"


def render_page(pdf_path: Path, page: str, output_png: Path, dpi: int, force: bool) -> str:
    if not pdf_path.exists():
        return "missing_pdf"
    if output_png.exists() and not force:
        return "already_rendered"
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_root = output_png.with_suffix("")
    proc = subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(int(page)),
            "-l",
            str(int(page)),
            "-r",
            str(dpi),
            "-png",
            "-singlefile",
            str(pdf_path),
            str(output_root),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return f"render_failed: {clean(proc.stderr)[:200]}"
    if not output_png.exists():
        return "render_failed: output_missing"
    return "rendered"


def build_manifest_rows(queue_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in queue_rows:
        descriptor_text = candidate_text_by_descriptor(row)
        for descriptor in [item for item in row.get("recommended_candidates", "").split("|") if item]:
            candidate_type, label, page = parse_candidate_descriptor(descriptor)
            render_relpath = ""
            if page:
                render_relpath = str(source_page_path(row.get("source_id", ""), page).relative_to(ROOT))
            rows.append(
                {
                    "queue_id": row.get("queue_id", ""),
                    "queue_audit_status": row.get("queue_audit_status", ""),
                    "source_id": row.get("source_id", ""),
                    "paper_title": row.get("paper_title", ""),
                    "response_type": row.get("response_type", ""),
                    "local_relpath": row.get("local_relpath", ""),
                    "candidate_descriptor": descriptor,
                    "candidate_type": candidate_type,
                    "candidate_label": label,
                    "pdf_page": page,
                    "source_page_render": render_relpath,
                    "render_status": "pending",
                    "candidate_text": descriptor_text.get(descriptor, ""),
                    "next_action": "Crop exact figure/table panel from rendered source page; do not pool until panel, axes, units, variance, and sample size are verified.",
                }
            )
    return rows


def render_manifest_pages(rows: list[dict[str, object]], dpi: int, force: bool) -> None:
    status_by_render: dict[str, str] = {}
    path_by_render: dict[str, Path] = {}
    for row in rows:
        render_relpath = str(row.get("source_page_render", ""))
        page = str(row.get("pdf_page", ""))
        local_relpath = str(row.get("local_relpath", ""))
        if not render_relpath or not page:
            row["render_status"] = "no_page_to_render"
            continue
        if render_relpath not in status_by_render:
            output_png = ROOT / render_relpath
            pdf_path = ROOT / local_relpath
            status_by_render[render_relpath] = render_page(pdf_path, page, output_png, dpi, force)
            path_by_render[render_relpath] = output_png
        row["render_status"] = status_by_render[render_relpath]
        if path_by_render[render_relpath].exists():
            row["source_page_render"] = str(path_by_render[render_relpath].relative_to(ROOT))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-audit", type=Path, default=QUEUE_AUDIT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    queue_rows = read_csv(args.queue_audit)
    if not queue_rows:
        raise SystemExit(f"Missing or empty queue audit file: {args.queue_audit}")
    rows = build_manifest_rows(queue_rows)
    render_manifest_pages(rows, args.dpi, args.force)
    write_csv(
        args.manifest,
        [
            "queue_id",
            "queue_audit_status",
            "source_id",
            "paper_title",
            "response_type",
            "local_relpath",
            "candidate_descriptor",
            "candidate_type",
            "candidate_label",
            "pdf_page",
            "source_page_render",
            "render_status",
            "candidate_text",
            "next_action",
        ],
        rows,
    )
    rendered_pages = {row["source_page_render"] for row in rows if row.get("source_page_render") and (ROOT / str(row["source_page_render"])).exists()}
    failed = [row for row in rows if str(row.get("render_status", "")).startswith("render_failed") or row.get("render_status") == "missing_pdf"]
    print(f"Wrote source page render manifest to {args.manifest.relative_to(ROOT)}")
    print(f"Candidate rows: {len(rows)}")
    print(f"Rendered page images: {len(rendered_pages)}")
    print(f"Failed rows: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

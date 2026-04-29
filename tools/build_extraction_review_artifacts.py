#!/usr/bin/env python3
"""Build source-review queues for figure digitization and legacy extraction QA."""

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
PIPELINE_DIR = ROOT / "pipeline"
DATA_DIR = ROOT / "data"
DIGITIZATION_DIR = ROOT / "digitization"
SOURCE_REVIEW_DIR = DIGITIZATION_DIR / "source_review"

DIGITIZATION_QUEUE = PIPELINE_DIR / "DIGITIZATION_FIGURE_QUEUE.csv"
EXTRACTION_WORKPLAN = PIPELINE_DIR / "EXTRACTION_WORKPLAN.csv"
SCREENING_LOG = DATA_DIR / "screening" / "SCREENING_LOG_FINAL.csv"
SOURCE_RETRIEVAL_LOG = DATA_DIR / "literature" / "SOURCE_RETRIEVAL_LOG.csv"

EXTRACTION_TABLES = {
    "EXTRACTION_RATES.csv": DATA_DIR / "extraction" / "EXTRACTION_RATES.csv",
    "EXTRACTION_FITNESS.csv": DATA_DIR / "extraction" / "EXTRACTION_FITNESS.csv",
    "EXTRACTION_SURVIVAL.csv": DATA_DIR / "extraction" / "EXTRACTION_SURVIVAL.csv",
}

CAPTION_START = re.compile(
    r"^\s*((?:Supplementary\s+)?(?:Fig(?:ure)?\.?|Table)\s*\.?\s*(?:S?\d+[A-Za-z]?|[IVXLC]+))[\s.:;\-]*(.*)$",
    re.IGNORECASE,
)
MENTION_LABELS = re.compile(
    r"\b(Figs?\.?|Figures?|Tables?)\s*\.?\s*((?:S?\d+[A-Za-z]?)(?:\s*(?:,|and|-)\s*S?\d+[A-Za-z]?)*)",
    re.IGNORECASE,
)

RESPONSE_TERMS = {
    "rate": [
        "regeneration",
        "regenerate",
        "healing",
        "recovery",
        "repair",
        "lesion",
        "wound",
        "tissue",
        "area",
        "rate",
        "time",
    ],
    "growth": [
        "growth",
        "calcification",
        "biomass",
        "extension",
        "linear",
        "skeletal",
        "weight",
        "mass",
        "area",
    ],
    "reproduction": [
        "reproduction",
        "reproductive",
        "fecundity",
        "oocyte",
        "oocytes",
        "egg",
        "eggs",
        "gamete",
        "gametes",
        "planula",
        "gonad",
    ],
    "survival": [
        "survival",
        "survivorship",
        "mortality",
        "dead",
        "death",
        "partial mortality",
        "tissue loss",
    ],
}

REQUIRED_LEGACY_PROVENANCE_FIELDS = [
    "source_id",
    "paper_title",
    "local_relpath",
    "response_type",
    "figure_or_table_label",
    "page",
    "panel_label",
    "extraction_provenance",
    "units",
    "variance_type",
    "sample_size",
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clean_text(text: str, limit: int | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if limit is not None and len(cleaned) > limit:
        return cleaned[: limit - 3].rstrip() + "..."
    return cleaned


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def local_pdf_status(local_relpath: str) -> str:
    if local_relpath and (ROOT / local_relpath).exists():
        return "local_pdf_available"
    return "missing_local_pdf"


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_pdf_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )


def pdf_page_count(pdf_path: Path) -> str:
    if not pdf_path.exists():
        return ""
    proc = run_pdf_command(["pdfinfo", str(pdf_path)], timeout=30)
    if proc.returncode != 0:
        return ""
    for line in proc.stdout.splitlines():
        if line.lower().startswith("pages:"):
            return line.split(":", 1)[1].strip()
    return ""


def pdftotext_pages(pdf_path: Path) -> tuple[str, list[str]]:
    if not pdf_path.exists():
        return "missing_local_pdf", []
    proc = run_pdf_command(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"])
    if proc.returncode != 0:
        return "pdftotext_failed", []
    if not proc.stdout.strip():
        return "pdftotext_empty", []
    return "parsed", proc.stdout.split("\f")


def canonical_label(raw_label: str) -> str:
    label = clean_text(raw_label)
    label = re.sub(r"\s+", " ", label)
    label = re.sub(r"(?i)^fig\s+", "Fig. ", label)
    label = re.sub(r"(?i)^figure\s+", "Figure ", label)
    label = re.sub(r"(?i)^table\s+", "Table ", label)
    return label


def caption_candidates_from_pages(pages: list[str], max_chars: int = 1200) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for page_number, page_text in enumerate(pages, start=1):
        lines = [line.rstrip() for line in page_text.splitlines()]
        index = 0
        while index < len(lines):
            match = CAPTION_START.match(lines[index])
            if not match:
                index += 1
                continue

            caption_lines = [lines[index]]
            next_index = index + 1
            while next_index < len(lines) and len(clean_text(" ".join(caption_lines))) < max_chars:
                next_line = lines[next_index].rstrip()
                if CAPTION_START.match(next_line):
                    break
                if not next_line.strip() and len(clean_text(" ".join(caption_lines))) >= 160:
                    break
                if re.match(r"^\s*(references|acknowledg|materials and methods|methods|results|discussion)\b", next_line, re.I):
                    if len(caption_lines) > 1:
                        break
                caption_lines.append(next_line)
                next_index += 1

            label = canonical_label(match.group(1))
            caption_text = clean_text(" ".join(caption_lines), limit=max_chars)
            candidate_type = "table" if label.lower().startswith("table") else "figure"
            candidates.append(
                {
                    "candidate_type": candidate_type,
                    "candidate_label": label,
                    "candidate_page": str(page_number),
                    "candidate_text": caption_text,
                }
            )
            index = max(next_index, index + 1)
    return candidates


def mention_candidates_from_pages(pages: list[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for page_number, page_text in enumerate(pages, start=1):
        for line in page_text.splitlines():
            cleaned_line = clean_text(line, limit=500)
            if not cleaned_line:
                continue
            for match in MENTION_LABELS.finditer(cleaned_line):
                prefix = match.group(1).lower()
                label_type = "table" if prefix.startswith("table") else "figure"
                label_prefix = "Table" if label_type == "table" else "Fig."
                for number in re.findall(r"S?\d+[A-Za-z]?", match.group(2), flags=re.IGNORECASE):
                    label = f"{label_prefix} {number}"
                    key = (label, str(page_number))
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        {
                            "candidate_type": "mention",
                            "candidate_label": label,
                            "candidate_page": str(page_number),
                            "candidate_text": cleaned_line,
                        }
                    )
            if re.search(r"\bfigure,\s*[A-D](?:,|\s+and)", cleaned_line, flags=re.IGNORECASE) or (
                re.search(r"\bA,", cleaned_line)
                and re.search(r"\bB,", cleaned_line)
                and re.search(r"\b(regeneration|damaged|colonies|colony|photograph|image)\b", cleaned_line, flags=re.IGNORECASE)
                and len(cleaned_line) >= 80
            ):
                key = ("unlabeled figure", str(page_number))
                if key not in seen:
                    seen.add(key)
                    candidates.append(
                        {
                            "candidate_type": "mention",
                            "candidate_label": "unlabeled figure",
                            "candidate_page": str(page_number),
                            "candidate_text": cleaned_line,
                        }
                    )
    return candidates


def score_candidate(candidate: dict[str, str], response_type: str) -> tuple[int, list[str]]:
    text = candidate.get("candidate_text", "").lower()
    terms = RESPONSE_TERMS.get(response_type, [])
    matched = []
    for term in terms:
        if re.search(rf"\b{re.escape(term.lower())}\b", text):
            matched.append(term)
    score = len(matched) * 10
    if response_type == "rate" and any(term in matched for term in ["regeneration", "healing", "recovery", "repair"]):
        score += 5
    if response_type == "growth" and "growth" in matched:
        score += 5
    if response_type == "reproduction" and any(term in matched for term in ["fecundity", "reproduction", "reproductive"]):
        score += 5
    if response_type == "survival" and any(term in matched for term in ["survival", "survivorship", "mortality"]):
        score += 5
    return score, matched


def build_required_clip_rule(source_id: str, response_type: str) -> str:
    prefix = (source_id or "source")[:8]
    return f"digitization/figures/{prefix}__{response_type}__fig-<printed-label>_panel-<panel>.png"


def build_required_data_rule(source_id: str, response_type: str) -> str:
    prefix = (source_id or "source")[:8]
    return f"digitization/data/{prefix}__{response_type}__fig-<printed-label>_panel-<panel>.csv"


def build_figure_source_review_rows(
    digitization_rows: list[dict[str, str]],
    max_candidates_per_row: int = 5,
) -> list[dict[str, str]]:
    pdf_cache: dict[str, tuple[str, str, str, list[dict[str, str]]]] = {}
    out: list[dict[str, str]] = []

    for row in digitization_rows:
        local_relpath = row.get("local_relpath", "")
        status = row.get("source_file_status", "") or local_pdf_status(local_relpath)
        source_id = row.get("source_id", "")
        response_type = row.get("response_type", "")

        base = {
            "queue_id": row.get("queue_id", ""),
            "digitization_status": row.get("digitization_status", ""),
            "source_id": source_id,
            "paper_title": row.get("paper_title", ""),
            "response_type": response_type,
            "source_file_status": status,
            "local_relpath": local_relpath,
            "required_clip_naming_rule": build_required_clip_rule(source_id, response_type),
            "required_data_naming_rule": build_required_data_rule(source_id, response_type),
        }

        if status != "local_pdf_available":
            out.append(
                {
                    **base,
                    "pdf_sha256": "",
                    "pdf_page_count": "",
                    "caption_parse_status": "blocked_missing_local_pdf",
                    "candidate_rank": "",
                    "candidate_score": "",
                    "candidate_type": "",
                    "candidate_label": "",
                    "candidate_page": "",
                    "candidate_text": "",
                    "matched_terms": "",
                    "review_status": "blocked_missing_local_pdf",
                    "selected_for_clipping": "",
                    "reviewer": "",
                    "review_notes": "Retrieve source PDF before figure/table labeling or clipping.",
                }
            )
            continue

        if local_relpath not in pdf_cache:
            pdf_path = ROOT / local_relpath
            pdf_hash = file_sha256(pdf_path)
            page_count = pdf_page_count(pdf_path)
            parse_status, pages = pdftotext_pages(pdf_path)
            candidates = caption_candidates_from_pages(pages) if parse_status == "parsed" else []
            if parse_status == "parsed" and not candidates:
                candidates = mention_candidates_from_pages(pages)
            pdf_cache[local_relpath] = (pdf_hash, page_count, parse_status, candidates)

        pdf_hash, page_count, parse_status, candidates = pdf_cache[local_relpath]
        scored_candidates = []
        for candidate in candidates:
            score, matched = score_candidate(candidate, response_type)
            scored_candidates.append((score, matched, candidate))
        scored_candidates.sort(
            key=lambda item: (
                -item[0],
                int(item[2].get("candidate_page") or 0),
                item[2].get("candidate_label", ""),
            )
        )

        if not scored_candidates:
            out.append(
                {
                    **base,
                    "pdf_sha256": pdf_hash,
                    "pdf_page_count": page_count,
                    "caption_parse_status": parse_status if parse_status != "parsed" else "no_caption_or_mention_candidates",
                    "candidate_rank": "",
                    "candidate_score": "",
                    "candidate_type": "",
                    "candidate_label": "",
                    "candidate_page": "",
                    "candidate_text": "",
                    "matched_terms": "",
                    "review_status": "no_caption_or_mention_candidates",
                    "selected_for_clipping": "",
                    "reviewer": "",
                    "review_notes": "No figure/table captions detected by pdftotext; inspect PDF manually.",
                }
            )
            continue

        for rank, (score, matched, candidate) in enumerate(scored_candidates[:max_candidates_per_row], start=1):
            out.append(
                {
                    **base,
                    "pdf_sha256": pdf_hash,
                    "pdf_page_count": page_count,
                    "caption_parse_status": parse_status,
                    "candidate_rank": str(rank),
                    "candidate_score": str(score),
                    "candidate_type": candidate.get("candidate_type", ""),
                    "candidate_label": candidate.get("candidate_label", ""),
                    "candidate_page": candidate.get("candidate_page", ""),
                    "candidate_text": candidate.get("candidate_text", ""),
                    "matched_terms": "|".join(matched),
                    "review_status": "candidate_review_needed",
                    "selected_for_clipping": "",
                    "reviewer": "",
                    "review_notes": "Select the exact printed figure/table label and panel before assigning clip/data paths.",
                }
            )

    return out


def retrieval_log_by_source(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_id", ""): row for row in rows if row.get("source_id", "")}


def build_source_retrieval_queue_rows(
    screening_rows: list[dict[str, str]],
    workplan_rows: list[dict[str, str]],
    digitization_rows: list[dict[str, str]],
    retrieval_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    workplan_blocked: dict[str, list[str]] = defaultdict(list)
    digitization_blocked: dict[str, list[str]] = defaultdict(list)
    for row in workplan_rows:
        if row.get("extraction_status") == "blocked_missing_local_pdf":
            workplan_blocked[row.get("source_id", "")].append(row.get("response_type", ""))
    for row in digitization_rows:
        if row.get("digitization_status") == "blocked_missing_local_pdf":
            digitization_blocked[row.get("source_id", "")].append(row.get("queue_id", ""))

    retrieval_by_source = retrieval_log_by_source(retrieval_rows)
    out: list[dict[str, str]] = []
    for row in screening_rows:
        source_id = row.get("source_id", "")
        primary_missing = row.get("final_status") == "include_primary" and local_pdf_status(row.get("local_relpath", "")) != "local_pdf_available"
        if not primary_missing and source_id not in workplan_blocked and source_id not in digitization_blocked:
            continue
        log = retrieval_by_source.get(source_id, {})
        out.append(
            {
                "source_id": source_id,
                "paper_title": row.get("paper_title", ""),
                "final_status": row.get("final_status", ""),
                "extraction_readiness": row.get("extraction_readiness", ""),
                "notebook_present": "1" if truthy(row.get("notebook_present", "")) else "0",
                "local_present": "1" if truthy(row.get("local_present", "")) else "0",
                "local_relpath": row.get("local_relpath", ""),
                "blocked_workplan_responses": "|".join(sorted(set(workplan_blocked.get(source_id, [])))),
                "blocked_digitization_queue_ids": "|".join(sorted(set(digitization_blocked.get(source_id, [])))),
                "retrieval_status": log.get("retrieval_status", "not_logged"),
                "search_date": log.get("search_date", ""),
                "searched_locations": log.get("searched_locations", ""),
                "search_terms": log.get("search_terms", ""),
                "public_source_status": log.get("public_source_status", ""),
                "next_action": log.get("next_action", "Document search status and retrieve PDF before extraction."),
                "notes": log.get("notes", ""),
            }
        )
    out.sort(key=lambda item: (item["retrieval_status"], item["paper_title"]))
    return out


def legacy_units(row: dict[str, str], response_type: str) -> tuple[str, str]:
    if response_type == "rate":
        return "Rate_Unit", row.get("Rate_Unit", "")
    if response_type == "growth":
        return "Outcome_Type", row.get("Outcome_Type", "")
    if response_type == "reproduction":
        return "Outcome_Type", row.get("Outcome_Type", "")
    if response_type == "survival":
        has_counts = any(row.get(field, "") for field in ["Control_Total", "Control_Dead", "Wounded_Total", "Wounded_Dead"])
        return "survival_counts", "raw_counts" if has_counts else ""
    return "", ""


def legacy_variance(row: dict[str, str], response_type: str) -> tuple[str, str]:
    if response_type == "rate":
        return "Variance_Type", row.get("Variance_Type", "")
    if response_type in {"growth", "reproduction"}:
        return "Var_Type", row.get("Var_Type", "")
    if response_type == "survival":
        has_counts = any(row.get(field, "") for field in ["Control_Total", "Control_Dead", "Wounded_Total", "Wounded_Dead"])
        return "survival_counts", "raw_counts" if has_counts else ""
    return "", ""


def legacy_sample_size(row: dict[str, str], response_type: str) -> tuple[str, str]:
    if response_type in {"rate", "growth", "reproduction"}:
        return "Sample_Size", row.get("Sample_Size", "")
    if response_type == "survival":
        control = row.get("Control_Total", "")
        wounded = row.get("Wounded_Total", "")
        return "Control_Total|Wounded_Total", f"{control}|{wounded}".strip("|")
    return "", ""


def legacy_value_fields(row: dict[str, str], response_type: str) -> str:
    if response_type == "rate":
        return f"Rate_Value={row.get('Rate_Value', '')}"
    if response_type in {"growth", "reproduction"}:
        fields = ["Control_Mean", "Control_Var", "Wounded_Mean", "Wounded_Var"]
        return "; ".join(f"{field}={row.get(field, '')}" for field in fields)
    if response_type == "survival":
        fields = ["Control_Total", "Control_Dead", "Wounded_Total", "Wounded_Dead", "Duration_Days"]
        return "; ".join(f"{field}={row.get(field, '')}" for field in fields)
    return ""


def workplan_response_pairs(workplan_rows: list[dict[str, str]] | None) -> set[tuple[str, str]]:
    if not workplan_rows:
        return set()
    return {
        (row.get("source_id", ""), row.get("response_type", ""))
        for row in workplan_rows
        if row.get("source_id", "") and row.get("response_type", "")
    }


def workplan_crosswalk_status(row: dict[str, str], pairs: set[tuple[str, str]]) -> str:
    source_id = row.get("source_id", "")
    response_type = row.get("response_type", "")
    if not source_id or not response_type:
        return "missing_source_or_response"
    if not pairs:
        return "not_checked"
    if (source_id, response_type) in pairs:
        return "matched_workplan_response"
    return "response_not_in_workplan"


def build_legacy_extraction_qa_rows(
    extraction_tables: dict[str, Path],
    workplan_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    pairs = workplan_response_pairs(workplan_rows)
    hash_cache: dict[str, str] = {}
    for table_name, table_path in extraction_tables.items():
        for index, row in enumerate(read_csv(table_path), start=2):
            response_type = row.get("response_type", "")
            local_relpath = row.get("local_relpath", "")
            source_file_status = local_pdf_status(local_relpath)
            if source_file_status == "local_pdf_available" and local_relpath not in hash_cache:
                hash_cache[local_relpath] = file_sha256(ROOT / local_relpath)
            crosswalk_status = workplan_crosswalk_status(row, pairs)
            units_field, units_value = legacy_units(row, response_type)
            variance_field, variance_value = legacy_variance(row, response_type)
            sample_field, sample_value = legacy_sample_size(row, response_type)
            required_values = {
                "source_id": row.get("source_id", ""),
                "paper_title": row.get("paper_title", ""),
                "local_relpath": row.get("local_relpath", ""),
                "response_type": response_type,
                "figure_or_table_label": row.get("figure_or_table_label", ""),
                "page": row.get("page", ""),
                "panel_label": row.get("panel_label", ""),
                "extraction_provenance": row.get("extraction_provenance", ""),
                "units": units_value,
                "variance_type": variance_value,
                "sample_size": sample_value,
            }
            missing = [field for field in REQUIRED_LEGACY_PROVENANCE_FIELDS if not clean_text(required_values.get(field, ""))]
            if missing:
                review_status = "needs_source_provenance_review"
                recommended_action = "Verify source PDF, record exact figure/table label, page, panel/all, units, variance, and sample-size source."
            elif row.get("qa_status", "") not in {"qa_passed", "source_verified"}:
                review_status = "needs_qa_signoff"
                recommended_action = "Confirm extracted value against source and set qa_status after review."
            else:
                review_status = "source_verified"
                recommended_action = ""
            out.append(
                {
                    "table_name": table_name,
                    "csv_line": str(index),
                    "source_id": row.get("source_id", ""),
                    "paper_title": row.get("paper_title", ""),
                    "local_relpath": local_relpath,
                    "response_type": response_type,
                    "source_file_status": source_file_status,
                    "source_pdf_sha256": hash_cache.get(local_relpath, ""),
                    "workplan_crosswalk_status": crosswalk_status,
                    "source_match_status": row.get("source_match_status", ""),
                    "figure_or_table_label": row.get("figure_or_table_label", ""),
                    "page": row.get("page", ""),
                    "panel_label": row.get("panel_label", ""),
                    "extraction_provenance": row.get("extraction_provenance", ""),
                    "qa_status": row.get("qa_status", ""),
                    "units_field": units_field,
                    "units_value": units_value,
                    "variance_type_field": variance_field,
                    "variance_type_value": variance_value,
                    "sample_size_field": sample_field,
                    "sample_size_value": sample_value,
                    "value_fields": legacy_value_fields(row, response_type),
                    "missing_required_fields": "|".join(missing),
                    "review_status": review_status,
                    "recommended_action": recommended_action,
                    "reviewer": "",
                    "review_notes": "",
                }
            )
    return out


def build_summary(
    figure_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    legacy_rows: list[dict[str, str]],
) -> str:
    figure_status = Counter(row.get("review_status", "") for row in figure_rows)
    caption_status = Counter(row.get("caption_parse_status", "") for row in figure_rows)
    source_status = Counter(row.get("retrieval_status", "") for row in source_rows)
    legacy_status = Counter(row.get("review_status", "") for row in legacy_rows)
    crosswalk_status = Counter(row.get("workplan_crosswalk_status", "") for row in legacy_rows)
    missing_fields = Counter()
    for row in legacy_rows:
        for field in row.get("missing_required_fields", "").split("|"):
            if field:
                missing_fields[field] += 1

    def table(counter: Counter[str], label: str) -> str:
        lines = [f"| {label} | Count |", "| --- | ---: |"]
        for key, value in sorted(counter.items()):
            lines.append(f"| `{key}` | {value} |")
        return "\n".join(lines)

    return "\n".join(
        [
            "# Extraction Review Summary",
            "",
            "Generated by `python3 tools/build_extraction_review_artifacts.py`.",
            "",
            "These review files are execution aids. They do not replace the screening source of truth or the extraction tables.",
            "",
            "## Figure Source Review",
            "",
            f"- Review rows: {len(figure_rows)}",
            "",
            table(figure_status, "Review status"),
            "",
            table(caption_status, "Caption parse status"),
            "",
            "## Source Retrieval",
            "",
            f"- Missing-source rows: {len(source_rows)}",
            "",
            table(source_status, "Retrieval status"),
            "",
            "## Legacy Extraction QA",
            "",
            f"- Legacy extraction rows: {len(legacy_rows)}",
            "",
            table(legacy_status, "Legacy review status"),
            "",
            table(crosswalk_status, "Workplan crosswalk status"),
            "",
            table(missing_fields, "Missing required field"),
            "",
            "## Rules",
            "",
            "- Do not assign `clip_path` or `digitized_data_path` until the exact printed figure/table label, PDF page, panel, axes/units, variance source, and sample-size source are verified.",
            "- A source can remain in PRISMA as included only if its source-availability status is explicit; extraction stays blocked until the PDF/source file is recovered.",
            "- Legacy extracted rows remain review-only until the row-level provenance fields are filled and QA signed off.",
            "",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-candidates-per-row", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=SOURCE_REVIEW_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    digitization_rows = read_csv(DIGITIZATION_QUEUE)
    workplan_rows = read_csv(EXTRACTION_WORKPLAN)
    screening_rows = read_csv(SCREENING_LOG)
    retrieval_rows = read_csv(SOURCE_RETRIEVAL_LOG)

    if not digitization_rows:
        raise SystemExit(f"Missing or empty source file: {DIGITIZATION_QUEUE.relative_to(ROOT)}")
    if not workplan_rows:
        raise SystemExit(f"Missing or empty source file: {EXTRACTION_WORKPLAN.relative_to(ROOT)}")
    if not screening_rows:
        raise SystemExit(f"Missing or empty source file: {SCREENING_LOG.relative_to(ROOT)}")

    figure_rows = build_figure_source_review_rows(digitization_rows, args.max_candidates_per_row)
    source_rows = build_source_retrieval_queue_rows(screening_rows, workplan_rows, digitization_rows, retrieval_rows)
    legacy_rows = build_legacy_extraction_qa_rows(EXTRACTION_TABLES, workplan_rows)

    write_csv(
        args.output_dir / "FIGURE_SOURCE_REVIEW.csv",
        [
            "queue_id",
            "digitization_status",
            "source_id",
            "paper_title",
            "response_type",
            "source_file_status",
            "local_relpath",
            "pdf_sha256",
            "pdf_page_count",
            "caption_parse_status",
            "candidate_rank",
            "candidate_score",
            "candidate_type",
            "candidate_label",
            "candidate_page",
            "candidate_text",
            "matched_terms",
            "review_status",
            "selected_for_clipping",
            "reviewer",
            "review_notes",
            "required_clip_naming_rule",
            "required_data_naming_rule",
        ],
        figure_rows,
    )
    write_csv(
        args.output_dir / "SOURCE_RETRIEVAL_QUEUE.csv",
        [
            "source_id",
            "paper_title",
            "final_status",
            "extraction_readiness",
            "notebook_present",
            "local_present",
            "local_relpath",
            "blocked_workplan_responses",
            "blocked_digitization_queue_ids",
            "retrieval_status",
            "search_date",
            "searched_locations",
            "search_terms",
            "public_source_status",
            "next_action",
            "notes",
        ],
        source_rows,
    )
    write_csv(
        args.output_dir / "LEGACY_EXTRACTION_QA_QUEUE.csv",
        [
            "table_name",
            "csv_line",
            "source_id",
            "paper_title",
            "local_relpath",
            "response_type",
            "source_file_status",
            "source_pdf_sha256",
            "workplan_crosswalk_status",
            "source_match_status",
            "figure_or_table_label",
            "page",
            "panel_label",
            "extraction_provenance",
            "qa_status",
            "units_field",
            "units_value",
            "variance_type_field",
            "variance_type_value",
            "sample_size_field",
            "sample_size_value",
            "value_fields",
            "missing_required_fields",
            "review_status",
            "recommended_action",
            "reviewer",
            "review_notes",
        ],
        legacy_rows,
    )
    write_text(args.output_dir / "EXTRACTION_REVIEW_SUMMARY.md", build_summary(figure_rows, source_rows, legacy_rows))

    print(f"Wrote extraction review artifacts to {args.output_dir.relative_to(ROOT)}")
    print(f"Figure source review rows: {len(figure_rows)}")
    print(f"Source retrieval rows: {len(source_rows)}")
    print(f"Legacy extraction QA rows: {len(legacy_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

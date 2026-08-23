#!/usr/bin/env python3
"""Build auditable rate-extraction artifacts for the primary rate pool."""

from __future__ import annotations

import csv
import hashlib
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKPLAN = ROOT / "pipeline" / "EXTRACTION_WORKPLAN.csv"
FIGURE_QUEUE_AUDIT = ROOT / "digitization" / "source_review" / "FIGURE_QUEUE_AUDIT_STATUS.csv"
FIGURE_CROP_MANIFEST = ROOT / "digitization" / "figures" / "FIGURE_CROP_MANIFEST.csv"
LEGACY_RATES = ROOT / "data" / "extraction" / "EXTRACTION_RATES.csv"
PILOT_RATES = ROOT / "data" / "extraction" / "TIER1_EXTRACTION_PILOT.csv"

OUTPUT_DIR = ROOT / "data" / "extraction" / "rate"
SOURCE_INDEX = OUTPUT_DIR / "RATE_SOURCE_INDEX.csv"
TEXT_EVIDENCE = OUTPUT_DIR / "RATE_TEXT_EVIDENCE.csv"
EFFECT_SEEDS = OUTPUT_DIR / "RATE_EFFECT_SIZE_SEEDS.csv"
CURATED_OBSERVATIONS = OUTPUT_DIR / "RATE_EXTRACTED_OBSERVATIONS.csv"
SOURCE_REVIEW_OVERRIDES = OUTPUT_DIR / "RATE_SOURCE_REVIEW_OVERRIDES.csv"
SUMMARY = OUTPUT_DIR / "RATE_EXTRACTION_SUMMARY.md"

RATE_SOURCE_FIELDS = [
    "source_id",
    "paper_title",
    "local_relpath",
    "source_file_status",
    "extraction_readiness",
    "requires_digitization",
    "recommended_action",
    "pdf_parse_status",
    "pdf_page_count",
    "pdf_text_chars",
    "pdf_text_sha256",
    "text_evidence_rows",
    "curated_observation_count",
    "curated_analysis_ready_count",
    "legacy_rate_row_count",
    "pilot_seed_row_count",
    "figure_queue_id",
    "figure_queue_status",
    "recommended_candidate_count",
    "crop_proposal_count",
    "valid_crop_proposal_count",
    "figure_candidate_count",
    "table_candidate_count",
    "digitized_data_file_count",
    "rate_extraction_route",
    "analysis_ready",
    "next_action",
    "source_review_override_reason",
    "final_rationale",
]

TEXT_EVIDENCE_FIELDS = [
    "source_id",
    "paper_title",
    "local_relpath",
    "evidence_rank",
    "pdf_page",
    "evidence_kind",
    "candidate_label",
    "candidate_type",
    "score",
    "snippet",
    "text_sha256",
]

EFFECT_SEED_FIELDS = [
    "rate_effect_id",
    "source_id",
    "paper_title",
    "local_relpath",
    "seed_source",
    "seed_source_row",
    "effect_status",
    "analysis_ready",
    "rate_derivation_basis",
    "effect_measure",
    "species",
    "location",
    "stressor_or_treatment",
    "wound_area_mm2",
    "rate_value",
    "rate_unit",
    "variance_type",
    "variance_value",
    "sample_size",
    "time_to_healing_days",
    "final_extent",
    "duration_days",
    "figure_or_table_label",
    "page",
    "panel_label",
    "provenance_status",
    "notes",
]

CAPTION_START = re.compile(
    r"^\s*((?:Supplementary\s+)?(?:Fig(?:ure)?\.?|FIG\.?|Table)\s*\.?\s*(?:S?\d+[A-Za-z]?|[IVXLC]+|I))"
    r"[\s.:;\-]*(.*)$",
    re.IGNORECASE,
)

RATE_TERMS = {
    "closure": re.compile(r"\b(healed|healing|closed|closure|complete(?:ly)? healed|time to heal)\b", re.I),
    "wound": re.compile(r"\b(wound|lesion|scar|injur(?:y|ies)|tissue regeneration|repair|recovery)\b", re.I),
    "rate": re.compile(r"\b(rate|slope|d-?1|day-?1|days?|month-?1|mm2|mm\s*2|cm2|cm\s*2|%)\b", re.I),
    "table_figure": re.compile(r"\b(fig(?:ure)?\.?|table)\b", re.I),
}

NUMERIC = re.compile(r"\d")
RATE_UNIT = re.compile(
    r"(?i)(mm\s*2\s*(?:d|day)|cm\s*2\s*(?:d|day)|%\s*(?:d|day)|"
    r"(?:d|day)\s*[-−]?\s*1|month\s*[-−]?\s*1|mm\s*(?:d|day))"
)

PILOT_SOURCE_PREFIX_MAP = {
    ("Bak", "1983"): "dde85c3e",
    ("Burmester et al.", "2017"): "9616c9c9",
    ("Cameron & Edmunds", "2014"): "26babed0",
    ("Bak & Es", "1980"): "12e9e864",
}


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


def clean_text(value: str, limit: int | None = None) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if limit is not None and len(value) > limit:
        return value[: limit - 3].rstrip() + "..."
    return value


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def nonempty(value: str) -> bool:
    return bool(str(value or "").strip())


def make_unique_header(header: list[str]) -> list[str]:
    seen: Counter[str] = Counter()
    out: list[str] = []
    for field in header:
        seen[field] += 1
        if seen[field] == 1:
            out.append(field)
        else:
            out.append(f"{field}_{seen[field]}")
    return out


def read_csv_allow_duplicate_headers(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            header = make_unique_header(next(reader))
        except StopIteration:
            return []
        return [dict(zip(header, row)) for row in reader]


def run_pdf_text(pdf_path: Path) -> tuple[str, list[str], str]:
    if not pdf_path.exists():
        return "missing_local_pdf", [], ""
    proc = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return "pdftotext_failed", [], ""
    if not proc.stdout.strip():
        return "pdftotext_empty", [], ""
    text_hash = hashlib.sha256(proc.stdout.encode("utf-8", "replace")).hexdigest()
    return "parsed", proc.stdout.split("\f"), text_hash


def score_snippet(snippet: str, evidence_kind: str) -> int:
    score = 0
    if NUMERIC.search(snippet):
        score += 2
    if RATE_UNIT.search(snippet):
        score += 6
    for key, pattern in RATE_TERMS.items():
        if pattern.search(snippet):
            score += {"closure": 5, "wound": 4, "rate": 3, "table_figure": 1}[key]
    if evidence_kind == "caption_or_table_start":
        score += 2
    if re.search(r"\b(mean|SD|SE|CI|n\s*=|sample)\b", snippet, re.I):
        score += 2
    if re.search(r"\b(initial|final|over time|time series|day 0|day 1)\b", snippet, re.I):
        score += 2
    return score


def caption_blocks(pages: list[str]) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for page_number, page in enumerate(pages, start=1):
        lines = page.splitlines()
        index = 0
        while index < len(lines):
            match = CAPTION_START.match(lines[index])
            if not match:
                index += 1
                continue
            block_lines = [lines[index].strip()]
            cursor = index + 1
            while cursor < len(lines) and len(clean_text(" ".join(block_lines))) < 1200:
                if CAPTION_START.match(lines[cursor]):
                    break
                if lines[cursor].strip():
                    block_lines.append(lines[cursor].strip())
                if not lines[cursor].strip() and len(block_lines) >= 3:
                    break
                cursor += 1
            label = clean_text(match.group(1))
            snippet = clean_text(" ".join(block_lines), 1000)
            candidate_type = "table" if label.lower().startswith("table") else "figure"
            blocks.append(
                {
                    "pdf_page": str(page_number),
                    "evidence_kind": "caption_or_table_start",
                    "candidate_label": label,
                    "candidate_type": candidate_type,
                    "snippet": snippet,
                }
            )
            index = max(cursor, index + 1)
    return blocks


def numeric_keyword_windows(pages: list[str]) -> list[dict[str, str]]:
    windows: list[dict[str, str]] = []
    seen: set[tuple[int, str]] = set()
    for page_number, page in enumerate(pages, start=1):
        lines = page.splitlines()
        for line_index, line in enumerate(lines):
            if not NUMERIC.search(line):
                continue
            if not (RATE_TERMS["closure"].search(line) or RATE_TERMS["wound"].search(line) or RATE_UNIT.search(line)):
                continue
            block = [
                lines[i].rstrip()
                for i in range(max(0, line_index - 2), min(len(lines), line_index + 3))
                if lines[i].strip()
            ]
            snippet = clean_text(" / ".join(block), 1000)
            key = (page_number, snippet[:180])
            if key in seen:
                continue
            seen.add(key)
            windows.append(
                {
                    "pdf_page": str(page_number),
                    "evidence_kind": "numeric_keyword_window",
                    "candidate_label": "",
                    "candidate_type": "text",
                    "snippet": snippet,
                }
            )
    return windows


def extract_text_evidence(source: dict[str, str], pages: list[str], text_hash: str, max_rows: int = 12) -> list[dict[str, str]]:
    candidates = caption_blocks(pages) + numeric_keyword_windows(pages)
    scored: list[dict[str, str]] = []
    for candidate in candidates:
        snippet = candidate["snippet"]
        score = score_snippet(snippet, candidate["evidence_kind"])
        if score < 9:
            continue
        row = {
            "source_id": source["source_id"],
            "paper_title": source["paper_title"],
            "local_relpath": source["local_relpath"],
            "pdf_page": candidate["pdf_page"],
            "evidence_kind": candidate["evidence_kind"],
            "candidate_label": candidate["candidate_label"],
            "candidate_type": candidate["candidate_type"],
            "score": str(score),
            "snippet": snippet,
            "text_sha256": text_hash,
        }
        scored.append(row)

    scored.sort(
        key=lambda row: (
            -int(row["score"]),
            int(row["pdf_page"]) if row["pdf_page"].isdigit() else 9999,
            row["snippet"],
        )
    )
    deduped: list[dict[str, str]] = []
    seen_snippets: set[str] = set()
    for row in scored:
        normalized = clean_text(row["snippet"][:260]).lower()
        if normalized in seen_snippets:
            continue
        seen_snippets.add(normalized)
        row["evidence_rank"] = str(len(deduped) + 1)
        deduped.append(row)
        if len(deduped) >= max_rows:
            break
    return deduped


def rate_sources_from_workplan() -> list[dict[str, str]]:
    return [
        row
        for row in read_csv(WORKPLAN)
        if row.get("final_status") == "include_primary" and row.get("response_type") == "rate"
    ]


def figure_audit_by_source() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_csv(FIGURE_QUEUE_AUDIT):
        if row.get("response_type") == "rate":
            out[row.get("source_id", "")] = row
    return out


def crop_counts_by_source() -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in read_csv(FIGURE_CROP_MANIFEST):
        if row.get("response_type") != "rate":
            continue
        source_id = row.get("source_id", "")
        counts[source_id]["crop_proposal_count"] += 1
        if row.get("crop_status") != "retained_rejected_not_cropped":
            counts[source_id]["valid_crop_proposal_count"] += 1
        if row.get("candidate_type") == "figure":
            counts[source_id]["figure_candidate_count"] += 1
        if row.get("candidate_type") == "table":
            counts[source_id]["table_candidate_count"] += 1
        if nonempty(row.get("digitized_data_path")) and (ROOT / row["digitized_data_path"]).exists():
            counts[source_id]["digitized_data_file_count"] += 1
    return counts


def curated_counts_by_source() -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in read_csv(CURATED_OBSERVATIONS):
        source_id = row.get("source_id", "")
        if not source_id:
            continue
        counts[source_id]["curated_observation_count"] += 1
        if row.get("analysis_ready") == "1":
            counts[source_id]["curated_analysis_ready_count"] += 1
    return counts


def source_review_overrides() -> dict[str, dict[str, str]]:
    return {row.get("source_id", ""): row for row in read_csv(SOURCE_REVIEW_OVERRIDES) if row.get("source_id")}


def legacy_seed_rows(workplan_by_source: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, row in enumerate(read_csv(LEGACY_RATES), start=2):
        source_id = row.get("source_id", "")
        source = workplan_by_source.get(source_id, {})
        rate_unit = row.get("Rate_Unit", "")
        if "Exponential" in rate_unit:
            basis = "reported_exponential_slope"
            measure = "rate_constant_k"
        elif "% d" in rate_unit or "% day" in rate_unit:
            basis = "reported_proportional_rate"
            measure = "proportional_rate"
        elif "mm2" in rate_unit or "mm²" in rate_unit:
            basis = "reported_areal_rate"
            measure = "areal_rate"
        elif rate_unit.strip().startswith("mm"):
            basis = "reported_linear_rate"
            measure = "linear_rate"
        else:
            basis = "reported_rate_unspecified_basis"
            measure = "reported_rate"
        rows.append(
            {
                "rate_effect_id": f"LEGACY-{source_id[:8]}-{index}",
                "source_id": source_id,
                "paper_title": row.get("paper_title") or source.get("paper_title", ""),
                "local_relpath": row.get("local_relpath") or source.get("local_relpath", ""),
                "seed_source": "data/extraction/EXTRACTION_RATES.csv",
                "seed_source_row": str(index),
                "effect_status": "legacy_numeric_value_needs_provenance",
                "analysis_ready": "0",
                "rate_derivation_basis": basis,
                "effect_measure": measure,
                "species": row.get("Species", ""),
                "location": row.get("Location", ""),
                "stressor_or_treatment": row.get("Stressor", ""),
                "wound_area_mm2": row.get("Wound_Area_mm2", ""),
                "rate_value": row.get("Rate_Value", ""),
                "rate_unit": rate_unit,
                "variance_type": row.get("Variance_Type", ""),
                "variance_value": row.get("Variance_Value", ""),
                "sample_size": row.get("Sample_Size", ""),
                "time_to_healing_days": "",
                "final_extent": "",
                "duration_days": "",
                "figure_or_table_label": row.get("figure_or_table_label", ""),
                "page": row.get("page", ""),
                "panel_label": row.get("panel_label", ""),
                "provenance_status": row.get("qa_status", "needs_source_provenance_review"),
                "notes": row.get("Notes", ""),
            }
        )
    return rows


def pilot_basis(row: dict[str, str]) -> tuple[str, str, str, str]:
    measures = []
    for field, basis, measure in [
        ("Rate_Constant_k", "reported_or_calculated_exponential_slope", "rate_constant_k"),
        ("Linear_Rate", "reported_or_calculated_linear_rate", "linear_rate"),
        ("Areal_Rate", "reported_or_calculated_areal_rate", "areal_rate"),
        ("Proportional_Rate", "reported_or_calculated_proportional_rate", "proportional_rate"),
        ("Time_to_Healing", "time_to_closure", "time_to_healing"),
    ]:
        value = row.get(field, "")
        if nonempty(value) and value != "NA":
            measures.append((basis, measure, field, value))
    if not measures:
        return "pilot_covariate_only_no_rate_value", "none", "", ""
    basis, measure, field, value = measures[0]
    return basis, measure, field, value


def pilot_source_id(row: dict[str, str], workplan_by_source: dict[str, dict[str, str]]) -> str:
    prefix = PILOT_SOURCE_PREFIX_MAP.get((row.get("Author", ""), row.get("Year", "")), "")
    if not prefix:
        return ""
    matches = [source_id for source_id in workplan_by_source if source_id.startswith(prefix)]
    return matches[0] if len(matches) == 1 else ""


def pilot_seed_rows(workplan_by_source: dict[str, dict[str, str]], legacy_source_ids: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for index, row in enumerate(read_csv_allow_duplicate_headers(PILOT_RATES), start=2):
        source_id = pilot_source_id(row, workplan_by_source)
        source = workplan_by_source.get(source_id, {})
        basis, measure, value_field, value = pilot_basis(row)
        effect_status = "pilot_seed_needs_source_review"
        if source_id in legacy_source_ids:
            effect_status = "pilot_seed_conflicts_or_overlaps_with_legacy_rate"
        out.append(
            {
                "rate_effect_id": f"PILOT-{source_id[:8] or 'unmapped'}-{index}",
                "source_id": source_id,
                "paper_title": source.get("paper_title", ""),
                "local_relpath": source.get("local_relpath", ""),
                "seed_source": "data/extraction/TIER1_EXTRACTION_PILOT.csv",
                "seed_source_row": str(index),
                "effect_status": effect_status,
                "analysis_ready": "0",
                "rate_derivation_basis": basis,
                "effect_measure": measure,
                "species": " ".join(part for part in [row.get("Genus", ""), row.get("Species", "")] if part and part != "NA"),
                "location": row.get("Location", ""),
                "stressor_or_treatment": "",
                "wound_area_mm2": row.get("Area_mm2", ""),
                "rate_value": value if measure != "time_to_healing" else "",
                "rate_unit": value_field,
                "variance_type": row.get("Variance", ""),
                "variance_value": "",
                "sample_size": row.get("Sample_Size", ""),
                "time_to_healing_days": value if measure == "time_to_healing" else row.get("Time_to_Healing", ""),
                "final_extent": row.get("Final_Extent", ""),
                "duration_days": row.get("Duration_days", ""),
                "figure_or_table_label": "",
                "page": "",
                "panel_label": "",
                "provenance_status": "needs_source_provenance_review",
                "notes": row.get("Notes", ""),
            }
        )
    return out


def route_for_source(
    source: dict[str, str],
    curated_count: int,
    curated_ready_count: int,
    legacy_count: int,
    pilot_count: int,
    figure_audit: dict[str, str],
    crop_counts: Counter[str],
) -> tuple[str, str, str]:
    if curated_ready_count > 0:
        return (
            "curated_values_analysis_ready",
            "1",
            "Use curated extracted observations; keep source-level provenance with the row.",
        )
    if curated_count > 0:
        return (
            "curated_values_available_needs_qc",
            "0",
            "Independently QC the extracted observation rows before pooling.",
        )
    if int(crop_counts.get("digitized_data_file_count", 0)) > 0:
        return (
            "digitized_data_available_needs_effect_extraction",
            "0",
            "Extract rate observations/effect sizes from the digitized-data file and complete QA.",
        )
    if legacy_count or pilot_count:
        return (
            "seed_values_available_needs_provenance_qa",
            "0",
            "Verify exact source figure/table/text, page, units, variance, and sample-size evidence before pooling.",
        )
    if truthy(source.get("requires_digitization", "")):
        if figure_audit.get("queue_audit_status") == "no_valid_candidate_found":
            return (
                "not_extractable_no_valid_figure_or_table_candidate",
                "0",
                "Do a full-text adjudication; if no text-only rate exists, remove this source from the rate extraction pool.",
            )
        if int(crop_counts.get("valid_crop_proposal_count", 0)) > 0:
            return (
                "needs_figure_or_table_digitization",
                "0",
                "Review crop box/panel labels, digitize plotted points or transcribe table values, then derive rates.",
            )
        return (
            "needs_audited_source_candidate",
            "0",
            "Find exact figure/table/page before digitization.",
        )
    return (
        "needs_text_or_table_extraction",
        "0",
        "Read text/tables and extract reported rates, initial/final wound sizes, time series, or time to closure.",
    )


def build_outputs() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    sources = rate_sources_from_workplan()
    workplan_by_source = {row.get("source_id", ""): row for row in sources}
    figure_audit = figure_audit_by_source()
    crop_counts = crop_counts_by_source()
    curated_counts = curated_counts_by_source()
    overrides = source_review_overrides()

    legacy_counts = Counter(row.get("source_id", "") for row in read_csv(LEGACY_RATES))
    pilot_raw = read_csv_allow_duplicate_headers(PILOT_RATES)
    pilot_counts = Counter(pilot_source_id(row, workplan_by_source) for row in pilot_raw)

    source_rows: list[dict[str, str]] = []
    evidence_rows: list[dict[str, str]] = []

    for source in sources:
        status, pages, text_hash = run_pdf_text(ROOT / source.get("local_relpath", ""))
        text_chars = str(sum(len(page) for page in pages))
        source_evidence = extract_text_evidence(source, pages, text_hash) if pages else []
        for row in source_evidence:
            evidence_rows.append(row)

        audit_row = figure_audit.get(source.get("source_id", ""), {})
        counts = crop_counts.get(source.get("source_id", ""), Counter())
        curated = curated_counts.get(source.get("source_id", ""), Counter())
        route, analysis_ready, next_action = route_for_source(
            source,
            int(curated.get("curated_observation_count", 0)),
            int(curated.get("curated_analysis_ready_count", 0)),
            legacy_counts[source.get("source_id", "")],
            pilot_counts[source.get("source_id", "")],
            audit_row,
            counts,
        )
        override_reason = ""
        override = overrides.get(source.get("source_id", ""))
        if override:
            route = override.get("rate_extraction_route", route) or route
            analysis_ready = override.get("analysis_ready", analysis_ready) or analysis_ready
            next_action = override.get("next_action", next_action) or next_action
            override_reason = override.get("override_reason", "")

        source_rows.append(
            {
                "source_id": source.get("source_id", ""),
                "paper_title": source.get("paper_title", ""),
                "local_relpath": source.get("local_relpath", ""),
                "source_file_status": source.get("source_file_status", ""),
                "extraction_readiness": source.get("extraction_readiness", ""),
                "requires_digitization": source.get("requires_digitization", ""),
                "recommended_action": source.get("recommended_action", ""),
                "pdf_parse_status": status,
                "pdf_page_count": str(len(pages)) if pages else "",
                "pdf_text_chars": text_chars if pages else "0",
                "pdf_text_sha256": text_hash,
                "text_evidence_rows": str(len(source_evidence)),
                "curated_observation_count": str(curated.get("curated_observation_count", 0)),
                "curated_analysis_ready_count": str(curated.get("curated_analysis_ready_count", 0)),
                "legacy_rate_row_count": str(legacy_counts[source.get("source_id", "")]),
                "pilot_seed_row_count": str(pilot_counts[source.get("source_id", "")]),
                "figure_queue_id": audit_row.get("queue_id", ""),
                "figure_queue_status": audit_row.get("queue_audit_status", ""),
                "recommended_candidate_count": audit_row.get("recommended_candidate_count", ""),
                "crop_proposal_count": str(counts.get("crop_proposal_count", 0)),
                "valid_crop_proposal_count": str(counts.get("valid_crop_proposal_count", 0)),
                "figure_candidate_count": str(counts.get("figure_candidate_count", 0)),
                "table_candidate_count": str(counts.get("table_candidate_count", 0)),
                "digitized_data_file_count": str(counts.get("digitized_data_file_count", 0)),
                "rate_extraction_route": route,
                "analysis_ready": analysis_ready,
                "next_action": next_action,
                "source_review_override_reason": override_reason,
                "final_rationale": source.get("final_rationale", ""),
            }
        )

    effect_rows = legacy_seed_rows(workplan_by_source)
    effect_rows.extend(pilot_seed_rows(workplan_by_source, {row.get("source_id", "") for row in effect_rows}))
    return source_rows, evidence_rows, effect_rows


def write_summary(source_rows: list[dict[str, str]], evidence_rows: list[dict[str, str]], effect_rows: list[dict[str, str]]) -> None:
    route_counts = Counter(row["rate_extraction_route"] for row in source_rows)
    readiness_counts = Counter(row["extraction_readiness"] for row in source_rows)
    figure_status_counts = Counter(row["figure_queue_status"] for row in source_rows if row["figure_queue_status"])
    summary = [
        "# Rate Extraction Summary",
        "",
        "Generated by `python3 tools/build_rate_extraction_dataset.py`.",
        "",
        "## Counts",
        "",
        f"- Rate-response primary sources: {len(source_rows)}",
        f"- Full-text PDF parses: {sum(1 for row in source_rows if row['pdf_parse_status'] == 'parsed')} / {len(source_rows)}",
        f"- Ranked text-evidence rows: {len(evidence_rows)}",
        f"- Curated extracted observation rows: {sum(int(row['curated_observation_count']) for row in source_rows)}",
        f"- Curated analysis-ready observation rows: {sum(int(row['curated_analysis_ready_count']) for row in source_rows)}",
        f"- Seed effect-size rows: {len(effect_rows)}",
        f"- Analysis-ready effect rows: {sum(1 for row in effect_rows if row['analysis_ready'] == '1')}",
        "",
        "## Extraction Readiness",
        "",
    ]
    for key, value in sorted(readiness_counts.items()):
        summary.append(f"- `{key}`: {value}")
    summary.extend(["", "## Extraction Routes", ""])
    for key, value in sorted(route_counts.items()):
        summary.append(f"- `{key}`: {value}")
    summary.extend(["", "## Figure Queue Status", ""])
    if figure_status_counts:
        for key, value in sorted(figure_status_counts.items()):
            summary.append(f"- `{key}`: {value}")
    else:
        summary.append("- No rate sources are currently in the audited figure queue.")
    summary.extend(
        [
            "",
            "## Use Notes",
            "",
            "- `RATE_SOURCE_INDEX.csv` is the 57-paper source-level audit and worklist.",
            "- `RATE_TEXT_EVIDENCE.csv` contains ranked, reproducible snippets from full-text PDF parsing. Use these to verify text/table extraction decisions.",
            "- `RATE_EXTRACTED_OBSERVATIONS.csv` contains curated rows extracted from printed prose/tables; rows stay provisional unless `analysis_ready=1`.",
            "- `RATE_EFFECT_SIZE_SEEDS.csv` carries legacy and pilot numeric values only as seeds. All rows currently remain `analysis_ready=0` until source provenance is filled.",
            "- Figure-derived values must not be pooled until the crop, panel, axis, variance/sample-size, and digitized-data fields are complete in the digitization workspace.",
            "",
        ]
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text("\n".join(summary), encoding="utf-8")


def main() -> int:
    if not WORKPLAN.exists():
        print(f"Missing workplan: {WORKPLAN}", file=sys.stderr)
        return 1
    source_rows, evidence_rows, effect_rows = build_outputs()
    write_csv(SOURCE_INDEX, RATE_SOURCE_FIELDS, source_rows)
    write_csv(TEXT_EVIDENCE, TEXT_EVIDENCE_FIELDS, evidence_rows)
    write_csv(EFFECT_SEEDS, EFFECT_SEED_FIELDS, effect_rows)
    write_summary(source_rows, evidence_rows, effect_rows)
    print(f"Wrote {SOURCE_INDEX.relative_to(ROOT)} ({len(source_rows)} rows)")
    print(f"Wrote {TEXT_EVIDENCE.relative_to(ROOT)} ({len(evidence_rows)} rows)")
    print(f"Wrote {EFFECT_SEEDS.relative_to(ROOT)} ({len(effect_rows)} rows)")
    print(f"Wrote {SUMMARY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

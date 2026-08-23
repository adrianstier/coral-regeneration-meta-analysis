#!/usr/bin/env python3
"""Build a strict analysis-ready gate for extracted coral regeneration rows."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKPLAN = ROOT / "pipeline" / "EXTRACTION_WORKPLAN.csv"
EXISTING_ROWS = ROOT / "data" / "extraction" / "all_responses" / "ALL_RESPONSE_EXISTING_EXTRACTION_ROWS.csv"
CROP_MANIFEST = ROOT / "digitization" / "figures" / "FIGURE_CROP_MANIFEST.csv"
CANDIDATES = ROOT / "data" / "extraction" / "all_responses" / "ALL_RESPONSE_COVARIATE_CANDIDATES.csv"
NLM_BATCHES = ROOT / "data" / "extraction" / "all_responses" / "NOTEBOOKLM_VALIDATION_BATCHES.csv"
NLM_LOG = ROOT / "data" / "extraction" / "all_responses" / "NOTEBOOKLM_VALIDATION_RUN_LOG.csv"
OUT_DIR = ROOT / "data" / "extraction" / "analysis_ready"
OBS_AUDIT = OUT_DIR / "ANALYSIS_READY_OBSERVATION_AUDIT.csv"
READY_OBS = OUT_DIR / "ANALYSIS_READY_OBSERVATIONS.csv"
ISSUES = OUT_DIR / "ANALYSIS_READY_ISSUES.csv"
BLOCKING_QUEUE = OUT_DIR / "ANALYSIS_READY_BLOCKING_QUEUE.csv"
RESPONSE_QUEUE = OUT_DIR / "ANALYSIS_READY_RESPONSE_QUEUE.csv"
SUMMARY = OUT_DIR / "ANALYSIS_READY_SUMMARY.md"

READY_QA_STATUSES = {"qc_passed", "analysis_ready", "ready_for_analysis"}
NOT_REPORTED = {"none", "not reported", "not_reported", "na", "n/a", "unknown", ""}
PRIMARY_RESPONSES = {"rate", "growth", "reproduction", "survival"}

ISSUE_FIELDS = [
    "severity",
    "issue_id",
    "normalized_row_id",
    "source_id",
    "response_type",
    "source_table",
    "source_row",
    "message",
    "expected",
    "observed",
]

OBS_AUDIT_FIELDS = [
    "normalized_row_id",
    "source_table",
    "source_row",
    "source_id",
    "response_type",
    "paper_title",
    "local_relpath",
    "analysis_ready",
    "readiness_status",
    "blocking_issue_count",
    "blocking_issues",
    "warning_issues",
    "next_action",
    "taxon_raw",
    "outcome_type",
    "treatment_or_stressor",
    "response_value",
    "response_unit",
    "rate_value",
    "rate_unit",
    "rate_derivation_basis",
    "observation_type",
    "control_value",
    "wounded_value",
    "variance_type",
    "variance_value",
    "sample_size",
    "duration_days",
    "timepoint_or_interval",
    "figure_or_table_label",
    "page",
    "panel_label",
    "qa_status",
    "evidence_key",
    "extraction_provenance",
    "calculation_notes",
    "value_data_file",
    "matched_crop_count",
    "matched_crop_paths",
    "matched_crop_review_statuses",
    "matched_final_clip_paths",
    "matched_digitized_data_paths",
    "concrete_digitized_data_files",
    "concrete_final_clip_files",
]

RESPONSE_QUEUE_FIELDS = [
    "source_id",
    "response_type",
    "paper_title",
    "local_relpath",
    "priority_rank",
    "extraction_readiness",
    "existing_extraction_rows",
    "analysis_ready_rows",
    "blocking_extraction_rows",
    "crop_proposals",
    "crop_proposals_need_human_qa",
    "concrete_digitized_data_files",
    "pdf_text_candidate_rows",
    "notebooklm_batch_id",
    "notebooklm_validation_status",
    "response_gate_status",
    "next_action",
    "blocking_summary",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def has_value(value: object) -> bool:
    return clean(value).lower() not in NOT_REPORTED


def relpath(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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


def is_placeholder_path(path: str) -> bool:
    return "<" in str(path or "") or ">" in str(path or "")


def concrete_existing_path(path: str) -> bool:
    if not has_value(path) or is_placeholder_path(path):
        return False
    return (ROOT / path).exists()


def label_tokens(label: str) -> list[str]:
    tokens: list[str] = []
    for part in re.split(r"\s*(?:;|\||,|\band\b)\s*", str(label or ""), flags=re.IGNORECASE):
        cleaned = clean(part)
        if cleaned:
            tokens.append(cleaned)
    return tokens


def normalize_label(label: str) -> str:
    label = clean(label).lower()
    label = re.sub(r"\bfigures?\b", "fig", label)
    label = re.sub(r"\bfigs?\b\.?", "fig", label)
    label = re.sub(r"\btables?\b", "table", label)
    label = re.sub(r"[^a-z0-9]+", "", label)
    return label


def figure_label_present(label: str) -> bool:
    return bool(re.search(r"\bfig(?:ure|ures|s)?\.?\b", str(label or ""), flags=re.IGNORECASE))


def table_label_present(label: str) -> bool:
    return bool(re.search(r"\btable\b", str(label or ""), flags=re.IGNORECASE))


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("source_id", ""), row.get("response_type", "")


def original_rows_by_source_row(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    wanted_files = {row.get("source_table", "") for row in rows if row.get("source_table", "")}
    for source_table in sorted(wanted_files):
        for row_number, original in enumerate(read_csv(ROOT / source_table), start=2):
            by_file[source_table].append({"_source_row": str(row_number), **original})
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for source_table, originals in by_file.items():
        for original in originals:
            lookup[(source_table, original["_source_row"])] = original
    return lookup


def crop_rows_for_observation(row: dict[str, str], crop_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    source_id, response_type = row_key(row)
    page = clean(row.get("page", ""))
    labels = {normalize_label(label) for label in label_tokens(row.get("figure_or_table_label", ""))}
    if not source_id or not response_type or not labels:
        return []
    matches: list[dict[str, str]] = []
    for crop in crop_rows:
        if crop.get("source_id") != source_id or crop.get("response_type") != response_type:
            continue
        if page and clean(crop.get("pdf_page", "")) != page:
            continue
        candidate_label = normalize_label(crop.get("candidate_label", ""))
        if candidate_label in labels:
            matches.append(crop)
    return matches


def add_issue(
    issues: list[dict[str, str]],
    row: dict[str, str],
    issue_id: str,
    message: str,
    *,
    severity: str = "blocker",
    expected: str = "",
    observed: str = "",
) -> None:
    issues.append(
        {
            "severity": severity,
            "issue_id": issue_id,
            "normalized_row_id": row.get("normalized_row_id", ""),
            "source_id": row.get("source_id", ""),
            "response_type": row.get("response_type", ""),
            "source_table": row.get("source_table", ""),
            "source_row": row.get("source_row", ""),
            "message": message,
            "expected": expected,
            "observed": observed,
        }
    )


def original_value(original: dict[str, str], *fields: str) -> str:
    for field in fields:
        if has_value(original.get(field, "")):
            return clean(original.get(field, ""))
    return ""


def response_measure_present(row: dict[str, str], original: dict[str, str]) -> bool:
    response_type = row.get("response_type", "")
    if response_type == "survival":
        return all(
            has_value(original.get(field, ""))
            for field in ["Control_Total", "Control_Dead", "Wounded_Total", "Wounded_Dead"]
        )
    if has_value(row.get("response_value", "")) or has_value(original.get("Rate_Value", "")):
        return True
    if has_value(row.get("control_value", "")) and has_value(row.get("wounded_value", "")):
        return True
    if has_value(original.get("Control_Mean", "")) and has_value(original.get("Wounded_Mean", "")):
        return True
    if has_value(original.get("rate_value", "")):
        return True
    return False


def response_unit_present(row: dict[str, str], original: dict[str, str]) -> bool:
    if row.get("response_type") == "survival":
        return response_measure_present(row, original)
    return has_value(
        row.get("response_unit", "")
        or original.get("Rate_Unit", "")
        or original.get("rate_unit", "")
        or original.get("Outcome_Type", "")
        or original.get("observation_type", "")
    )


def variance_or_counts_present(row: dict[str, str], original: dict[str, str]) -> bool:
    response_type = row.get("response_type", "")
    if response_type == "survival":
        return response_measure_present(row, original)
    if has_value(original.get("Control_Var", "")) and has_value(original.get("Wounded_Var", "")):
        return True
    variance_type = clean(row.get("variance_type", "") or original.get("Variance_Type", "") or original.get("Var_Type", ""))
    variance_value = clean(row.get("variance_value", "") or original.get("Variance_Value", "") or original.get("variance_value", ""))
    if variance_type.lower() == "none" and variance_value in {"0", "0.0"}:
        return False
    if has_value(variance_type) and has_value(variance_value):
        return True
    response_value = clean(row.get("response_value", "") or original.get("response_value", ""))
    if "/" in response_value and has_value(row.get("sample_size", "") or original.get("sample_size", "")):
        return True
    return False


def time_or_duration_present(row: dict[str, str], original: dict[str, str]) -> bool:
    if has_value(row.get("duration_days", "")):
        return True
    if has_value(original.get("Duration_Days", "")):
        return True
    if has_value(original.get("timepoint_or_interval", "")):
        return True
    return False


def next_action_for_issues(issue_ids: list[str]) -> str:
    issue_set = set(issue_ids)
    if "qa_status_not_ready" in issue_set and len(issue_set) == 1:
        return "Independent reviewer should verify the row against the cited PDF/table/figure and set qa_status to qc_passed."
    if "figure_digitized_data_missing" in issue_set or "figure_crop_not_qc_passed" in issue_set:
        return "Review crop box/panel, create final clip, digitize or transcribe the data file, then independently QC the extracted row."
    if "source_provenance_missing" in issue_set or "page_missing" in issue_set:
        return "Record exact figure/table label, page, panel, and evidence key from the PDF before QC."
    if "response_measure_missing" in issue_set:
        return "Extract the response value or raw counts from the cited source before QC."
    return "Resolve blocking fields, then independently verify against the source PDF."


def audit_observation(
    row: dict[str, str],
    original: dict[str, str],
    crop_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    source_table_path = ROOT / row.get("source_table", "")
    matched_crops = crop_rows_for_observation(row, crop_rows)
    matched_crop_paths = [crop.get("crop_path", "") for crop in matched_crops if crop.get("crop_path", "")]
    matched_crop_statuses = [crop.get("crop_review_status", "") for crop in matched_crops if crop.get("crop_review_status", "")]
    matched_clip_paths = [crop.get("final_clip_path", "") for crop in matched_crops if crop.get("final_clip_path", "")]
    matched_data_paths = [crop.get("digitized_data_path", "") for crop in matched_crops if crop.get("digitized_data_path", "")]
    concrete_data_paths = [path for path in matched_data_paths if concrete_existing_path(path)]
    concrete_clip_paths = [path for path in matched_clip_paths if concrete_existing_path(path)]

    if not has_value(row.get("source_id", "")):
        add_issue(issues, row, "source_id_missing", "Extracted row has no source_id.")
    if not has_value(row.get("response_type", "")):
        add_issue(issues, row, "response_type_missing", "Extracted row has no response_type.")
    if not has_value(row.get("taxon_raw", "") or original.get("Species", "") or original.get("species", "")):
        add_issue(issues, row, "taxon_missing", "Extracted row has no taxon/species.")
    if not response_measure_present(row, original):
        add_issue(issues, row, "response_measure_missing", "Extracted row has no usable response value or raw count set.")
    if not response_unit_present(row, original):
        add_issue(issues, row, "response_unit_missing", "Extracted row has no response unit, outcome type, or raw-count basis.")
    if not variance_or_counts_present(row, original):
        add_issue(issues, row, "variance_missing", "Extracted row lacks variance or raw-count information.")
    if not has_value(row.get("sample_size", "") or original.get("Sample_Size", "") or original.get("sample_size", "")):
        add_issue(issues, row, "sample_size_missing", "Extracted row has no sample size.")
    if row.get("response_type") in {"rate", "survival", "growth"} and not time_or_duration_present(row, original):
        add_issue(issues, row, "time_or_duration_missing", "Extracted row has no timepoint, interval, or duration.")

    if not source_table_path.exists():
        add_issue(
            issues,
            row,
            "value_data_file_missing",
            "The source extraction table for this row does not exist.",
            expected=relpath(source_table_path),
            observed="missing",
        )
    if not has_value(row.get("figure_or_table_label", "")):
        add_issue(issues, row, "source_provenance_missing", "Exact figure/table label is missing.")
    if not has_value(row.get("page", "")):
        add_issue(issues, row, "page_missing", "PDF page is missing.")

    qa_status = clean(row.get("qa_status", "") or original.get("qa_status", ""))
    if qa_status.lower() not in READY_QA_STATUSES:
        add_issue(
            issues,
            row,
            "qa_status_not_ready",
            "Extracted row has not passed independent QC.",
            expected=" | ".join(sorted(READY_QA_STATUSES)),
            observed=qa_status or "blank",
        )

    label = row.get("figure_or_table_label", "")
    if figure_label_present(label):
        if not matched_crops:
            add_issue(issues, row, "figure_crop_missing", "Figure-derived row has no matching crop-manifest row.")
        if matched_crops and not any(status in READY_QA_STATUSES for status in matched_crop_statuses):
            add_issue(
                issues,
                row,
                "figure_crop_not_qc_passed",
                "Figure crop exists only as an unreviewed or non-final proposal.",
                expected="qc_passed crop review",
                observed=" | ".join(sorted(set(matched_crop_statuses))) or "blank",
            )
        if not concrete_clip_paths:
            add_issue(
                issues,
                row,
                "figure_final_clip_missing",
                "Figure-derived row has no concrete final clip file.",
                expected="existing final_clip_path without placeholders",
                observed=" | ".join(matched_clip_paths) or "blank",
            )
        if not concrete_data_paths:
            add_issue(
                issues,
                row,
                "figure_digitized_data_missing",
                "Figure-derived row has no concrete digitized data CSV.",
                expected="existing digitized_data_path without placeholders",
                observed=" | ".join(matched_data_paths) or "blank",
            )
    elif not table_label_present(label) and has_value(label):
        add_issue(
            issues,
            row,
            "source_label_type_unclear",
            "Source label is present but is not clearly a table or figure.",
            severity="warning",
            observed=label,
        )

    blocking_ids = [issue["issue_id"] for issue in issues if issue["severity"] == "blocker"]
    warning_ids = [issue["issue_id"] for issue in issues if issue["severity"] != "blocker"]
    audit_row: dict[str, object] = {
        **{field: row.get(field, "") for field in OBS_AUDIT_FIELDS},
        "analysis_ready": int(not blocking_ids),
        "readiness_status": "analysis_ready" if not blocking_ids else "blocked",
        "blocking_issue_count": len(blocking_ids),
        "blocking_issues": "|".join(blocking_ids),
        "warning_issues": "|".join(warning_ids),
        "next_action": next_action_for_issues(blocking_ids),
        "evidence_key": original_value(original, "evidence_key"),
        "extraction_provenance": original_value(original, "extraction_provenance"),
        "rate_value": original_value(original, "rate_value", "Rate_Value"),
        "rate_unit": original_value(original, "rate_unit", "Rate_Unit"),
        "rate_derivation_basis": original_value(original, "rate_derivation_basis"),
        "observation_type": row.get("outcome_type", "") or original_value(original, "observation_type", "Outcome_Type"),
        "timepoint_or_interval": original_value(original, "timepoint_or_interval"),
        "calculation_notes": original_value(original, "calculation_notes", "Notes"),
        "value_data_file": row.get("source_table", ""),
        "matched_crop_count": len(matched_crops),
        "matched_crop_paths": "|".join(matched_crop_paths),
        "matched_crop_review_statuses": "|".join(matched_crop_statuses),
        "matched_final_clip_paths": "|".join(matched_clip_paths),
        "matched_digitized_data_paths": "|".join(matched_data_paths),
        "concrete_digitized_data_files": "|".join(concrete_data_paths),
        "concrete_final_clip_files": "|".join(concrete_clip_paths),
    }
    return audit_row, issues


def notebook_lookup(batch_rows: list[dict[str, str]], log_rows: list[dict[str, str]]) -> dict[tuple[str, str], tuple[str, str]]:
    log_by_batch = {row.get("batch_id", ""): row for row in log_rows}
    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    for batch in batch_rows:
        batch_id = batch.get("batch_id", "")
        response = batch.get("response_type", "")
        status = log_by_batch.get(batch_id, {}).get("status", "")
        if status == "skipped_existing":
            status = "validated_existing_json"
        for source_id in batch.get("source_ids", "").split("|"):
            if source_id:
                lookup[(source_id, response)] = (batch_id, status)
    return lookup


def response_next_action(status: str) -> str:
    return {
        "analysis_ready_observations_present": "Ready rows exist; keep them locked unless upstream source data change.",
        "extracted_values_need_provenance_or_qc": "Verify existing extracted rows against PDFs, record exact source evidence, and set qa_status only after independent QC.",
        "crop_proposals_need_human_qa_and_digitization": "Review proposed crop boxes, set panel labels, create final clips, digitize/transcribe data CSVs, then extract rows.",
        "extract_from_pdf_text_or_table_candidates": "Use PDF text candidates and NotebookLM validation to extract source-verified rows.",
        "full_pdf_review_needed": "Read the PDF directly and identify extractable text, table, or figure evidence.",
    }[status]


def build_response_queue(
    workplan_rows: list[dict[str, str]],
    audit_rows: list[dict[str, object]],
    crop_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    nlm_lookup: dict[tuple[str, str], tuple[str, str]],
) -> list[dict[str, object]]:
    audit_by_response: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in audit_rows:
        audit_by_response[(str(row.get("source_id", "")), str(row.get("response_type", "")))].append(row)
    crop_by_response = Counter(row_key(row) for row in crop_rows if row.get("crop_status") != "retained_rejected_not_cropped")
    crop_need_qa = Counter(
        row_key(row)
        for row in crop_rows
        if row.get("crop_status") != "retained_rejected_not_cropped"
        and row.get("crop_review_status", "").lower() not in READY_QA_STATUSES
    )
    concrete_data = Counter(
        row_key(row)
        for row in crop_rows
        if row.get("crop_status") != "retained_rejected_not_cropped"
        and concrete_existing_path(row.get("digitized_data_path", ""))
    )
    candidates_by_response = Counter(row_key(row) for row in candidate_rows)

    rows: list[dict[str, object]] = []
    for workplan in workplan_rows:
        if workplan.get("final_status") != "include_primary" or workplan.get("response_type") not in PRIMARY_RESPONSES:
            continue
        key = row_key(workplan)
        audits = audit_by_response.get(key, [])
        ready_count = sum(1 for row in audits if str(row.get("analysis_ready", "")) == "1")
        blocked_count = sum(1 for row in audits if str(row.get("readiness_status", "")) == "blocked")
        crops = crop_by_response.get(key, 0)
        crop_qa = crop_need_qa.get(key, 0)
        candidate_count = candidates_by_response.get(key, 0)
        batch_id, nlm_status = nlm_lookup.get(key, ("", ""))
        if ready_count:
            gate_status = "analysis_ready_observations_present"
        elif audits:
            gate_status = "extracted_values_need_provenance_or_qc"
        elif crops:
            gate_status = "crop_proposals_need_human_qa_and_digitization"
        elif candidate_count:
            gate_status = "extract_from_pdf_text_or_table_candidates"
        else:
            gate_status = "full_pdf_review_needed"

        issue_counter = Counter()
        for audit in audits:
            for issue in str(audit.get("blocking_issues", "")).split("|"):
                if issue:
                    issue_counter[issue] += 1
        rows.append(
            {
                "source_id": key[0],
                "response_type": key[1],
                "paper_title": workplan.get("paper_title", ""),
                "local_relpath": workplan.get("local_relpath", ""),
                "priority_rank": workplan.get("priority_rank", ""),
                "extraction_readiness": workplan.get("extraction_readiness", ""),
                "existing_extraction_rows": len(audits),
                "analysis_ready_rows": ready_count,
                "blocking_extraction_rows": blocked_count,
                "crop_proposals": crops,
                "crop_proposals_need_human_qa": crop_qa,
                "concrete_digitized_data_files": concrete_data.get(key, 0),
                "pdf_text_candidate_rows": candidate_count,
                "notebooklm_batch_id": batch_id,
                "notebooklm_validation_status": nlm_status,
                "response_gate_status": gate_status,
                "next_action": response_next_action(gate_status),
                "blocking_summary": " | ".join(f"{issue}={count}" for issue, count in sorted(issue_counter.items())),
            }
        )
    return rows


def write_summary(
    path: Path,
    audit_rows: list[dict[str, object]],
    ready_rows: list[dict[str, object]],
    issue_rows: list[dict[str, str]],
    response_rows: list[dict[str, object]],
    crop_rows: list[dict[str, str]],
) -> None:
    response_counts = Counter(str(row.get("response_type", "")) for row in audit_rows)
    ready_counts = Counter(str(row.get("response_type", "")) for row in ready_rows)
    issue_counts = Counter(row["issue_id"] for row in issue_rows if row.get("severity") == "blocker")
    response_status_counts = Counter(str(row.get("response_gate_status", "")) for row in response_rows)
    crop_status_counts = Counter(row.get("crop_review_status", "") for row in crop_rows if row.get("crop_status") != "retained_rejected_not_cropped")
    concrete_digitized = sum(
        1
        for row in crop_rows
        if row.get("crop_status") != "retained_rejected_not_cropped"
        and concrete_existing_path(row.get("digitized_data_path", ""))
    )
    lines = [
        "# Analysis-Ready Extraction Gate",
        "",
        "Generated by `python3 tools/build_analysis_ready_dataset.py`.",
        "",
        "## Current Result",
        "",
        f"- extracted observation rows audited: {len(audit_rows)}",
        f"- analysis-ready rows: {len(ready_rows)}",
        f"- blocker issues: {sum(1 for row in issue_rows if row.get('severity') == 'blocker')}",
        f"- primary response rows in response queue: {len(response_rows)}",
        f"- reviewed concrete digitized data files found: {concrete_digitized}",
        "",
        "## Audited Rows By Response",
        "",
    ]
    for response, count in sorted(response_counts.items()):
        lines.append(f"- {response}: {count} audited; {ready_counts.get(response, 0)} analysis-ready")
    lines.extend(["", "## Response Gate Status", ""])
    for status, count in sorted(response_status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Crop Review Status", ""])
    for status, count in sorted(crop_status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Top Blocking Issues", ""])
    for issue, count in issue_counts.most_common(20):
        lines.append(f"- `{issue}`: {count}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `{relpath(READY_OBS)}`",
            f"- `{relpath(OBS_AUDIT)}`",
            f"- `{relpath(ISSUES)}`",
            f"- `{relpath(BLOCKING_QUEUE)}`",
            f"- `{relpath(RESPONSE_QUEUE)}`",
            "",
            "## Rules",
            "",
            "- The gate is fail-closed: blank, placeholder, unreviewed, or missing provenance fields block pooling.",
            "- Figure-derived values require a reviewed crop, concrete final clip, and concrete digitized data CSV.",
            "- Table/text-derived values require exact label/page evidence and independent QC in the source extraction table.",
            "- Survival raw counts can satisfy the variance requirement because binomial variance can be derived from counts.",
            "- No row should enter modeling until it appears in `ANALYSIS_READY_OBSERVATIONS.csv`.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_outputs(args: argparse.Namespace) -> int:
    existing_rows = read_csv(args.existing_rows)
    crop_rows = read_csv(args.crop_manifest)
    workplan_rows = read_csv(args.workplan)
    candidate_rows = read_csv(args.candidates)
    original_lookup = original_rows_by_source_row(existing_rows)
    nlm_lookup = notebook_lookup(read_csv(args.notebooklm_batches), read_csv(args.notebooklm_log))

    audit_rows: list[dict[str, object]] = []
    issue_rows: list[dict[str, str]] = []
    for row in existing_rows:
        original = original_lookup.get((row.get("source_table", ""), row.get("source_row", "")), {})
        audit_row, issues = audit_observation(row, original, crop_rows)
        audit_rows.append(audit_row)
        issue_rows.extend(issues)

    ready_rows = [row for row in audit_rows if str(row.get("analysis_ready", "")) == "1"]
    blocking_rows = [row for row in audit_rows if str(row.get("readiness_status", "")) == "blocked"]
    response_rows = build_response_queue(workplan_rows, audit_rows, crop_rows, candidate_rows, nlm_lookup)

    write_csv(args.observation_audit, OBS_AUDIT_FIELDS, audit_rows)
    write_csv(args.ready_observations, OBS_AUDIT_FIELDS, ready_rows)
    write_csv(args.issues, ISSUE_FIELDS, issue_rows)
    write_csv(args.blocking_queue, OBS_AUDIT_FIELDS, blocking_rows)
    write_csv(args.response_queue, RESPONSE_QUEUE_FIELDS, response_rows)
    write_summary(args.summary, audit_rows, ready_rows, issue_rows, response_rows, crop_rows)
    print(f"Wrote {relpath(args.summary)}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workplan", type=Path, default=WORKPLAN)
    parser.add_argument("--existing-rows", type=Path, default=EXISTING_ROWS)
    parser.add_argument("--crop-manifest", type=Path, default=CROP_MANIFEST)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--notebooklm-batches", type=Path, default=NLM_BATCHES)
    parser.add_argument("--notebooklm-log", type=Path, default=NLM_LOG)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--observation-audit", type=Path, default=OBS_AUDIT)
    parser.add_argument("--ready-observations", type=Path, default=READY_OBS)
    parser.add_argument("--issues", type=Path, default=ISSUES)
    parser.add_argument("--blocking-queue", type=Path, default=BLOCKING_QUEUE)
    parser.add_argument("--response-queue", type=Path, default=RESPONSE_QUEUE)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _ = generated  # Kept for future provenance stamping without changing output schema.
    return build_outputs(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

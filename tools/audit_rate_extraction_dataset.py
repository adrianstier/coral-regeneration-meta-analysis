#!/usr/bin/env python3
"""Audit the rate-extraction workspace for join, provenance, and readiness errors."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKPLAN = ROOT / "pipeline" / "EXTRACTION_WORKPLAN.csv"
FIGURE_QUEUE_AUDIT = ROOT / "digitization" / "source_review" / "FIGURE_QUEUE_AUDIT_STATUS.csv"
FIGURE_CROP_MANIFEST = ROOT / "digitization" / "figures" / "FIGURE_CROP_MANIFEST.csv"
DIGITIZED_DATA_DIR = ROOT / "digitization" / "data"
RATE_DIR = ROOT / "data" / "extraction" / "rate"
SOURCE_INDEX = RATE_DIR / "RATE_SOURCE_INDEX.csv"
TEXT_EVIDENCE = RATE_DIR / "RATE_TEXT_EVIDENCE.csv"
CURATED_OBSERVATIONS = RATE_DIR / "RATE_EXTRACTED_OBSERVATIONS.csv"
EFFECT_SEEDS = RATE_DIR / "RATE_EFFECT_SIZE_SEEDS.csv"
SOURCE_REVIEW_OVERRIDES = RATE_DIR / "RATE_SOURCE_REVIEW_OVERRIDES.csv"
AUDIT_CSV = RATE_DIR / "RATE_EXTRACTION_AUDIT.csv"
AUDIT_SUMMARY = RATE_DIR / "RATE_EXTRACTION_AUDIT_SUMMARY.md"

AUDIT_FIELDS = [
    "severity",
    "check_id",
    "source_id",
    "row_id",
    "file",
    "message",
    "expected",
    "observed",
]

ALLOWED_ROUTES = {
    "curated_values_analysis_ready",
    "curated_values_available_needs_qc",
    "digitized_data_available_needs_effect_extraction",
    "seed_values_available_needs_provenance_qa",
    "needs_figure_or_table_digitization",
    "needs_audited_source_candidate",
    "needs_text_or_table_extraction",
    "not_extractable_no_valid_figure_or_table_candidate",
    "not_rate_extractable_wrong_response_assignment",
}

ALLOWED_BASES = {
    "reported_areal_rate",
    "reported_linear_rate",
    "reported_proportional_rate",
    "reported_exponential_slope",
    "reported_rate_unspecified_basis",
    "reported_or_calculated_exponential_slope",
    "reported_or_calculated_linear_rate",
    "reported_or_calculated_areal_rate",
    "reported_or_calculated_proportional_rate",
    "initial_final_wound_size",
    "time_series_wound_size",
    "time_to_closure",
    "pilot_covariate_only_no_rate_value",
}

READY_QA_STATUSES = {"qc_passed", "analysis_ready", "ready_for_analysis"}
NUMERICISH = re.compile(r"^\s*(?:NA|na|n/a|[-+]?(\d+\.?\d*|\.\d+)(?:\s*[-/]\s*\d+\.?\d*)?)?\s*$")


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def relpath(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def add_issue(
    issues: list[dict[str, str]],
    severity: str,
    check_id: str,
    message: str,
    *,
    source_id: str = "",
    row_id: str = "",
    file: Path | str = "",
    expected: str = "",
    observed: str = "",
) -> None:
    issues.append(
        {
            "severity": severity,
            "check_id": check_id,
            "source_id": source_id,
            "row_id": row_id,
            "file": relpath(file) if isinstance(file, Path) else str(file),
            "message": message,
            "expected": expected,
            "observed": observed,
        }
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_csv_strict(path: Path, issues: list[dict[str, str]]) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        add_issue(issues, "error", "missing_csv", "Required CSV file is missing.", file=path)
        return [], []
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            add_issue(issues, "error", "empty_csv", "Required CSV file has no header.", file=path)
            return [], []
        duplicate_headers = [field for field, count in Counter(header).items() if count > 1]
        if duplicate_headers:
            add_issue(
                issues,
                "error",
                "duplicate_header",
                "CSV header names must be unique.",
                file=path,
                observed=" | ".join(sorted(duplicate_headers)),
            )
        for row_number, values in enumerate(reader, start=2):
            if len(values) != len(header):
                add_issue(
                    issues,
                    "error",
                    "csv_row_width_mismatch",
                    "CSV row does not have the same number of fields as the header.",
                    row_id=str(row_number),
                    file=path,
                    expected=str(len(header)),
                    observed=str(len(values)),
                )
            padded = values[: len(header)] + [""] * max(0, len(header) - len(values))
            row = dict(zip(header, padded))
            row["_row_number"] = str(row_number)
            rows.append(row)
    return header, rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def parse_int(value: str) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def ids_with_duplicates(rows: list[dict[str, str]], field: str) -> list[str]:
    counts = Counter(row.get(field, "") for row in rows if row.get(field, ""))
    return sorted(key for key, count in counts.items() if count > 1)


def assert_unique_ids(
    issues: list[dict[str, str]], rows: list[dict[str, str]], field: str, file: Path, check_id: str
) -> None:
    for duplicate in ids_with_duplicates(rows, field):
        add_issue(
            issues,
            "error",
            check_id,
            f"`{field}` values must be unique.",
            row_id=duplicate,
            file=file,
            expected="1 row",
            observed=str(sum(1 for row in rows if row.get(field) == duplicate)),
        )


def workplan_rate_sources(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("final_status") == "include_primary" and row.get("response_type") == "rate"
    ]


def group_counts(rows: list[dict[str, str]], field: str) -> Counter[str]:
    return Counter(row.get(field, "") for row in rows if row.get(field, ""))


def audit_source_index(
    issues: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    workplan_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
    effect_rows: list[dict[str, str]],
    figure_queue_rows: list[dict[str, str]],
    crop_rows: list[dict[str, str]],
) -> None:
    rate_workplan = workplan_rate_sources(workplan_rows)
    source_ids = {row.get("source_id", "") for row in source_rows}
    workplan_ids = {row.get("source_id", "") for row in rate_workplan}
    assert_unique_ids(issues, source_rows, "source_id", SOURCE_INDEX, "duplicate_source_index_id")

    if len(source_rows) != len(rate_workplan):
        add_issue(
            issues,
            "error",
            "rate_source_count_mismatch",
            "RATE_SOURCE_INDEX.csv should contain exactly one row per primary rate source in EXTRACTION_WORKPLAN.csv.",
            file=SOURCE_INDEX,
            expected=str(len(rate_workplan)),
            observed=str(len(source_rows)),
        )
    if source_ids != workplan_ids:
        missing = sorted(workplan_ids - source_ids)
        extra = sorted(source_ids - workplan_ids)
        add_issue(
            issues,
            "error",
            "rate_source_id_set_mismatch",
            "RATE_SOURCE_INDEX.csv source_ids differ from the primary rate workplan source_ids.",
            file=SOURCE_INDEX,
            expected="missing: none; extra: none",
            observed=f"missing: {' | '.join(missing) or 'none'}; extra: {' | '.join(extra) or 'none'}",
        )

    workplan_by_source = {row.get("source_id", ""): row for row in rate_workplan}
    evidence_counts = group_counts(evidence_rows, "source_id")
    observation_counts = group_counts(observation_rows, "source_id")
    observation_ready_counts = Counter(
        row.get("source_id", "") for row in observation_rows if row.get("analysis_ready") == "1"
    )
    effect_counts = group_counts(effect_rows, "source_id")
    figure_queue_by_source = {
        row.get("source_id", ""): row for row in figure_queue_rows if row.get("response_type") == "rate"
    }
    crop_count = Counter()
    valid_crop_count = Counter()
    digitized_count = Counter()
    figure_candidate_count = Counter()
    table_candidate_count = Counter()
    for row in crop_rows:
        if row.get("response_type") != "rate":
            continue
        source_id = row.get("source_id", "")
        crop_count[source_id] += 1
        if row.get("crop_status") != "retained_rejected_not_cropped":
            valid_crop_count[source_id] += 1
        if row.get("candidate_type") == "figure":
            figure_candidate_count[source_id] += 1
        if row.get("candidate_type") == "table":
            table_candidate_count[source_id] += 1
        data_path = row.get("digitized_data_path", "")
        if data_path and (ROOT / data_path).exists():
            digitized_count[source_id] += 1

    for row in source_rows:
        source_id = row.get("source_id", "")
        workplan = workplan_by_source.get(source_id, {})
        local_relpath = row.get("local_relpath", "")
        pdf_path = ROOT / local_relpath if local_relpath else ROOT
        if local_relpath and not pdf_path.exists():
            add_issue(
                issues,
                "error",
                "source_pdf_missing",
                "Source index points to a local PDF that does not exist.",
                source_id=source_id,
                file=SOURCE_INDEX,
                observed=local_relpath,
            )
        if workplan:
            for field in ["paper_title", "local_relpath", "requires_digitization", "recommended_action", "final_rationale"]:
                if row.get(field, "") != workplan.get(field, ""):
                    add_issue(
                        issues,
                        "error",
                        "source_workplan_field_mismatch",
                        f"Source index `{field}` differs from EXTRACTION_WORKPLAN.csv.",
                        source_id=source_id,
                        file=SOURCE_INDEX,
                        expected=workplan.get(field, ""),
                        observed=row.get(field, ""),
                    )
        if row.get("pdf_parse_status") != "parsed":
            add_issue(
                issues,
                "error",
                "pdf_not_parsed",
                "Each local primary rate PDF should parse to text.",
                source_id=source_id,
                file=SOURCE_INDEX,
                expected="parsed",
                observed=row.get("pdf_parse_status", ""),
            )
        for field in ["pdf_page_count", "pdf_text_chars"]:
            parsed = parse_int(row.get(field, ""))
            if parsed is None or parsed <= 0:
                add_issue(
                    issues,
                    "error",
                    "pdf_parse_metric_invalid",
                    f"`{field}` should be a positive integer for parsed PDFs.",
                    source_id=source_id,
                    file=SOURCE_INDEX,
                    observed=row.get(field, ""),
                )
        text_hash = row.get("pdf_text_sha256", "")
        if len(text_hash) != 64:
            add_issue(
                issues,
                "error",
                "pdf_text_hash_invalid",
                "Parsed PDF text hash should be a SHA-256 hex digest.",
                source_id=source_id,
                file=SOURCE_INDEX,
                expected="64 characters",
                observed=str(len(text_hash)),
            )
        if str(evidence_counts[source_id]) != row.get("text_evidence_rows", ""):
            add_issue(
                issues,
                "error",
                "text_evidence_count_mismatch",
                "Source index text_evidence_rows differs from RATE_TEXT_EVIDENCE.csv.",
                source_id=source_id,
                file=SOURCE_INDEX,
                expected=str(evidence_counts[source_id]),
                observed=row.get("text_evidence_rows", ""),
            )
        if evidence_counts[source_id] == 0:
            add_issue(
                issues,
                "error",
                "source_missing_text_evidence",
                "Parsed rate source has no ranked text-evidence rows.",
                source_id=source_id,
                file=TEXT_EVIDENCE,
            )
        if str(observation_counts[source_id]) != row.get("curated_observation_count", ""):
            add_issue(
                issues,
                "error",
                "curated_observation_count_mismatch",
                "Source index curated_observation_count differs from RATE_EXTRACTED_OBSERVATIONS.csv.",
                source_id=source_id,
                file=SOURCE_INDEX,
                expected=str(observation_counts[source_id]),
                observed=row.get("curated_observation_count", ""),
            )
        if str(observation_ready_counts[source_id]) != row.get("curated_analysis_ready_count", ""):
            add_issue(
                issues,
                "error",
                "curated_ready_count_mismatch",
                "Source index curated_analysis_ready_count differs from RATE_EXTRACTED_OBSERVATIONS.csv.",
                source_id=source_id,
                file=SOURCE_INDEX,
                expected=str(observation_ready_counts[source_id]),
                observed=row.get("curated_analysis_ready_count", ""),
            )
        for field, counts in [
            ("crop_proposal_count", crop_count),
            ("valid_crop_proposal_count", valid_crop_count),
            ("figure_candidate_count", figure_candidate_count),
            ("table_candidate_count", table_candidate_count),
            ("digitized_data_file_count", digitized_count),
        ]:
            if str(counts[source_id]) != row.get(field, ""):
                add_issue(
                    issues,
                    "error",
                    "crop_count_mismatch",
                    f"Source index `{field}` differs from FIGURE_CROP_MANIFEST.csv and local digitized files.",
                    source_id=source_id,
                    file=SOURCE_INDEX,
                    expected=str(counts[source_id]),
                    observed=row.get(field, ""),
                )
        if truthy(row.get("requires_digitization", "")) and source_id not in figure_queue_by_source:
            add_issue(
                issues,
                "error",
                "digitization_source_missing_queue_status",
                "Rate source requires digitization but lacks a rate FIGURE_QUEUE_AUDIT_STATUS row.",
                source_id=source_id,
                file=FIGURE_QUEUE_AUDIT,
            )
        route = row.get("rate_extraction_route", "")
        if route not in ALLOWED_ROUTES:
            add_issue(
                issues,
                "error",
                "unknown_rate_route",
                "Rate extraction route is not in the allowed route vocabulary.",
                source_id=source_id,
                file=SOURCE_INDEX,
                observed=route,
            )
        if row.get("analysis_ready", "") not in {"0", "1"}:
            add_issue(
                issues,
                "error",
                "invalid_source_analysis_ready",
                "Source-level analysis_ready must be 0 or 1.",
                source_id=source_id,
                file=SOURCE_INDEX,
                observed=row.get("analysis_ready", ""),
            )
        if row.get("analysis_ready") == "1" and route != "curated_values_analysis_ready":
            add_issue(
                issues,
                "error",
                "source_analysis_ready_route_mismatch",
                "Source is marked analysis-ready through a non-ready route.",
                source_id=source_id,
                file=SOURCE_INDEX,
                expected="curated_values_analysis_ready",
                observed=route,
            )
        if route == "curated_values_available_needs_qc" and observation_counts[source_id] == 0:
            add_issue(
                issues,
                "error",
                "curated_route_without_rows",
                "Curated route requires at least one curated observation row.",
                source_id=source_id,
                file=SOURCE_INDEX,
            )
        if route == "seed_values_available_needs_provenance_qa" and effect_counts[source_id] == 0:
            add_issue(
                issues,
                "error",
                "seed_route_without_seed_rows",
                "Seed route requires at least one seed row.",
                source_id=source_id,
                file=SOURCE_INDEX,
            )
        if route == "needs_figure_or_table_digitization" and not truthy(row.get("requires_digitization", "")):
            add_issue(
                issues,
                "error",
                "digitization_route_without_digitization_flag",
                "Digitization route requires requires_digitization=1.",
                source_id=source_id,
                file=SOURCE_INDEX,
            )
        if route == "not_rate_extractable_wrong_response_assignment" and not row.get("source_review_override_reason", ""):
            add_issue(
                issues,
                "error",
                "non_rate_override_missing_reason",
                "Wrong-response route must be tied to an explicit override reason.",
                source_id=source_id,
                file=SOURCE_INDEX,
            )


def audit_evidence(
    issues: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> None:
    source_by_id = {row.get("source_id", ""): row for row in source_rows}
    ranks_by_source: dict[str, list[int]] = defaultdict(list)
    for row in evidence_rows:
        source_id = row.get("source_id", "")
        if source_id not in source_by_id:
            add_issue(
                issues,
                "error",
                "text_evidence_unknown_source",
                "Text evidence row source_id is not in RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                row_id=row.get("_row_number", ""),
                file=TEXT_EVIDENCE,
            )
            continue
        if row.get("text_sha256", "") != source_by_id[source_id].get("pdf_text_sha256", ""):
            add_issue(
                issues,
                "error",
                "text_evidence_hash_mismatch",
                "Text evidence hash differs from source-index parsed text hash.",
                source_id=source_id,
                row_id=row.get("_row_number", ""),
                file=TEXT_EVIDENCE,
                expected=source_by_id[source_id].get("pdf_text_sha256", ""),
                observed=row.get("text_sha256", ""),
            )
        rank = parse_int(row.get("evidence_rank", ""))
        if rank is None or rank <= 0:
            add_issue(
                issues,
                "error",
                "text_evidence_rank_invalid",
                "Evidence rank must be a positive integer.",
                source_id=source_id,
                row_id=row.get("_row_number", ""),
                file=TEXT_EVIDENCE,
                observed=row.get("evidence_rank", ""),
            )
        else:
            ranks_by_source[source_id].append(rank)
        for field in ["pdf_page", "score"]:
            parsed = parse_int(row.get(field, ""))
            if parsed is None or parsed <= 0:
                add_issue(
                    issues,
                    "error",
                    "text_evidence_numeric_field_invalid",
                    f"`{field}` must be a positive integer.",
                    source_id=source_id,
                    row_id=row.get("_row_number", ""),
                    file=TEXT_EVIDENCE,
                    observed=row.get(field, ""),
                )
        if not row.get("snippet", "").strip():
            add_issue(
                issues,
                "error",
                "text_evidence_blank_snippet",
                "Text evidence row has no snippet.",
                source_id=source_id,
                row_id=row.get("_row_number", ""),
                file=TEXT_EVIDENCE,
            )
    for source_id, ranks in ranks_by_source.items():
        expected = list(range(1, len(ranks) + 1))
        observed = sorted(ranks)
        if observed != expected:
            add_issue(
                issues,
                "error",
                "text_evidence_rank_sequence",
                "Evidence ranks should be contiguous within each source.",
                source_id=source_id,
                file=TEXT_EVIDENCE,
                expected=",".join(map(str, expected)),
                observed=",".join(map(str, observed)),
            )


def audit_curated_observations(
    issues: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> None:
    source_ids = {row.get("source_id", "") for row in source_rows}
    assert_unique_ids(issues, observation_rows, "observation_id", CURATED_OBSERVATIONS, "duplicate_observation_id")
    for row in observation_rows:
        source_id = row.get("source_id", "")
        row_id = row.get("observation_id", row.get("_row_number", ""))
        if source_id not in source_ids:
            add_issue(
                issues,
                "error",
                "curated_observation_unknown_source",
                "Curated observation source_id is not in RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
            )
        if row.get("analysis_ready", "") not in {"0", "1"}:
            add_issue(
                issues,
                "error",
                "invalid_curated_analysis_ready",
                "Curated observation analysis_ready must be 0 or 1.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
                observed=row.get("analysis_ready", ""),
            )
        if row.get("analysis_ready") == "1" and row.get("qa_status", "") not in READY_QA_STATUSES:
            add_issue(
                issues,
                "error",
                "curated_ready_without_ready_qc",
                "Curated observation cannot be analysis-ready with a provisional QA status.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
                observed=row.get("qa_status", ""),
            )
        if row.get("rate_derivation_basis", "") not in ALLOWED_BASES:
            add_issue(
                issues,
                "error",
                "unknown_curated_derivation_basis",
                "Curated observation has an unknown rate_derivation_basis.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
                observed=row.get("rate_derivation_basis", ""),
            )
        for field in ["observation_type", "species", "timepoint_or_interval", "figure_or_table_label", "page", "evidence_key"]:
            if not row.get(field, "").strip():
                add_issue(
                    issues,
                    "warning",
                    "curated_required_context_blank",
                    f"Curated observation lacks `{field}` context.",
                    source_id=source_id,
                    row_id=row_id,
                    file=CURATED_OBSERVATIONS,
                )
        if parse_int(row.get("page", "")) is None:
            add_issue(
                issues,
                "error",
                "curated_page_invalid",
                "Curated observation page must be an integer PDF page.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
                observed=row.get("page", ""),
            )
        variance_type = row.get("variance_type", "").strip()
        variance_value = row.get("variance_value", "").strip()
        if (variance_type and not variance_value and variance_type != "not_reported") or (variance_value and not variance_type):
            add_issue(
                issues,
                "warning",
                "curated_variance_partial",
                "Variance type/value are only partially populated.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
                expected="both fields or explicit not_reported",
                observed=f"{variance_type} / {variance_value}",
            )
        sample_size = row.get("sample_size", "").strip()
        if sample_size and not NUMERICISH.match(sample_size):
            add_issue(
                issues,
                "error",
                "curated_sample_size_not_numericish",
                "Sample size should be blank or numeric-like.",
                source_id=source_id,
                row_id=row_id,
                file=CURATED_OBSERVATIONS,
                observed=sample_size,
            )


def audit_effect_seeds(
    issues: list[dict[str, str]],
    effect_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> None:
    source_ids = {row.get("source_id", "") for row in source_rows}
    assert_unique_ids(issues, effect_rows, "rate_effect_id", EFFECT_SEEDS, "duplicate_rate_effect_id")
    for row in effect_rows:
        source_id = row.get("source_id", "")
        row_id = row.get("rate_effect_id", row.get("_row_number", ""))
        if source_id not in source_ids:
            add_issue(
                issues,
                "error",
                "effect_seed_unknown_source",
                "Seed effect source_id is not in RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                row_id=row_id,
                file=EFFECT_SEEDS,
            )
        if row.get("analysis_ready", "") not in {"0", "1"}:
            add_issue(
                issues,
                "error",
                "invalid_effect_analysis_ready",
                "Seed effect analysis_ready must be 0 or 1.",
                source_id=source_id,
                row_id=row_id,
                file=EFFECT_SEEDS,
                observed=row.get("analysis_ready", ""),
            )
        if row.get("analysis_ready") == "1" and row.get("provenance_status", "") not in READY_QA_STATUSES:
            add_issue(
                issues,
                "error",
                "effect_ready_without_ready_provenance",
                "Seed effect cannot be analysis-ready with a provisional provenance status.",
                source_id=source_id,
                row_id=row_id,
                file=EFFECT_SEEDS,
                observed=row.get("provenance_status", ""),
            )
        if row.get("rate_derivation_basis", "") not in ALLOWED_BASES:
            add_issue(
                issues,
                "error",
                "unknown_effect_derivation_basis",
                "Seed effect has an unknown rate_derivation_basis.",
                source_id=source_id,
                row_id=row_id,
                file=EFFECT_SEEDS,
                observed=row.get("rate_derivation_basis", ""),
            )
        if not row.get("seed_source", "").strip() or not row.get("seed_source_row", "").strip():
            add_issue(
                issues,
                "error",
                "effect_seed_source_blank",
                "Seed effect must identify the source CSV and row.",
                source_id=source_id,
                row_id=row_id,
                file=EFFECT_SEEDS,
            )


def audit_overrides(
    issues: list[dict[str, str]],
    override_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> None:
    source_ids = {row.get("source_id", "") for row in source_rows}
    assert_unique_ids(issues, override_rows, "source_id", SOURCE_REVIEW_OVERRIDES, "duplicate_override_source_id")
    for row in override_rows:
        source_id = row.get("source_id", "")
        if source_id not in source_ids:
            add_issue(
                issues,
                "error",
                "override_unknown_source",
                "Source-review override source_id is not in RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                file=SOURCE_REVIEW_OVERRIDES,
            )
        if row.get("rate_extraction_route", "") not in ALLOWED_ROUTES:
            add_issue(
                issues,
                "error",
                "override_unknown_route",
                "Source-review override route is not in the allowed route vocabulary.",
                source_id=source_id,
                file=SOURCE_REVIEW_OVERRIDES,
                observed=row.get("rate_extraction_route", ""),
            )
        if not row.get("override_reason", "").strip():
            add_issue(
                issues,
                "error",
                "override_reason_blank",
                "Source-review override must explain the source-level decision.",
                source_id=source_id,
                file=SOURCE_REVIEW_OVERRIDES,
            )


def audit_figure_links(
    issues: list[dict[str, str]],
    figure_queue_rows: list[dict[str, str]],
    crop_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
) -> None:
    source_ids = {row.get("source_id", "") for row in source_rows}
    queue_ids = {row.get("figure_queue_id", "") for row in source_rows if row.get("figure_queue_id", "")}
    for row in figure_queue_rows:
        if row.get("response_type") != "rate":
            continue
        source_id = row.get("source_id", "")
        queue_id = row.get("queue_id", "")
        if source_id not in source_ids:
            add_issue(
                issues,
                "error",
                "rate_figure_queue_unknown_source",
                "Rate figure-queue status row is not tied to a source-index row.",
                source_id=source_id,
                row_id=queue_id,
                file=FIGURE_QUEUE_AUDIT,
            )
        if queue_id and queue_id not in queue_ids:
            add_issue(
                issues,
                "error",
                "rate_figure_queue_not_indexed",
                "Rate figure-queue status row is not indexed by RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                row_id=queue_id,
                file=FIGURE_QUEUE_AUDIT,
            )
    for row in crop_rows:
        if row.get("response_type") != "rate":
            continue
        source_id = row.get("source_id", "")
        queue_id = row.get("queue_id", "")
        if source_id not in source_ids:
            add_issue(
                issues,
                "error",
                "rate_crop_unknown_source",
                "Rate crop-manifest row source_id is not in RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                row_id=queue_id,
                file=FIGURE_CROP_MANIFEST,
            )
        if queue_id and queue_id not in queue_ids:
            add_issue(
                issues,
                "error",
                "rate_crop_queue_not_indexed",
                "Rate crop-manifest row queue_id is not indexed by RATE_SOURCE_INDEX.csv.",
                source_id=source_id,
                row_id=queue_id,
                file=FIGURE_CROP_MANIFEST,
            )
        for field in ["source_page_render", "crop_path"]:
            value = row.get(field, "")
            if value and not (ROOT / value).exists():
                add_issue(
                    issues,
                    "error",
                    "rate_crop_file_missing",
                    f"`{field}` points to a missing local file.",
                    source_id=source_id,
                    row_id=queue_id,
                    file=FIGURE_CROP_MANIFEST,
                    observed=value,
                )
        data_path = row.get("digitized_data_path", "")
        if data_path and (ROOT / data_path).exists() and not data_path.startswith(relpath(DIGITIZED_DATA_DIR)):
            add_issue(
                issues,
                "warning",
                "digitized_data_outside_data_dir",
                "Digitized data path exists but is outside digitization/data.",
                source_id=source_id,
                row_id=queue_id,
                file=FIGURE_CROP_MANIFEST,
                observed=data_path,
            )


def add_status_notes(
    issues: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
    effect_rows: list[dict[str, str]],
) -> None:
    ready_sources = sum(1 for row in source_rows if row.get("analysis_ready") == "1")
    ready_observations = sum(1 for row in observation_rows if row.get("analysis_ready") == "1")
    ready_effects = sum(1 for row in effect_rows if row.get("analysis_ready") == "1")
    if ready_sources == ready_observations == ready_effects == 0:
        add_issue(
            issues,
            "warning",
            "no_analysis_ready_rate_rows",
            "No source, curated observation, or seed effect row is currently marked analysis-ready.",
            file=SOURCE_INDEX,
            expected="analysis-ready rows after independent QC",
            observed="0",
        )
    for route, count in sorted(group_counts(source_rows, "rate_extraction_route").items()):
        add_issue(
            issues,
            "info",
            "rate_route_count",
            "Current source-level extraction route count.",
            row_id=route,
            file=SOURCE_INDEX,
            observed=str(count),
        )
    digitization_remaining = sum(
        1 for row in source_rows if row.get("rate_extraction_route") == "needs_figure_or_table_digitization"
    )
    if digitization_remaining:
        add_issue(
            issues,
            "warning",
            "digitization_remaining",
            "Rate sources still need figure/table digitization before pooling.",
            file=SOURCE_INDEX,
            observed=str(digitization_remaining),
        )


def write_summary(
    issues: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
    effect_rows: list[dict[str, str]],
) -> None:
    severity_counts = Counter(row["severity"] for row in issues)
    route_counts = group_counts(source_rows, "rate_extraction_route")
    basis_counts = group_counts(observation_rows, "rate_derivation_basis")
    lines = [
        "# Rate Extraction Audit Summary",
        "",
        "Generated by `python3 tools/audit_rate_extraction_dataset.py`.",
        "",
        "## Pass/Fail",
        "",
        f"- Errors: {severity_counts.get('error', 0)}",
        f"- Warnings: {severity_counts.get('warning', 0)}",
        f"- Info rows: {severity_counts.get('info', 0)}",
        "",
        "## Coverage",
        "",
        f"- Source-index rows: {len(source_rows)}",
        f"- Ranked text-evidence rows: {len(evidence_rows)}",
        f"- Curated provisional observation rows: {len(observation_rows)}",
        f"- Seed effect-size rows: {len(effect_rows)}",
        f"- Analysis-ready source rows: {sum(1 for row in source_rows if row.get('analysis_ready') == '1')}",
        f"- Analysis-ready curated rows: {sum(1 for row in observation_rows if row.get('analysis_ready') == '1')}",
        f"- Analysis-ready seed rows: {sum(1 for row in effect_rows if row.get('analysis_ready') == '1')}",
        "",
        "## Source Routes",
        "",
    ]
    for route, count in sorted(route_counts.items()):
        lines.append(f"- `{route}`: {count}")
    lines.extend(["", "## Curated Observation Bases", ""])
    if basis_counts:
        for basis, count in sorted(basis_counts.items()):
            lines.append(f"- `{basis}`: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Notes", ""])
    if severity_counts.get("error", 0):
        lines.append("- Audit failed. See `RATE_EXTRACTION_AUDIT.csv` for blocking rows.")
    else:
        lines.append("- No blocking structural, join, or readiness errors were found.")
    lines.append(
        "- Warnings identify known non-analysis-ready work, especially figure/table digitization and independent QC."
    )
    lines.append("")
    AUDIT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    issues: list[dict[str, str]] = []
    _, workplan_rows = read_csv_strict(WORKPLAN, issues)
    _, source_rows = read_csv_strict(SOURCE_INDEX, issues)
    _, evidence_rows = read_csv_strict(TEXT_EVIDENCE, issues)
    _, observation_rows = read_csv_strict(CURATED_OBSERVATIONS, issues)
    _, effect_rows = read_csv_strict(EFFECT_SEEDS, issues)
    _, override_rows = read_csv_strict(SOURCE_REVIEW_OVERRIDES, issues)
    figure_queue_rows = read_csv(FIGURE_QUEUE_AUDIT)
    crop_rows = read_csv(FIGURE_CROP_MANIFEST)

    if source_rows:
        audit_source_index(
            issues,
            source_rows,
            workplan_rows,
            evidence_rows,
            observation_rows,
            effect_rows,
            figure_queue_rows,
            crop_rows,
        )
        audit_evidence(issues, evidence_rows, source_rows)
        audit_curated_observations(issues, observation_rows, source_rows)
        audit_effect_seeds(issues, effect_rows, source_rows)
        audit_overrides(issues, override_rows, source_rows)
        audit_figure_links(issues, figure_queue_rows, crop_rows, source_rows)
        add_status_notes(issues, source_rows, observation_rows, effect_rows)

    write_csv(AUDIT_CSV, AUDIT_FIELDS, issues)
    write_summary(issues, source_rows, evidence_rows, observation_rows, effect_rows)

    severity_counts = Counter(row["severity"] for row in issues)
    print(f"Wrote {relpath(AUDIT_CSV)} ({len(issues)} rows)")
    print(f"Wrote {relpath(AUDIT_SUMMARY)}")
    print(
        "Audit results: "
        f"{severity_counts.get('error', 0)} errors, "
        f"{severity_counts.get('warning', 0)} warnings, "
        f"{severity_counts.get('info', 0)} info"
    )
    return 1 if severity_counts.get("error", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())

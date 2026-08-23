#!/usr/bin/env python3
"""Audit local dataset tables against the connected NotebookLM notebook."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_REGISTRY = ROOT / "notebook_covariates" / "notebooklm_notebooks.csv"
SOURCE_REGISTRY = ROOT / "notebook_covariates" / "notebooklm_source_registry.csv"
OUT_DIR = ROOT / "data" / "extraction" / "all_responses"
AUDIT_CSV = OUT_DIR / "NOTEBOOKLM_DATASET_AUDIT.csv"
VALUE_AUDIT_CSV = OUT_DIR / "NOTEBOOKLM_VALUE_SUPPORT_AUDIT.csv"
SUMMARY = OUT_DIR / "NOTEBOOKLM_DATASET_AUDIT_SUMMARY.md"
CACHE_DIR = ROOT / ".cache" / "notebooklm_source_content"

SOURCE_SCAN_ROOTS = [
    ROOT / "data",
    ROOT / "notebook_covariates",
    ROOT / "pipeline",
    ROOT / "digitization" / "source_review",
    ROOT / "digitization" / "figures",
]

SKIP_SOURCE_AUDIT_FILES = {
    SOURCE_REGISTRY,
    AUDIT_CSV,
    VALUE_AUDIT_CSV,
    ROOT / "notebook_covariates" / "notebooklm_notebooks.csv",
}

UNIQUE_SOURCE_TABLES = {
    ROOT / "data" / "screening" / "SCREENING_LOG_FINAL.csv",
    ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv",
    ROOT / "notebook_covariates" / "notebook_covariates_all_sources_geoaugmented.csv",
    ROOT / "data" / "extraction" / "all_responses" / "ALL_RESPONSE_SOURCE_INDEX.csv",
    ROOT / "data" / "extraction" / "rate" / "RATE_SOURCE_INDEX.csv",
    ROOT / "data" / "extraction" / "meta_analysis" / "META_ANALYSIS_COVARIATES.csv",
    ROOT / "data" / "extraction" / "meta_analysis" / "META_ANALYSIS_COVARIATE_AUDIT.csv",
    ROOT / "data" / "literature" / "LITERATURE_MAP.csv",
}

PRIMARY_NOTEBOOK_ROLE = "primary_all_sources"
SOURCE_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
WORD_RE = re.compile(r"[a-z0-9]+")

MISSING_VALUES = {
    "",
    "na",
    "n/a",
    "none",
    "null",
    "not reported",
    "not_reported",
    "unknown",
    "not applicable",
    "not_applicable",
}

TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "coral",
    "corals",
    "doi",
    "effect",
    "effects",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "pdf",
    "reef",
    "the",
    "to",
    "with",
}

VALUE_STOPWORDS = TITLE_STOPWORDS | {
    "at",
    "be",
    "cm",
    "cm2",
    "control",
    "controls",
    "day",
    "days",
    "deg",
    "degree",
    "degrees",
    "each",
    "et",
    "fig",
    "figure",
    "lab",
    "m",
    "mm",
    "mm2",
    "n",
    "per",
    "spp",
    "table",
    "than",
    "that",
    "this",
    "was",
    "were",
}

SOURCE_COVARIATE_FIELDS = [
    "study_year",
    "location_raw",
    "site_name",
    "country_territory",
    "water_body",
    "latitude_raw",
    "longitude_raw",
    "depth_min_m",
    "depth_max_m",
    "species",
    "growth_form",
    "tissue_type",
    "colony_size_cm",
    "symbiont_status",
    "lesion_source",
    "lesion_method",
    "lesion_type",
    "area_mm2",
    "rel_wound_size",
    "perimeter_mm",
    "lesion_depth",
    "num_lesions",
    "lesion_position",
    "temperature_c",
    "temp_manip",
    "ph_or_pco2",
    "nutrient_enrich",
    "light_par",
    "light_regime",
    "sedimentation",
    "flow_regime",
    "sample_size",
    "replication_level",
    "randomization",
    "blocking",
    "control_description",
]

MODEL_RAW_COVARIATE_FIELDS = [
    "taxon_raw",
    "growth_form_raw",
    "tissue_type_raw",
    "skeletal_porosity_raw_evidence",
    "study_type_raw",
    "initial_wound_area_raw",
    "wound_perimeter_raw",
    "lesion_depth_raw",
    "num_lesions_raw",
    "temperature_raw",
    "pH_or_pCO2_raw",
    "nutrient_enrichment_raw",
    "sedimentation_raw",
    "flow_regime_raw",
    "light_raw",
    "symbiont_status_raw",
    "lesion_method_raw",
    "lesion_type_raw",
    "location_raw",
    "site",
    "country_territory",
    "water_body",
]

EXTRACTION_VALUE_FIELDS = {
    ROOT / "data" / "extraction" / "EXTRACTION_RATES.csv": [
        "Species",
        "Wound_Area_mm2",
        "Rate_Value",
        "Rate_Unit",
        "Variance_Type",
        "Variance_Value",
        "Sample_Size",
        "Location",
        "Stressor",
    ],
    ROOT / "data" / "extraction" / "EXTRACTION_FITNESS.csv": [
        "Species",
        "Outcome_Type",
        "Control_Mean",
        "Control_Var",
        "Wounded_Mean",
        "Wounded_Var",
        "Var_Type",
        "Sample_Size",
        "Stressor",
    ],
    ROOT / "data" / "extraction" / "EXTRACTION_SURVIVAL.csv": [
        "Species",
        "Control_Total",
        "Control_Dead",
        "Wounded_Total",
        "Wounded_Dead",
        "Duration_Days",
        "Stressor",
    ],
    ROOT / "data" / "extraction" / "rate" / "RATE_EXTRACTED_OBSERVATIONS.csv": [
        "species",
        "site",
        "treatment",
        "timepoint_or_interval",
        "response_value",
        "response_unit",
        "rate_value",
        "rate_unit",
        "variance_type",
        "variance_value",
        "sample_size",
        "figure_or_table_label",
        "page",
    ],
    ROOT / "data" / "extraction" / "rate" / "RATE_EFFECT_SIZE_SEEDS.csv": [
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
    ],
    ROOT / "data" / "extraction" / "all_responses" / "ALL_RESPONSE_EXISTING_EXTRACTION_ROWS.csv": [
        "taxon_raw",
        "outcome_type",
        "treatment_or_stressor",
        "response_value",
        "response_unit",
        "control_value",
        "wounded_value",
        "variance_type",
        "variance_value",
        "sample_size",
        "duration_days",
        "figure_or_table_label",
        "page",
        "panel_label",
    ],
}

SOURCE_VALUE_FILES = {
    ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv": SOURCE_COVARIATE_FIELDS,
    ROOT / "notebook_covariates" / "notebook_covariates_all_sources_geoaugmented.csv": SOURCE_COVARIATE_FIELDS,
    ROOT / "data" / "extraction" / "meta_analysis" / "META_ANALYSIS_COVARIATES.csv": MODEL_RAW_COVARIATE_FIELDS,
}

DERIVED_TARGET_COVARIATES = {"genus", "family"}
DERIVED_SOURCE_HINTS = {"taxon_trait_lookup.csv", "META_ANALYSIS_COVARIATES.csv"}

AUDIT_FIELDS = [
    "severity",
    "check_id",
    "file",
    "row_id",
    "source_id",
    "message",
    "expected",
    "observed",
    "notebook_title",
    "local_title",
    "details",
]

VALUE_AUDIT_FIELDS = [
    "value_key",
    "source_id",
    "paper_title",
    "covariate",
    "value",
    "value_kind",
    "dataset_files",
    "row_count",
    "support_status",
    "token_coverage",
    "numeric_coverage",
    "matched_terms",
    "notebook_content_chars",
    "notebook_content_sha256",
    "note",
]

SOURCE_REGISTRY_FIELDS = [
    "source_id",
    "title",
    "type",
    "url",
    "normalized_title",
    "in_screening_final",
    "in_primary_covariates",
    "in_all_source_covariates",
    "in_all_response_source_index",
    "in_rate_source_index",
    "in_extraction_workplan",
    "in_digitization_queue",
    "in_any_source_table",
    "dataset_table_count",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relpath(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def fold(value: object) -> str:
    text = clean(value)
    text = text.replace("µ", "u").replace("μ", "u").replace("°", " deg ")
    text = text.replace("²", "2").replace("⁻", "-")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def compact(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(value))


def title_tokens(value: object) -> set[str]:
    return {
        token
        for token in WORD_RE.findall(fold(value))
        if len(token) >= 3 and token not in TITLE_STOPWORDS and not token.isdigit()
    }


def value_tokens(value: object) -> set[str]:
    return {
        token
        for token in WORD_RE.findall(fold(value))
        if len(token) >= 3 and token not in VALUE_STOPWORDS and not token.isdigit()
    }


def numeric_tokens(value: object) -> list[str]:
    tokens: list[str] = []
    for match in NUMBER_RE.findall(fold(value)):
        stripped = match.strip("+")
        if "." in stripped:
            stripped = stripped.rstrip("0").rstrip(".")
        tokens.append(stripped)
    return tokens


def meaningful(value: object) -> bool:
    normalized = fold(value)
    return normalized not in MISSING_VALUES


def title_similarity(left: object, right: object) -> float:
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    if not left_tokens or not right_tokens:
        return 1.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def add_issue(
    rows: list[dict[str, str]],
    severity: str,
    check_id: str,
    message: str,
    *,
    file: Path | str = "",
    row_id: str = "",
    source_id: str = "",
    expected: str = "",
    observed: str = "",
    notebook_title: str = "",
    local_title: str = "",
    details: str = "",
) -> None:
    rows.append(
        {
            "severity": severity,
            "check_id": check_id,
            "file": relpath(file) if isinstance(file, Path) else str(file),
            "row_id": row_id,
            "source_id": source_id,
            "message": message,
            "expected": expected,
            "observed": observed,
            "notebook_title": notebook_title,
            "local_title": local_title,
            "details": details,
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row_number, row in enumerate(reader, start=2):
            row["_row_number"] = str(row_number)
            rows.append(row)
        return rows


def read_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration:
            return []


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def notebook_id_from_registry(path: Path = NOTEBOOK_REGISTRY) -> str:
    for row in read_csv(path):
        if row.get("role") == PRIMARY_NOTEBOOK_ROLE:
            notebook_id = clean(row.get("notebook_id", ""))
            if notebook_id:
                return notebook_id
    raise RuntimeError(f"No `{PRIMARY_NOTEBOOK_ROLE}` row found in {relpath(path)}")


def expected_source_count_from_registry(path: Path = NOTEBOOK_REGISTRY) -> int | None:
    for row in read_csv(path):
        if row.get("role") == PRIMARY_NOTEBOOK_ROLE:
            try:
                return int(row.get("source_count", "") or 0)
            except ValueError:
                return None
    return None


def run_json(cmd: list[str], timeout: int) -> object:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(" ".join(proc.stderr.split()) or f"command failed: {' '.join(cmd)}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse JSON from {' '.join(cmd)}: {exc}") from exc


def fetch_notebook_sources(notebook_id: str, timeout: int) -> list[dict[str, str]]:
    payload = run_json(["nlm", "source", "list", notebook_id, "--json"], timeout=timeout)
    if not isinstance(payload, list):
        raise RuntimeError("NotebookLM source list JSON was not a list")
    rows: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "source_id": clean(item.get("id", "")),
                "title": clean(item.get("title", "")),
                "type": clean(item.get("type", "")),
                "url": clean(item.get("url", "")),
            }
        )
    return rows


def csv_files_to_scan() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_SCAN_ROOTS:
        if not root.exists():
            continue
        files.extend(root.rglob("*.csv"))
    return sorted({path.resolve() for path in files if path.resolve() not in SKIP_SOURCE_AUDIT_FILES})


def split_source_ids(row: dict[str, str]) -> list[str]:
    source_ids: list[str] = []
    if "source_id" in row:
        value = clean(row.get("source_id", ""))
        if value:
            source_ids.append(value)
    if "source_ids" in row:
        raw = clean(row.get("source_ids", ""))
        if raw:
            source_ids.extend([part.strip() for part in re.split(r"[|,]", raw) if part.strip()])
    return source_ids


def source_title_from_row(row: dict[str, str]) -> str:
    for field in ("paper_title", "local_filename", "title", "source_title"):
        value = clean(row.get(field, ""))
        if value:
            return value
    return ""


def truthy_notebook_present(value: str) -> bool | None:
    normalized = fold(value)
    if normalized in {"1", "true", "yes", "y", "present"}:
        return True
    if normalized in {"0", "false", "no", "n", "absent"}:
        return False
    return None


def audit_source_tables(
    notebook_sources: list[dict[str, str]],
    *,
    title_threshold: float,
) -> tuple[list[dict[str, str]], dict[str, set[str]], Counter[str]]:
    issues: list[dict[str, str]] = []
    notebook_by_id = {row["source_id"]: row for row in notebook_sources if row.get("source_id")}
    notebook_ids = set(notebook_by_id)
    dataset_membership: dict[str, set[str]] = defaultdict(set)
    scanned_files = Counter()

    expected_count = expected_source_count_from_registry()
    if expected_count is not None and len(notebook_sources) != expected_count:
        add_issue(
            issues,
            "error",
            "notebook_source_count_mismatch",
            "Notebook source count differs from the local notebook registry.",
            file=NOTEBOOK_REGISTRY,
            expected=str(expected_count),
            observed=str(len(notebook_sources)),
        )

    normalized_title_to_sources: dict[str, list[dict[str, str]]] = defaultdict(list)
    for source in notebook_sources:
        normalized_title_to_sources[compact(source.get("title", ""))].append(source)
    for normalized_title, rows in sorted(normalized_title_to_sources.items()):
        if normalized_title and len(rows) > 1:
            add_issue(
                issues,
                "warning",
                "duplicate_notebook_source_title",
                "NotebookLM has multiple sources with the same normalized title.",
                expected="one source per normalized title",
                observed=str(len(rows)),
                notebook_title=" | ".join(row.get("title", "") for row in rows[:4]),
                source_id=" | ".join(row.get("source_id", "") for row in rows[:4]),
            )

    for path in csv_files_to_scan():
        header = read_header(path)
        if "source_id" not in header and "source_ids" not in header and "notebook_present" not in header:
            continue
        rows = read_csv(path)
        scanned_files[relpath(path)] = len(rows)
        source_counts: Counter[str] = Counter()
        for row in rows:
            if "source_id" in header and not clean(row.get("source_id", "")):
                flag = truthy_notebook_present(row.get("notebook_present", ""))
                final_status = fold(row.get("final_status", ""))
                local_title = source_title_from_row(row)
                if not local_title and flag is None and not final_status:
                    continue
                severity = "info"
                if flag is True or final_status.startswith("include"):
                    severity = "error"
                add_issue(
                    issues,
                    severity,
                    "blank_source_id",
                    "Source-bearing table row has no source_id to compare against NotebookLM.",
                    file=path,
                    row_id=row.get("_row_number", ""),
                    expected="NotebookLM source_id when notebook_present=true or final_status is included",
                    observed="blank",
                    local_title=local_title,
                    details=f"final_status={row.get('final_status', '')}; notebook_present={row.get('notebook_present', '')}",
                )
            row_source_ids = split_source_ids(row)
            for source_id in row_source_ids:
                source_counts[source_id] += 1
                dataset_membership[source_id].add(relpath(path))
                notebook_source = notebook_by_id.get(source_id)
                local_title = source_title_from_row(row)
                if source_id and not SOURCE_ID_RE.match(source_id):
                    add_issue(
                        issues,
                        "warning",
                        "non_uuid_source_id",
                        "Source ID does not look like a NotebookLM UUID.",
                        file=path,
                        row_id=row.get("_row_number", ""),
                        source_id=source_id,
                    )
                if source_id not in notebook_ids:
                    severity = "warning"
                    if truthy_notebook_present(row.get("notebook_present", "")) is True:
                        severity = "error"
                    add_issue(
                        issues,
                        severity,
                        "source_absent_from_notebook",
                        "Dataset row source_id is not present in the primary NotebookLM source list.",
                        file=path,
                        row_id=row.get("_row_number", ""),
                        source_id=source_id,
                        expected="source_id in NotebookLM source list",
                        observed="absent",
                        local_title=local_title,
                    )
                    continue
                if local_title:
                    similarity = title_similarity(local_title, notebook_source.get("title", ""))
                    if similarity < title_threshold:
                        add_issue(
                            issues,
                            "warning",
                            "source_title_low_similarity",
                            "Dataset title has low token overlap with the NotebookLM title for the same source_id.",
                            file=path,
                            row_id=row.get("_row_number", ""),
                            source_id=source_id,
                            expected=f"title token similarity >= {title_threshold:.2f}",
                            observed=f"{similarity:.2f}",
                            notebook_title=notebook_source.get("title", ""),
                            local_title=local_title,
                        )
            if "notebook_present" in row and row_source_ids:
                flag = truthy_notebook_present(row.get("notebook_present", ""))
                if flag is not None:
                    for source_id in row_source_ids:
                        actual = source_id in notebook_ids
                        if flag != actual:
                            add_issue(
                                issues,
                                "error" if flag else "warning",
                                "notebook_present_flag_mismatch",
                                "`notebook_present` does not match the connected NotebookLM source list.",
                                file=path,
                                row_id=row.get("_row_number", ""),
                                source_id=source_id,
                                expected=str(actual).lower(),
                                observed=str(flag).lower(),
                                notebook_title=notebook_by_id.get(source_id, {}).get("title", ""),
                                local_title=source_title_from_row(row),
                            )
        if path in UNIQUE_SOURCE_TABLES:
            for source_id, count in sorted(source_counts.items()):
                if count > 1:
                    add_issue(
                        issues,
                        "error",
                        "duplicate_source_id_unique_table",
                        "Source-level table has duplicate source_id rows.",
                        file=path,
                        source_id=source_id,
                        expected="1 row",
                        observed=str(count),
                    )

    return issues, dataset_membership, scanned_files


def annotate_source_registry(
    notebook_sources: list[dict[str, str]], dataset_membership: dict[str, set[str]]
) -> list[dict[str, object]]:
    membership_files = {
        "in_screening_final": ROOT / "data" / "screening" / "SCREENING_LOG_FINAL.csv",
        "in_primary_covariates": ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv",
        "in_all_source_covariates": ROOT / "notebook_covariates" / "notebook_covariates_all_sources_geoaugmented.csv",
        "in_all_response_source_index": ROOT / "data" / "extraction" / "all_responses" / "ALL_RESPONSE_SOURCE_INDEX.csv",
        "in_rate_source_index": ROOT / "data" / "extraction" / "rate" / "RATE_SOURCE_INDEX.csv",
        "in_extraction_workplan": ROOT / "pipeline" / "EXTRACTION_WORKPLAN.csv",
        "in_digitization_queue": ROOT / "pipeline" / "DIGITIZATION_FIGURE_QUEUE.csv",
    }
    ids_by_file: dict[str, set[str]] = {}
    for path in membership_files.values():
        ids: set[str] = set()
        for row in read_csv(path):
            ids.update(split_source_ids(row))
        ids_by_file[relpath(path)] = ids

    rows: list[dict[str, object]] = []
    for source in notebook_sources:
        source_id = source["source_id"]
        memberships = dataset_membership.get(source_id, set())
        row: dict[str, object] = {
            **source,
            "normalized_title": compact(source.get("title", "")),
            "in_any_source_table": int(bool(memberships)),
            "dataset_table_count": len(memberships),
        }
        for field, path in membership_files.items():
            row[field] = int(source_id in ids_by_file.get(relpath(path), set()))
        rows.append(row)
    return rows


def value_key(source_id: str, covariate: str, value: str, kind: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{covariate}|{value}|{kind}".encode("utf-8")).hexdigest()[:12]
    return f"nlmval_{digest}"


def add_value_record(
    records: dict[tuple[str, str, str, str], dict[str, object]],
    *,
    source_id: str,
    paper_title: str,
    covariate: str,
    value: object,
    kind: str,
    dataset_file: Path,
) -> None:
    cleaned = clean(value)
    if not source_id or not meaningful(cleaned):
        return
    key = (source_id, covariate, cleaned, kind)
    if key not in records:
        records[key] = {
            "source_id": source_id,
            "paper_title": paper_title,
            "covariate": covariate,
            "value": cleaned,
            "value_kind": kind,
            "dataset_files": set(),
            "row_count": 0,
        }
    records[key]["dataset_files"].add(relpath(dataset_file))  # type: ignore[index]
    records[key]["row_count"] = int(records[key]["row_count"]) + 1


def collect_value_records() -> list[dict[str, object]]:
    records: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for path, fields in SOURCE_VALUE_FILES.items():
        for row in read_csv(path):
            source_id = clean(row.get("source_id", ""))
            paper_title = clean(row.get("paper_title", ""))
            for field in fields:
                add_value_record(
                    records,
                    source_id=source_id,
                    paper_title=paper_title,
                    covariate=field,
                    value=row.get(field, ""),
                    kind="source_covariate",
                    dataset_file=path,
                )

    target_path = ROOT / "data" / "extraction" / "all_responses" / "ALL_RESPONSE_COVARIATE_TARGETS.csv"
    for row in read_csv(target_path):
        value = row.get("existing_value", "")
        covariate = clean(row.get("covariate", ""))
        existing_source = clean(row.get("existing_source", ""))
        if not meaningful(value):
            continue
        if covariate in DERIVED_TARGET_COVARIATES or any(hint in existing_source for hint in DERIVED_SOURCE_HINTS):
            kind = "derived_or_model_covariate"
        else:
            kind = "response_covariate_target"
        add_value_record(
            records,
            source_id=clean(row.get("source_id", "")),
            paper_title=clean(row.get("paper_title", "")),
            covariate=covariate,
            value=value,
            kind=kind,
            dataset_file=target_path,
        )

    for path, fields in EXTRACTION_VALUE_FIELDS.items():
        for row in read_csv(path):
            source_id = clean(row.get("source_id", ""))
            paper_title = clean(row.get("paper_title", ""))
            for field in fields:
                add_value_record(
                    records,
                    source_id=source_id,
                    paper_title=paper_title,
                    covariate=field,
                    value=row.get(field, ""),
                    kind="quantitative_extraction_value",
                    dataset_file=path,
                )

    rows: list[dict[str, object]] = []
    for (_source_id, covariate, value, kind), record in records.items():
        record["value_key"] = value_key(record["source_id"], covariate, value, kind)
        record["dataset_files"] = " | ".join(sorted(record["dataset_files"]))  # type: ignore[arg-type]
        rows.append(record)
    return sorted(rows, key=lambda row: (str(row["source_id"]), str(row["value_kind"]), str(row["covariate"])))


def load_cached_content(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("content", ""), str):
        return payload
    return None


def fetch_source_content(source_id: str, *, cache_dir: Path, timeout: int, use_cache: bool) -> dict[str, object]:
    cache_path = cache_dir / f"{source_id}.json"
    if use_cache:
        cached = load_cached_content(cache_path)
        if cached is not None:
            cached["cache_status"] = "cached"
            return cached

    payload = run_json(["nlm", "source", "content", source_id, "--json"], timeout=timeout)
    if not isinstance(payload, dict):
        raise RuntimeError("source content JSON was not an object")
    content = str(payload.get("content", ""))
    result = {
        "source_id": source_id,
        "title": clean(payload.get("title", "")),
        "source_type": clean(payload.get("source_type", "")),
        "url": clean(payload.get("url", "")),
        "char_count": int(payload.get("char_count", len(content)) or len(content)),
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "fetched_at_utc": utc_now(),
        "content": content,
        "cache_status": "fetched",
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def support_for_value(value: object, content: str) -> dict[str, object]:
    folded_content = fold(content)
    compact_content = compact(content)
    folded_value = fold(value)
    compact_value = compact(value)
    if len(compact_value) >= 5 and compact_value in compact_content:
        return {
            "support_status": "direct_string_match",
            "token_coverage": "1.00",
            "numeric_coverage": "1.00",
            "matched_terms": clean(value)[:160],
        }

    content_tokens = set(WORD_RE.findall(folded_content))
    words = value_tokens(value)
    numbers = numeric_tokens(value)
    matched_words = sorted(token for token in words if token in content_tokens)
    matched_numbers = sorted({number for number in numbers if re.search(rf"(?<!\d){re.escape(number)}(?!\d)", folded_content)})
    token_coverage = len(matched_words) / len(words) if words else 0.0
    numeric_coverage = len(matched_numbers) / len(numbers) if numbers else 1.0

    if words and token_coverage >= 0.8 and numeric_coverage >= 0.8:
        status = "high_token_match"
    elif numbers and not words and numeric_coverage >= 0.8 and all(len(number) >= 2 for number in numbers):
        status = "numeric_only_present"
    elif (words and token_coverage >= 0.4) or (numbers and numeric_coverage > 0):
        status = "partial_token_or_numeric_match"
    else:
        status = "no_direct_text_match"
    matched_terms = " | ".join((matched_words + matched_numbers)[:20])
    return {
        "support_status": status,
        "token_coverage": f"{token_coverage:.2f}" if words else "",
        "numeric_coverage": f"{numeric_coverage:.2f}" if numbers else "",
        "matched_terms": matched_terms,
    }


def audit_value_support(
    value_records: list[dict[str, object]],
    notebook_ids: set[str],
    *,
    cache_dir: Path,
    content_timeout: int,
    workers: int,
    use_cache: bool,
    max_content_sources: int | None,
) -> list[dict[str, object]]:
    source_ids = sorted({str(row["source_id"]) for row in value_records if row["source_id"] in notebook_ids})
    if max_content_sources is not None:
        source_ids = source_ids[:max_content_sources]

    content_by_source: dict[str, dict[str, object]] = {}
    fetch_errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(
                fetch_source_content,
                source_id,
                cache_dir=cache_dir,
                timeout=content_timeout,
                use_cache=use_cache,
            ): source_id
            for source_id in source_ids
        }
        for future in as_completed(futures):
            source_id = futures[future]
            try:
                content_by_source[source_id] = future.result()
            except Exception as exc:  # noqa: BLE001 - audit should record source-level failures.
                fetch_errors[source_id] = str(exc)[:500]

    rows: list[dict[str, object]] = []
    for record in value_records:
        source_id = str(record["source_id"])
        row = {field: record.get(field, "") for field in VALUE_AUDIT_FIELDS}
        if source_id not in notebook_ids:
            row.update(
                {
                    "support_status": "source_absent_from_notebook",
                    "note": "Source ID is not in the primary NotebookLM source list.",
                }
            )
        elif str(record.get("value_kind", "")) == "derived_or_model_covariate":
            row.update(
                {
                    "support_status": "derived_or_model_covariate_not_text_checked",
                    "note": "Value is derived from a model/trait layer or external lookup, so exact paper-text support is not required.",
                }
            )
        elif source_id in fetch_errors:
            row.update({"support_status": "content_fetch_failed", "note": fetch_errors[source_id]})
        elif source_id not in content_by_source:
            row.update(
                {
                    "support_status": "content_not_fetched",
                    "note": "Content source limit prevented this source from being checked.",
                }
            )
        else:
            content_payload = content_by_source[source_id]
            content = str(content_payload.get("content", ""))
            support = support_for_value(record.get("value", ""), content)
            row.update(support)
            row["notebook_content_chars"] = content_payload.get("char_count", len(content))
            row["notebook_content_sha256"] = content_payload.get("content_sha256", "")
            if row["support_status"] == "no_direct_text_match":
                row["note"] = (
                    "No direct NotebookLM text match; review against the PDF/figure before treating this as an error."
                )
        rows.append(row)
    return rows


def write_summary(
    *,
    path: Path,
    notebook_id: str,
    notebook_sources: list[dict[str, str]],
    source_issues: list[dict[str, str]],
    source_membership: dict[str, set[str]],
    scanned_files: Counter[str],
    value_rows: list[dict[str, object]],
    elapsed_seconds: float,
) -> None:
    issue_counts = Counter(row.get("severity", "") for row in source_issues)
    check_counts = Counter(row.get("check_id", "") for row in source_issues)
    value_status_counts = Counter(str(row.get("support_status", "")) for row in value_rows)
    value_kind_counts = Counter(str(row.get("value_kind", "")) for row in value_rows)
    no_direct_covariates = Counter(
        str(row.get("covariate", ""))
        for row in value_rows
        if row.get("support_status") == "no_direct_text_match"
    )

    dataset_ids = set(source_membership)
    notebook_ids = {row["source_id"] for row in notebook_sources}
    absent_ids = sorted(dataset_ids - notebook_ids)
    notebook_only_ids = sorted(notebook_ids - dataset_ids)

    source_issue_examples = [
        row
        for row in source_issues
        if row.get("severity") in {"error", "warning"}
        and row.get("check_id") in {"source_absent_from_notebook", "notebook_present_flag_mismatch", "source_title_low_similarity"}
    ][:12]

    lines = [
        "# NotebookLM Dataset Audit Summary",
        "",
        "Generated by `python3 tools/audit_dataset_against_notebooklm.py`.",
        "",
        f"- generated_at_utc: `{utc_now()}`",
        f"- notebook_id: `{notebook_id}`",
        f"- notebook_sources: {len(notebook_sources)}",
        f"- source-bearing CSV files scanned: {len(scanned_files)}",
        f"- distinct local dataset source IDs: {len(dataset_ids)}",
        f"- local dataset source IDs present in NotebookLM: {len(dataset_ids & notebook_ids)}",
        f"- local dataset source IDs absent from NotebookLM: {len(absent_ids)}",
        f"- NotebookLM sources not referenced by scanned dataset tables: {len(notebook_only_ids)}",
        f"- source-audit findings: {len(source_issues)}",
        f"- source-audit errors: {issue_counts.get('error', 0)}",
        f"- source-audit warnings: {issue_counts.get('warning', 0)}",
        f"- source-audit info: {issue_counts.get('info', 0)}",
        f"- value-support records audited: {len(value_rows)}",
        f"- elapsed_seconds: {elapsed_seconds:.1f}",
        "",
        "## Source Audit Checks",
        "",
    ]
    if check_counts:
        for check_id, count in sorted(check_counts.items()):
            lines.append(f"- `{check_id}`: {count}")
    else:
        lines.append("- no source-level issues detected")

    lines.extend(["", "## Value Support Status", ""])
    if value_status_counts:
        for status, count in sorted(value_status_counts.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- value support audit was not run")

    lines.extend(["", "## Value Kinds", ""])
    if value_kind_counts:
        for kind, count in sorted(value_kind_counts.items()):
            lines.append(f"- `{kind}`: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## No Direct Text Match Hotspots", ""])
    if no_direct_covariates:
        for covariate, count in no_direct_covariates.most_common(15):
            lines.append(f"- `{covariate}`: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Priority Examples", ""])
    if source_issue_examples:
        for row in source_issue_examples:
            lines.append(
                "- "
                f"{row.get('severity')} `{row.get('check_id')}` "
                f"{row.get('source_id')} in `{row.get('file')}`: "
                f"{row.get('observed') or row.get('message')}"
            )
    else:
        lines.append("- No source-ID, `notebook_present`, or title-similarity priority examples.")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This audit checks whether local dataset source IDs, NotebookLM presence flags, source titles, validation batches, and extracted values are consistent with the connected NotebookLM source list. `no_direct_text_match` in the value-support table is a triage flag, not proof that a value is wrong; digitized figure values, normalized categories, and derived trait joins can be correct without an exact raw-text match.",
            "",
            "## Files",
            "",
            f"- `{relpath(SOURCE_REGISTRY)}`",
            f"- `{relpath(AUDIT_CSV)}`",
            f"- `{relpath(VALUE_AUDIT_CSV)}`",
            f"- `{relpath(SUMMARY)}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook-id", default="", help="NotebookLM notebook ID. Defaults to notebook registry.")
    parser.add_argument("--source-timeout", type=int, default=120, help="Seconds for source-list command.")
    parser.add_argument("--content-timeout", type=int, default=90, help="Seconds per source-content command.")
    parser.add_argument("--workers", type=int, default=4, help="Parallel source-content fetch workers.")
    parser.add_argument("--title-threshold", type=float, default=0.20, help="Warn below this title-token similarity.")
    parser.add_argument("--skip-value-support", action="store_true", help="Only audit source coverage and flags.")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached NotebookLM source content.")
    parser.add_argument("--max-content-sources", type=int, default=None, help="Limit content fetches for smoke tests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = time.monotonic()
    notebook_id = args.notebook_id or notebook_id_from_registry()
    notebook_sources = fetch_notebook_sources(notebook_id, timeout=args.source_timeout)
    source_issues, source_membership, scanned_files = audit_source_tables(
        notebook_sources,
        title_threshold=args.title_threshold,
    )
    source_registry_rows = annotate_source_registry(notebook_sources, source_membership)
    write_csv(SOURCE_REGISTRY, SOURCE_REGISTRY_FIELDS, source_registry_rows)
    write_csv(AUDIT_CSV, AUDIT_FIELDS, source_issues)

    value_rows: list[dict[str, object]] = []
    if not args.skip_value_support:
        value_records = collect_value_records()
        value_rows = audit_value_support(
            value_records,
            {row["source_id"] for row in notebook_sources},
            cache_dir=CACHE_DIR,
            content_timeout=args.content_timeout,
            workers=args.workers,
            use_cache=not args.no_cache,
            max_content_sources=args.max_content_sources,
        )
    write_csv(VALUE_AUDIT_CSV, VALUE_AUDIT_FIELDS, value_rows)

    write_summary(
        path=SUMMARY,
        notebook_id=notebook_id,
        notebook_sources=notebook_sources,
        source_issues=source_issues,
        source_membership=source_membership,
        scanned_files=scanned_files,
        value_rows=value_rows,
        elapsed_seconds=time.monotonic() - start,
    )
    print(f"Wrote {relpath(SOURCE_REGISTRY)}")
    print(f"Wrote {relpath(AUDIT_CSV)}")
    print(f"Wrote {relpath(VALUE_AUDIT_CSV)}")
    print(f"Wrote {relpath(SUMMARY)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

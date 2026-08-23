#!/usr/bin/env python3
"""Build metafor-ready inputs from rows that passed the analysis-ready gate."""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READY_OBSERVATIONS = ROOT / "data" / "extraction" / "analysis_ready" / "ANALYSIS_READY_OBSERVATIONS.csv"
COVARIATES = ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv"
OUT_DIR = ROOT / "data" / "extraction" / "meta_analysis"
MODEL_COVARIATES = OUT_DIR / "META_ANALYSIS_COVARIATES.csv"
META_INPUTS = OUT_DIR / "META_ANALYSIS_INPUTS.csv"
META_AUDIT = OUT_DIR / "META_ANALYSIS_INPUT_AUDIT.csv"
META_ISSUES = OUT_DIR / "META_ANALYSIS_INPUT_ISSUES.csv"
META_SCHEMA = OUT_DIR / "META_ANALYSIS_INPUT_SCHEMA.csv"
SUMMARY = OUT_DIR / "META_ANALYSIS_SUMMARY.md"

MISSING = {"", "na", "n/a", "none", "null", "not reported", "not_reported", "unknown"}
Z_95 = 1.96

INPUT_FIELDS = [
    "model_include",
    "effect_id",
    "study_id",
    "obs_id",
    "source_id",
    "source_table",
    "source_row",
    "response_type",
    "analysis_stratum",
    "effect_family",
    "effect_size_metric",
    "yi",
    "vi",
    "effect_direction",
    "event_definition",
    "dependent_effect_cluster",
    "authors",
    "year",
    "paper_title",
    "species",
    "taxon_raw",
    "taxon_count",
    "taxon_parse_status",
    "genus_candidates",
    "genus",
    "genus_model_status",
    "family_candidates",
    "family",
    "family_model_status",
    "taxonomy_lookup_status",
    "site",
    "location_raw",
    "country_territory",
    "water_body",
    "latitude",
    "longitude",
    "depth_min_m",
    "depth_max_m",
    "depth_mid_m",
    "depth_span_m",
    "study_type",
    "field_lab_mesocosm",
    "field_lab_mesocosm_status",
    "growth_form",
    "growth_form_standard",
    "growth_form_model_status",
    "tissue_type",
    "skeletal_porosity",
    "skeletal_porosity_model_status",
    "lesion_method",
    "injury_mechanism_standard",
    "lesion_type",
    "tissue_skeleton_involvement_standard",
    "initial_wound_area_mm2",
    "initial_wound_area_mid_mm2",
    "initial_wound_area_status",
    "temperature_c",
    "temperature_mid_c",
    "temperature_status",
    "temperature_regime",
    "pH_or_pCO2",
    "pH_mid",
    "pCO2_uatm_mid",
    "carbonate_chemistry_status",
    "nutrient_enrichment",
    "nutrient_enrichment_standard",
    "sedimentation",
    "sedimentation_standard",
    "flow_regime",
    "flow_regime_standard",
    "light_standard",
    "symbiont_status",
    "symbiont_status_standard",
    "covariate_readiness_status",
    "covariate_warnings",
    "treatment_or_stressor",
    "outcome_type",
    "observation_type",
    "rate_derivation_basis",
    "rate_value",
    "rate_unit",
    "response_value",
    "response_unit",
    "control_mean",
    "control_sd",
    "control_n",
    "treatment_mean",
    "treatment_sd",
    "treatment_n",
    "control_events",
    "control_total",
    "treatment_events",
    "treatment_total",
    "variance_type",
    "variance_value",
    "sample_size",
    "timepoint_or_interval",
    "duration_days",
    "figure_or_table_label",
    "page",
    "panel_label",
    "value_data_file",
    "concrete_digitized_data_files",
    "calculation_notes",
]

AUDIT_FIELDS = INPUT_FIELDS + [
    "effect_input_status",
    "effect_blockers",
    "effect_warnings",
]

ISSUE_FIELDS = [
    "severity",
    "issue_id",
    "effect_id",
    "source_id",
    "response_type",
    "message",
    "expected",
    "observed",
]

SCHEMA_ROWS = [
    {
        "column": "study_id",
        "required_for": "all models",
        "description": "Cluster identifier for study-level random effects; currently source_id.",
    },
    {
        "column": "obs_id",
        "required_for": "all models",
        "description": "Unique effect-size row within a study.",
    },
    {
        "column": "yi",
        "required_for": "metafor",
        "description": "Computed effect size. Empty unless the raw inputs support a defensible calculation.",
    },
    {
        "column": "vi",
        "required_for": "metafor",
        "description": "Sampling variance for yi. Empty rows are excluded from META_ANALYSIS_INPUTS.csv.",
    },
    {
        "column": "analysis_stratum",
        "required_for": "all models",
        "description": "Prevents mixing incompatible effect-size scales, for example raw areal rates and log odds ratios.",
    },
    {
        "column": "dependent_effect_cluster",
        "required_for": "multilevel models",
        "description": "Cluster for non-independent effects sharing the same source/response/taxon/outcome/treatment.",
    },
    {
        "column": "effect_size_metric",
        "required_for": "all models",
        "description": "Metric passed to metafor or modeled directly; examples include raw_rate, log_odds_ratio_mortality, and log_response_ratio.",
    },
    {
        "column": "effect_direction",
        "required_for": "interpretation",
        "description": "Direction of positive yi, because higher values mean different things for healing rate versus mortality.",
    },
    {
        "column": "family",
        "required_for": "taxonomic moderators",
        "description": "Single model-ready family from the normalized covariate layer; blank when mixed or missing.",
    },
    {
        "column": "skeletal_porosity",
        "required_for": "trait moderators",
        "description": "Single perforate/imperforate moderator only when the covariate layer marks it unambiguous.",
    },
    {
        "column": "growth_form_standard",
        "required_for": "trait moderators",
        "description": "Coarse normalized growth-form moderator from the covariate layer.",
    },
    {
        "column": "field_lab_mesocosm",
        "required_for": "study-design moderators",
        "description": "Standardized field, lab, mesocosm, or mixed setting.",
    },
]


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def has_value(value: object) -> bool:
    return clean(value).lower() not in MISSING


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


def relpath(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_float(value: object) -> float | None:
    text = clean(value)
    if not has_value(text):
        return None
    text = text.replace(",", "")
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_int(value: object) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    if abs(number - round(number)) > 1e-9:
        return None
    return int(round(number))


def parse_range(value: object) -> tuple[float, float] | None:
    text = clean(value).replace(",", "")
    text = re.sub(r"(?<=\d)\s*-\s*(?=\d)", " ", text)
    numbers = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
    if len(numbers) < 2:
        return None
    lo, hi = float(numbers[0]), float(numbers[1])
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def normalized_token(value: object) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", clean(value).lower()).strip("_")
    return token or "unspecified"


def parse_authors_year(row: dict[str, str], covariate: dict[str, str]) -> tuple[str, str]:
    title = clean(row.get("paper_title", "") or covariate.get("paper_title", ""))
    year = clean(covariate.get("study_year", ""))
    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    if year_match:
        year = year_match.group(0)
    authors = ""
    if " - " in title:
        authors = title.split(" - ", 1)[0].strip()
    return authors, year


def original_rows_by_source_row(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    wanted_files = {row.get("source_table", "") for row in rows if row.get("source_table", "")}
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for source_table in sorted(wanted_files):
        for row_number, original in enumerate(read_csv(ROOT / source_table), start=2):
            lookup[(source_table, str(row_number))] = original
    return lookup


def original_value(row: dict[str, str], original: dict[str, str], *fields: str) -> str:
    for field in fields:
        if has_value(row.get(field, "")):
            return clean(row.get(field, ""))
        if has_value(original.get(field, "")):
            return clean(original.get(field, ""))
    return ""


def sampling_variance_from_summary(
    variance_type: str,
    variance_value: str,
    sample_size: int | None,
) -> tuple[float | None, str | None]:
    vtype = clean(variance_type).lower()
    vvalue = clean(variance_value)
    if not has_value(vtype) or not has_value(vvalue):
        return None, "variance_missing"
    if "ci" in vtype or "confidence" in vtype:
        value_range = parse_range(vvalue)
        if not value_range:
            return None, "ci_bounds_unparseable"
        low, high = value_range
        se = (high - low) / (2 * Z_95)
        return se * se, None
    value = parse_float(vvalue)
    if value is None:
        return None, "variance_value_unparseable"
    if vtype in {"se", "s.e.", "standard error", "sem"} or "standard error" in vtype:
        return value * value, None
    if vtype in {"sd", "s.d.", "standard deviation"} or "standard deviation" in vtype:
        if not sample_size or sample_size <= 0:
            return None, "sd_without_sample_size"
        return (value * value) / sample_size, None
    return None, "unsupported_variance_type"


def effect_family(row: dict[str, str]) -> str:
    response = row.get("response_type", "")
    basis = clean(row.get("rate_derivation_basis", "")).lower()
    unit = clean(row.get("rate_unit", "") or row.get("response_unit", "")).lower()
    outcome = clean(row.get("observation_type", "") or row.get("outcome_type", "")).lower()
    if response == "survival":
        return "binary_survival"
    if response in {"growth", "reproduction"}:
        return "treatment_control_continuous"
    if "exponential" in basis or "exponential" in unit or "slope" in basis:
        return "absolute_exponential_rate"
    if "closure" in basis or "time_to_closure" in basis:
        return "time_to_closure_or_endpoint"
    if "percent" in unit or "%" in unit or "proportion" in unit or "percent" in outcome:
        return "endpoint_proportion_or_percent"
    if "mm2" in unit or "cm2" in unit:
        return "absolute_areal_rate"
    if re.search(r"\b(?:mm|cm)\b", unit):
        return "absolute_linear_rate"
    if response == "rate":
        return "absolute_rate_other"
    return "unclassified"


def analysis_stratum(row: dict[str, str], family: str) -> str:
    unit = normalized_token(row.get("rate_unit", "") or row.get("response_unit", ""))
    if family == "binary_survival":
        return "survival:log_odds_ratio_mortality"
    if family == "treatment_control_continuous":
        return f"{row.get('response_type', '')}:log_response_ratio"
    if family.startswith("absolute") or family.startswith("endpoint") or family.startswith("time"):
        return f"{row.get('response_type', '')}:{family}:{unit}"
    return f"{row.get('response_type', '')}:{family}"


def rate_effect(row: dict[str, str]) -> tuple[str, str, str, str | None]:
    value = parse_float(row.get("rate_value", "") or row.get("response_value", ""))
    sample_size = parse_int(row.get("sample_size", ""))
    vi, blocker = sampling_variance_from_summary(row.get("variance_type", ""), row.get("variance_value", ""), sample_size)
    if value is None:
        return "", "", "", "rate_value_missing"
    if vi is None:
        return f"{value:.12g}", "", "", blocker
    return f"{value:.12g}", f"{vi:.12g}", "raw_rate_or_endpoint_mean", None


def survival_effect(original: dict[str, str]) -> tuple[str, str, str | None]:
    control_total = parse_int(original.get("Control_Total", ""))
    control_dead = parse_int(original.get("Control_Dead", ""))
    treatment_total = parse_int(original.get("Wounded_Total", ""))
    treatment_dead = parse_int(original.get("Wounded_Dead", ""))
    counts = [control_total, control_dead, treatment_total, treatment_dead]
    if any(value is None for value in counts):
        return "", "", "survival_counts_missing"
    assert control_total is not None and control_dead is not None
    assert treatment_total is not None and treatment_dead is not None
    control_alive = control_total - control_dead
    treatment_alive = treatment_total - treatment_dead
    if min(control_dead, control_alive, treatment_dead, treatment_alive) < 0:
        return "", "", "survival_counts_inconsistent"
    cells = [treatment_dead, treatment_alive, control_dead, control_alive]
    if any(cell == 0 for cell in cells):
        cells = [cell + 0.5 for cell in cells]
    td, ta, cd, ca = cells
    yi = math.log((td * ca) / (ta * cd))
    vi = sum(1 / cell for cell in cells)
    return f"{yi:.12g}", f"{vi:.12g}", None


def sd_from_variance(value: str, variance_type: str, n: int | None) -> float | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    vtype = clean(variance_type).lower()
    if vtype in {"sd", "s.d.", "standard deviation"} or "standard deviation" in vtype:
        return parsed
    if vtype in {"se", "s.e.", "standard error", "sem"} or "standard error" in vtype:
        if not n:
            return None
        return parsed * math.sqrt(n)
    return None


def continuous_rom_effect(row: dict[str, str], original: dict[str, str]) -> tuple[str, str, str | None]:
    control_mean = parse_float(original_value(row, original, "control_value", "Control_Mean"))
    treatment_mean = parse_float(original_value(row, original, "wounded_value", "Wounded_Mean"))
    control_n = parse_int(original_value(row, original, "Control_N", "control_n"))
    treatment_n = parse_int(original_value(row, original, "Wounded_N", "wounded_n", "treatment_n"))
    variance_type = original_value(row, original, "variance_type", "Var_Type", "Variance_Type")
    control_sd = sd_from_variance(original.get("Control_Var", ""), variance_type, control_n)
    treatment_sd = sd_from_variance(original.get("Wounded_Var", ""), variance_type, treatment_n)
    if control_mean is None or treatment_mean is None:
        return "", "", "continuous_means_missing"
    if control_mean <= 0 or treatment_mean <= 0:
        return "", "", "rom_requires_positive_means"
    if not control_n or not treatment_n:
        return "", "", "group_sample_sizes_missing"
    if control_sd is None or treatment_sd is None:
        return "", "", "group_variance_missing_or_unusable"
    yi = math.log(treatment_mean / control_mean)
    vi = (treatment_sd**2) / (treatment_n * treatment_mean**2) + (control_sd**2) / (control_n * control_mean**2)
    return f"{yi:.12g}", f"{vi:.12g}", None


def issue(
    issue_rows: list[dict[str, str]],
    severity: str,
    issue_id: str,
    row: dict[str, str],
    message: str,
    expected: str = "",
    observed: str = "",
) -> None:
    issue_rows.append(
        {
            "severity": severity,
            "issue_id": issue_id,
            "effect_id": row.get("effect_id", ""),
            "source_id": row.get("source_id", ""),
            "response_type": row.get("response_type", ""),
            "message": message,
            "expected": expected,
            "observed": observed,
        }
    )


def base_meta_row(
    row: dict[str, str],
    original: dict[str, str],
    covariate: dict[str, str],
    model_covariate: dict[str, str] | None = None,
) -> dict[str, object]:
    model_covariate = model_covariate or {}
    authors, year = parse_authors_year(row, covariate)
    effect_id = row.get("normalized_row_id", "") or f"{row.get('source_id', '')}_{row.get('source_row', '')}"
    species = original_value(row, original, "taxon_raw", "Species", "species") or covariate.get("species", "")
    return {
        "model_include": 0,
        "effect_id": effect_id,
        "study_id": row.get("source_id", ""),
        "obs_id": effect_id,
        "source_id": row.get("source_id", ""),
        "source_table": row.get("source_table", ""),
        "source_row": row.get("source_row", ""),
        "response_type": row.get("response_type", ""),
        "authors": authors,
        "year": year,
        "paper_title": row.get("paper_title", "") or covariate.get("paper_title", ""),
        "species": species,
        "taxon_raw": species,
        "taxon_count": model_covariate.get("taxon_count", ""),
        "taxon_parse_status": model_covariate.get("taxon_parse_status", ""),
        "genus_candidates": model_covariate.get("genus_candidates", ""),
        "genus": model_covariate.get("genus", ""),
        "genus_model_status": model_covariate.get("genus_model_status", ""),
        "family_candidates": model_covariate.get("family_candidates", ""),
        "family": model_covariate.get("family", ""),
        "family_model_status": model_covariate.get("family_model_status", ""),
        "taxonomy_lookup_status": model_covariate.get("taxonomy_lookup_status", ""),
        "site": covariate.get("site_name", ""),
        "location_raw": covariate.get("location_raw", ""),
        "country_territory": covariate.get("country_territory", ""),
        "water_body": covariate.get("water_body", ""),
        "latitude": covariate.get("latitude_best", "") or covariate.get("latitude", ""),
        "longitude": covariate.get("longitude_best", "") or covariate.get("longitude", ""),
        "depth_min_m": covariate.get("depth_min_m", ""),
        "depth_max_m": covariate.get("depth_max_m", ""),
        "depth_mid_m": model_covariate.get("depth_mid_m", ""),
        "depth_span_m": model_covariate.get("depth_span_m", ""),
        "study_type": covariate.get("study_type", ""),
        "field_lab_mesocosm": model_covariate.get("field_lab_mesocosm", ""),
        "field_lab_mesocosm_status": model_covariate.get("field_lab_mesocosm_status", ""),
        "growth_form": covariate.get("growth_form", ""),
        "growth_form_standard": model_covariate.get("growth_form_standard", ""),
        "growth_form_model_status": model_covariate.get("growth_form_model_status", ""),
        "tissue_type": covariate.get("tissue_type", ""),
        "skeletal_porosity": model_covariate.get("skeletal_porosity", ""),
        "skeletal_porosity_model_status": model_covariate.get("skeletal_porosity_model_status", ""),
        "lesion_method": covariate.get("lesion_method", ""),
        "injury_mechanism_standard": model_covariate.get("injury_mechanism_standard", ""),
        "lesion_type": covariate.get("lesion_type", ""),
        "tissue_skeleton_involvement_standard": model_covariate.get("tissue_skeleton_involvement_standard", ""),
        "initial_wound_area_mm2": covariate.get("area_mm2", ""),
        "initial_wound_area_mid_mm2": model_covariate.get("initial_wound_area_mid_mm2", ""),
        "initial_wound_area_status": model_covariate.get("initial_wound_area_status", ""),
        "temperature_c": covariate.get("temperature_c", ""),
        "temperature_mid_c": model_covariate.get("temperature_mid_c", ""),
        "temperature_status": model_covariate.get("temperature_status", ""),
        "temperature_regime": covariate.get("temp_manip", ""),
        "pH_or_pCO2": covariate.get("ph_or_pco2", "") or covariate.get("pH_or_pCO2", ""),
        "pH_mid": model_covariate.get("pH_mid", ""),
        "pCO2_uatm_mid": model_covariate.get("pCO2_uatm_mid", ""),
        "carbonate_chemistry_status": model_covariate.get("carbonate_chemistry_status", ""),
        "nutrient_enrichment": covariate.get("nutrient_enrich", ""),
        "nutrient_enrichment_standard": model_covariate.get("nutrient_enrichment_standard", ""),
        "sedimentation": covariate.get("sedimentation", ""),
        "sedimentation_standard": model_covariate.get("sedimentation_standard", ""),
        "flow_regime": covariate.get("flow_regime", ""),
        "flow_regime_standard": model_covariate.get("flow_regime_standard", ""),
        "light_standard": model_covariate.get("light_standard", ""),
        "symbiont_status": covariate.get("symbiont_status", ""),
        "symbiont_status_standard": model_covariate.get("symbiont_status_standard", ""),
        "covariate_readiness_status": model_covariate.get("covariate_readiness_status", ""),
        "covariate_warnings": model_covariate.get("covariate_warnings", ""),
        "treatment_or_stressor": original_value(row, original, "treatment_or_stressor", "Stressor", "treatment"),
        "outcome_type": original_value(row, original, "outcome_type", "Outcome_Type"),
        "observation_type": original_value(row, original, "observation_type"),
        "rate_derivation_basis": original_value(row, original, "rate_derivation_basis"),
        "rate_value": original_value(row, original, "rate_value", "Rate_Value"),
        "rate_unit": original_value(row, original, "rate_unit", "Rate_Unit"),
        "response_value": original_value(row, original, "response_value"),
        "response_unit": original_value(row, original, "response_unit"),
        "control_mean": original_value(row, original, "control_value", "Control_Mean"),
        "control_sd": "",
        "control_n": original_value(row, original, "Control_N", "control_n"),
        "treatment_mean": original_value(row, original, "wounded_value", "Wounded_Mean"),
        "treatment_sd": "",
        "treatment_n": original_value(row, original, "Wounded_N", "wounded_n", "treatment_n"),
        "control_events": original_value(row, original, "Control_Dead"),
        "control_total": original_value(row, original, "Control_Total"),
        "treatment_events": original_value(row, original, "Wounded_Dead"),
        "treatment_total": original_value(row, original, "Wounded_Total"),
        "variance_type": original_value(row, original, "variance_type", "Var_Type", "Variance_Type"),
        "variance_value": original_value(row, original, "variance_value", "Variance_Value"),
        "sample_size": original_value(row, original, "sample_size", "Sample_Size"),
        "timepoint_or_interval": original_value(row, original, "timepoint_or_interval"),
        "duration_days": original_value(row, original, "duration_days", "Duration_Days"),
        "figure_or_table_label": row.get("figure_or_table_label", ""),
        "page": row.get("page", ""),
        "panel_label": row.get("panel_label", ""),
        "value_data_file": row.get("value_data_file", ""),
        "concrete_digitized_data_files": row.get("concrete_digitized_data_files", ""),
        "calculation_notes": original_value(row, original, "calculation_notes", "Notes"),
    }


def build_meta_row(
    row: dict[str, str],
    original: dict[str, str],
    covariate: dict[str, str],
    issue_rows: list[dict[str, str]],
    model_covariate: dict[str, str] | None = None,
) -> dict[str, object]:
    meta_row = base_meta_row(row, original, covariate, model_covariate)
    family = effect_family({**row, **{key: str(value) for key, value in meta_row.items()}})
    metric = ""
    yi = ""
    vi = ""
    blocker = None
    event_definition = ""
    direction = "larger values indicate faster or greater regeneration"

    if family == "binary_survival":
        metric = "log_odds_ratio_mortality"
        event_definition = "mortality"
        direction = "positive values indicate higher mortality in wounded/damaged corals"
        yi, vi, blocker = survival_effect(original)
    elif family == "treatment_control_continuous":
        metric = "log_response_ratio"
        direction = "positive values indicate larger wounded/damaged mean relative to control"
        yi, vi, blocker = continuous_rom_effect(row, original)
    elif row.get("response_type", "") == "rate":
        metric = "raw_rate_or_endpoint_mean"
        yi, vi, metric_from_calc, blocker = rate_effect({**row, **{key: str(value) for key, value in meta_row.items()}})
        metric = metric_from_calc or metric
    else:
        blocker = "unsupported_response_type"

    meta_row["effect_family"] = family
    meta_row["effect_size_metric"] = metric
    meta_row["analysis_stratum"] = analysis_stratum({**row, **{key: str(value) for key, value in meta_row.items()}}, family)
    meta_row["yi"] = yi
    meta_row["vi"] = vi
    meta_row["effect_direction"] = direction
    meta_row["event_definition"] = event_definition
    meta_row["dependent_effect_cluster"] = "|".join(
        [
            clean(meta_row.get("source_id", "")),
            clean(meta_row.get("response_type", "")),
            normalized_token(meta_row.get("species", "")),
            normalized_token(meta_row.get("outcome_type", "") or meta_row.get("observation_type", "")),
            normalized_token(meta_row.get("treatment_or_stressor", "")),
        ]
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if blocker:
        blockers.append(blocker)
        issue(
            issue_rows,
            "blocker",
            blocker,
            {**row, "effect_id": str(meta_row["effect_id"])},
            "Analysis-ready observation does not yet have a computable metafor yi/vi pair.",
            expected="yi and vi",
            observed=blocker,
        )
    if not has_value(meta_row.get("analysis_stratum", "")):
        blockers.append("analysis_stratum_missing")
    if not has_value(meta_row.get("latitude", "")) or not has_value(meta_row.get("longitude", "")):
        warnings.append("best_coordinates_missing")
    if not has_value(meta_row.get("species", "")):
        blockers.append("species_missing")
    if not has_value(meta_row.get("covariate_readiness_status", "")):
        warnings.append("model_covariates_not_built_or_not_joined")
    meta_row["model_include"] = int(not blockers and has_value(yi) and has_value(vi))
    meta_row["effect_input_status"] = "effect_size_ready" if meta_row["model_include"] else "effect_size_blocked"
    meta_row["effect_blockers"] = "|".join(dict.fromkeys(blockers))
    meta_row["effect_warnings"] = "|".join(dict.fromkeys(warnings))
    return meta_row


def write_summary(
    path: Path,
    ready_rows: list[dict[str, str]],
    audit_rows: list[dict[str, object]],
    input_rows: list[dict[str, object]],
    issue_rows: list[dict[str, str]],
    model_covariate_rows: list[dict[str, str]],
) -> None:
    status_counts = Counter(str(row.get("effect_input_status", "")) for row in audit_rows)
    strata_counts = Counter(str(row.get("analysis_stratum", "")) for row in input_rows)
    issue_counts = Counter(row.get("issue_id", "") for row in issue_rows)
    covariate_fields = [
        "genus",
        "family",
        "growth_form_standard",
        "skeletal_porosity",
        "field_lab_mesocosm",
        "depth_mid_m",
        "initial_wound_area_mid_mm2",
        "temperature_mid_c",
        "pH_mid",
        "pCO2_uatm_mid",
    ]
    lines = [
        "# Meta-Analysis Input Summary",
        "",
        "Generated by `python3 tools/build_meta_analysis_inputs.py`.",
        "",
        "## Current Result",
        "",
        f"- analysis-ready observations read: {len(ready_rows)}",
        f"- metafor-ready input rows: {len(input_rows)}",
        f"- input audit rows: {len(audit_rows)}",
        f"- effect-size blocker issues: {sum(1 for row in issue_rows if row.get('severity') == 'blocker')}",
        f"- model-covariate rows available: {len(model_covariate_rows)}",
        "",
        "## Effect Input Status",
        "",
    ]
    if status_counts:
        for status, count in sorted(status_counts.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- no analysis-ready observations available yet")
    lines.extend(["", "## Analysis Strata In Model Inputs", ""])
    if strata_counts:
        for stratum, count in sorted(strata_counts.items()):
            lines.append(f"- `{stratum}`: {count}")
    else:
        lines.append("- no model input strata available yet")
    lines.extend(["", "## Model Covariate Coverage", ""])
    if model_covariate_rows:
        for field in covariate_fields:
            present = sum(1 for row in model_covariate_rows if has_value(row.get(field, "")))
            lines.append(f"- `{field}`: {present}/{len(model_covariate_rows)}")
    else:
        lines.append("- no model-covariate rows available; run `python3 tools/build_model_covariates.py`")
    lines.extend(["", "## Top Issues", ""])
    if issue_counts:
        for issue_id, count in issue_counts.most_common(20):
            lines.append(f"- `{issue_id}`: {count}")
    else:
        lines.append("- no effect-size issues because no analysis-ready rows reached this layer")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `{relpath(META_INPUTS)}`",
            f"- `{relpath(MODEL_COVARIATES)}`",
            f"- `{relpath(META_AUDIT)}`",
            f"- `{relpath(META_ISSUES)}`",
            f"- `{relpath(META_SCHEMA)}`",
            "",
            "## Modeling Rule",
            "",
            "- Fit models only from rows in `META_ANALYSIS_INPUTS.csv`.",
            "- Do not mix `analysis_stratum` values in one pooled model unless a manuscript-facing rationale and conversion are documented.",
            "- Use multilevel models for multiple effects per source: `rma.mv(yi, vi, random = ~ 1 | study_id / obs_id, data = dat)`.",
            "- Use robust variance checks clustered by `study_id` when dependence assumptions are uncertain.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_outputs(args: argparse.Namespace) -> int:
    ready_rows = read_csv(args.ready_observations)
    covariates = {row.get("source_id", ""): row for row in read_csv(args.covariates)}
    model_covariate_rows = read_csv(args.model_covariates)
    model_covariates = {row.get("source_id", ""): row for row in model_covariate_rows}
    original_lookup = original_rows_by_source_row(ready_rows)
    issue_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, object]] = []
    input_rows: list[dict[str, object]] = []
    for row in ready_rows:
        original = original_lookup.get((row.get("source_table", ""), row.get("source_row", "")), {})
        covariate = covariates.get(row.get("source_id", ""), {})
        model_covariate = model_covariates.get(row.get("source_id", ""), {})
        meta_row = build_meta_row(row, original, covariate, issue_rows, model_covariate)
        audit_rows.append(meta_row)
        if str(meta_row.get("model_include", "")) == "1":
            input_rows.append(meta_row)
    write_csv(args.meta_inputs, INPUT_FIELDS, input_rows)
    write_csv(args.meta_audit, AUDIT_FIELDS, audit_rows)
    write_csv(args.meta_issues, ISSUE_FIELDS, issue_rows)
    write_csv(args.meta_schema, ["column", "required_for", "description"], SCHEMA_ROWS)
    write_summary(args.summary, ready_rows, audit_rows, input_rows, issue_rows, model_covariate_rows)
    print(f"Wrote {relpath(args.summary)}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready-observations", type=Path, default=READY_OBSERVATIONS)
    parser.add_argument("--covariates", type=Path, default=COVARIATES)
    parser.add_argument("--model-covariates", type=Path, default=MODEL_COVARIATES)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--meta-inputs", type=Path, default=META_INPUTS)
    parser.add_argument("--meta-audit", type=Path, default=META_AUDIT)
    parser.add_argument("--meta-issues", type=Path, default=META_ISSUES)
    parser.add_argument("--meta-schema", type=Path, default=META_SCHEMA)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return build_outputs(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

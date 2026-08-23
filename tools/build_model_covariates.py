#!/usr/bin/env python3
"""Build model-ready covariate fields from source-level covariates."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_COVARIATES = ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv"
TAXON_LOOKUP = ROOT / "notebook_covariates" / "taxon_trait_lookup.csv"
OUT_DIR = ROOT / "data" / "extraction" / "meta_analysis"
MODEL_COVARIATES = OUT_DIR / "META_ANALYSIS_COVARIATES.csv"
COVARIATE_AUDIT = OUT_DIR / "META_ANALYSIS_COVARIATE_AUDIT.csv"
COVARIATE_SCHEMA = OUT_DIR / "META_ANALYSIS_COVARIATE_SCHEMA.csv"
COVARIATE_SUMMARY = OUT_DIR / "META_ANALYSIS_COVARIATE_SUMMARY.md"

MISSING = {"", "na", "n/a", "none", "null", "not reported", "not_reported", "unknown"}
POROSITY_PATTERN = re.compile(r"\b(?:im)?perforat\w*", re.IGNORECASE)

COVARIATE_FIELDS = [
    "source_id",
    "paper_title",
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
    "growth_form_raw",
    "growth_form_standard_candidates",
    "growth_form_standard",
    "growth_form_model_status",
    "tissue_type_raw",
    "skeletal_porosity_raw_evidence",
    "skeletal_porosity_candidates",
    "skeletal_porosity",
    "skeletal_porosity_model_status",
    "study_type_raw",
    "field_lab_mesocosm",
    "field_lab_mesocosm_status",
    "depth_min_m",
    "depth_max_m",
    "depth_mid_m",
    "depth_span_m",
    "initial_wound_area_raw",
    "initial_wound_area_min_mm2",
    "initial_wound_area_max_mm2",
    "initial_wound_area_mid_mm2",
    "initial_wound_area_status",
    "wound_perimeter_raw",
    "wound_perimeter_min_mm",
    "wound_perimeter_max_mm",
    "wound_perimeter_mid_mm",
    "wound_perimeter_status",
    "lesion_depth_raw",
    "lesion_depth_min_mm",
    "lesion_depth_max_mm",
    "lesion_depth_mid_mm",
    "lesion_depth_status",
    "num_lesions_raw",
    "num_lesions_min",
    "num_lesions_max",
    "num_lesions_mid",
    "num_lesions_status",
    "temperature_raw",
    "temperature_min_c",
    "temperature_max_c",
    "temperature_mid_c",
    "temperature_status",
    "pH_or_pCO2_raw",
    "pH_min",
    "pH_max",
    "pH_mid",
    "pCO2_uatm_min",
    "pCO2_uatm_max",
    "pCO2_uatm_mid",
    "carbonate_chemistry_status",
    "nutrient_enrichment_raw",
    "nutrient_enrichment_standard",
    "sedimentation_raw",
    "sedimentation_standard",
    "flow_regime_raw",
    "flow_regime_standard",
    "light_raw",
    "light_standard",
    "symbiont_status_raw",
    "symbiont_status_standard",
    "lesion_method_raw",
    "injury_mechanism_standard",
    "lesion_type_raw",
    "tissue_skeleton_involvement_standard",
    "location_raw",
    "site",
    "country_territory",
    "water_body",
    "latitude",
    "longitude",
    "coordinate_basis",
    "coordinate_confidence",
    "covariate_readiness_status",
    "covariate_blockers",
    "covariate_warnings",
    "notes",
]

AUDIT_FIELDS = COVARIATE_FIELDS + [
    "source_covariate_status",
    "model_covariate_status",
]

SCHEMA_ROWS = [
    {
        "column": "genus",
        "required_for": "taxonomic moderators",
        "description": "Single accepted genus when the source row maps to one genus; blank for mixed or ambiguous rows.",
    },
    {
        "column": "family",
        "required_for": "taxonomic moderators",
        "description": "Single family from the taxon trait lookup; blank if multiple families or lookup is missing.",
    },
    {
        "column": "skeletal_porosity",
        "required_for": "trait moderators",
        "description": "Single normalized perforate/imperforate value only when source or lookup evidence is unambiguous.",
    },
    {
        "column": "growth_form_standard",
        "required_for": "trait moderators",
        "description": "Coarse model-ready growth form when raw growth form maps to one category.",
    },
    {
        "column": "field_lab_mesocosm",
        "required_for": "study-design moderators",
        "description": "Standardized field, lab, mesocosm, or mixed setting.",
    },
    {
        "column": "depth_mid_m",
        "required_for": "environment moderators",
        "description": "Midpoint of source-level depth range when numeric depth is available.",
    },
    {
        "column": "initial_wound_area_mid_mm2",
        "required_for": "wound-geometry moderators",
        "description": "Midpoint of reported initial wound area values in mm2; preserve raw field for interpretation.",
    },
    {
        "column": "temperature_mid_c",
        "required_for": "environment moderators",
        "description": "Midpoint of source-level temperature values in degrees C when reported.",
    },
    {
        "column": "covariate_readiness_status",
        "required_for": "all moderator analyses",
        "description": "Core readiness flag for using this source in moderator models.",
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


def normalized_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", clean(value).lower()).strip("_")


def unique_join(values: list[str]) -> str:
    return "; ".join(dict.fromkeys(value for value in values if has_value(value)))


def split_raw_taxa(value: object) -> list[str]:
    text = clean(value)
    if not has_value(text):
        return []
    parts = re.split(r",|;|\band\b|/|\(|\)", text)
    taxa: list[str] = []
    for part in parts:
        part = clean(part)
        if not part:
            continue
        match = re.match(r"([A-Z][A-Za-z-]+)(?:\s+([a-z][A-Za-z-]+|spp\.|sp\.|cf\.))?", part)
        if match:
            taxa.append(clean(match.group(0)))
    return taxa


def raw_genera(value: object) -> list[str]:
    genera: list[str] = []
    for taxon in split_raw_taxa(value):
        match = re.match(r"([A-Z][A-Za-z-]+)\b", taxon)
        if match:
            genera.append(match.group(1))
    return list(dict.fromkeys(genera))


def lookup_by_genus(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        for field in ("genus_raw", "genus", "worms_valid_name"):
            key = clean(row.get(field, ""))
            if key and key not in out:
                out[key] = row
    return out


def taxonomy_fields(taxon_raw: str, lookup: dict[str, dict[str, str]]) -> dict[str, str]:
    genera_raw = raw_genera(taxon_raw)
    accepted_genera: list[str] = []
    families: list[str] = []
    statuses: list[str] = []
    missing: list[str] = []
    for genus in genera_raw:
        record = lookup.get(genus, {})
        accepted = clean(record.get("genus", "")) or clean(record.get("worms_valid_name", "")) or genus
        accepted_genera.append(accepted)
        if has_value(record.get("family", "")):
            families.append(clean(record.get("family", "")))
        else:
            missing.append(genus)
        if has_value(record.get("taxonomy_lookup_status", "")):
            statuses.append(clean(record.get("taxonomy_lookup_status", "")))
    accepted_genera = list(dict.fromkeys(accepted_genera))
    families = list(dict.fromkeys(families))
    taxon_count = len(accepted_genera)
    if taxon_count == 0:
        parse_status = "taxon_missing"
    elif taxon_count == 1 and re.search(r"\bspp?\.|cf\.", taxon_raw, flags=re.IGNORECASE):
        parse_status = "single_genus_species_ambiguous"
    elif taxon_count == 1:
        parse_status = "single_taxon"
    else:
        parse_status = "multi_taxon"
    return {
        "taxon_count": str(taxon_count),
        "taxon_parse_status": parse_status,
        "genus_candidates": unique_join(accepted_genera),
        "genus": accepted_genera[0] if taxon_count == 1 else "",
        "genus_model_status": "single_genus_ready" if taxon_count == 1 else parse_status,
        "family_candidates": unique_join(families),
        "family": families[0] if len(families) == 1 else "",
        "family_model_status": family_status(taxon_count, families, missing),
        "taxonomy_lookup_status": unique_join(statuses) or ("lookup_missing" if genera_raw else "taxon_missing"),
    }


def family_status(taxon_count: int, families: list[str], missing: list[str]) -> str:
    if taxon_count == 0:
        return "taxon_missing"
    if missing:
        return "family_lookup_missing"
    if len(families) == 1:
        return "single_family_ready"
    if len(families) > 1:
        return "multiple_families_not_collapsed"
    return "family_missing"


def growth_form_categories(value: object) -> list[str]:
    text = normalized_token(value).replace("_", " ")
    if not text:
        return []
    mapping = [
        ("branching", r"\b(branch|branched|branching|arborescent|staghorn|digitate|corymbose|bushy|finger_like)\b"),
        ("massive_submassive", r"\b(massive|submassive|boulder|hemispherical|bumpy)\b"),
        ("encrusting", r"\bencrusting\b"),
        ("plating_foliose", r"\b(plating|foliose|foliaceous|sheeting|scroll|tabular)\b"),
        ("solitary", r"\bsolitary\b"),
        ("columnar", r"\bcolumnar\b"),
        ("colonial_unspecified", r"\bcolonial\b"),
    ]
    out: list[str] = []
    for category, pattern in mapping:
        if re.search(pattern, text):
            out.append(category)
    return list(dict.fromkeys(out))


def porosity_categories(row: dict[str, str], lookup: dict[str, dict[str, str]]) -> tuple[list[str], str]:
    candidates: list[str] = []
    evidence_parts: list[str] = []
    tissue = clean(row.get("tissue_type", ""))
    if POROSITY_PATTERN.search(tissue):
        if re.search(r"\bimperforat\w*", tissue, flags=re.IGNORECASE):
            candidates.append("imperforate")
        if re.search(r"(?<!im)\bperforat\w*", tissue, flags=re.IGNORECASE):
            candidates.append("perforate")
        evidence_parts.append(f"tissue_type={tissue}")
    for genus in raw_genera(row.get("species", "")):
        record = lookup.get(genus, {})
        porosity = clean(record.get("skeletal_porosity", "")).lower()
        if porosity in {"perforate", "imperforate"}:
            candidates.append(porosity)
            evidence_parts.append(f"taxon_trait_lookup:{genus}={porosity}")
    return list(dict.fromkeys(candidates)), "; ".join(evidence_parts)


def porosity_model_status(taxon_count: int, candidates: list[str]) -> str:
    if not candidates:
        return "porosity_missing"
    if len(candidates) > 1:
        return "multiple_porosity_values_not_collapsed"
    if taxon_count > 1:
        return "single_porosity_candidate_multi_taxon_not_model_ready"
    return "single_porosity_ready"


def numeric_values(value: object) -> list[float]:
    text = clean(value).replace(",", " ")
    if not text:
        return []
    for old, new in [("–", "-"), ("—", "-"), ("−", "-"), ("~", " "), ("<", " "), (">", " ")]:
        text = text.replace(old, new)
    text = re.sub(r"(?<=\d)\s*-\s*(?=\d)", " ", text)
    values: list[float] = []
    for match in re.finditer(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        try:
            values.append(float(match.group(0)))
        except ValueError:
            continue
    return values


def summarize_numeric(value: object) -> tuple[str, str, str, str]:
    values = numeric_values(value)
    raw = clean(value)
    if not values:
        return "", "", "", "missing"
    lo = min(values)
    hi = max(values)
    mid = (lo + hi) / 2
    status = "single_value" if len(values) == 1 else "range_or_multiple_values"
    if re.search(r"[<>~]|approx", raw, flags=re.IGNORECASE):
        status = f"{status}_approximate_or_censored"
    return f"{lo:.12g}", f"{hi:.12g}", f"{mid:.12g}", status


def midpoint_from_bounds(low_value: object, high_value: object) -> tuple[str, str]:
    low = numeric_values(low_value)
    high = numeric_values(high_value)
    values = []
    if low:
        values.append(low[0])
    if high:
        values.append(high[0])
    if not values:
        return "", ""
    span = max(values) - min(values)
    mid = (min(values) + max(values)) / 2
    return f"{mid:.12g}", f"{span:.12g}"


def standardize_study_type(value: object) -> tuple[str, str]:
    text = normalized_token(value)
    if not text:
        return "", "missing"
    has_field = "field" in text
    has_lab = "laboratory" in text or re.search(r"\blab\b", text) is not None
    has_mesocosm = "mesocosm" in text
    categories = []
    if has_field:
        categories.append("field")
    if has_lab:
        categories.append("lab")
    if has_mesocosm:
        categories.append("mesocosm")
    if len(categories) == 1:
        return categories[0], "single_setting_ready"
    if len(categories) > 1:
        return "_and_".join(categories), "mixed_setting_not_collapsed"
    return text, "unrecognized_setting_preserved"


def standardize_presence(value: object) -> str:
    text = clean(value)
    if not has_value(text):
        return ""
    low = text.lower()
    if re.search(r"\b(no|none|ambient|control|not enriched|unenriched)\b", low):
        return "absent_or_control"
    return "present_or_manipulated"


def standardize_symbiont(value: object) -> str:
    text = normalized_token(value)
    if not text:
        return ""
    if "aposymbiotic" in text or "asymbiotic" in text:
        return "aposymbiotic"
    if "symbiotic" in text:
        return "symbiotic"
    if "bleach" in text:
        return "bleached_or_reduced_symbionts"
    return text


def standardize_injury(value: object) -> str:
    text = normalized_token(value)
    if not text:
        return ""
    categories = []
    patterns = [
        ("air_or_water_jet", r"air_pick|airbrush|air_gun|compressed_air|waterpik|pressurized_seawater"),
        ("drill_or_grinding", r"dremel|drill|grinding|rotatory|rotary"),
        ("scraping_or_abrasion", r"scrap|abras|brush|file"),
        ("cutting_or_punch", r"scalpel|cut|bone_cutter|leather_punch|punch"),
        ("fragmentation_or_breakage", r"break|fragment|hammer|chisel"),
        ("natural_or_biotic_predation", r"fish|parrotfish|butterflyfish|snail|coralliophila|predation|grazing"),
        ("oil_or_pollution", r"oil|pollution"),
    ]
    for category, pattern in patterns:
        if re.search(pattern, text):
            categories.append(category)
    return unique_join(categories)


def standardize_tissue_involvement(value: object) -> str:
    text = normalized_token(value)
    if not text:
        return ""
    if "fragment" in text or "breakage" in text:
        return "fragmentation"
    has_tissue = "tissue" in text or "mortality" in text or "abrasion" in text
    has_skeleton = "skeleton" in text or "scraping" in text or "scrape" in text
    if has_tissue and has_skeleton:
        return "tissue_and_skeleton"
    if has_tissue:
        return "tissue_only"
    if has_skeleton:
        return "skeleton_involved"
    return text


def carbonate_fields(value: object) -> dict[str, str]:
    text = clean(value)
    values = numeric_values(text)
    out = {
        "pH_min": "",
        "pH_max": "",
        "pH_mid": "",
        "pCO2_uatm_min": "",
        "pCO2_uatm_max": "",
        "pCO2_uatm_mid": "",
        "carbonate_chemistry_status": "missing",
    }
    if not values:
        return out
    low = min(values)
    high = max(values)
    mid = (low + high) / 2
    if re.search(r"pco2|co2|uatm|ppm", text, flags=re.IGNORECASE) or high > 20:
        out.update(
            {
                "pCO2_uatm_min": f"{low:.12g}",
                "pCO2_uatm_max": f"{high:.12g}",
                "pCO2_uatm_mid": f"{mid:.12g}",
                "carbonate_chemistry_status": "pco2_reported",
            }
        )
    else:
        out.update(
            {
                "pH_min": f"{low:.12g}",
                "pH_max": f"{high:.12g}",
                "pH_mid": f"{mid:.12g}",
                "carbonate_chemistry_status": "ph_reported",
            }
        )
    return out


def build_covariate_row(row: dict[str, str], lookup: dict[str, dict[str, str]]) -> dict[str, object]:
    taxon_raw = clean(row.get("species", ""))
    taxonomy = taxonomy_fields(taxon_raw, lookup)
    growth_categories = growth_form_categories(row.get("growth_form", ""))
    porosity_candidates, porosity_evidence = porosity_categories(row, lookup)
    study_setting, study_setting_status = standardize_study_type(row.get("study_type", ""))
    depth_mid, depth_span = midpoint_from_bounds(row.get("depth_min_m", ""), row.get("depth_max_m", ""))
    area_min, area_max, area_mid, area_status = summarize_numeric(row.get("area_mm2", ""))
    perimeter_min, perimeter_max, perimeter_mid, perimeter_status = summarize_numeric(row.get("perimeter_mm", ""))
    lesion_depth_min, lesion_depth_max, lesion_depth_mid, lesion_depth_status = summarize_numeric(row.get("lesion_depth", ""))
    lesions_min, lesions_max, lesions_mid, lesions_status = summarize_numeric(row.get("num_lesions", ""))
    temp_min, temp_max, temp_mid, temp_status = summarize_numeric(row.get("temperature_c", ""))
    carbonate = carbonate_fields(row.get("ph_or_pco2", ""))

    blockers: list[str] = []
    warnings: list[str] = []
    if taxonomy["taxon_parse_status"] == "taxon_missing":
        blockers.append("taxon_missing")
    if taxonomy["taxon_parse_status"] == "multi_taxon":
        warnings.append("multi_taxon_row_trait_moderators_need_observation_taxon")
    if taxonomy["family_model_status"] != "single_family_ready":
        warnings.append(taxonomy["family_model_status"])
    if len(growth_categories) != 1:
        warnings.append("growth_form_not_single_standard_category")
    taxon_count = int(taxonomy["taxon_count"] or 0)
    porosity_value = porosity_candidates[0] if len(porosity_candidates) == 1 and taxon_count <= 1 else ""
    if len(porosity_candidates) != 1 or taxon_count > 1:
        warnings.append("skeletal_porosity_not_single_standard_category")
    if not depth_mid:
        warnings.append("depth_mid_m_missing")
    if not area_mid:
        warnings.append("initial_wound_area_mid_mm2_missing")

    core_ready = (
        taxonomy["genus_model_status"] == "single_genus_ready"
        and taxonomy["family_model_status"] == "single_family_ready"
        and len(growth_categories) == 1
        and has_value(study_setting)
    )
    return {
        "source_id": row.get("source_id", ""),
        "paper_title": row.get("paper_title", ""),
        "taxon_raw": taxon_raw,
        **taxonomy,
        "growth_form_raw": row.get("growth_form", ""),
        "growth_form_standard_candidates": unique_join(growth_categories),
        "growth_form_standard": growth_categories[0] if len(growth_categories) == 1 else "",
        "growth_form_model_status": "single_growth_form_ready"
        if len(growth_categories) == 1
        else ("growth_form_missing" if not growth_categories else "multiple_growth_forms_not_collapsed"),
        "tissue_type_raw": row.get("tissue_type", ""),
        "skeletal_porosity_raw_evidence": porosity_evidence,
        "skeletal_porosity_candidates": unique_join(porosity_candidates),
        "skeletal_porosity": porosity_value,
        "skeletal_porosity_model_status": porosity_model_status(taxon_count, porosity_candidates),
        "study_type_raw": row.get("study_type", ""),
        "field_lab_mesocosm": study_setting,
        "field_lab_mesocosm_status": study_setting_status,
        "depth_min_m": row.get("depth_min_m", ""),
        "depth_max_m": row.get("depth_max_m", ""),
        "depth_mid_m": depth_mid,
        "depth_span_m": depth_span,
        "initial_wound_area_raw": row.get("area_mm2", ""),
        "initial_wound_area_min_mm2": area_min,
        "initial_wound_area_max_mm2": area_max,
        "initial_wound_area_mid_mm2": area_mid,
        "initial_wound_area_status": area_status,
        "wound_perimeter_raw": row.get("perimeter_mm", ""),
        "wound_perimeter_min_mm": perimeter_min,
        "wound_perimeter_max_mm": perimeter_max,
        "wound_perimeter_mid_mm": perimeter_mid,
        "wound_perimeter_status": perimeter_status,
        "lesion_depth_raw": row.get("lesion_depth", ""),
        "lesion_depth_min_mm": lesion_depth_min,
        "lesion_depth_max_mm": lesion_depth_max,
        "lesion_depth_mid_mm": lesion_depth_mid,
        "lesion_depth_status": lesion_depth_status,
        "num_lesions_raw": row.get("num_lesions", ""),
        "num_lesions_min": lesions_min,
        "num_lesions_max": lesions_max,
        "num_lesions_mid": lesions_mid,
        "num_lesions_status": lesions_status,
        "temperature_raw": row.get("temperature_c", ""),
        "temperature_min_c": temp_min,
        "temperature_max_c": temp_max,
        "temperature_mid_c": temp_mid,
        "temperature_status": temp_status,
        "pH_or_pCO2_raw": row.get("ph_or_pco2", ""),
        **carbonate,
        "nutrient_enrichment_raw": row.get("nutrient_enrich", ""),
        "nutrient_enrichment_standard": standardize_presence(row.get("nutrient_enrich", "")),
        "sedimentation_raw": row.get("sedimentation", ""),
        "sedimentation_standard": standardize_presence(row.get("sedimentation", "")),
        "flow_regime_raw": row.get("flow_regime", ""),
        "flow_regime_standard": standardize_presence(row.get("flow_regime", "")),
        "light_raw": unique_join([row.get("light_par", ""), row.get("light_regime", "")]),
        "light_standard": standardize_presence(unique_join([row.get("light_par", ""), row.get("light_regime", "")])),
        "symbiont_status_raw": row.get("symbiont_status", ""),
        "symbiont_status_standard": standardize_symbiont(row.get("symbiont_status", "")),
        "lesion_method_raw": row.get("lesion_method", ""),
        "injury_mechanism_standard": standardize_injury(row.get("lesion_method", "")),
        "lesion_type_raw": row.get("lesion_type", ""),
        "tissue_skeleton_involvement_standard": standardize_tissue_involvement(row.get("lesion_type", "")),
        "location_raw": row.get("location_raw", ""),
        "site": row.get("site_name", ""),
        "country_territory": row.get("country_territory", ""),
        "water_body": row.get("water_body", ""),
        "latitude": row.get("latitude_best", "") or row.get("latitude", ""),
        "longitude": row.get("longitude_best", "") or row.get("longitude", ""),
        "coordinate_basis": row.get("best_coordinate_basis", ""),
        "coordinate_confidence": row.get("best_coordinate_confidence", ""),
        "covariate_readiness_status": "core_covariates_ready" if core_ready and not blockers else "covariates_partial",
        "covariate_blockers": unique_join(blockers),
        "covariate_warnings": unique_join(warnings),
        "notes": row.get("notes", ""),
        "source_covariate_status": row.get("notebook_covariate_status", ""),
        "model_covariate_status": "model_covariates_built",
    }


def write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    count = Counter(str(row.get("covariate_readiness_status", "")) for row in rows)
    coverage_fields = [
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
        "# Meta-Analysis Covariate Summary",
        "",
        "Generated by `python3 tools/build_model_covariates.py`.",
        "",
        "## Current Result",
        "",
        f"- source-level covariate rows read: {len(rows)}",
    ]
    for status, n_status in sorted(count.items()):
        lines.append(f"- `{status}`: {n_status}")
    lines.extend(["", "## Moderator Coverage", ""])
    for field in coverage_fields:
        present = sum(1 for row in rows if has_value(row.get(field, "")))
        lines.append(f"- `{field}`: {present}/{len(rows)}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- `{relpath(MODEL_COVARIATES)}`",
            f"- `{relpath(COVARIATE_AUDIT)}`",
            f"- `{relpath(COVARIATE_SCHEMA)}`",
            "",
            "## Modeling Rule",
            "",
            "- Use single-value moderator columns only when their `*_model_status` field says they are ready.",
            "- Do not collapse multi-taxon rows to one genus, growth form, or porosity unless the effect-size row identifies the taxon.",
            "- A family value may be usable for a multi-taxon source only when all listed taxa map to the same family.",
            "- Treat `skeletal_porosity` as model-ready only when the source row or taxon-trait lookup gives one unambiguous value.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_outputs(args: argparse.Namespace) -> int:
    primary_rows = read_csv(args.covariates)
    lookup = lookup_by_genus(read_csv(args.taxon_lookup))
    rows = [build_covariate_row(row, lookup) for row in primary_rows]
    write_csv(args.model_covariates, COVARIATE_FIELDS, rows)
    write_csv(args.covariate_audit, AUDIT_FIELDS, rows)
    write_csv(args.covariate_schema, ["column", "required_for", "description"], SCHEMA_ROWS)
    write_summary(args.summary, rows)
    print(f"Wrote {relpath(args.summary)}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covariates", type=Path, default=PRIMARY_COVARIATES)
    parser.add_argument("--taxon-lookup", type=Path, default=TAXON_LOOKUP)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--model-covariates", type=Path, default=MODEL_COVARIATES)
    parser.add_argument("--covariate-audit", type=Path, default=COVARIATE_AUDIT)
    parser.add_argument("--covariate-schema", type=Path, default=COVARIATE_SCHEMA)
    parser.add_argument("--summary", type=Path, default=COVARIATE_SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return build_outputs(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

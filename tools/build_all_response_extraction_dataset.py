#!/usr/bin/env python3
"""Build a response-wide extraction scaffold from every primary PDF."""

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
WORKPLAN = ROOT / "pipeline" / "EXTRACTION_WORKPLAN.csv"
COVARIATES = ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv"
SCHEMA = ROOT / "notebook_covariates" / "covariate_extraction_schema.csv"
MODEL_COVARIATES = ROOT / "data" / "extraction" / "meta_analysis" / "META_ANALYSIS_COVARIATES.csv"
RATE_OBSERVATIONS = ROOT / "data" / "extraction" / "rate" / "RATE_EXTRACTED_OBSERVATIONS.csv"
LEGACY_RATE = ROOT / "data" / "extraction" / "EXTRACTION_RATES.csv"
LEGACY_FITNESS = ROOT / "data" / "extraction" / "EXTRACTION_FITNESS.csv"
LEGACY_SURVIVAL = ROOT / "data" / "extraction" / "EXTRACTION_SURVIVAL.csv"
OUT_DIR = ROOT / "data" / "extraction" / "all_responses"
TEXT_DIR = OUT_DIR / "pdf_text"
SOURCE_INDEX = OUT_DIR / "ALL_RESPONSE_SOURCE_INDEX.csv"
TEXT_AUDIT = OUT_DIR / "ALL_RESPONSE_PDF_TEXT_AUDIT.csv"
EXISTING_ROWS = OUT_DIR / "ALL_RESPONSE_EXISTING_EXTRACTION_ROWS.csv"
CANDIDATES = OUT_DIR / "ALL_RESPONSE_COVARIATE_CANDIDATES.csv"
TARGETS = OUT_DIR / "ALL_RESPONSE_COVARIATE_TARGETS.csv"
NLM_BATCHES = OUT_DIR / "NOTEBOOKLM_VALIDATION_BATCHES.csv"
SUMMARY = OUT_DIR / "ALL_RESPONSE_EXTRACTION_SUMMARY.md"

PRIMARY_RESPONSES = {"rate", "growth", "reproduction", "survival"}
MISSING_TOKENS = {"", "na", "n/a", "none", "null", "not reported", "not_reported", "unknown"}
WORD_RE = re.compile(r"[A-Za-z0-9]+")


SOURCE_PREFILL = {
    "taxon_raw": "species",
    "initial_wound_area_mm2": "area_mm2",
    "injury_mechanism_standard": "lesion_method",
    "tissue_skeleton_involvement": "lesion_type",
    "temperature_c": "temperature_c",
    "temperature_regime": "temp_manip",
    "colony_size_value": "colony_size_cm",
    "sample_size": "sample_size",
    "field_lab_mesocosm": "study_type",
    "depth_m": "depth_min_m",
    "pH": "ph_or_pco2",
    "pCO2_uatm": "ph_or_pco2",
    "nutrient_treatment": "nutrient_enrich",
    "nutrient_concentration": "nutrient_enrich",
    "light_PAR": "light_par",
    "flow_speed": "flow_regime",
    "sedimentation": "sedimentation",
    "symbiotic_state": "symbiont_status",
    "lesion_depth_mm": "lesion_depth",
    "lesion_position_standard": "lesion_position",
    "num_lesions_per_colony": "num_lesions",
    "wound_perimeter_mm": "perimeter_mm",
}


MODEL_PREFILL = {
    "genus": "genus",
    "family": "family",
    "growth_form_standard": "growth_form_standard",
    "skeletal_porosity": "skeletal_porosity",
    "field_lab_mesocosm": "field_lab_mesocosm",
    "injury_mechanism_standard": "injury_mechanism_standard",
    "tissue_skeleton_involvement": "tissue_skeleton_involvement_standard",
    "depth_m": "depth_mid_m",
    "pH": "pH_mid",
    "pCO2_uatm": "pCO2_uatm_mid",
    "nutrient_treatment": "nutrient_enrichment_standard",
    "flow_speed": "flow_regime_standard",
}

PDF_FREE_MODEL_PREFILL = {"genus", "family"}


PATTERNS = {
    "initial_wound_area_mm2": [
        r".{0,80}\b(?:initial\s+)?(?:lesion|wound|scar|injur(?:y|ies))\s+(?:area|size|surface\s+area).{0,120}",
        r".{0,80}\b\d+(?:\.\d+)?\s*(?:mm2|mm\^2|cm2|cm\^2|cm-2)\b.{0,80}",
    ],
    "final_wound_area_mm2": [
        r".{0,80}\b(?:final|remaining|residual|end)\s+(?:lesion|wound|scar)\s+(?:area|size).{0,120}",
        r".{0,80}\b(?:percent|percentage|proportion)\s+(?:healed|closed|recovered|regenerated).{0,120}",
    ],
    "wound_shape_standard": [
        r".{0,80}\b(?:circular|rectangular|square|elliptical|wedge-shaped|irregular)\s+(?:lesion|wound|scar|injur(?:y|ies)).{0,80}",
    ],
    "wound_perimeter_mm": [
        r".{0,80}\b(?:lesion|wound|scar)\s+perimeter.{0,120}",
        r".{0,80}\bperimeter\s*(?:length)?\s*(?:of)?\s*(?:the)?\s*(?:lesion|wound|scar).{0,120}",
    ],
    "perimeter_area_ratio": [
        r".{0,80}\b(?:perimeter[- ]?to[- ]?(?:surface\s*)?area|P\s*:\s*A|P\s*:\s*SA).{0,120}",
    ],
    "lesion_depth_mm": [
        r".{0,80}\b(?:lesion|wound|scar|drill|drilled|gouge)\s+(?:depth|deep).{0,120}",
        r".{0,80}\b\d+(?:\.\d+)?\s*mm\s+deep\b.{0,80}",
    ],
    "lesion_position_standard": [
        r".{0,80}\b(?:top|side|base|apical|branch\s+tip|upper\s+surface|underside|center|centre)\s+(?:of|on)\s+(?:the\s+)?(?:colony|branch|coral).{0,120}",
    ],
    "num_lesions_per_colony": [
        r".{0,80}\b(?:one|two|three|single|multiple|\d+)\s+(?:lesions|wounds|scars|injuries)\s+(?:per|on|in)\s+(?:colony|coral|fragment|nubbin).{0,120}",
    ],
    "lesion_spacing_cm": [
        r".{0,80}\b(?:spacing|separated|distance)\s+(?:between|among)\s+(?:lesions|wounds|scars).{0,120}",
    ],
    "injury_mechanism_standard": [
        r".{0,80}\b(?:Dremel|drill|chisel|screwdriver|pliers|Waterpik|airbrush|brush|scalpel|bone\s+cutter|hammer|fragmented|scraped|abraded).{0,120}",
    ],
    "tissue_skeleton_involvement": [
        r".{0,80}\b(?:tissue\s+and\s+skeleton|tissue-only|tissue\s+only|skeleton\s+exposed|bare\s+skeleton|down\s+to\s+the\s+skeleton).{0,120}",
    ],
    "temperature_c": [
        r".{0,80}\b\d+(?:\.\d+)?\s*(?:deg\s*C|degrees\s*C|Celsius|C)\b.{0,100}",
        r".{0,80}\btemperature(?:s)?\s+(?:was|were|ranged|averaged|maintained|held).{0,120}",
    ],
    "temperature_regime": [
        r".{0,80}\b(?:ambient|elevated|warming|heated|thermal|bleaching)\s+(?:temperature|seawater|treatment|stress).{0,120}",
    ],
    "colony_size_value": [
        r".{0,80}\b(?:colony|fragment|nubbin|coral)\s+(?:size|diameter|height|surface\s+area|volume|mass).{0,120}",
    ],
    "monitoring_duration_days": [
        r".{0,80}\b(?:monitored|followed|observed|rephotographed|photographed)\s+(?:for|over|after).{0,120}",
        r".{0,80}\b(?:days|months|weeks)\s+(?:after|post[- ]?wounding|following)\b.{0,120}",
    ],
    "timepoint_days": [
        r".{0,80}\b(?:days?|d)\s*(?:0|3|5|8|10|14|20|30|40|60|75|90|120|150|300)\b.{0,120}",
        r".{0,80}\b(?:time\s*points?|sampling\s+days?|sampling\s+dates?).{0,120}",
    ],
    "time_interval_days": [
        r".{0,80}\b(?:between|from)\s+day\s+\d+.{0,80}\b(?:to|and)\s+day\s+\d+.{0,80}",
    ],
    "sample_size": [
        r".{0,80}\bn\s*=\s*\d+\b.{0,100}",
        r".{0,80}\b\d+\s+(?:colonies|corals|fragments|nubbins|replicates|lesions)\b.{0,100}",
    ],
    "variance_type": [
        r".{0,80}\b(?:mean\s*[+/-]|mean\s+plus|mean\s+/-|SE|SD|standard\s+error|standard\s+deviation|confidence\s+interval|CI)\b.{0,120}",
    ],
    "endpoint_definition": [
        r".{0,80}\b(?:considered|defined|scored|recognized)\s+(?:as\s+)?(?:healed|healing|recovered|recovery|closed).{0,160}",
        r".{0,80}\b(?:no\s+visible\s+skeleton|full\s+polyp|new\s+tissue|tissue\s+cover|pigmentation|feeding).{0,120}",
    ],
    "field_lab_mesocosm": [
        r".{0,80}\b(?:field|laboratory|lab|mesocosm|aquarium|tank|in\s+situ|flow-through)\b.{0,120}",
    ],
    "depth_m": [
        r".{0,80}\b(?:depth|depths)\s+(?:of|at|range|ranged|from).{0,120}",
        r".{0,80}\b\d+(?:\.\d+)?\s*m\s+(?:depth|deep)\b.{0,80}",
    ],
    "pH": [
        r".{0,80}\bpH\b.{0,120}",
    ],
    "pCO2_uatm": [
        r".{0,80}\b(?:pCO2|PCO2|CO2|uatm|microatm|ppm)\b.{0,120}",
    ],
    "omega_arag": [
        r".{0,80}\b(?:Omega|aragonite|saturation\s+state)\b.{0,120}",
    ],
    "nutrient_treatment": [
        r".{0,80}\b(?:nutrient|nitrate|nitrite|ammonium|phosphate|nitrogen|enrichment)\b.{0,120}",
    ],
    "nutrient_concentration": [
        r".{0,80}\b\d+(?:\.\d+)?\s*(?:uM|umol|micromol|mg\s*L-1|mg/L).{0,120}",
    ],
    "light_PAR": [
        r".{0,80}\b(?:PAR|irradiance|light|photoperiod|shading|shaded|umol\s+photons)\b.{0,120}",
    ],
    "flow_speed": [
        r".{0,80}\b(?:flow|current|water\s+motion|hydrodynamic|wave|clod\s+card|cm\s*s-1|cm/s)\b.{0,120}",
    ],
    "sedimentation": [
        r".{0,80}\b(?:sediment|sedimentation|turbidity|resuspension|silt)\b.{0,120}",
    ],
    "symbiotic_state": [
        r".{0,80}\b(?:symbiotic|aposymbiotic|zooxanthellate|azooxanthellate|bleached|Symbiodiniaceae|Symbiodinium)\b.{0,120}",
    ],
    "symbiont_density": [
        r".{0,80}\b(?:symbiont\s+density|zooxanthellae\s+density|cells\s+cm-2|chlorophyll)\b.{0,120}",
    ],
    "bleaching_status": [
        r".{0,80}\b(?:bleach(?:ed|ing)?|normally\s+pigmented|pigmentation|coloration|colouration)\b.{0,120}",
    ],
    "disease_status": [
        r".{0,80}\b(?:disease|syndrome|infection|white\s+band|black\s+band|pathogen|SCTLD)\b.{0,120}",
    ],
    "algal_competition": [
        r".{0,80}\b(?:algae|algal|turf|macroalgae|overgrowth|fouling)\b.{0,120}",
    ],
    "predator_context": [
        r".{0,80}\b(?:predation|predator|corallivory|corallivore|parrotfish|fish|snail|butterflyfish|damselfish)\b.{0,120}",
    ],
    "season": [
        r".{0,80}\b(?:season|summer|winter|spring|fall|autumn|cool|warming|hot|austral)\b.{0,120}",
    ],
}

KEYWORDS = {
    "initial_wound_area_mm2": ["lesion", "wound", "scar", "injur", "mm2", "cm2", "area", "size"],
    "final_wound_area_mm2": ["final", "remaining", "residual", "percent", "healed", "closed", "recovered"],
    "wound_shape_standard": ["circular", "rectangular", "square", "elliptical", "wedge", "irregular"],
    "wound_perimeter_mm": ["perimeter"],
    "perimeter_area_ratio": ["perimeter", "p:a", "p:sa", "surface area"],
    "lesion_depth_mm": ["depth", "deep", "drill", "gouge"],
    "lesion_position_standard": ["top", "side", "base", "apical", "branch tip", "upper", "underside", "center", "centre"],
    "num_lesions_per_colony": ["lesion", "wound", "scar", "injur"],
    "lesion_spacing_cm": ["spacing", "separated", "distance"],
    "injury_mechanism_standard": [
        "dremel",
        "drill",
        "chisel",
        "screwdriver",
        "pliers",
        "waterpik",
        "airbrush",
        "brush",
        "scalpel",
        "bone cutter",
        "hammer",
        "fragment",
        "scrap",
        "abrad",
    ],
    "tissue_skeleton_involvement": ["tissue", "skeleton", "bare", "exposed"],
    "temperature_c": ["temperature", "deg", "celsius", " c ", "seawater"],
    "temperature_regime": ["ambient", "elevated", "warming", "heated", "thermal", "bleaching"],
    "colony_size_value": ["colony", "fragment", "nubbin", "diameter", "height", "surface area", "volume", "mass"],
    "monitoring_duration_days": ["monitored", "followed", "observed", "rephotographed", "photographed", "days", "months", "weeks"],
    "timepoint_days": ["time", "day", "days", "sampling"],
    "time_interval_days": ["between", "from", "day"],
    "sample_size": ["n=", "n =", "colonies", "corals", "fragments", "nubbins", "replicates", "lesions"],
    "variance_type": ["mean", "se", "sd", "standard error", "standard deviation", "confidence", "ci"],
    "endpoint_definition": ["considered", "defined", "scored", "recognized", "healed", "healing", "recovered", "closed", "polyp", "pigmentation", "feeding"],
    "field_lab_mesocosm": ["field", "laboratory", "lab", "mesocosm", "aquarium", "tank", "in situ", "flow-through"],
    "depth_m": ["depth", "deep"],
    "pH": ["ph"],
    "pCO2_uatm": ["pco2", "co2", "uatm", "microatm", "ppm"],
    "omega_arag": ["omega", "aragonite", "saturation"],
    "nutrient_treatment": ["nutrient", "nitrate", "nitrite", "ammonium", "phosphate", "nitrogen", "enrichment"],
    "nutrient_concentration": ["um", "umol", "micromol", "mg/l", "mg l"],
    "light_PAR": ["par", "irradiance", "light", "photoperiod", "shad", "photons"],
    "flow_speed": ["flow", "current", "water motion", "hydrodynamic", "wave", "clod", "cm/s", "cm s"],
    "sedimentation": ["sediment", "sedimentation", "turbidity", "resuspension", "silt"],
    "symbiotic_state": ["symbiotic", "aposymbiotic", "zooxanthell", "bleached", "symbiodini"],
    "symbiont_density": ["symbiont density", "zooxanthellae density", "cells", "chlorophyll"],
    "bleaching_status": ["bleach", "pigment", "color", "colour"],
    "disease_status": ["disease", "syndrome", "infection", "white band", "black band", "pathogen", "sctld"],
    "algal_competition": ["algae", "algal", "turf", "macroalgae", "overgrowth", "fouling"],
    "predator_context": ["predation", "predator", "corallivory", "corallivore", "parrotfish", "fish", "snail", "butterflyfish", "damselfish"],
    "season": ["season", "summer", "winter", "spring", "fall", "autumn", "cool", "warming", "hot", "austral"],
}


EXTRACTION_ROW_FIELDS = [
    "normalized_row_id",
    "source_table",
    "source_row",
    "source_id",
    "paper_title",
    "local_relpath",
    "response_type",
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
    "qa_status",
    "notes",
]


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def has_value(value: object) -> bool:
    return clean(value).lower() not in MISSING_TOKENS


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def run_command(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def pdf_page_count(path: Path) -> str:
    code, stdout, _stderr = run_command(["pdfinfo", str(path)])
    if code != 0:
        return ""
    for line in stdout.splitlines():
        if line.lower().startswith("pages:"):
            return clean(line.split(":", 1)[1])
    return ""


def extract_pdf_text(path: Path, output_path: Path) -> tuple[str, str, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        try:
            text = output_path.read_text(encoding="utf-8", errors="replace")
            if text:
                return "read_cached", text, ""
        except OSError:
            pass
    code, _stdout, stderr = run_command(["pdftotext", "-layout", str(path), str(output_path)])
    if code != 0:
        return "pdftotext_failed", "", clean(stderr)[:300]
    try:
        text = output_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return "text_read_failed", "", clean(exc)[:300]
    return "read", text, ""


def title_overlap(title: str, text: str) -> str:
    title_tokens = {token.lower() for token in WORD_RE.findall(title) if len(token) >= 4}
    if not title_tokens:
        return ""
    text_tokens = {token.lower() for token in WORD_RE.findall(text[:8000])}
    return f"{len(title_tokens & text_tokens)}/{len(title_tokens)}"


def primary_workplan_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("final_status") == "include_primary" and row.get("response_type") in PRIMARY_RESPONSES
    ]


def group_by_source(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("source_id", "")].append(row)
    return grouped


def normalize_response_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def append_row(source_table: str, row_number: int, row: dict[str, str], response_type: str) -> None:
        source_id = row.get("source_id", "")
        rows.append(
            {
                "normalized_row_id": f"{Path(source_table).stem}-{row_number}",
                "source_table": source_table,
                "source_row": row_number,
                "source_id": source_id,
                "paper_title": row.get("paper_title", ""),
                "local_relpath": row.get("local_relpath", ""),
                "response_type": response_type,
                "taxon_raw": row.get("Species", row.get("species", "")),
                "outcome_type": row.get("Outcome_Type", row.get("observation_type", "")),
                "treatment_or_stressor": row.get("Stressor", row.get("treatment", "")),
                "response_value": row.get("Rate_Value", row.get("response_value", "")),
                "response_unit": row.get("Rate_Unit", row.get("response_unit", "")),
                "control_value": row.get("Control_Mean", row.get("Control_Total", "")),
                "wounded_value": row.get("Wounded_Mean", row.get("Wounded_Total", "")),
                "variance_type": row.get("Variance_Type", row.get("Var_Type", row.get("variance_type", ""))),
                "variance_value": row.get("Variance_Value", row.get("variance_value", "")),
                "sample_size": row.get("Sample_Size", row.get("sample_size", "")),
                "duration_days": row.get("Duration_Days", ""),
                "figure_or_table_label": row.get("figure_or_table_label", ""),
                "page": row.get("page", ""),
                "panel_label": row.get("panel_label", ""),
                "qa_status": row.get("qa_status", row.get("analysis_ready", "")),
                "notes": row.get("Notes", row.get("calculation_notes", "")),
            }
        )

    for path, response_type in [
        (LEGACY_RATE, "rate"),
        (LEGACY_FITNESS, "fitness"),
        (LEGACY_SURVIVAL, "survival"),
        (RATE_OBSERVATIONS, "rate"),
    ]:
        for idx, row in enumerate(read_csv(path), start=2):
            if path == LEGACY_FITNESS:
                response_type = row.get("response_type", "fitness") or "fitness"
            append_row(relpath(path), idx, row, response_type)
    return rows


def text_windows(text: str) -> list[str]:
    windows: list[str] = []
    chunks = re.split(r"\f|\n+|(?<=[.!?])\s+", text)
    for chunk in chunks:
        cleaned = clean(chunk)
        if len(cleaned) < 35:
            continue
        if len(cleaned) <= 700:
            windows.append(cleaned)
            continue
        words = cleaned.split()
        for idx in range(0, len(words), 70):
            window = " ".join(words[idx : idx + 90])
            if len(window) >= 35:
                windows.append(window)
    return windows


def snippets_for(covariate: str, windows: list[str], max_snippets: int = 3) -> list[str]:
    snippets: list[str] = []
    keywords = KEYWORDS.get(covariate, [])
    for pattern in PATTERNS.get(covariate, []):
        compiled = re.compile(pattern, flags=re.IGNORECASE)
        for window in windows:
            lower = window.lower()
            if keywords and not any(keyword in lower for keyword in keywords):
                continue
            match = compiled.search(window)
            if not match:
                continue
            snippet = clean(match.group(0))
            if snippet and snippet not in snippets:
                snippets.append(snippet[:350])
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def existing_response_values(
    rows: list[dict[str, object]],
) -> dict[tuple[str, str, str], list[dict[str, object]]]:
    mapped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    covariate_fields = {
        "taxon_raw": "taxon_raw",
        "sample_size": "sample_size",
        "variance_type": "variance_type",
        "variance_value": "variance_value",
        "monitoring_duration_days": "duration_days",
    }
    for row in rows:
        source_id = str(row.get("source_id", ""))
        response_type = str(row.get("response_type", ""))
        for covariate, field in covariate_fields.items():
            if has_value(row.get(field, "")):
                mapped[(source_id, response_type, covariate)].append(row)
    return mapped


def covariate_prefill(
    covariate: str,
    source_covariate: dict[str, str],
    model_covariate: dict[str, str],
    source_covariates_path: Path,
    model_covariates_path: Path,
) -> tuple[str, str, str]:
    model_field = MODEL_PREFILL.get(covariate, "")
    if model_field and has_value(model_covariate.get(model_field, "")):
        return clean(model_covariate.get(model_field, "")), "existing_model_covariate", relpath(model_covariates_path)
    source_field = SOURCE_PREFILL.get(covariate, "")
    if source_field and has_value(source_covariate.get(source_field, "")):
        return clean(source_covariate.get(source_field, "")), "existing_source_covariate", relpath(source_covariates_path)
    return "", "not_extracted", ""


def needs_pdf_verification(covariate: str, existing_status: str) -> int:
    if existing_status in {"pdf_text_candidate", "existing_source_covariate"}:
        return 1
    if existing_status == "existing_model_covariate" and covariate not in PDF_FREE_MODEL_PREFILL:
        return 1
    return 0


def build_outputs(args: argparse.Namespace) -> int:
    workplan_rows = primary_workplan_rows(read_csv(args.workplan))
    covariate_rows = read_csv(args.covariates)
    model_covariate_rows = read_csv(args.model_covariates)
    schema_rows = read_csv(args.schema)
    existing_rows = normalize_response_rows()
    existing_by_key = existing_response_values(existing_rows)
    covariates_by_source = {row.get("source_id", ""): row for row in covariate_rows if row.get("source_id", "")}
    model_covariates_by_source = {
        row.get("source_id", ""): row for row in model_covariate_rows if row.get("source_id", "")
    }
    by_source = group_by_source(workplan_rows)

    text_by_source: dict[str, str] = {}
    windows_by_source: dict[str, list[str]] = {}
    source_index_rows: list[dict[str, object]] = []
    text_audit_rows: list[dict[str, object]] = []

    for source_id, rows in sorted(by_source.items()):
        first = rows[0]
        local_relpath = first.get("local_relpath", "")
        pdf_path = ROOT / local_relpath
        text_path = args.text_dir / f"{source_id}.txt"
        responses = sorted({row.get("response_type", "") for row in rows})
        file_status = "available" if pdf_path.exists() else "missing"
        page_count = pdf_page_count(pdf_path) if pdf_path.exists() else ""
        pdf_hash = file_sha256(pdf_path) if pdf_path.exists() else ""
        text_status = "not_read_missing_pdf"
        text = ""
        text_error = ""
        if pdf_path.exists():
            text_status, text, text_error = extract_pdf_text(pdf_path, text_path)
        text_by_source[source_id] = text
        windows_by_source[source_id] = text_windows(text)
        text_chars = len(text)
        text_hash = text_sha256(text) if text else ""
        overlap = title_overlap(first.get("paper_title", ""), text)
        text_audit_rows.append(
            {
                "source_id": source_id,
                "paper_title": first.get("paper_title", ""),
                "local_relpath": local_relpath,
                "pdf_read_status": text_status,
                "pdf_page_count": page_count,
                "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else "",
                "pdf_sha256": pdf_hash,
                "text_path": relpath(text_path),
                "text_chars": text_chars,
                "text_sha256": text_hash,
                "title_token_overlap_page_start": overlap,
                "read_error": text_error,
            }
        )
        source_index_rows.append(
            {
                "source_id": source_id,
                "paper_title": first.get("paper_title", ""),
                "local_relpath": local_relpath,
                "response_types": "|".join(responses),
                "response_count": len(responses),
                "workplan_response_rows": len(rows),
                "source_file_status": file_status,
                "pdf_read_status": text_status,
                "pdf_page_count": page_count,
                "pdf_text_chars": text_chars,
                "pdf_text_sha256": text_hash,
                "notebook_present": first.get("notebook_present", ""),
                "local_present": first.get("local_present", ""),
                "extraction_readiness": first.get("extraction_readiness", ""),
            }
        )

    candidate_rows: list[dict[str, object]] = []
    target_rows: list[dict[str, object]] = []
    candidate_counter = 0
    snippet_cache: dict[tuple[str, str], list[str]] = {}

    for workplan_row in workplan_rows:
        source_id = workplan_row.get("source_id", "")
        response_type = workplan_row.get("response_type", "")
        cov_row = covariates_by_source.get(source_id, {})
        windows = windows_by_source.get(source_id, [])
        for schema_row in schema_rows:
            covariate = schema_row.get("covariate", "")
            model_cov_row = model_covariates_by_source.get(source_id, {})
            existing_value, existing_status, existing_source = covariate_prefill(
                covariate,
                cov_row,
                model_cov_row,
                args.covariates,
                args.model_covariates,
            )
            response_matches = existing_by_key.get((source_id, response_type, covariate), [])
            if response_matches:
                values = sorted({clean(match.get(covariate if covariate in match else {
                    "taxon_raw": "taxon_raw",
                    "sample_size": "sample_size",
                    "variance_type": "variance_type",
                    "variance_value": "variance_value",
                    "monitoring_duration_days": "duration_days",
                }.get(covariate, ""), "")) for match in response_matches})
                values = [value for value in values if value]
                if values:
                    existing_value = " | ".join(values[:8])
                    existing_status = "existing_response_extraction"
                    existing_source = "legacy_or_rate_extraction_tables"
            cache_key = (source_id, covariate)
            if cache_key not in snippet_cache:
                snippet_cache[cache_key] = snippets_for(covariate, windows)
            snippets = snippet_cache[cache_key]
            if snippets and existing_status == "not_extracted":
                existing_status = "pdf_text_candidate"
            target_rows.append(
                {
                    "source_id": source_id,
                    "response_type": response_type,
                    "paper_title": workplan_row.get("paper_title", ""),
                    "local_relpath": workplan_row.get("local_relpath", ""),
                    "covariate": covariate,
                    "tier": schema_row.get("tier", ""),
                    "domain": schema_row.get("domain", ""),
                    "recommended_grain": schema_row.get("recommended_grain", ""),
                    "expected_accessibility": schema_row.get("expected_accessibility", ""),
                    "current_schema_status": schema_row.get("current_schema_status", ""),
                    "target_status": existing_status,
                    "existing_value": existing_value,
                    "existing_source": existing_source,
                    "pdf_candidate_count": len(snippets),
                    "needs_pdf_verification": needs_pdf_verification(covariate, existing_status),
                    "needs_notebooklm_check": int(schema_row.get("tier", "") in {"1", "2"}),
                    "notes": schema_row.get("notes", ""),
                }
            )
            for idx, snippet in enumerate(snippets, start=1):
                candidate_counter += 1
                candidate_rows.append(
                    {
                        "candidate_id": f"cand_{candidate_counter:06d}",
                        "source_id": source_id,
                        "response_type": response_type,
                        "paper_title": workplan_row.get("paper_title", ""),
                        "local_relpath": workplan_row.get("local_relpath", ""),
                        "covariate": covariate,
                        "tier": schema_row.get("tier", ""),
                        "domain": schema_row.get("domain", ""),
                        "recommended_grain": schema_row.get("recommended_grain", ""),
                        "evidence_source": "pdf_text_regex",
                        "candidate_rank": idx,
                        "candidate_text": snippet,
                        "existing_value": existing_value,
                        "target_status": existing_status,
                        "needs_pdf_verification": 1,
                    }
                )

    batch_rows = build_notebooklm_batches(workplan_rows, schema_rows)
    write_csv(args.source_index, list(source_index_rows[0].keys()) if source_index_rows else [], source_index_rows)
    write_csv(args.text_audit, list(text_audit_rows[0].keys()) if text_audit_rows else [], text_audit_rows)
    write_csv(args.existing_rows, EXTRACTION_ROW_FIELDS, existing_rows)
    write_csv(
        args.targets,
        [
            "source_id",
            "response_type",
            "paper_title",
            "local_relpath",
            "covariate",
            "tier",
            "domain",
            "recommended_grain",
            "expected_accessibility",
            "current_schema_status",
            "target_status",
            "existing_value",
            "existing_source",
            "pdf_candidate_count",
            "needs_pdf_verification",
            "needs_notebooklm_check",
            "notes",
        ],
        target_rows,
    )
    write_csv(
        args.candidates,
        [
            "candidate_id",
            "source_id",
            "response_type",
            "paper_title",
            "local_relpath",
            "covariate",
            "tier",
            "domain",
            "recommended_grain",
            "evidence_source",
            "candidate_rank",
            "candidate_text",
            "existing_value",
            "target_status",
            "needs_pdf_verification",
        ],
        candidate_rows,
    )
    write_csv(
        args.notebooklm_batches,
        ["batch_id", "response_type", "source_count", "source_ids", "query_prompt"],
        batch_rows,
    )
    write_summary(args.summary, workplan_rows, source_index_rows, text_audit_rows, target_rows, candidate_rows, batch_rows)
    print(f"Wrote {relpath(args.summary)}")
    return 0


def build_notebooklm_batches(
    workplan_rows: list[dict[str, str]], schema_rows: list[dict[str, str]], batch_size: int = 10
) -> list[dict[str, object]]:
    by_response: dict[str, list[str]] = defaultdict(list)
    for row in workplan_rows:
        source_id = row.get("source_id", "")
        response = row.get("response_type", "")
        if source_id and source_id not in by_response[response]:
            by_response[response].append(source_id)
    tier1 = [row["covariate"] for row in schema_rows if row.get("tier") == "1"]
    tier2 = [row["covariate"] for row in schema_rows if row.get("tier") == "2"]
    rows: list[dict[str, object]] = []
    for response, source_ids in sorted(by_response.items()):
        for batch_idx in range(0, len(source_ids), batch_size):
            ids = source_ids[batch_idx : batch_idx + batch_size]
            batch_number = batch_idx // batch_size + 1
            prompt = (
                f"For these {response} response sources, independently check the paper text for Tier 1 and Tier 2 "
                "covariates. Return strict CSV rows with source_id,response_type,covariate,reported_status,"
                "raw_value,standardized_value,units,evidence_quote,figure_or_table_label,page_or_section,confidence,"
                "needs_pdf_verification. Tier 1 covariates: "
                + "; ".join(tier1)
                + ". Tier 2 covariates: "
                + "; ".join(tier2)
                + ". Use reported_status values reported, not_reported, inferred_from_text, external_lookup_needed, "
                "or not_applicable. Do not invent values."
            )
            rows.append(
                {
                    "batch_id": f"{response}_{batch_number:02d}",
                    "response_type": response,
                    "source_count": len(ids),
                    "source_ids": "|".join(ids),
                    "query_prompt": prompt,
                }
            )
    return rows


def write_summary(
    path: Path,
    workplan_rows: list[dict[str, str]],
    source_rows: list[dict[str, object]],
    text_rows: list[dict[str, object]],
    target_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    batch_rows: list[dict[str, object]],
) -> None:
    response_counts = Counter(row.get("response_type", "") for row in workplan_rows)
    target_status_counts = Counter(str(row.get("target_status", "")) for row in target_rows)
    tier_counts = Counter(str(row.get("tier", "")) for row in target_rows)
    pdf_status_counts = Counter(str(row.get("pdf_read_status", "")) for row in text_rows)
    lines = [
        "# All-Response Extraction Summary",
        "",
        "Generated by `python3 tools/build_all_response_extraction_dataset.py`.",
        "",
        "## Scope",
        "",
        f"- primary response rows: {len(workplan_rows)}",
        f"- unique primary PDFs read: {len(source_rows)}",
        f"- response counts: {', '.join(f'{k}={v}' for k, v in sorted(response_counts.items()))}",
        f"- NotebookLM validation batches: {len(batch_rows)}",
        "",
        "## PDF Read Audit",
        "",
    ]
    for status, count in sorted(pdf_status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Covariate Targets", ""])
    for tier, count in sorted(tier_counts.items()):
        lines.append(f"- Tier {tier}: {count}")
    lines.append("")
    for status, count in sorted(target_status_counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(
        [
            "",
            f"- PDF regex candidate rows: {len(candidate_rows)}",
            "",
            "## Files",
            "",
            f"- `{relpath(SOURCE_INDEX)}`",
            f"- `{relpath(TEXT_AUDIT)}`",
            f"- `{relpath(EXISTING_ROWS)}`",
            f"- `{relpath(TARGETS)}`",
            f"- `{relpath(CANDIDATES)}`",
            f"- `{relpath(NLM_BATCHES)}`",
            "",
            "## Conventions",
            "",
            "- Blank target cells mean not yet extracted from that artifact, not zero or biological absence.",
            "- PDF regex candidates are evidence prompts, not analysis-ready values.",
            "- `existing_model_covariate` can mean external taxonomy or standardized source-level metadata; use `needs_pdf_verification` to distinguish which still need source checks.",
            "- NotebookLM validation is an independent check; pooled values still require PDF, table, or figure provenance.",
            "- Tier 3 taxon traits should be joined from an external trait/taxonomy table rather than extracted as paper-level free text.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workplan", type=Path, default=WORKPLAN)
    parser.add_argument("--covariates", type=Path, default=COVARIATES)
    parser.add_argument("--model-covariates", type=Path, default=MODEL_COVARIATES)
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--text-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--source-index", type=Path, default=SOURCE_INDEX)
    parser.add_argument("--text-audit", type=Path, default=TEXT_AUDIT)
    parser.add_argument("--existing-rows", type=Path, default=EXISTING_ROWS)
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--notebooklm-batches", type=Path, default=NLM_BATCHES)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return build_outputs(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Audit trait and taxonomy covariate coverage for figure-linked source sets."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COVARIATES = ROOT / "notebook_covariates" / "notebook_covariates_primary_geoaugmented.csv"
MODEL_COVARIATES = ROOT / "data" / "extraction" / "meta_analysis" / "META_ANALYSIS_COVARIATES.csv"
RAW_OVERVIEW_SOURCE_INDEX = ROOT / "figures" / "raw_response_overview_source_index.csv"
DIGITIZATION_QUEUE = ROOT / "pipeline" / "DIGITIZATION_FIGURE_QUEUE.csv"
RATE_SOURCE_INDEX = ROOT / "data" / "extraction" / "rate" / "RATE_SOURCE_INDEX.csv"
SUMMARY_CSV = ROOT / "notebook_covariates" / "trait_covariate_coverage_by_source_set.csv"
SOURCE_DETAIL_CSV = ROOT / "notebook_covariates" / "trait_covariate_coverage_by_source.csv"
SCHEMA_GAPS_CSV = ROOT / "notebook_covariates" / "trait_covariate_schema_gaps.csv"
SUMMARY_MD = ROOT / "notebook_covariates" / "TRAIT_COVARIATE_COVERAGE.md"

SOURCE_LEVEL_FIELDS = [
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
    "sample_size",
    "study_type",
    "study_year",
    "country_territory",
    "water_body",
    "temperature_c",
    "ph_or_pco2",
    "nutrient_enrich",
    "light_par",
    "light_regime",
    "sedimentation",
    "flow_regime",
]

MODEL_READY_TRAIT_FIELDS = [
    "taxon_count",
    "genus",
    "family",
    "growth_form_standard",
    "taxonomy_family",
    "skeletal_porosity",
    "porosity",
    "perforate_status",
    "imperforate_status",
    "clade",
    "coral_taxon_id",
]

MODEL_READY_ALIASES = {
    "taxonomy_family": "family",
    "porosity": "skeletal_porosity",
    "perforate_status": "skeletal_porosity",
    "imperforate_status": "skeletal_porosity",
}

MISSING_TOKENS = {
    "",
    "na",
    "n/a",
    "none",
    "null",
    "not applicable",
    "not_applicable",
    "not reported",
    "not_reported",
    "unknown",
}

POROSITY_PATTERN = re.compile(r"\b(?:im)?perforat", re.IGNORECASE)
MULTI_OR_AMBIGUOUS_SPECIES_PATTERN = re.compile(r",|;|\band\b|spp\.|cf\.|/|\bor\b", re.IGNORECASE)


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


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


def has_value(value: object) -> bool:
    return clean(value).lower() not in MISSING_TOKENS


def source_ids_raw_overview(rows: list[dict[str, str]]) -> list[str]:
    return sorted(
        {
            row.get("source_id", "")
            for row in rows
            if row.get("source_id", "") and row.get("plot_status", "").startswith("plotted")
        }
    )


def source_ids_all(rows: list[dict[str, str]]) -> list[str]:
    return sorted({row.get("source_id", "") for row in rows if row.get("source_id", "")})


def source_sets() -> dict[str, list[str]]:
    return {
        "raw_overview_plotted": source_ids_raw_overview(read_csv(RAW_OVERVIEW_SOURCE_INDEX)),
        "digitization_queue": source_ids_all(read_csv(DIGITIZATION_QUEUE)),
        "rate_source_index": source_ids_all(read_csv(RATE_SOURCE_INDEX)),
    }


def coverage_row(
    source_set: str,
    n_sources: int,
    field: str,
    field_status: str,
    n_present: int,
    notes: str = "",
) -> dict[str, object]:
    n_missing = n_sources - n_present
    percent_present = "" if n_sources == 0 else f"{100 * n_present / n_sources:.1f}"
    return {
        "source_set": source_set,
        "n_sources": n_sources,
        "field": field,
        "field_status": field_status,
        "n_present": n_present,
        "n_missing": n_missing,
        "percent_present": percent_present,
        "notes": notes,
    }


def build_coverage(
    covariate_rows: list[dict[str, str]],
    model_covariate_rows: list[dict[str, str]],
    sets: dict[str, list[str]],
) -> list[dict[str, object]]:
    headers = set(covariate_rows[0].keys()) if covariate_rows else set()
    model_headers = set(model_covariate_rows[0].keys()) if model_covariate_rows else set()
    by_source = {row.get("source_id", ""): row for row in covariate_rows if row.get("source_id", "")}
    model_by_source = {row.get("source_id", ""): row for row in model_covariate_rows if row.get("source_id", "")}
    rows: list[dict[str, object]] = []

    for source_set, source_ids in sets.items():
        selected = [by_source.get(source_id, {}) for source_id in source_ids]
        n_sources = len(source_ids)
        for field in SOURCE_LEVEL_FIELDS:
            status = "column_present" if field in headers else "column_absent"
            n_present = sum(has_value(row.get(field, "")) for row in selected) if field in headers else 0
            rows.append(coverage_row(source_set, n_sources, field, status, n_present))

        selected_model = [model_by_source.get(source_id, {}) for source_id in source_ids]
        for field in MODEL_READY_TRAIT_FIELDS:
            status = "model_column_present" if field in model_headers else "model_column_absent"
            n_present = sum(has_value(row.get(field, "")) for row in selected_model) if field in model_headers else 0
            rows.append(
                coverage_row(
                    source_set,
                    n_sources,
                    field,
                    status,
                    n_present,
                    "Requested model-ready taxonomy/trait moderator from META_ANALYSIS_COVARIATES.csv.",
                )
            )

        rows.append(
            coverage_row(
                source_set,
                n_sources,
                "tissue_type_mentions_perforate_or_imperforate",
                "derived_text_check",
                sum(bool(POROSITY_PATTERN.search(row.get("tissue_type", ""))) for row in selected),
                "Text search in tissue_type only; this is not a normalized porosity moderator.",
            )
        )
        rows.append(
            coverage_row(
                source_set,
                n_sources,
                "notes_or_tissue_mentions_perforate_or_imperforate",
                "derived_text_check",
                sum(
                    bool(POROSITY_PATTERN.search(f"{row.get('tissue_type', '')} {row.get('notes', '')}"))
                    for row in selected
                ),
                "Text search in tissue_type plus notes; this is evidence of recoverability, not a clean field.",
            )
        )
        species_present = [row for row in selected if has_value(row.get("species", ""))]
        rows.append(
            coverage_row(
                source_set,
                len(species_present),
                "species_multi_or_ambiguous_among_nonblank",
                "derived_text_check",
                sum(bool(MULTI_OR_AMBIGUOUS_SPECIES_PATTERN.search(row.get("species", ""))) for row in species_present),
                "Denominator is nonblank species rows because this is an ambiguity flag, not field coverage.",
            )
        )
    return rows


def build_source_detail(
    covariate_rows: list[dict[str, str]],
    model_covariate_rows: list[dict[str, str]],
    sets: dict[str, list[str]],
) -> list[dict[str, object]]:
    by_source = {row.get("source_id", ""): row for row in covariate_rows if row.get("source_id", "")}
    model_by_source = {row.get("source_id", ""): row for row in model_covariate_rows if row.get("source_id", "")}
    details: list[dict[str, object]] = []
    for source_set, source_ids in sets.items():
        for source_id in source_ids:
            row = by_source.get(source_id, {})
            model = model_by_source.get(source_id, {})
            tissue_text = row.get("tissue_type", "")
            notes_text = row.get("notes", "")
            species = row.get("species", "")
            details.append(
                {
                    "source_set": source_set,
                    "source_id": source_id,
                    "paper_title": row.get("paper_title", ""),
                    "species": species,
                    "growth_form": row.get("growth_form", ""),
                    "tissue_type": tissue_text,
                    "genus": model.get("genus", ""),
                    "genus_candidates": model.get("genus_candidates", ""),
                    "family": model.get("family", ""),
                    "family_candidates": model.get("family_candidates", ""),
                    "growth_form_standard": model.get("growth_form_standard", ""),
                    "skeletal_porosity": model.get("skeletal_porosity", ""),
                    "skeletal_porosity_candidates": model.get("skeletal_porosity_candidates", ""),
                    "skeletal_porosity_model_status": model.get("skeletal_porosity_model_status", ""),
                    "has_species": int(has_value(species)),
                    "has_growth_form": int(has_value(row.get("growth_form", ""))),
                    "has_tissue_type": int(has_value(tissue_text)),
                    "has_model_genus": int(has_value(model.get("genus", ""))),
                    "has_model_family": int(has_value(model.get("family", ""))),
                    "has_growth_form_standard": int(has_value(model.get("growth_form_standard", ""))),
                    "has_model_skeletal_porosity": int(has_value(model.get("skeletal_porosity", ""))),
                    "tissue_type_mentions_perforate_or_imperforate": int(bool(POROSITY_PATTERN.search(tissue_text))),
                    "notes_or_tissue_mentions_perforate_or_imperforate": int(
                        bool(POROSITY_PATTERN.search(f"{tissue_text} {notes_text}"))
                    ),
                    "species_multi_or_ambiguous": int(bool(MULTI_OR_AMBIGUOUS_SPECIES_PATTERN.search(species))),
                }
            )
    return details


def build_schema_gaps(
    covariate_rows: list[dict[str, str]],
    model_covariate_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    headers = set(covariate_rows[0].keys()) if covariate_rows else set()
    model_headers = set(model_covariate_rows[0].keys()) if model_covariate_rows else set()
    rows: list[dict[str, object]] = []
    for field in MODEL_READY_TRAIT_FIELDS:
        if field in model_headers:
            status = "present_model_covariate_layer"
            resolution = "Use META_ANALYSIS_COVARIATES.csv and the paired model-status columns."
        elif MODEL_READY_ALIASES.get(field, "") in model_headers:
            status = "covered_by_model_covariate_alias"
            resolution = f"Use `{MODEL_READY_ALIASES[field]}` in META_ANALYSIS_COVARIATES.csv instead of adding a duplicate alias."
        elif field in headers:
            status = "present_source_covariate_layer"
            resolution = "Normalize this source-level field before using it as a moderator."
        else:
            status = "absent"
            resolution = "Add a taxon-level trait table and join it to model covariates."
        rows.append(
            {
                "field": field,
                "schema_status": status,
                "recommended_resolution": resolution,
            }
        )
    return rows


def format_count(rows: list[dict[str, object]], source_set: str, field: str) -> str:
    for row in rows:
        if row.get("source_set") == source_set and row.get("field") == field:
            return f"{row.get('n_present')}/{row.get('n_sources')}"
    return "NA"


def write_summary_md(
    path: Path,
    coverage_rows: list[dict[str, object]],
    schema_gaps: list[dict[str, object]],
) -> None:
    absent_fields = [row["field"] for row in schema_gaps if row["schema_status"] == "absent"]
    alias_fields = [row["field"] for row in schema_gaps if row["schema_status"] == "covered_by_model_covariate_alias"]
    lines = [
        "# Trait Covariate Coverage",
        "",
        "Generated by `python3 tools/audit_trait_covariate_coverage.py`.",
        "",
        "## Interpretation",
        "",
        "- `species`, `growth_form`, and `tissue_type` are source-level fields in the primary covariate table.",
        "- `genus`, `family`, `growth_form_standard`, and conservative `skeletal_porosity` fields are now built in `data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv`.",
        "- `skeletal_porosity` remains sparse because `tissue_type` is heterogeneous free text and WoRMS does not supply porosity; full coverage still needs an external trait source.",
        "- Multi-species source rows are flagged and should not be collapsed to one genus, growth form, or porosity unless the effect-size row identifies the taxon.",
        "",
        "## Trait Columns Still Not Implemented",
        "",
        ", ".join(f"`{field}`" for field in absent_fields) if absent_fields else "None.",
        "",
        "## Alias Columns Covered By Existing Fields",
        "",
        ", ".join(f"`{field}`" for field in alias_fields) if alias_fields else "None.",
        "",
        "## Coverage In Figure-Linked Source Sets",
        "",
        "| Source set | N | Species | Raw growth | Raw tissue | Genus | Family | Growth standard | Skeletal porosity | Tissue mentions porosity | Notes/tissue mentions porosity | Multi/ambiguous species |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for source_set in ["raw_overview_plotted", "digitization_queue", "rate_source_index"]:
        n_sources = next(
            int(row["n_sources"]) for row in coverage_rows if row["source_set"] == source_set and row["field"] == "species"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    source_set,
                    str(n_sources),
                    format_count(coverage_rows, source_set, "species"),
                    format_count(coverage_rows, source_set, "growth_form"),
                    format_count(coverage_rows, source_set, "tissue_type"),
                    format_count(coverage_rows, source_set, "genus"),
                    format_count(coverage_rows, source_set, "family"),
                    format_count(coverage_rows, source_set, "growth_form_standard"),
                    format_count(coverage_rows, source_set, "skeletal_porosity"),
                    format_count(coverage_rows, source_set, "tissue_type_mentions_perforate_or_imperforate"),
                    format_count(coverage_rows, source_set, "notes_or_tissue_mentions_perforate_or_imperforate"),
                    format_count(coverage_rows, source_set, "species_multi_or_ambiguous_among_nonblank"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- `{relpath(SUMMARY_CSV)}`",
            f"- `{relpath(SOURCE_DETAIL_CSV)}`",
            f"- `{relpath(SCHEMA_GAPS_CSV)}`",
            f"- `{relpath(MODEL_COVARIATES)}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covariates", type=Path, default=COVARIATES)
    parser.add_argument("--model-covariates", type=Path, default=MODEL_COVARIATES)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--source-detail-csv", type=Path, default=SOURCE_DETAIL_CSV)
    parser.add_argument("--schema-gaps-csv", type=Path, default=SCHEMA_GAPS_CSV)
    parser.add_argument("--summary-md", type=Path, default=SUMMARY_MD)
    args = parser.parse_args()

    covariate_rows = read_csv(args.covariates)
    model_covariate_rows = read_csv(args.model_covariates)
    sets = source_sets()
    coverage_rows = build_coverage(covariate_rows, model_covariate_rows, sets)
    detail_rows = build_source_detail(covariate_rows, model_covariate_rows, sets)
    schema_gap_rows = build_schema_gaps(covariate_rows, model_covariate_rows)

    write_csv(
        args.summary_csv,
        ["source_set", "n_sources", "field", "field_status", "n_present", "n_missing", "percent_present", "notes"],
        coverage_rows,
    )
    write_csv(
        args.source_detail_csv,
        [
            "source_set",
            "source_id",
            "paper_title",
            "species",
            "growth_form",
            "tissue_type",
            "genus",
            "genus_candidates",
            "family",
            "family_candidates",
            "growth_form_standard",
            "skeletal_porosity",
            "skeletal_porosity_candidates",
            "skeletal_porosity_model_status",
            "has_species",
            "has_growth_form",
            "has_tissue_type",
            "has_model_genus",
            "has_model_family",
            "has_growth_form_standard",
            "has_model_skeletal_porosity",
            "tissue_type_mentions_perforate_or_imperforate",
            "notes_or_tissue_mentions_perforate_or_imperforate",
            "species_multi_or_ambiguous",
        ],
        detail_rows,
    )
    write_csv(args.schema_gaps_csv, ["field", "schema_status", "recommended_resolution"], schema_gap_rows)
    write_summary_md(args.summary_md, coverage_rows, schema_gap_rows)
    print(f"Wrote {relpath(args.summary_md)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

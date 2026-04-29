# Extraction Pipeline

This repository is a coral regeneration meta-analysis. The pipeline below keeps screening, PRISMA counts, extraction, figure clipping, and QA tied to one source-of-truth table.

## Source Of Truth

Use these files in this order:

1. `data/screening/SCREENING_LOG_FINAL.csv` - final paper-level adjudication, inclusion status, response flags, extraction readiness, and rationale.
2. `data/screening/HYPOTHESIS_X_RESPONSE_MATRIX.csv` - compact hypothesis-by-response matrix derived from the final screening decisions.
3. `notebook_covariates/notebook_covariates_primary_geoaugmented.csv` - primary-study covariates and georeferenced study metadata.
4. `notebook_covariates/notebook_covariate_missingness_primary_geoaugmented.csv` - covariate missingness used to prioritize follow-up checks.
5. `data/extraction/EXTRACTION_RATES.csv`, `data/extraction/EXTRACTION_FITNESS.csv`, and `data/extraction/EXTRACTION_SURVIVAL.csv` - extracted quantitative outcomes with source-level provenance.
6. `data/literature/LITERATURE_MAP.csv` - compact generated index of screening status and local PDF paths.
7. `data/literature/SOURCE_RETRIEVAL_LOG.csv` - hand-curated status for included sources that cannot yet be tied to a local PDF.
8. `pipeline/EXTRACTION_WORKPLAN.csv` and `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` - generated work queues; do not edit them as the upstream truth.
9. `digitization/source_review/*.csv` - generated execution aids for candidate captions, source retrieval, and legacy extraction QA.

`data/screening/SCREENING_LOG.csv`, `data/screening/SCREENING_LOG_V2.csv`, and `data/screening/SCREENING_REVIEW_QUEUE.csv` are retained as historical working artifacts unless they are explicitly regenerated during a new screening pass.

## Rebuild Command

Run:

```bash
python3 tools/build_pipeline_outputs.py
python3 tools/build_extraction_review_artifacts.py
```

The command writes:

- `pipeline/PRISMA_COUNTS.md` - manuscript-facing counts for the PRISMA flow.
- `pipeline/LITERATURE_ORGANIZATION_AUDIT.csv` - one row per final screening record with local-file and folder-status checks.
- `pipeline/LITERATURE_REORG_AUDIT.csv` - git-aware audit of flat PDF deletes versus organized PDF copies.
- `pipeline/EXTRACTION_WORKPLAN.csv` - one row per paper-response extraction task.
- `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` - one row per figure/table digitization task that still needs source clipping.
- `pipeline/PIPELINE_QA_REPORT.md` - compact warnings and next actions.
- `pipeline/PIPELINE_MANIFEST.md` - generated-file inventory.

The extraction-review command writes:

- `digitization/source_review/FIGURE_SOURCE_REVIEW.csv` - candidate printed labels and pages detected from available PDFs with `pdftotext`.
- `digitization/source_review/SOURCE_RETRIEVAL_QUEUE.csv` - blocked included sources lacking local PDFs, joined to `data/literature/SOURCE_RETRIEVAL_LOG.csv`.
- `digitization/source_review/LEGACY_EXTRACTION_QA_QUEUE.csv` - row-level provenance QA queue for existing extraction tables.
- `digitization/source_review/EXTRACTION_REVIEW_SUMMARY.md` - counts of candidate captions, blocked source retrieval, and legacy provenance gaps.

To reorganize PDFs after changing final screening status, run:

```bash
python3 tools/organize_literature_from_screening.py --apply
```

The literature folders intentionally encode only final paper status:

- `literature/META_ANALYSIS_POOL/` - primary quantitative papers.
- `literature/MECHANISMS_ONLY/` - narrative mechanism papers.
- `literature/EXCLUDED_FINAL/` - scope and review exclusions.
- `literature/DUPLICATES/` - duplicate aliases retained for traceability.

## Extraction Order

Work down `pipeline/EXTRACTION_WORKPLAN.csv` by `priority_rank`.

- `1`: primary studies marked `ready_extract`; extract directly from tables or text first.
- `2`: primary studies marked `needs_digitization`; clip and digitize figures/tables before effect-size extraction.
- `3`: primary studies that need readiness review before extraction.
- `4`: mechanism-only papers retained for narrative synthesis, not pooled effect sizes.

For quantitative extraction, every extracted row should retain:

- `source_id`
- `paper_title`
- `local_relpath`
- response type
- species or taxon
- wound type and geometry if reported
- treatment/stressor and control context
- mean or rate value
- variance type and value
- sample size
- time interval or duration
- location/covariates used in moderators
- extraction notes and figure/table provenance

## Figure Clipping And Labeling

Use `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` as the figure clipping manifest. Rows with `digitization_status=blocked_missing_local_pdf` must be retrieved before any clipping. Rows with `digitization_status=needs_figure_id` have the source PDF available but still need exact figure/table labels, pages, panels, axes, units, variance, and sample-size provenance before clip paths are assigned.

Use `digitization/source_review/FIGURE_SOURCE_REVIEW.csv` to triage likely printed figure/table labels and PDF pages. This file is a candidate list, not evidence by itself. A value is ready for clipping only after a reviewer selects the exact printed label and panel from the source PDF.

Store clipped source images under:

```text
digitization/figures/<source_id-prefix>__<response>__fig-<number>_panel-<letter>.png
```

Store digitized points or table transcriptions under:

```text
digitization/data/<source_id-prefix>__<response>__fig-<number>_panel-<letter>.csv
```

Each completed queue row should fill:

- `figure_or_table_label` - manuscript label exactly as printed, for example `Fig. 2`, `Table 1`, or `Supplementary Fig. S3`.
- `page` - PDF page containing the source figure or table.
- `panel_label` - panel letter or `all` when the entire figure/table is used.
- `x_axis` and `y_axis` - axis labels exactly as printed.
- `units` - rate, percent cover, survival, fecundity, or other measurement units.
- `variance_type` - `SE`, `SD`, `CI`, raw counts, or `not_reported`.
- `sample_size_source` - where sample size was obtained.
- `clip_path` - path to the clipped source image.
- `digitized_data_path` - path to digitized points or transcription.
- `digitizer`, `qa_reviewer`, and `qa_status`.
- `notes` - any assumptions, conversions, or exclusion decisions.

Do not pool a figure-derived value unless the clip path, label, page, panel, axis units, variance type, sample-size source, and digitized-data path are recorded.

Existing legacy extraction rows are tracked in `digitization/source_review/LEGACY_EXTRACTION_QA_QUEUE.csv`. Rows marked `needs_source_provenance_review` must not be treated as source-verified until exact figure/table provenance and QA reviewer signoff are recorded in the source extraction table.

## PRISMA Rules

The PRISMA summary in `pipeline/PRISMA_COUNTS.md` is generated from `data/screening/SCREENING_LOG_FINAL.csv`.

- `include_primary` contributes to the quantitative meta-analysis pool.
- `include_mechanism_only` contributes to narrative mechanism synthesis only.
- `exclude_scope` and `exclude_review` are full-text exclusions.
- `duplicate_alias` is counted separately from exclusions because it is not an independent record.
- `ready_extract` and `needs_digitization` split the primary pool into immediate extraction versus figure/table digitization.

When screening decisions change, update `data/screening/SCREENING_LOG_FINAL.csv` through the adjudication workflow and rebuild the pipeline outputs. Do not hand-edit PRISMA counts.

## QA Checklist

Before using the PRISMA counts or extraction tables in manuscript text:

- Rebuild `pipeline/` with `python3 tools/build_pipeline_outputs.py`.
- Rebuild extraction-review artifacts with `python3 tools/build_extraction_review_artifacts.py`.
- Confirm `pipeline/PIPELINE_QA_REPORT.md` has no blocking local-file or hash warnings.
- Resolve any folder placements marked `folder_needs_review` in `pipeline/LITERATURE_ORGANIZATION_AUDIT.csv`.
- Complete every required row in `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` before treating figure-derived values as extracted.
- Check that every pooled extracted value links back to a `source_id`, figure/table label, page, units, variance type, and sample size.

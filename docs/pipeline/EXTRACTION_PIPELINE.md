# Extraction Pipeline

This repository is a coral regeneration meta-analysis. The pipeline below keeps screening, PRISMA counts, extraction, figure clipping, and QA tied to one source-of-truth table.

## Source Of Truth

Use these files in this order:

1. `data/screening/SCREENING_LOG_FINAL.csv` - final paper-level adjudication, inclusion status, response flags, extraction readiness, and rationale.
2. `data/screening/HYPOTHESIS_X_RESPONSE_MATRIX.csv` - compact hypothesis-by-response matrix derived from the final screening decisions.
3. `notebook_covariates/NOTEBOOKLM_NOTEBOOKS.md` and `notebook_covariates/notebooklm_notebooks.csv` - canonical connected NotebookLM notebook registry. The primary extraction notebook is `Coral regeneration all sources` (`bb37eb1a-3b19-4f6c-9cc3-7df3a41e1388`), with 267 sources as last verified on 2026-08-16.
4. `notebook_covariates/notebook_covariates_primary_geoaugmented.csv` - primary-study covariates and georeferenced study metadata.
5. `notebook_covariates/taxon_trait_lookup.csv` - genus-level WoRMS taxonomy lookup for family joins; skeletal-porosity fields remain separate trait fields with their own provenance.
6. `notebook_covariates/notebook_covariate_missingness_primary_geoaugmented.csv` - covariate missingness used to prioritize follow-up checks.
7. `data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv` - model-ready moderator layer derived from source covariates plus taxon lookup.
8. `data/extraction/EXTRACTION_RATES.csv`, `data/extraction/EXTRACTION_FITNESS.csv`, and `data/extraction/EXTRACTION_SURVIVAL.csv` - extracted quantitative outcomes with source-level provenance.
9. `data/extraction/rate/` - rate-specific source index, ranked text evidence, provisional curated observations, legacy/pilot seed rows, and source-level audit outputs.
10. `data/extraction/all_responses/` - response-wide PDF-read audit, source index, covariate target matrix, text-evidence candidates, and NotebookLM validation outputs for rate, growth, survival, and reproduction.
11. `data/extraction/analysis_ready/` - strict fail-closed gate that says which extracted rows can enter modeling and why every other row is blocked.
12. `data/extraction/meta_analysis/` - metafor-ready input layer with `yi`, `vi`, effect-size family, analysis stratum, dependence identifiers, and moderator columns.
13. `data/literature/LITERATURE_MAP.csv` - compact generated index of screening status and local PDF paths.
14. `data/literature/SOURCE_RETRIEVAL_LOG.csv` - hand-curated status for included sources that cannot yet be tied to a local PDF.
15. `pipeline/EXTRACTION_WORKPLAN.csv` and `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` - generated work queues; do not edit them as the upstream truth.
16. `digitization/source_review/*.csv` and `digitization/figures/FIGURE_CROP_MANIFEST.csv` - generated execution aids for candidate captions, audited candidate corrections, crop proposals, source retrieval, and legacy extraction QA.

`data/screening/SCREENING_LOG.csv`, `data/screening/SCREENING_LOG_V2.csv`, and `data/screening/SCREENING_REVIEW_QUEUE.csv` are retained as historical working artifacts unless they are explicitly regenerated during a new screening pass.

## Rebuild Command

Run:

```bash
python3 tools/build_pipeline_outputs.py
python3 tools/build_extraction_review_artifacts.py
python3 tools/merge_figure_candidate_audits.py
python3 tools/render_audited_source_pages.py
python3 tools/build_figure_visual_reaudit.py
python3 tools/build_figure_crop_manifest.py
python3 tools/audit_figure_indexing.py
python3 tools/build_rate_extraction_dataset.py
python3 tools/audit_rate_extraction_dataset.py
python3 tools/build_taxon_trait_lookup.py
python3 tools/build_model_covariates.py
python3 tools/audit_trait_covariate_coverage.py
python3 tools/build_all_response_extraction_dataset.py
python3 tools/run_notebooklm_validation_batches.py --query-timeout 180 --process-timeout 260
python3 tools/audit_dataset_against_notebooklm.py
python3 tools/build_analysis_ready_dataset.py
python3 tools/build_meta_analysis_inputs.py
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

The figure-candidate audit merge command writes:

- `digitization/source_review/FIGURE_SOURCE_REVIEW_VALIDATED.csv` - raw candidate rows joined to independent audit results and corrected label/page fields.
- `digitization/source_review/FIGURE_CANDIDATE_AUDIT.csv` - normalized reviewer audit rows.
- `digitization/source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` - one audited decision row per digitization queue item.
- `digitization/source_review/FIGURE_CANDIDATE_AUDIT_SUMMARY.md` - audit coverage and outcome counts.

The source-page render command writes:

- `digitization/figures/SOURCE_PAGE_RENDER_MANIFEST.csv` - one row per audited candidate label/page with the rendered source-page image path.
- `digitization/figures/source_pages/*.png` - full-page source images for visual figure/table clipping. These are not final cropped panel clips.

The visual reaudit command writes:

- `digitization/source_review/FIGURE_VISUAL_REAUDIT.csv` - accepted rendered candidates plus retained caption-level rejected candidates.
- `digitization/source_review/FIGURE_VISUAL_REAUDIT_SUMMARY.md` - render verification, crop readiness, extractability class, and retained rejection counts.

The crop-manifest command writes:

- `digitization/figures/FIGURE_CROP_MANIFEST.csv` - accepted visual candidates with proposed crop paths and retained rejected candidates marked as not croppable.
- `digitization/figures/FIGURE_CROP_SUMMARY.md` - crop status, review status, extractability, and caption-locator counts.
- `digitization/figures/crop_review/*.png` - reproducible proposal images for human crop-box QA. These are not final cropped panel clips.

The figure-index audit command writes:

- `digitization/figures/FIGURE_INDEX_AUDIT.csv` - structural checks over source IDs, local PDFs, hashes, page counts, queue joins, render paths, crop paths, crop boxes, and concrete digitized-data paths.
- `digitization/figures/FIGURE_INDEX_AUDIT_SUMMARY.md` - compact pass/fail counts for the figure-to-source and figure-to-data indexing chain.

The rate-extraction commands write:

- `data/extraction/rate/RATE_SOURCE_INDEX.csv` - one source-level row for each primary rate-response paper, joined to local PDFs, parsed text, curated rows, seed rows, figure queues, crop proposals, and extraction route.
- `data/extraction/rate/RATE_TEXT_EVIDENCE.csv` - ranked full-text evidence snippets generated from parsed PDFs.
- `data/extraction/rate/RATE_EXTRACTED_OBSERVATIONS.csv` - provisional raw observations manually extracted from printed prose or tables.
- `data/extraction/rate/RATE_EFFECT_SIZE_SEEDS.csv` - legacy and pilot numeric rows carried forward as seeds only.
- `data/extraction/rate/RATE_EXTRACTION_AUDIT.csv` and `RATE_EXTRACTION_AUDIT_SUMMARY.md` - structural, join, provenance, and readiness checks for the rate layer.

The all-response extraction and NotebookLM validation commands use the primary notebook listed in `notebook_covariates/NOTEBOOKLM_NOTEBOOKS.md` and write:

- `data/extraction/all_responses/ALL_RESPONSE_SOURCE_INDEX.csv` - one row per primary PDF, with response memberships and local PDF/text-read status.
- `data/extraction/all_responses/ALL_RESPONSE_PDF_TEXT_AUDIT.csv` - one row per PDF with page counts, file/text hashes, text paths, text lengths, and title-overlap checks.
- `data/extraction/all_responses/ALL_RESPONSE_EXISTING_EXTRACTION_ROWS.csv` - normalized legacy/rate extraction rows used only as seeds or existing-value indicators.
- `data/extraction/all_responses/ALL_RESPONSE_COVARIATE_TARGETS.csv` - every response-by-covariate target from the current covariate schema, including target status and whether PDF/NotebookLM verification is needed.
- `data/extraction/all_responses/ALL_RESPONSE_COVARIATE_CANDIDATES.csv` - regex-derived PDF text snippets that point reviewers to possible values; these are not analysis-ready rows.
- `data/extraction/all_responses/NOTEBOOKLM_VALIDATION_BATCHES.csv` - response-specific source batches used to query the connected NotebookLM notebook.
- `data/extraction/all_responses/notebooklm_validation/*.json` - raw NotebookLM JSON validation outputs with cited evidence for each batch.
- `data/extraction/all_responses/ALL_RESPONSE_EXTRACTION_SUMMARY.md` and `NOTEBOOKLM_VALIDATION_SUMMARY.md` - compact rebuild summaries.

The NotebookLM dataset audit command writes:

- `notebook_covariates/notebooklm_source_registry.csv` - current connected NotebookLM source list, annotated with membership in the local source-bearing tables.
- `data/extraction/all_responses/NOTEBOOKLM_DATASET_AUDIT.csv` - source-ID coverage, `notebook_present` flag, duplicate-title, duplicate-source-row, and title-similarity checks across source-bearing dataset CSVs.
- `data/extraction/all_responses/NOTEBOOKLM_VALUE_SUPPORT_AUDIT.csv` - direct NotebookLM raw-text support checks for source-derived covariates and quantitative extraction values. `no_direct_text_match` is a review flag, not automatic evidence that a value is wrong.
- `data/extraction/all_responses/NOTEBOOKLM_DATASET_AUDIT_SUMMARY.md` - compact source and value-support audit summary.

The current all-response layer covers 121 primary response rows across 76 PDFs: rate = 57, growth = 30, survival = 27, and reproduction = 7. The PDF-read audit records 76 successful text reads. The target matrix has 5,808 response-covariate targets and 4,756 PDF-text candidate snippets. NotebookLM validation has 13 response batches covering 121 response-specific source checks; raw outputs are saved under `data/extraction/all_responses/notebooklm_validation/`.

The model-covariate commands write:

- `notebook_covariates/taxon_trait_lookup.csv` - one row per genus detected in the primary covariate table, with family populated from the WoRMS Aphia REST API after filtering to Scleractinia/Hexacorallia records.
- `notebook_covariates/TAXON_TRAIT_LOOKUP_SUMMARY.md` - compact status for the taxonomy lookup.
- `data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv` - one row per primary source with normalized genus, family, growth-form, conservative skeletal-porosity, study-design, environmental, wound-geometry, and coordinate moderator fields.
- `data/extraction/meta_analysis/META_ANALYSIS_COVARIATE_AUDIT.csv` - same rows with readiness/status fields for moderator-use checks.
- `data/extraction/meta_analysis/META_ANALYSIS_COVARIATE_SCHEMA.csv` and `META_ANALYSIS_COVARIATE_SUMMARY.md` - modeling meaning and coverage counts.

The current model-covariate layer covers 76 primary sources. It has genus for 57/76, family for 59/76, standardized growth form for 55/76, conservative skeletal porosity for 7/76, field/lab/mesocosm setting for 76/76, depth midpoint for 65/76, initial wound area midpoint for 53/76, temperature midpoint for 34/76, pH midpoint for 3/76, and pCO2 midpoint for 2/76. Skeletal porosity remains intentionally sparse until an external morphology/trait lookup is added.

The analysis-ready command writes:

- `data/extraction/analysis_ready/ANALYSIS_READY_OBSERVATIONS.csv` - the only extracted observation rows allowed to enter modeling.
- `data/extraction/analysis_ready/ANALYSIS_READY_OBSERVATION_AUDIT.csv` - one row per extracted observation with readiness status, blockers, matched crop paths, and matched digitized-data paths.
- `data/extraction/analysis_ready/ANALYSIS_READY_ISSUES.csv` - one issue per blocking or warning condition.
- `data/extraction/analysis_ready/ANALYSIS_READY_BLOCKING_QUEUE.csv` - extracted rows that need provenance, digitization, or independent QC before pooling.
- `data/extraction/analysis_ready/ANALYSIS_READY_RESPONSE_QUEUE.csv` - one row per primary source-response task with the next action needed.
- `data/extraction/analysis_ready/ANALYSIS_READY_SUMMARY.md` - compact gate summary.

The current gate audits 92 extracted observation rows and marks 0 as analysis-ready. That is intentional: existing rows still need source provenance or independent QC, and figure-derived rows still need reviewed crop boxes, final clips, and concrete digitized-data CSVs.

The meta-analysis input command writes:

- `data/extraction/meta_analysis/META_ANALYSIS_INPUTS.csv` - one row per effect-size-ready modeling input with `yi`, `vi`, study/effect IDs, analysis stratum, and moderators.
- `data/extraction/meta_analysis/META_ANALYSIS_INPUT_AUDIT.csv` - one row per upstream analysis-ready observation, including effect-size blockers if `yi/vi` cannot be computed.
- `data/extraction/meta_analysis/META_ANALYSIS_INPUT_ISSUES.csv` - effect-size calculation blockers and warnings.
- `data/extraction/meta_analysis/META_ANALYSIS_INPUT_SCHEMA.csv` - schema and modeling meaning of key columns.
- `data/extraction/meta_analysis/META_ANALYSIS_SUMMARY.md` and `META_ANALYSIS_MODEL_PLAN.md` - compact status and project-specific modeling rules.

The current meta-analysis input table is empty because no row has passed the upstream analysis-ready gate. Once rows pass, the builder will keep survival log odds ratios, continuous log response ratios, and raw-rate/endpoints in separate `analysis_stratum` values so incompatible scales are not pooled accidentally.

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

Use `digitization/source_review/FIGURE_SOURCE_REVIEW.csv` only as the raw candidate list. Use `digitization/source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` as the audited clipping worklist after independent candidate review. Rows marked `audited_candidate_available` still require visual confirmation of panel, axes, units, variance, and sample size before clipping. Rows marked `no_valid_candidate_found` should not be clipped unless a later full-text review identifies valid non-caption evidence.

Use `digitization/figures/SOURCE_PAGE_RENDER_MANIFEST.csv` to find the rendered source-page image for each audited candidate. Files under `digitization/figures/source_pages/` are full-page photos for review and cropping; final clip files should still be saved under `digitization/figures/<source_id-prefix>__<response>__fig-<number>_panel-<letter>.png`.

Use `digitization/source_review/FIGURE_VISUAL_REAUDIT.csv` as the bridge from source-page photos to final cropping. Rows marked `accepted_visual_candidate` are source-page verified but not cropped. Rows marked `retained_caption_rejected` preserve rejected candidates and should not enter clipping unless a later reviewer overturns the caption audit.

Use `digitization/figures/FIGURE_CROP_MANIFEST.csv` as the reproducible crop-proposal worklist. Rows marked `auto_crop_proposal_created` point to files in `digitization/figures/crop_review/` and remain `needs_human_crop_box_qa` until a reviewer confirms or adjusts the exact panel/table boundary. Rows marked `retained_rejected_not_cropped` are retained for provenance and should stay outside extraction.

Use `digitization/figures/FIGURE_INDEX_AUDIT_SUMMARY.md` as the end-to-end indexing gate after rebuilding crops. It should report zero structural errors before any figure-derived value is pooled. Warnings such as `queue_no_valid_candidate_found` can be legitimate, but those response rows remain non-extractable until a later full-text review finds usable evidence.

Use `data/extraction/rate/RATE_EXTRACTION_AUDIT_SUMMARY.md` as the rate-specific source/data gate. It should report zero errors before any rate row is pooled. Warnings currently mean the rate layer remains provisional: rows require independent QC, legacy/pilot seeds require source provenance, or figure/table values still need digitization.

Use `data/extraction/analysis_ready/ANALYSIS_READY_OBSERVATIONS.csv` as the only modeling input candidate. If a row is absent from that file, it is not analysis-ready, even if it appears in a legacy extraction table, crop manifest, NotebookLM validation output, or provisional rate table.

Use `data/extraction/meta_analysis/META_ANALYSIS_INPUTS.csv` as the only `metafor` input table. Rows must have `yi` and `vi`, and models should not mix `analysis_stratum` values unless an explicit conversion/rationale is documented. Moderator models should use normalized covariate fields from `META_ANALYSIS_COVARIATES.csv`, and only when the paired `*_model_status` field shows the moderator is usable for that row.

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
- Rebuild figure-candidate audit overlays with `python3 tools/merge_figure_candidate_audits.py` after reviewer audit files are updated.
- Render audited source pages with `python3 tools/render_audited_source_pages.py` before manual panel/table cropping.
- Rebuild the visual reaudit with `python3 tools/build_figure_visual_reaudit.py` so accepted rendered candidates and retained rejected rows stay synchronized.
- Rebuild crop proposals with `python3 tools/build_figure_crop_manifest.py` so crop-review images and retained rejected rows stay synchronized.
- Run `python3 tools/audit_figure_indexing.py` and confirm `FIGURE_INDEX_AUDIT_SUMMARY.md` reports zero structural errors.
- Rebuild the rate workspace with `python3 tools/build_rate_extraction_dataset.py`.
- Run `python3 tools/audit_rate_extraction_dataset.py` and confirm `RATE_EXTRACTION_AUDIT_SUMMARY.md` reports zero errors.
- Rebuild all-response extraction targets with `python3 tools/build_all_response_extraction_dataset.py`.
- Run `python3 tools/run_notebooklm_validation_batches.py --query-timeout 180 --process-timeout 260` and confirm every response batch has a valid JSON file with cited sources.
- Run `python3 tools/build_analysis_ready_dataset.py` and use only `ANALYSIS_READY_OBSERVATIONS.csv` for modeling.
- Run `python3 tools/build_meta_analysis_inputs.py` and use only `META_ANALYSIS_INPUTS.csv` for `metafor`.
- Confirm `pipeline/PIPELINE_QA_REPORT.md` has no blocking local-file or hash warnings.
- Resolve any folder placements marked `folder_needs_review` in `pipeline/LITERATURE_ORGANIZATION_AUDIT.csv`.
- Complete every required row in `pipeline/DIGITIZATION_FIGURE_QUEUE.csv`, using `digitization/source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` as the audited label/page guide, before treating figure-derived values as extracted.
- Check that every pooled extracted value links back to a `source_id`, figure/table label, page, units, variance type, and sample size.

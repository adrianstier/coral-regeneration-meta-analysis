# Coral Regeneration Meta-Analysis

This repository currently houses the screening, literature organization, covariate, extraction, and figure/table digitization infrastructure for a systematic review and eventual meta-analysis of coral regeneration after wounding.

## Current State

As of the current repository state:

- The adjudicated library contains 156 full-text records.
- The quantitative meta-analysis pool contains 76 primary studies: 20 ready for table/text extraction and 56 requiring figure/table digitization.
- The narrative mechanism pool contains 20 studies.
- Local PDF coverage is complete for the primary pool; four non-primary records remain without local PDFs.
- The statistical meta-analysis and manuscript draft have not started yet; no `renv`, R modeling scripts, effect-size scripts, or manuscript directory are present.

## Objectives

- **Quantify average coral healing rates** across species, environments, and wound types.
- **Understand how coral traits** (taxonomy, morphology, tissue type) shape regeneration outcomes.
- **Test specific hypotheses** about environmental stressors and healing success.
- **Identify knowledge gaps** to guide future research priorities.
- **Create an open-access database** of coral healing metrics and metadata.

## Source Of Truth

<<<<<<< Updated upstream
---
*Follow PRISMA guidelines for all systematic review steps.*

<!-- lab-xref -->
## Lab cross-reference

**Drive folder:** `…/Coral-Regeneration/Projects/15. Meta_Analysis_Healing_Growth_Reproduction_2025/` — Project **P15** (PRISMA meta-analysis). Feeds synthesis stats into the regeneration review (Manuscript **A**, repo [`adrianstier/coral-regen-review`](https://github.com/adrianstier/coral-regen-review)).
=======
Use these files before consulting generated work queues:

- `data/screening/SCREENING_LOG_FINAL.csv`: adjudicated paper-level status, response flags, extraction readiness, and rationale.
- `data/screening/HYPOTHESIS_X_RESPONSE_MATRIX.csv`: hypothesis-by-response matrix derived from final screening.
- `notebook_covariates/NOTEBOOKLM_NOTEBOOKS.md` and `notebook_covariates/notebooklm_notebooks.csv`: canonical connected NotebookLM notebook registry. The primary extraction notebook is `Coral regeneration all sources` (`bb37eb1a-3b19-4f6c-9cc3-7df3a41e1388`), with 267 sources as last verified on 2026-08-16.
- `notebook_covariates/notebook_covariates_primary_geoaugmented.csv`: current primary-study moderator/covariate table, including exact, approximate, and best-coordinate fields.
- `notebook_covariates/taxon_trait_lookup.csv`: genus-level WoRMS taxonomy lookup used to populate model-ready family fields.
- `notebook_covariates/COVARIATE_EXTRACTION_STRATEGY.md` and `notebook_covariates/covariate_extraction_schema.csv`: current moderator strategy, including which covariates should be extracted from papers versus joined from taxon-trait tables.
- `data/extraction/EXTRACTION_RATES.csv`, `data/extraction/EXTRACTION_FITNESS.csv`, and `data/extraction/EXTRACTION_SURVIVAL.csv`: quantitative extraction tables. Legacy rows still need row-level source provenance before pooling.
- `data/extraction/rate/`: rate-specific source index, text-evidence snippets, provisional curated observations, legacy/pilot seed rows, and audit summaries.
- `data/extraction/all_responses/`: response-wide PDF-read audit, source index, covariate target matrix, PDF-text evidence candidates, and NotebookLM validation batches for rate, growth, survival, and reproduction.
- `data/extraction/analysis_ready/`: strict fail-closed gate that says which extracted rows can enter modeling and why every other row is blocked.
- `data/extraction/meta_analysis/`: metafor-ready input layer with `yi`, `vi`, effect-size family, analysis stratum, dependence identifiers, and moderator columns.

Generated files under `pipeline/`, `digitization/source_review/`, and `digitization/figures/` are execution aids. Rebuild them from the upstream tables instead of hand-editing them as source-of-truth records.

## Rebuild Generated QA

Run the current generated-output chain in this order:

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

Then review:

- `pipeline/PIPELINE_QA_REPORT.md`
- `pipeline/PRISMA_COUNTS.md`
- `digitization/source_review/EXTRACTION_REVIEW_SUMMARY.md`
- `digitization/source_review/FIGURE_CANDIDATE_AUDIT_SUMMARY.md`
- `digitization/source_review/FIGURE_VISUAL_REAUDIT_SUMMARY.md`
- `digitization/figures/FIGURE_CROP_SUMMARY.md`
- `digitization/figures/FIGURE_INDEX_AUDIT_SUMMARY.md`
- `data/extraction/rate/RATE_EXTRACTION_SUMMARY.md`
- `data/extraction/rate/RATE_EXTRACTION_AUDIT_SUMMARY.md`
- `data/extraction/meta_analysis/META_ANALYSIS_COVARIATE_SUMMARY.md`
- `data/extraction/all_responses/ALL_RESPONSE_EXTRACTION_SUMMARY.md`
- `data/extraction/all_responses/NOTEBOOKLM_VALIDATION_SUMMARY.md`
- `data/extraction/all_responses/NOTEBOOKLM_DATASET_AUDIT_SUMMARY.md`
- `data/extraction/analysis_ready/ANALYSIS_READY_SUMMARY.md`
- `data/extraction/meta_analysis/META_ANALYSIS_SUMMARY.md`
- `notebook_covariates/NOTEBOOKLM_NOTEBOOKS.md`
- `notebook_covariates/COVARIATE_EXTRACTION_STRATEGY.md`
- `notebook_covariates/TRAIT_COVARIATE_COVERAGE.md`

## Directory Map

- `archive/`: original Zotero/PDF-library export artifacts retained for traceability.
- `data/`: adjudicated screening, extraction, and compact literature metadata tables.
- `digitization/`: figure/table source-review, rendered source pages, crop proposals, and future digitized data.
- `docs/`: protocol, audit, and extraction-pipeline documentation.
- `literature/`: organized local PDF library by final status.
- `notebook_covariates/`: connected NotebookLM notebook registry, NotebookLM-derived study covariates, taxon-trait lookup inputs, and approximate georeference outputs.
- `pipeline/`: generated PRISMA counts, workplans, literature audits, and QA report.
- `tests/`: regression tests for the Python pipeline tools.
- `tools/`: Python utilities that rebuild screening, pipeline, covariate, georeference, source-review, and digitization artifacts.

## Validation

Run the lightweight regression suite after editing pipeline tools:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Follow PRISMA guidelines for all systematic review steps. See `PLAN.md` for the protocol and `docs/pipeline/EXTRACTION_PIPELINE.md` for operational details.
>>>>>>> Stashed changes

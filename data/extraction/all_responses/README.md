# All-Response Extraction Workspace

This directory is the response-wide extraction scaffold for the coral regeneration meta-analysis. It applies the same covariate schema across rate, growth, survival, and reproduction response rows.

## Rebuild

```bash
python3 tools/build_all_response_extraction_dataset.py
python3 tools/run_notebooklm_validation_batches.py --query-timeout 180 --process-timeout 260
python3 tools/audit_dataset_against_notebooklm.py
python3 tools/build_analysis_ready_dataset.py
```

The build reads every local primary-pool PDF with `pdftotext -layout` and caches the text under `pdf_text/`. The NotebookLM validation command queries the connected notebook in response-specific batches and saves raw JSON under `notebooklm_validation/`. The NotebookLM dataset audit checks the full local source-ID/value layer against the primary 267-source notebook registry.

The analysis-ready gate is written under `data/extraction/analysis_ready/`. Use `ANALYSIS_READY_OBSERVATIONS.csv` as the only modeling candidate table; rows in this all-response workspace are evidence targets and validation leads, not automatically poolable observations.

## Current Scope

- Primary response rows: 121
- Unique primary PDFs read: 76
- Response rows: rate = 57, growth = 30, survival = 27, reproduction = 7
- Covariate targets: 5,808
- PDF-text candidate snippets: 4,756
- NotebookLM validation batches: 13
- NotebookLM response-specific source checks: 121
- NotebookLM dataset source IDs checked: 128 local IDs, all present in the primary notebook
- NotebookLM value-support records checked: 5,261

## Files

- `ALL_RESPONSE_SOURCE_INDEX.csv`: one row per primary PDF, with response memberships and local PDF/text status.
- `ALL_RESPONSE_PDF_TEXT_AUDIT.csv`: PDF page counts, file hashes, text hashes, text paths, text lengths, and title-overlap checks.
- `ALL_RESPONSE_EXISTING_EXTRACTION_ROWS.csv`: normalized legacy/rate rows used as seeds and existing-value indicators.
- `ALL_RESPONSE_COVARIATE_TARGETS.csv`: one response-by-covariate target per schema field, with target status and verification flags.
- `ALL_RESPONSE_COVARIATE_CANDIDATES.csv`: PDF text snippets that point reviewers to possible covariate values.
- `NOTEBOOKLM_VALIDATION_BATCHES.csv`: the response-specific source batches and prompts.
- `NOTEBOOKLM_VALIDATION_RUN_LOG.csv`: status, timing, answer length, and source count for each NotebookLM batch.
- `NOTEBOOKLM_VALIDATION_SUMMARY.md`: compact NotebookLM validation summary.
- `NOTEBOOKLM_DATASET_AUDIT.csv`: source-ID coverage, `notebook_present` flag, duplicate-title, duplicate-row, and title-similarity checks across source-bearing dataset CSVs.
- `NOTEBOOKLM_VALUE_SUPPORT_AUDIT.csv`: direct raw-text support checks against NotebookLM source content for source-derived covariates and quantitative extraction values.
- `NOTEBOOKLM_DATASET_AUDIT_SUMMARY.md`: compact source and value-support audit summary.
- `notebooklm_validation/*.json`: raw NotebookLM answers and citations.

## Interpretation

Blank cells mean a value has not yet been extracted from that artifact. They do not mean zero, absence, or no biological effect.

Rows marked `pdf_text_candidate` are evidence leads from full-text regex search. They still need direct PDF/table/figure verification before they can become analysis-ready data.

Tier 3 taxon traits, including family, growth form, skeletal porosity, and perforate/imperforate status, should be joined from an external taxon-trait table after species names are cleaned. They are tracked here so the final moderator matrix is complete, but they should not be treated as paper-extracted free text.

`no_direct_text_match` in `NOTEBOOKLM_VALUE_SUPPORT_AUDIT.csv` is a triage flag. It means the exact local value was not found in NotebookLM's raw text export; it does not automatically invalidate figure-digitized values, normalized categories, or derived trait joins.

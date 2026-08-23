# Screening Audit Workflow

This note documents the rebuilt screening workflow for the coral regeneration meta-analysis library.

## Current Status

`data/screening/SCREENING_LOG_FINAL.csv` is now the source-of-truth screening and adjudication table. `data/screening/SCREENING_LOG_V2.csv` and `data/screening/SCREENING_REVIEW_QUEUE.csv` are retained as historical working artifacts from the rebuild.

For current PRISMA counts, extraction queues, literature organization checks, and figure digitization manifests, run:

```bash
python3 tools/build_pipeline_outputs.py
```

Then review `pipeline/PRISMA_COUNTS.md`, `pipeline/EXTRACTION_WORKPLAN.csv`, `pipeline/DIGITIZATION_FIGURE_QUEUE.csv`, and `pipeline/PIPELINE_QA_REPORT.md`.

## Why This Rebuild Was Needed

The existing `SCREENING_LOG.csv` and folder labels were not reliable enough to use as the project source of truth.

Problems found:

- The old CSV was malformed because filenames containing commas were not consistently quoted.
- Several papers were placed in folders that contradicted their actual status.
- Some prior NotebookLM audit batches duplicated the same paper with conflicting verdicts.
- Some exclusions were too aggressive because they were based on incomplete excerpts rather than full source text.

## Current Source-of-Truth Hierarchy

During the rebuild, use these in order:

1. Raw source text from NotebookLM-backed papers via `nlm content source <source_id>`.
2. Local PDF full text for papers not present in NotebookLM or when the notebook excerpts are incomplete.
3. NotebookLM audit verdicts only as a first-pass classification layer, not as the final answer by themselves.

After adjudication, use `data/screening/SCREENING_LOG_FINAL.csv` and the generated outputs described in `docs/pipeline/EXTRACTION_PIPELINE.md`.

## What The New Manifest Does

`data/screening/SCREENING_LOG_V2.csv` is built as one canonical row per paper across the union of:

- NotebookLM sources
- Local PDFs in `literature/**/*.pdf`
- Existing audit records from `docs/audit/FULL_LIBRARY_AUDIT.md`

It then assigns each paper to one of these buckets:

- `include_primary`: quantitative paper ready for response-variable extraction
- `include_primary_needs_fulltext`: quantitative paper kept, but figures/tables/full text are still needed
- `include_primary_conflicted`: at least one audit included the paper and another excluded it; needs adjudication
- `include_mechanism_only`: useful for mechanism/narrative sections, not currently a primary quantitative source
- `review_fulltext_needed`: potentially useful, but the current evidence is not enough to keep or exclude confidently
- `review_needed`: not adequately audited yet
- `exclude_scope`: outside the meta-analysis scope
- `exclude_review`: review/methods paper, not a primary-data study

## Current Generated Snapshot

From `pipeline/PRISMA_COUNTS.md` and `pipeline/PIPELINE_QA_REPORT.md` after final adjudication:

- 156 adjudicated full-text records
- 128 NotebookLM-covered records
- 152 local PDFs under `literature/`
- 76 primary quantitative records
- 20 mechanism-only records
- 20 primary records ready for table/text extraction
- 56 primary records needing figure/table digitization
- 0 primary records missing a local PDF
- 0 folder placements currently needing review

Final status counts:

- `duplicate_alias`: 6
- `exclude_review`: 8
- `exclude_scope`: 46
- `include_mechanism_only`: 20
- `include_primary`: 76

Response-variable coverage:

- `rate`: 57
- `growth`: 30
- `mechanism`: 32
- `survival`: 27
- `reproduction`: 7

## Current Implications

- Do not use the old `data/screening/SCREENING_LOG.csv` for screening decisions.
- Do not use folder placement by itself as screening truth.
- Treat `data/screening/SCREENING_LOG_V2.csv` and `data/screening/SCREENING_REVIEW_QUEUE.csv` as historical rebuild artifacts only.
- Use `pipeline/EXTRACTION_WORKPLAN.csv` for the current response-level extraction queue.
- Use `digitization/source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` and `digitization/figures/FIGURE_CROP_MANIFEST.csv` for current figure/table clipping and crop-review work.

## Current Recommended Next Step

After any screening edit, rebuild the generated outputs, then resolve digitization work in this order:

1. Re-check rows marked `no_valid_candidate_found` and record final extractability decisions.
2. Human-QA crop proposals before digitizing or transcribing values.
3. Run `python3 tools/audit_figure_indexing.py` after any crop or digitized-data path is promoted.
4. Fill legacy extraction provenance before pooling existing extraction rows.

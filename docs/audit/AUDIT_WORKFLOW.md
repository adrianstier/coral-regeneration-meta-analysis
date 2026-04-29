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

## Historical Snapshot

From the rebuilt manifest before final adjudication:

- 156 canonical paper records
- 128 NotebookLM sources
- 151 local PDFs
- 123 records matched across both NotebookLM and local PDFs
- 104 records already have at least one audit verdict
- 16 records still have conflicting audits

Bucket counts:

- `include_primary`: 16
- `include_primary_needs_fulltext`: 12
- `include_primary_conflicted`: 10
- `include_mechanism_only`: 10
- `review_fulltext_needed`: 43
- `review_needed`: 55
- `exclude_scope`: 7
- `exclude_review`: 3

Response-variable coverage among currently tagged candidates:

- `rate`: 54
- `growth`: 22
- `mechanism`: 13
- `survival`: 9
- `reproduction`: 6

## Historical Immediate Implications

- Do not use the old `data/screening/SCREENING_LOG.csv` for screening decisions.
- Do not trust current folder placement by itself.
- Use `data/screening/SCREENING_LOG_V2.csv` as the working manifest during manifest rebuilds only.
- Use `data/screening/SCREENING_REVIEW_QUEUE.csv` to prioritize manual adjudication during manifest rebuilds only.

Examples of papers currently misfiled in `META_ANALYSIS_POOL` but tagged as hard excludes:

- `Ayling - 1983 ... DEMOSPONGIAE ...`
- `Barton et al. - 2017 ... review ...`
- `Henry and Hart - 2005 ... Review`

Examples of papers currently sitting in excluded folders but still needing review:

- `Bruckner et al. - 2000 ...`
- `Fox et al. - 2019 ...`
- `Glynn et al. - 2025 ...`

## Historical Recommended Next Step

Work down `data/screening/SCREENING_REVIEW_QUEUE.csv` and adjudicate the papers in this order:

1. `include_primary_conflicted`
2. `include_primary_needs_fulltext`
3. `review_fulltext_needed`
4. `review_needed`

After that, extraction tables should be rebuilt from the cleaned manifest rather than from the current folder structure.

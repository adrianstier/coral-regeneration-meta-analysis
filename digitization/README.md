# Digitization Workspace

Use `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` as the generated manifest for figure and table extraction.
Use `digitization/source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` as the audited worklist for exact source figure/table choices before clipping.

## Directories

- `figures/` - clipped source panels or tables from PDFs.
- `data/` - digitized point data or table transcriptions.
- `source_review/` - generated review queues for candidate captions, audited candidate corrections, missing sources, and legacy extraction QA.

## Review Artifacts

Rebuild source-review artifacts after rebuilding `pipeline/`:

```bash
python3 tools/build_extraction_review_artifacts.py
python3 tools/merge_figure_candidate_audits.py
```

The first command writes:

- `source_review/FIGURE_SOURCE_REVIEW.csv` - candidate figure/table captions ranked for each digitization queue row.
- `source_review/SOURCE_RETRIEVAL_QUEUE.csv` - included primary sources that still lack local PDFs.
- `source_review/LEGACY_EXTRACTION_QA_QUEUE.csv` - existing extracted rows that still need source-level provenance review.
- `source_review/EXTRACTION_REVIEW_SUMMARY.md` - compact counts of blocked, review-needed, and provenance-missing rows.

After independent candidate review files are placed in `source_review/agent_audits/`, the merge command writes:

- `source_review/FIGURE_SOURCE_REVIEW_VALIDATED.csv` - every raw candidate row with audit status and corrected label/page fields.
- `source_review/FIGURE_CANDIDATE_AUDIT.csv` - normalized raw audit rows from each reviewer.
- `source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` - one row per digitization queue item with recommended audited candidates or `no_valid_candidate_found`.
- `source_review/FIGURE_CANDIDATE_AUDIT_SUMMARY.md` - coverage and status counts for the independent audit.

## Required Provenance

Every completed digitization task must record these fields in the queue:

- printed figure or table label
- PDF page
- panel label
- x-axis and y-axis labels
- units
- variance type
- sample-size source
- clip path
- digitized-data path
- digitizer
- QA reviewer
- QA status
- extraction notes

Do not use a figure-derived value in a pooled table until the queue row has a source clip and a digitized-data file.
Raw candidate captions are not source clips. They only identify pages and labels for manual clipping and verification.
Rows marked `no_valid_candidate_found` in the queue audit should not be clipped unless a later full-text review identifies valid non-caption evidence.

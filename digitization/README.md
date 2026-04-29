# Digitization Workspace

Use `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` as the generated manifest for figure and table extraction.
Use `digitization/source_review/FIGURE_SOURCE_REVIEW.csv` to choose the exact source figure/table before clipping.

## Directories

- `figures/` - clipped source panels or tables from PDFs.
- `data/` - digitized point data or table transcriptions.
- `source_review/` - generated review queues for candidate captions, missing sources, and legacy extraction QA.

## Review Artifacts

Rebuild source-review artifacts after rebuilding `pipeline/`:

```bash
python3 tools/build_extraction_review_artifacts.py
```

The command writes:

- `source_review/FIGURE_SOURCE_REVIEW.csv` - candidate figure/table captions ranked for each digitization queue row.
- `source_review/SOURCE_RETRIEVAL_QUEUE.csv` - included primary sources that still lack local PDFs.
- `source_review/LEGACY_EXTRACTION_QA_QUEUE.csv` - existing extracted rows that still need source-level provenance review.
- `source_review/EXTRACTION_REVIEW_SUMMARY.md` - compact counts of blocked, review-needed, and provenance-missing rows.

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
Candidate captions are not source clips. They only identify pages and labels for manual clipping and verification.

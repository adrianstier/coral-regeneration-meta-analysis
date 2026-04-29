# Pipeline QA Report

Generated from the current repository state by `tools/build_pipeline_outputs.py`.

## Status

| Final status | Count |
| --- | ---: |
| `duplicate_alias` | 6 |
| `exclude_review` | 8 |
| `exclude_scope` | 46 |
| `include_mechanism_only` | 20 |
| `include_primary` | 76 |

## Extraction Workplan

- Workplan rows: 139
- Digitization figure queue rows: 85

| Response | Count |
| --- | ---: |
| `growth` | 30 |
| `mechanism` | 20 |
| `rate` | 57 |
| `reproduction` | 6 |
| `survival` | 26 |

| Recommended action | Count |
| --- | ---: |
| `digitize_figures_or_graphs` | 83 |
| `extract_from_tables_or_text` | 34 |
| `mechanism_narrative` | 20 |
| `retrieve_local_pdf_before_extraction` | 2 |

Digitization status:

| Digitization status | Count |
| --- | ---: |
| `blocked_missing_local_pdf` | 2 |
| `needs_figure_id` | 83 |

## QA Warnings

- 1 included primary records are missing a local PDF.
- 2 extraction workplan rows are blocked by missing local PDFs.
- 2 digitization rows are blocked by missing local PDFs.
- 83 digitization rows still need exact figure/table labels before clipping.

## Folder Placements To Review

- None.

## Included Primary Sources To Retrieve

- `needs_digitization`: Coral-Damsel-Wounding-Manuscript.pdf

## Literature Reorganization

- Deleted flat tracked PDFs: 150
- Current PDFs under `literature/`: 151
- Hash-matched organized copies: 150
- Hash mismatches: 0
- Missing organized copies: 0

# PRISMA Counts

Generated from `data/screening/SCREENING_LOG_FINAL.csv` by `tools/build_pipeline_outputs.py`.

## Flow Summary

- Records in adjudicated full-text library: 156
- Duplicate aliases retained only for traceability: 6
- Full-text records excluded from the primary synthesis: 54
- Mechanism-only records retained for narrative synthesis: 20
- Primary quantitative records included in the meta-analysis pool: 76
- Primary records ready for table/text extraction: 20
- Primary records needing figure/table digitization: 56
- Primary records currently missing a local PDF: 1

## Final Status

| Final status | Count |
| --- | ---: |
| `duplicate_alias` | 6 |
| `exclude_review` | 8 |
| `exclude_scope` | 46 |
| `include_mechanism_only` | 20 |
| `include_primary` | 76 |

## Extraction Readiness

| Readiness | Count |
| --- | ---: |
| `needs_digitization` | 56 |
| `not_for_extraction` | 80 |
| `ready_extract` | 20 |

## Response Coverage

| Response | Count |
| --- | ---: |
| `growth` | 30 |
| `mechanism` | 32 |
| `rate` | 57 |
| `reproduction` | 6 |
| `survival` | 26 |

## Source Availability

NotebookLM coverage:

| NotebookLM status | Count |
| --- | ---: |
| `missing` | 28 |
| `present` | 128 |

Local PDF coverage:

| Local PDF status | Count |
| --- | ---: |
| `missing` | 5 |
| `present` | 151 |

Primary local PDF coverage:

| Primary local PDF status | Count |
| --- | ---: |
| `missing` | 1 |
| `present` | 75 |

## Literature Reorganization Check

- Deleted flat tracked PDFs reported by git: 150
- Current PDFs under `literature/`: 151
- Deleted flat PDFs matched to one organized filename: 150
- Exact blob hash matches among matched files: 150
- Hash mismatches: 0
- Missing organized copies: 0
- Duplicate organized filenames needing manual resolution: 0

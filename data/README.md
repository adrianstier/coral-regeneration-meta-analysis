# Data Directory

This directory holds hand-curated and extracted data inputs. Generated QA and work queues are written to `pipeline/`.

## Subdirectories

- `screening/`: final screening/adjudication tables plus historical screening logs.
- `extraction/`: quantitative extraction tables and tier-1 extraction templates.
- `literature/`: compact generated metadata maps for the local PDF library.

Use `data/screening/SCREENING_LOG_FINAL.csv` as the screening source of truth.
`data/literature/LITERATURE_MAP.csv` is rebuilt from that source by `python3 tools/build_pipeline_outputs.py`; do not use it as the adjudication source of truth.

# Analysis-Ready Extraction Gate

This directory is the fail-closed gate between extracted/candidate values and any statistical model.

## Rebuild

```bash
python3 tools/build_analysis_ready_dataset.py
python3 tools/build_model_covariates.py
python3 tools/build_meta_analysis_inputs.py
```

Run it after rebuilding the all-response extraction workspace, figure crop manifest, and NotebookLM validation outputs.

## Current Result

- Extracted observation rows audited: 92
- Analysis-ready rows: 0
- Primary response rows queued: 121
- Concrete reviewed digitized data files found: 0

This is the correct current status: the repository has candidate values, crop proposals, PDF-text evidence, and NotebookLM validation, but no row has yet passed the strict source-provenance and independent-QA gate.

## Files

- `ANALYSIS_READY_OBSERVATIONS.csv`: rows allowed to enter modeling. Currently empty except for headers.
- `ANALYSIS_READY_OBSERVATION_AUDIT.csv`: one row per extracted observation with pass/fail status, blockers, matched crop paths, and matched digitized-data paths.
- `ANALYSIS_READY_ISSUES.csv`: one issue per blocking or warning condition.
- `ANALYSIS_READY_BLOCKING_QUEUE.csv`: extracted rows that need provenance, digitization, or independent QC before pooling.
- `ANALYSIS_READY_RESPONSE_QUEUE.csv`: one row per primary source-response task with the next action needed.
- `ANALYSIS_READY_SUMMARY.md`: compact status and blocking-issue counts.
- `GET_TO_ANALYSIS_READY_PLAN.md`: staged work plan for moving rows through the gate.

## Gate Rules

The gate is deliberately conservative.

- Figure-derived values require exact figure/page evidence, a reviewed crop, a concrete final clip, a concrete digitized-data CSV, and independent QC.
- Table/text-derived values require exact table/text/page evidence and independent QC in the source extraction table.
- Survival rows can satisfy the variance requirement with raw dead/total counts because binomial variance can be derived.
- Placeholder paths such as `panel-<panel>.csv` are not concrete data files.
- `qa_status` must be `qc_passed`, `analysis_ready`, or `ready_for_analysis`.

No row should enter modeling until it appears in `ANALYSIS_READY_OBSERVATIONS.csv`.

Rows that pass this gate still need a computable effect size and sampling variance before modeling. That second check is handled in `data/extraction/meta_analysis/`.

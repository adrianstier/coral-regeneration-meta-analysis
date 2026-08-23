# Getting To Analysis-Ready Data

The current gate is doing the right thing: it marks zero rows as analysis-ready because extracted values still need source verification, crop/digitization, or independent QC. The path forward is to move rows through the gate in batches, starting with rows that need the least new work.

## Rebuild Loop

After every batch:

```bash
python3 tools/build_analysis_ready_dataset.py
python3 tools/build_meta_analysis_inputs.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

Do not edit files under `data/extraction/analysis_ready/` by hand. Update the source extraction tables, crop manifest, final clips, or digitized data files, then rebuild the gate.

## Batch 1: Verify Existing Table/Text Rate Rows

Start with the 10 rows whose only blocker is `qa_status_not_ready`. These should be fastest because they already have source label, page, sample size, variance, time interval, and rate/unit fields. They need direct PDF/table verification and then `qa_status=qc_passed` in `data/extraction/rate/RATE_EXTRACTED_OBSERVATIONS.csv`.

Sources:

- `348d7203-b68d-472c-89da-e3e6704b2f50`: 3 rows, Table 1, page 4, *Acropora palmata*, reported exponential slopes.
- `3a3fb59c-a303-49f1-aa80-21ffe7d182cf`: 5 rows, Table I, page 7, *Acropora palmata*, interval linear/areal recovery rates.
- `6b96575e-9bf7-46f2-a12e-73b565f46629`: 2 rows, Table 1, page 5, *Porites astreoides*, mean tissue regeneration rates.

For each row, verify:

- source PDF and page match the row;
- figure/table label is exact;
- taxon, treatment, rate value, units, variance, sample size, and interval match the source;
- the calculation note is faithful;
- no row is a duplicate treatment/timepoint unless it is intentionally a distinct effect.

Expected payoff: up to 10 analysis-ready rate rows without new digitization.

## Batch 2: Fill Sample Sizes For Existing Rate Rows

Next, address rows blocked by `sample_size_missing|qa_status_not_ready`, especially the `6a14a9e9` block. These already have extraction structure but need sample-size evidence from the PDF.

For each row:

- read the source table/figure caption and Methods for sample size;
- record whether `n` is colonies, lesions, fragments, or repeated measurements;
- avoid filling a pooled or per-treatment sample size unless the paper says which it is;
- update `sample_size` in the source extraction table only after evidence is explicit;
- then run independent QC.

## Batch 3: Fix Legacy Rows With Missing Provenance

Legacy rows in `data/extraction/EXTRACTION_RATES.csv`, `EXTRACTION_FITNESS.csv`, and `EXTRACTION_SURVIVAL.csv` have values but missing source provenance. These cannot be trusted until exact labels/pages are recorded.

For each row:

- find the exact source table, figure, or text passage;
- fill `figure_or_table_label`, `page`, `panel_label` where relevant, and `extraction_provenance`;
- fill missing time or duration fields for rate/growth/survival rows;
- verify variance/sample-size conventions;
- set `qa_status=qc_passed` only after an independent check.

Expected payoff: 29 legacy rows can move from provenance-blocked to QC-ready or analysis-ready.

## Batch 4: Crop QA And Digitize Existing Figure Proposals

There are 168 crop proposals with `crop_review_status=needs_human_crop_box_qa` and no concrete digitized data files. This is the largest block.

For each source-response:

- inspect the source-page PNG and crop proposal;
- adjust or accept the crop box;
- replace placeholder paths like `panel-<panel>.csv` with concrete panel labels;
- create a final clip under `digitization/figures/`;
- digitize points or transcribe the table under `digitization/data/`;
- record axes, units, variance type, sample-size source, digitizer, QA reviewer, and QA status;
- extract rows from the digitized data into the source extraction table;
- rebuild the analysis-ready gate.

Expected payoff: 63 source-response tasks can move from crop proposal to extracted rows.

## Batch 5: Extract From PDF Text Candidates

The remaining 23 source-response tasks have no extracted rows and no crop proposals but do have PDF text candidates and NotebookLM validation. These need direct PDF reading and extraction.

For each source-response:

- review `ALL_RESPONSE_COVARIATE_CANDIDATES.csv` for that source/response;
- read the cached PDF text and rendered pages around candidate evidence;
- decide whether the response is extractable from text/table, requires a new figure crop, or should be marked not extractable;
- write source-verified rows into the appropriate extraction table;
- rebuild the gate.

## Stopping Rule

A row can enter modeling only when it appears in:

```text
data/extraction/meta_analysis/META_ANALYSIS_INPUTS.csv
```

Rows in NotebookLM output, crop proposals, provisional rate observations, legacy extraction tables, or `ANALYSIS_READY_OBSERVATIONS.csv` are not `metafor` inputs until they also have a computable effect size (`yi`) and sampling variance (`vi`) in `META_ANALYSIS_INPUTS.csv`.

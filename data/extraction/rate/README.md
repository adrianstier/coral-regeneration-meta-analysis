# Rate Extraction Workspace

This directory contains the rate-specific extraction layer for the coral regeneration meta-analysis.

Regenerate the files with:

```bash
python3 tools/build_rate_extraction_dataset.py
python3 tools/audit_rate_extraction_dataset.py
python3 tools/audit_trait_covariate_coverage.py
```

## Files

- `RATE_SOURCE_INDEX.csv` - one row for each of the 57 primary papers flagged for a regeneration-rate response.
- `RATE_TEXT_EVIDENCE.csv` - ranked full-text snippets from each PDF that mention wound size, lesion recovery, time to healing, or reported rates.
- `RATE_EXTRACTED_OBSERVATIONS.csv` - curated provisional observations extracted from printed prose and tables.
- `RATE_EFFECT_SIZE_SEEDS.csv` - legacy and pilot numeric values carried forward as seeds only.
- `RATE_SOURCE_REVIEW_OVERRIDES.csv` - explicit source-level review decisions that override generated routing.
- `RATE_EXTRACTION_SUMMARY.md` - generated counts and route summary.
- `RATE_EXTRACTION_AUDIT.csv` - generated pass/fail rows for structural, join, provenance, and readiness checks.
- `RATE_EXTRACTION_AUDIT_SUMMARY.md` - generated audit summary.
- `../../../notebook_covariates/TRAIT_COVARIATE_COVERAGE.md` - generated audit of source-linked trait/taxonomy coverage, including the current absence of model-ready family and skeletal-porosity fields.

## QA Rules

Rows in `RATE_EFFECT_SIZE_SEEDS.csv` are not analysis-ready unless `analysis_ready=1`.

Rows in `RATE_EXTRACTED_OBSERVATIONS.csv` are also provisional until independent QC; this file is intentionally closer to raw paper observations than to a pooled effect-size table.

Blank cells in this directory mean "not populated for this raw observation yet" unless an explicit status field says otherwise. They do not mean zero. Use explicit values such as `not_reported`, `not_applicable`, or a note in `calculation_notes` when that distinction matters for analysis.

Raw printed values are preserved as strings when a paper reports fractions, ranges, categorical endpoints, or units that are not yet harmonized. Examples include `13/14`, `4-5`, `0.170-0.267`, and `complete`. Downstream analysis tables must create separate normalized numeric columns rather than overwriting these raw fields.

Seed rows from `EXTRACTION_RATES.csv` and `TIER1_EXTRACTION_PILOT.csv` remain provisional until the exact figure, table, or text page is recorded along with units, variance, and sample-size evidence.

Figure-derived rows remain provisional until the digitization workspace has a checked source clip, panel label, axis units, variance/sample-size status, and `digitized_data_path`.

## Rate Derivation Categories

Use these categories when adding reviewed rows:

- `reported_areal_rate` - paper reports an area-normalized wound closure rate.
- `reported_linear_rate` - paper reports linear tissue-front advance.
- `reported_proportional_rate` - paper reports percent or proportional closure per time.
- `reported_exponential_slope` - paper reports a fitted decay slope or rate constant.
- `initial_final_wound_size` - rate is derived from initial and final wound size over a known interval.
- `time_series_wound_size` - rate is derived from repeated wound-size observations.
- `time_to_closure` - paper reports days or months until wound closure.

Do not collapse these into one effect-size scale until the conversion rule is explicit.

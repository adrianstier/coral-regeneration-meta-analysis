# Gemini Instructions

You are an AI assistant helping with the Coral Regeneration Meta-Analysis project. Adhere to the following guidelines:

- **Use the current source of truth:** Screening/adjudication decisions live in `data/screening/SCREENING_LOG_FINAL.csv`. Do not use folder placement, `SCREENING_LOG.csv`, `SCREENING_LOG_V2.csv`, or `SCREENING_REVIEW_QUEUE.csv` as current adjudication truth.
- **Preserve provenance:** Every extracted outcome must retain `source_id`, `paper_title`, `local_relpath`, response type, figure/table label, page, panel, units, variance type, sample-size source, extraction notes, and QA status.
- **Respect the coordinate layers:** `latitude`/`longitude` are reported-exact coordinates only. Approximate or inferred locations belong in `latitude_approx`/`longitude_approx`; analysis-ready mapping should use `latitude_best`/`longitude_best`.
- **Rebuild generated outputs:** After changing screening, extraction, covariate, literature, or digitization inputs, run the documented rebuild chain in `README.md` and review the generated QA summaries before using counts or extracted values.
- **Run the figure index gate:** After rebuilding figure/table source pages and crop proposals, run `python3 tools/audit_figure_indexing.py`. Do not pool figure-derived values unless the audit has zero structural errors and each warning has an explicit extraction decision.
- **Run the rate extraction gate:** After changing rate extraction inputs, run `python3 tools/build_rate_extraction_dataset.py` and `python3 tools/audit_rate_extraction_dataset.py`. Do not pool rate rows unless `RATE_EXTRACTION_AUDIT_SUMMARY.md` reports zero errors and the relevant rows have independent QC/provenance signoff.
- **Do not pool legacy rows prematurely:** Existing extraction rows marked `needs_source_provenance_review` remain review-only until figure/table provenance and QA reviewer signoff are complete.
- **Analysis stage is pending:** No effect-size, `metafor`, `brms`, forest-plot, funnel-plot, or manuscript pipeline exists yet. Add `renv` and analysis documentation when that stage starts.

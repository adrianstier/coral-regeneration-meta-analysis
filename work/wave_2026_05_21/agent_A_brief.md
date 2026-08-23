# Agent A — Legacy extraction provenance fill (§4)

## Context

This is a PRISMA-style coral regeneration meta-analysis at `/Users/adrianstier/coral-regeneration-meta-analysis/`. Twenty-nine "legacy" extracted data rows (rates, fitness, survival) live in `data/extraction/EXTRACTION_RATES.csv`, `EXTRACTION_FITNESS.csv`, `EXTRACTION_SURVIVAL.csv`. Each row has a numeric value (e.g., a healing rate) and a source PDF, but is missing `figure_or_table_label`, `page`, and `panel_label`. Until those are filled, the values cannot enter the pooled meta-analysis. All rows are currently marked `qa_status=needs_source_provenance_review`.

## Your assignment

For each of the 29 rows in `work/wave_2026_05_21/agent_A_input.csv`, open the local PDF at `local_relpath` (path is relative to the project root, e.g., `literature/META_ANALYSIS_POOL/Bak - 1983 - ...pdf`) and find which exact figure or table the extracted numeric value came from. Then fill:

- `figure_or_table_label` — e.g., `Fig. 4`, `Fig. 4a`, `Table 2`, `Table 3 (Col. 3)`. Match the printed label exactly.
- `page` — printed PDF page where the figure/table appears (1-indexed, matches `pdftotext` page numbers).
- `panel_label` — `A`, `B`, `top-left`, or empty if no panel.
- `axes_units` — units shown on the figure axis or table column (e.g., `mm²/day`, `% per day`, `day⁻¹`).
- `variance_source` — exact phrasing in the paper, e.g., `Mean ± SE (Fig. 4 error bars)`, `SD reported in Table 2 caption`.
- `sample_size_source` — where N comes from, e.g., `n=8 colonies, Methods §2.3`, `n=12, Table 2 footnote`.
- `provenance_notes` — anything unusual: digitized from a panel, computed from reported summary, etc.
- `qa_status` — set to `provenance_filled` if you successfully fill the above 6 fields; `needs_alternative_source` if the value cannot be located in the cited PDF and probably came from a different paper or panel; `flag_for_PI` if there's a discrepancy worth flagging.

## How to extract

- Use `pdftotext -layout literature/META_ANALYSIS_POOL/<file>.pdf /tmp/x.txt` to skim text and find candidate figures/tables.
- For figures, render the page with `pdftoppm -r 180 -f <page> -l <page> <pdf> /tmp/page -png` and look at the image (use the Read tool on the PNG).
- The value in the row (`Rate_Value`, `Control_Mean`/`Wounded_Mean`, or `Control_Dead`/`Wounded_Dead`) tells you what to look for. Cross-check that the units (`Rate_Unit`, `Var_Type`) match.
- For the Bak 1983 rate of `-0.048 d⁻¹` for Acropora palmata @ 100 mm² wound, that's an exponential decay rate constant — look for Fig./Table reporting healing rate constants.

## Output

Write your filled CSV to `work/wave_2026_05_21/outputs/A/legacy_provenance.csv` with the same columns as the input plus the new `figure_or_table_label`, `page`, `panel_label`, `axes_units`, `variance_source`, `sample_size_source`, `provenance_notes`, `qa_status` fields. Also write `work/wave_2026_05_21/outputs/A/REPORT.md` with:

- Total rows attempted / filled / flagged.
- A table of any flagged rows with the reason.
- Spot-checks: 3 rows where you describe exactly which figure / page / panel you saw.

## Constraints

- Do NOT modify any file outside `work/wave_2026_05_21/outputs/A/`.
- Do NOT invent provenance — if you cannot find the value in the PDF, mark `qa_status=needs_alternative_source` and explain.
- Quote a short snippet of the figure caption in `provenance_notes` so I can verify.

## Working directory

`/Users/adrianstier/coral-regeneration-meta-analysis/`

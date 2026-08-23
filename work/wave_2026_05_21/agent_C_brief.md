# Agent C — Wound geometry covariate fill, primary batch 1 (§5a)

## Context

Coral regeneration meta-analysis at `/Users/adrianstier/coral-regeneration-meta-analysis/`. Historical note, updated 2026-08-03: this worker brief was dispatched against an older 77-primary-row covariate table. The current primary pool has 76 rows after Cox 2014 was reclassified to `exclude_review`. In the current geoaugmented table, `perimeter_mm` is filled for 3/76 primary rows and `rel_wound_size` for 21/76. The geometry/P:A moderator remains the most data-starved hypothesis.

## Your assignment

For each of the ~26 primary papers in `work/wave_2026_05_21/agent_C_input.csv` (use the `local_relpath` column to find the PDF), extract or impute these fields by reading the Methods + Results + figure captions:

- `area_mm2` — initial wound area in mm². Read from Methods or figure axes.
- `perimeter_mm` — initial wound perimeter in mm. If not reported, compute from area + shape assumption (circle: P = 2√(πA); square: P = 4√A; rectangle: from L × W) and prefix with `est:` (e.g., `est:35.4`).
- `rel_wound_size` — wound area divided by colony surface area or projected area, if both are reported.
- `colony_size_cm` — colony diameter or longest dimension in cm.
- `lesion_type` — one of `tissue_only`, `tissue_and_skeleton`, `fragmentation`, `corallivore_natural`, `corallivore_experimental`, `other`.
- `lesion_method` — `airbrush`, `waterpik`, `bone_cutter`, `drill`, `scalpel`, `forceps`, `natural`, `other` (specify).
- `lesion_depth` — `surface`, `partial_thickness`, `full_thickness` (through to skeleton), or `unknown`.
- `num_lesions` — number of wounds per colony.
- `lesion_position` — `apical`, `subapical`, `distal`, `basal`, `lateral`, `random`, `not_reported`.
- `geometry_imputation_method` — for each row, briefly state: `reported_directly` | `circle_assumption_from_area` | `square_assumption_from_area` | `rectangle_from_L_W` | `digitized_from_figure` | `not_available`.
- `confidence` — `high` (reported directly with units), `medium` (computed from reported values + standard shape), `low` (digitized or imputed loosely), `na` (cannot determine).

## How to extract

- `pdftotext -layout` the PDF, then search the Methods section for wound dimensions.
- For papers that show wound photos with a scale bar, render the figure with `pdftoppm` and digitize the wound area using pixel measurement (it's OK to approximate).
- If the paper reports lesion area in cm², convert: 1 cm² = 100 mm².
- If only initial wound *diameter* is given (assume circular wound): area = π × (d/2)², perimeter = π × d.

## Output

`work/wave_2026_05_21/outputs/C/geometry_batch_1.csv` with these columns:
`source_id, paper_title, area_mm2, perimeter_mm, rel_wound_size, colony_size_cm, lesion_type, lesion_method, lesion_depth, num_lesions, lesion_position, geometry_imputation_method, confidence, notes`.

Plus `work/wave_2026_05_21/outputs/C/REPORT.md` summarizing: how many papers had perimeter reported directly vs imputed, any oddball wound geometries, and any papers where you flagged the row as `not_available`.

## Constraints

- Do NOT modify any file outside `work/wave_2026_05_21/outputs/C/`.
- When computing perimeter from area, ALWAYS prefix with `est:` so I can identify imputed values in downstream sensitivity analyses.
- Be honest about confidence — if a paper says "small lesions" without dimensions, mark `not_available` and confidence `na`.
- Don't try to fill environmental fields (temperature, pH, nutrients) — that's a different agent's job.

## Working directory

`/Users/adrianstier/coral-regeneration-meta-analysis/`

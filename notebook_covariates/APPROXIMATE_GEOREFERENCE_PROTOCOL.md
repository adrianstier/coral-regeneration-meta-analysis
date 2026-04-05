# Approximate Georeference Protocol

## Goal
Add an approximate coordinate layer for study sites when papers do not report exact latitude/longitude, while preserving the existing reported-exact coordinate layer.

## Core Rule
- `latitude` and `longitude` remain the reported-exact coordinate fields.
- Approximate or inferred site coordinates must **not** overwrite reported-exact coordinates.
- Approximate coordinates belong in:
  - `latitude_approx`
  - `longitude_approx`
  - `approx_coordinate_basis`
  - `approx_coordinate_confidence`
  - `approx_location_notes`
- `latitude_best` and `longitude_best` are derived:
  - use exact reported coordinates when present
  - otherwise use approximate coordinates

## Acceptable Approximate Bases
- `site_facility_centroid`
- `reef_centroid`
- `bay_centroid`
- `island_centroid`
- `town_or_lab_centroid`
- `coast_or_region_centroid`
- `study_extent_midpoint`

## Confidence Labels
- `high`: a named site, reef, station, laboratory, caye, or bay could be tied to a specific place confidently
- `medium`: locality is somewhat broader, but still reasonably constrained to a known island, coast, bay, or reef system
- `low`: only a broad region or multi-site extent could be identified

## Agent Rules
- Use the paper methods/locality description first.
- Use NotebookLM or local PDF text to confirm the site wording before georeferencing.
- If exact coordinates are reported in the paper, do not place them in the approximate fields.
- If the paper already has non-exact coordinates mixed into the old exact columns, treat those as approximate and preserve the distinction in the final merge.
- If a study spans multiple distant sites and no single site dominates, use a centroid or midpoint only if it is still interpretable, and mark confidence `low`.
- If a single approximate point would be misleading, leave approximate coordinates blank and explain why.

## Secondary Exact Repairs
While reviewing the methods/locality section, agents may also fill remaining exact paper-level fields if explicitly recoverable:
- `depth_min_m`
- `depth_max_m`
- `growth_form`
- `tissue_type`
- `area_mm2`
- `temperature_c`
- `sample_size`

## Deliverables
- One agent repair CSV per worker queue
- One worker summary Markdown file per queue
- A merged location manifest with separate exact, approximate, and best coordinate fields
- A refreshed remaining-issue queue and summary

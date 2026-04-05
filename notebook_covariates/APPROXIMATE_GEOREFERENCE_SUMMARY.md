# Approximate Georeference Summary

## Scope
- georeference target rows reviewed: 59
- rows with approximate coordinate pairs after broadened merge: 53
- rows still lacking best coordinates after broadened merge: 2

## Location Coverage
- exact coordinate pairs: 70/134
- approximate coordinate pairs: 53/134
- best coordinate pairs: 123/134

## Primary Study Coverage
- exact coordinate pairs: 44/77
- approximate coordinate pairs: 32/77
- best coordinate pairs: 75/77
- depth coverage: 65/77
- growth form coverage: 75/77
- tissue type coverage: 74/77
- area coverage: 53/77
- temperature coverage: 34/77
- sample size coverage: 76/77

## Remaining Exact Missingness In Primary Rows
- `missing_location_raw`: 1
- `missing_exact_coords_latlon`: 33
- `missing_best_coords_latlon`: 2
- `missing_depth`: 12
- `missing_growth_form`: 2
- `missing_tissue_type`: 3
- `missing_area_mm2`: 24
- `missing_temperature_c`: 43
- `missing_sample_size`: 1

## Rows Still Missing Best Coordinates
- location rows with locality text but no best coordinates: 2
- `loc_072` Soong and Lang - 1992 - Reproductive Integration in Reef Corals.pdf: Caribbean coast of Panama
- `loc_087` Bruckner et al. - 2000 - Parrotfish predation on live coral “spot biting” and “focused biting”.pdf: western Atlantic

## Notes
- Existing mixed-quality coordinates were either promoted to exact when a worker confirmed they were reported in the paper, or moved into the approximate layer otherwise.
- Best coordinates are exact when available; otherwise they use the approximate layer.
- This broadened pass accepts town, island, facility, and broad study-extent proxies when that is the best defensible locality representation available.

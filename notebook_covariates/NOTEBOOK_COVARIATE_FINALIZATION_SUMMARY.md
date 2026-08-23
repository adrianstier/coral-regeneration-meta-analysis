# Notebook Covariate Finalization Summary

This file summarizes the current tracked covariate state after the worker-repair and approximate-georeference passes. Earlier pre-georeference outputs named `*_final.csv` have been superseded by the `*_geoaugmented.csv` files.

## Scope

- Current primary rows: 76
- Current all-source NotebookLM rows: 128
- Location-manifest rows: 134
- Worker rows with actual merged changes in the pre-georeference repair pass: 5

## Worker Merge Gains

- `latitude_raw`: +1
- `longitude_raw`: +1
- `latitude`: +1
- `longitude`: +1
- `depth_min_m`: +1
- `depth_max_m`: +1
- `growth_form`: +1
- `area_mm2`: +2
- `temperature_c`: +1

## Current Primary Coverage

- `location_raw`: 76/76
- exact coordinate pairs: 44/76
- approximate coordinate pairs: 32/76
- best coordinate pairs: 75/76
- depth: 65/76
- `growth_form`: 74/76
- `tissue_type`: 74/76
- `area_mm2`: 53/76
- `temperature_c`: 34/76
- `sample_size`: 76/76

## Current Primary Missingness

- `missing_location_raw`: 0
- `missing_exact_coords_latlon`: 32
- `missing_best_coords_latlon`: 1
- `missing_depth`: 11
- `missing_growth_form`: 2
- `missing_tissue_type`: 2
- `missing_area_mm2`: 23
- `missing_temperature_c`: 42
- `missing_sample_size`: 0

## Location Manifest

- rows: 134
- with locality text: 125/134
- with exact coordinate pairs: 70/134
- with approximate coordinate pairs: 53/134
- with best coordinate pairs: 123/134
- with depth: 93/134
- `reported_exact`: 70
- `reported_site_name`: 53
- `not_yet_resolved`: 11

## Worker Contribution Detail

- `agent_worker_1_33d2bc0d`: 1 rows changed
- `agent_worker_1_f7335f31`: 1 rows changed
- `agent_worker_2_3764e810`: 1 rows changed
- `agent_worker_3_58b15640`: 1 rows changed
- `agent_worker_3_daec544d`: 1 rows changed

## Current Files

- `notebook_covariates_primary_geoaugmented.csv`
- `notebook_covariates_all_sources_geoaugmented.csv`
- `notebook_covariate_missingness_primary_geoaugmented.csv`
- `notebook_covariate_remaining_queue_primary_geoaugmented.csv`
- `study_location_metadata_geoaugmented.csv`
- `study_location_geoapprox_remaining_queue.csv`
- `agent_worker_merge_audit.csv`
- `approx_georef/approx_georef_merge_audit.csv`

## Notes

- Cox 2014 has already been reclassified out of the primary pool upstream, so it is no longer a current primary-covariate missingness driver.
- The remaining primary missingness is dominated by true nonreporting, especially exact coordinates, single study-level temperatures, and lesion geometry.

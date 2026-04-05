# Notebook Covariate Finalization Summary

## Scope
- Base repaired primary rows: 77
- Final primary rows: 77
- Worker rows with actual merged changes: 5

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

## Missingness Before -> After
- `missing_location_raw`: 1 -> 1 (resolved 0)
- `missing_coords_latlon`: 34 -> 33 (resolved 1)
- `missing_depth`: 14 -> 13 (resolved 1)
- `missing_growth_form`: 3 -> 2 (resolved 1)
- `missing_tissue_type`: 3 -> 3 (resolved 0)
- `missing_area_mm2`: 27 -> 25 (resolved 2)
- `missing_temperature_c`: 44 -> 43 (resolved 1)
- `missing_sample_size`: 1 -> 1 (resolved 0)

## Final Primary Coverage
- `location_raw`: 76/77
- decimal coordinate pairs: 44/77
- depth: 64/77
- `growth_form`: 75/77
- `tissue_type`: 74/77
- `area_mm2`: 52/77
- `temperature_c`: 34/77
- `sample_size`: 76/77

## Location Manifest
- rows: 134
- with locality text: 125/134
- with coordinate pairs: 71/134
- with depth: 93/134
- `reported_exact`: 66
- `reported_site_name`: 54
- `not_yet_resolved`: 14

## Worker Contribution Detail
- `agent_worker_1_33d2bc0d`: 1 rows changed
- `agent_worker_1_f7335f31`: 1 rows changed
- `agent_worker_2_3764e810`: 1 rows changed
- `agent_worker_3_58b15640`: 1 rows changed
- `agent_worker_3_daec544d`: 1 rows changed

## Remaining Queue
- remaining primary rows with at least one unresolved tracked field: 62
- The remaining queue is dominated by true nonreporting, especially exact coordinates, single study-level temperatures, and lesion areas.
- `Cox - 2014 - Corallivory The Coral’s Point of View.pdf` remains in the queue only because it is still mislabeled as primary upstream.

## Files
- `notebook_covariates_primary_final.csv`
- `notebook_covariates_all_sources_final.csv`
- `notebook_covariate_missingness_primary_final.csv`
- `notebook_covariate_remaining_queue_primary_final.csv`
- `study_location_metadata_enriched_final.csv`
- `agent_worker_merge_audit.csv`

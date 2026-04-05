# Notebook Covariate Summary

## Coverage
- total notebook sources queried: 128
- parsed rows: 128 (100.0%)
- include_primary rows: 77
- include_primary parsed rows: 77 (100.0%)

## Status Counts
- `parsed`: 128

## Final Status Counts
- `duplicate_alias`: 2
- `exclude_review`: 6
- `exclude_scope`: 23
- `include_mechanism_only`: 20
- `include_primary`: 77

## Field Coverage Across Parsed Rows
- `study_type`: 128/128 (100.0%)
- `study_year`: 91/128 (71.1%)
- `location_raw`: 119/128 (93.0%)
- `latitude`: 65/128 (50.8%)
- `longitude`: 65/128 (50.8%)
- `depth_min_m`: 86/128 (67.2%)
- `depth_max_m`: 87/128 (68.0%)
- `species`: 126/128 (98.4%)
- `growth_form`: 111/128 (86.7%)
- `tissue_type`: 113/128 (88.3%)
- `colony_size_cm`: 73/128 (57.0%)
- `symbiont_status`: 53/128 (41.4%)
- `lesion_source`: 118/128 (92.2%)
- `lesion_method`: 115/128 (89.8%)
- `lesion_type`: 118/128 (92.2%)
- `area_mm2`: 68/128 (53.1%)
- `rel_wound_size`: 29/128 (22.7%)
- `perimeter_mm`: 4/128 (3.1%)
- `lesion_depth`: 51/128 (39.8%)
- `num_lesions`: 80/128 (62.5%)
- `lesion_position`: 87/128 (68.0%)
- `temperature_c`: 55/128 (43.0%)
- `temp_manip`: 17/128 (13.3%)
- `ph_or_pco2`: 11/128 (8.6%)
- `nutrient_enrich`: 18/128 (14.1%)
- `light_par`: 26/128 (20.3%)
- `light_regime`: 39/128 (30.5%)
- `sedimentation`: 4/128 (3.1%)
- `flow_regime`: 47/128 (36.7%)
- `sample_size`: 112/128 (87.5%)
- `replication_level`: 118/128 (92.2%)
- `randomization`: 63/128 (49.2%)
- `blocking`: 23/128 (18.0%)
- `control_description`: 87/128 (68.0%)

## Field Coverage Across Parsed Primary Rows
- `study_type`: 77/77 (100.0%)
- `study_year`: 65/77 (84.4%)
- `location_raw`: 76/77 (98.7%)
- `latitude`: 44/77 (57.1%)
- `longitude`: 44/77 (57.1%)
- `depth_min_m`: 64/77 (83.1%)
- `depth_max_m`: 64/77 (83.1%)
- `species`: 77/77 (100.0%)
- `growth_form`: 75/77 (97.4%)
- `tissue_type`: 74/77 (96.1%)
- `colony_size_cm`: 50/77 (64.9%)
- `symbiont_status`: 25/77 (32.5%)
- `lesion_source`: 76/77 (98.7%)
- `lesion_method`: 74/77 (96.1%)
- `lesion_type`: 76/77 (98.7%)
- `area_mm2`: 52/77 (67.5%)
- `rel_wound_size`: 21/77 (27.3%)
- `perimeter_mm`: 3/77 (3.9%)
- `lesion_depth`: 37/77 (48.1%)
- `num_lesions`: 57/77 (74.0%)
- `lesion_position`: 61/77 (79.2%)
- `temperature_c`: 34/77 (44.2%)
- `temp_manip`: 10/77 (13.0%)
- `ph_or_pco2`: 5/77 (6.5%)
- `nutrient_enrich`: 10/77 (13.0%)
- `light_par`: 17/77 (22.1%)
- `light_regime`: 18/77 (23.4%)
- `sedimentation`: 4/77 (5.2%)
- `flow_regime`: 25/77 (32.5%)
- `sample_size`: 76/77 (98.7%)
- `replication_level`: 76/77 (98.7%)
- `randomization`: 46/77 (59.7%)
- `blocking`: 17/77 (22.1%)
- `control_description`: 53/77 (68.8%)

## Location Resolution
- parsed rows with decimal coordinates: 65/128 (50.8%)
- parsed rows with any depth information: 87/128 (68.0%)

## Notes
- NotebookLM covariates are a structured screening and moderator layer, not a substitute for paper-level numeric outcome extraction.
- Excluded and review papers remain in this table because the user requested a full-notebook covariate pass.

# Notebook Covariate Summary

This summary reflects the current geoaugmented covariate files:

- `notebook_covariates_all_sources_geoaugmented.csv`
- `notebook_covariates_primary_geoaugmented.csv`
- `study_location_metadata_geoaugmented.csv`

Earlier `_final.csv` outputs were pre-georeference intermediates and should not be used as the current covariate layer.

## Coverage

- total NotebookLM sources parsed: 128
- parsed rows: 128 (100.0%)
- current `include_primary` rows: 76
- current `include_primary` parsed rows: 76 (100.0%)

## Final Status Counts

- `duplicate_alias`: 2
- `exclude_review`: 7
- `exclude_scope`: 23
- `include_mechanism_only`: 20
- `include_primary`: 76

These counts are for the 128 NotebookLM-covered sources only. Full project-level screening counts live in `pipeline/PRISMA_COUNTS.md`.

## Field Coverage Across Parsed Rows

- `study_type`: 128/128 (100.0%)
- `study_year`: 91/128 (71.1%)
- `location_raw`: 119/128 (93.0%)
- exact coordinate pairs: 65/128 (50.8%)
- approximate coordinate pairs: 53/128 (41.4%)
- best coordinate pairs: 117/128 (91.4%)
- depth: 88/128 (68.8%)
- `species`: 126/128 (98.4%)
- `growth_form`: 111/128 (86.7%)
- `tissue_type`: 113/128 (88.3%)
- `colony_size_cm`: 73/128 (57.0%)
- `symbiont_status`: 53/128 (41.4%)
- `lesion_source`: 118/128 (92.2%)
- `lesion_method`: 115/128 (89.8%)
- `lesion_type`: 118/128 (92.2%)
- `area_mm2`: 69/128 (53.9%)
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

- `study_type`: 76/76 (100.0%)
- `study_year`: 65/76 (85.5%)
- `location_raw`: 76/76 (100.0%)
- exact coordinate pairs: 44/76 (57.9%)
- approximate coordinate pairs: 32/76 (42.1%)
- best coordinate pairs: 75/76 (98.7%)
- depth: 65/76 (85.5%)
- `species`: 76/76 (100.0%)
- `growth_form`: 74/76 (97.4%)
- `tissue_type`: 74/76 (97.4%)
- `colony_size_cm`: 50/76 (65.8%)
- `symbiont_status`: 25/76 (32.9%)
- `lesion_source`: 76/76 (100.0%)
- `lesion_method`: 74/76 (97.4%)
- `lesion_type`: 76/76 (100.0%)
- `area_mm2`: 53/76 (69.7%)
- `rel_wound_size`: 21/76 (27.6%)
- `perimeter_mm`: 3/76 (3.9%)
- `lesion_depth`: 37/76 (48.7%)
- `num_lesions`: 57/76 (75.0%)
- `lesion_position`: 61/76 (80.3%)
- `temperature_c`: 34/76 (44.7%)
- `temp_manip`: 10/76 (13.2%)
- `ph_or_pco2`: 5/76 (6.6%)
- `nutrient_enrich`: 10/76 (13.2%)
- `light_par`: 17/76 (22.4%)
- `light_regime`: 18/76 (23.7%)
- `sedimentation`: 4/76 (5.3%)
- `flow_regime`: 25/76 (32.9%)
- `sample_size`: 76/76 (100.0%)
- `replication_level`: 76/76 (100.0%)
- `randomization`: 46/76 (60.5%)
- `blocking`: 17/76 (22.4%)
- `control_description`: 53/76 (69.7%)

## Notes

- NotebookLM covariates are a structured screening and moderator layer, not a substitute for paper-level numeric outcome extraction.
- Excluded and review papers remain in the all-source table because the covariate pass covered the full NotebookLM source set.
- Use `latitude`/`longitude` only for reported-exact coordinates. Use `latitude_best`/`longitude_best` for mapping or coarse geographic moderators where approximate site centroids are acceptable.
- Taxonomic and skeletal-architecture moderators are not fully model-ready in this table: `species`, `growth_form`, and a heterogeneous `tissue_type` field are present, but `genus`, `family`, `skeletal_porosity`, and clean `perforate`/`imperforate` status fields are not part of the current schema.
- The next covariate pass should follow `COVARIATE_EXTRACTION_STRATEGY.md`: keep study context source-level, move wound/treatment metadata to treatment or observation rows, and fill family/skeletal porosity/life history through a taxon-trait table.
- See `TRAIT_COVARIATE_COVERAGE.md` for the source-set audit tying trait coverage to the raw overview figure, digitization queue, and rate source index.

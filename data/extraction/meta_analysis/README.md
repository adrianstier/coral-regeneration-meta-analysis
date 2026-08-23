# Meta-Analysis Input Workspace

This directory is the modeling handoff layer. It converts rows that passed the source-provenance gate into effect-size inputs suitable for `metafor`.

## Rebuild

```bash
python3 tools/build_taxon_trait_lookup.py
python3 tools/build_model_covariates.py
python3 tools/build_analysis_ready_dataset.py
python3 tools/build_meta_analysis_inputs.py
```

The effect-size builder reads only `data/extraction/analysis_ready/ANALYSIS_READY_OBSERVATIONS.csv`. Candidate rows, NotebookLM answers, crop proposals, and provisional extraction rows do not enter the modeling input layer unless they pass the upstream gate. The covariate builder reads the source-level NotebookLM covariate table and the genus-level taxon lookup so moderator coverage can be audited even before any `yi/vi` row exists.

## Current Result

- Analysis-ready observations read: 0
- Metafor-ready input rows: 0
- Model-covariate source rows: 76
- Family coverage: 59/76
- Conservative skeletal-porosity coverage: 7/76

That is expected because `ANALYSIS_READY_OBSERVATIONS.csv` is currently empty.

## Files

- `META_ANALYSIS_COVARIATES.csv`: one row per primary source with normalized moderator fields for genus, family, growth form, skeletal porosity, study design, environmental context, wound geometry, and coordinates.
- `META_ANALYSIS_COVARIATE_AUDIT.csv`: model-covariate rows plus readiness/status fields.
- `META_ANALYSIS_COVARIATE_SCHEMA.csv`: modeling meaning of normalized covariate fields.
- `META_ANALYSIS_COVARIATE_SUMMARY.md`: compact moderator coverage summary.
- `META_ANALYSIS_INPUTS.csv`: one row per effect-size-ready modeling input, with `yi`, `vi`, `study_id`, `obs_id`, `analysis_stratum`, and moderator columns.
- `META_ANALYSIS_INPUT_AUDIT.csv`: one row per upstream analysis-ready observation, including effect-size blockers if `yi/vi` cannot be computed.
- `META_ANALYSIS_INPUT_ISSUES.csv`: effect-size calculation blockers and warnings.
- `META_ANALYSIS_INPUT_SCHEMA.csv`: minimal schema and modeling meaning of key columns.
- `META_ANALYSIS_SUMMARY.md`: compact rebuild summary.
- `META_ANALYSIS_MODEL_PLAN.md`: modeling plan and effect-size rules.

## Effect-Size Rules

- Survival rows with raw dead/total counts become log odds ratios for mortality.
- Continuous treatment-control rows become log response ratios only when positive means, usable variance, and group-specific sample sizes are known.
- Absolute regeneration rates and endpoints can be modeled as raw means only within compatible `analysis_stratum` values; do not pool areal rates, linear rates, percent endpoints, and exponential slopes in one model.
- Rows without defensible `yi` and `vi` stay out of `META_ANALYSIS_INPUTS.csv`.

## Modeling Rule

Use `META_ANALYSIS_INPUTS.csv` as the only modeling source. Fit multilevel models when studies contribute multiple effects:

```r
metafor::rma.mv(yi, vi, random = ~ 1 | study_id / obs_id, data = dat)
```

Use robust variance checks clustered by `study_id` when dependence assumptions are uncertain.

For moderator models, prefer the normalized columns inherited from `META_ANALYSIS_COVARIATES.csv`, such as `family`, `growth_form_standard`, `skeletal_porosity`, `field_lab_mesocosm`, `depth_mid_m`, `initial_wound_area_mid_mm2`, `temperature_mid_c`, `pH_mid`, and `pCO2_uatm_mid`. Use a moderator only when its paired model-status field indicates it is single-valued and usable for the row.

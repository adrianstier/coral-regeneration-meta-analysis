# Coral Regeneration Meta-Analysis Model Plan

This plan translates the `meta-analysis-R` skill into project-specific modeling rules. It should be updated only when the extraction schema or analysis question changes.

## Unit Of Analysis

The modeling table is one row per effect size. Required identifiers:

- `study_id`: source-level cluster, currently `source_id`.
- `obs_id`: unique row-level effect identifier.
- `dependent_effect_cluster`: source/response/taxon/outcome/treatment cluster used to flag related effects.

Multiple effects from one paper should be modeled with a multilevel structure rather than silently collapsed:

```r
metafor::rma.mv(yi, vi, random = ~ 1 | study_id / obs_id, data = dat, method = "REML")
```

Use `clubSandwich::coef_test(..., vcov = "CR2", cluster = dat$study_id)` as a robustness check when dependence within papers is uncertain.

## Effect-Size Families

### Regeneration Rate

Many rate rows are absolute outcomes rather than treatment-control contrasts. Keep incompatible units separate.

- `absolute_areal_rate`: examples include `mm2 d-1` or `cm2 month-1`; model only within a common converted area-time unit.
- `absolute_linear_rate`: examples include `mm month-1` or `cm month-1`; model separately from areal rates.
- `absolute_exponential_rate`: reported exponential slopes; model separately unless the underlying model form and log base are harmonized.
- `endpoint_proportion_or_percent`: percent healed/regenerated endpoints; model separately from rates unless converted to a defensible rate metric.
- `time_to_closure_or_endpoint`: closure-time or endpoint-complete recovery measures; model separately unless converted to a common event-time model.

For raw-rate strata, `yi` is the reported or converted mean/rate and `vi` is derived from SE, SD/n, or CI width. These are not combined across `analysis_stratum` values.

### Survival

Survival rows with raw control and wounded dead/total counts use log odds ratios for mortality:

```r
metafor::escalc(measure = "OR",
  ai = treatment_dead,
  bi = treatment_total - treatment_dead,
  ci = control_dead,
  di = control_total - control_dead,
  data = dat)
```

Positive `yi` means higher mortality in wounded, damaged, or stressed corals.

### Growth And Reproduction

Treatment-control growth and reproduction outcomes should use log response ratios when the data are strictly positive and group-specific sample sizes and variance estimates are known:

```r
metafor::escalc(measure = "ROM",
  m1i = treatment_mean, sd1i = treatment_sd, n1i = treatment_n,
  m2i = control_mean, sd2i = control_sd, n2i = control_n,
  data = dat)
```

Do not compute ROM from a single pooled sample-size field unless the source explicitly says it applies to each group. If means can be zero or negative, switch to a separate standardized-mean-difference or raw-difference analysis and document that change.

## Moderator Set

Primary moderators should come from the source/covariate layer, not from post hoc interpretation:

- taxon/species and externally joined family/trait fields;
- growth form and skeletal porosity/perforate status when cleaned;
- initial wound area and wound geometry;
- injury mechanism and tissue/skeleton involvement;
- field/lab/mesocosm setting;
- depth, temperature/regime, pH/pCO2, nutrients, sedimentation, flow, light;
- study duration or time interval;
- geographic coordinates and water body.

Models should report covariate missingness by `analysis_stratum` before fitting moderator models.

The current normalized moderator handoff is `data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv`. It is rebuilt from the NotebookLM source covariates plus `notebook_covariates/taxon_trait_lookup.csv`, which currently supplies genus-level family from WoRMS. Skeletal porosity is not supplied by WoRMS, so `skeletal_porosity` is populated only for unambiguous single-taxon rows with direct source-level porosity evidence; the `skeletal_porosity_candidates` and `skeletal_porosity_model_status` columns retain recoverable but non-model-ready cases.

## Minimum Reporting

For each fitted model, report:

- `k` studies and `n` effect sizes;
- overall effect with 95% CI;
- prediction interval;
- tau-squared and I-squared or multilevel variance components;
- moderator tests when used;
- influence diagnostics or leave-one-study-out sensitivity;
- publication-bias diagnostics only when sample size is defensible.

Publication-bias tests are underpowered with small `k`; do not overinterpret funnel asymmetry for sparse strata.

## Current Status

`META_ANALYSIS_INPUTS.csv` is currently empty because no extracted row has passed both the analysis-ready provenance gate and the effect-size `yi/vi` gate. The first practical target is still to verify the 10 near-ready table/text rate rows identified in `data/extraction/analysis_ready/GET_TO_ANALYSIS_READY_PLAN.md`.

`META_ANALYSIS_COVARIATES.csv` currently contains 76 source-level rows and is not empty. Coverage is high for family and study setting but still sparse for skeletal porosity and carbonate chemistry; this should guide the next covariate validation pass.

# Covariate Extraction Strategy

This document records the current moderator strategy after querying the `Coral regeneration all sources` NotebookLM notebook (`bb37eb1a-3b19-4f6c-9cc3-7df3a41e1388`) against the 57-source rate set in `data/extraction/rate/RATE_SOURCE_INDEX.csv`. The notebook was re-identified from the connected NotebookLM notebook list on 2026-08-16 and is registered in `notebook_covariates/NOTEBOOKLM_NOTEBOOKS.md`; use the notebook ID directly because tag-limited searches can miss it.

NotebookLM query ids used for this discovery pass:

- trait/taxonomy accessibility: `eb323c621bb8`
- wound-design accessibility: `ba83ae09d2c9`
- environment/stressor accessibility: `ef50a09806d1`
- tier ranking: `633da54d6a21`

## Design Decision

Do not keep expanding the source-level covariate table into one wide table for every moderator. The papers mix source-level, treatment-level, taxon-level, and observation-level information, and a single row per paper cannot represent that without ambiguous multi-value cells.

Use four linked layers:

- `source` layer: study context shared by a paper or source, such as field/lab/mesocosm, location, broad habitat, measurement method, endpoint definition, and monitoring schedule.
- `treatment` layer: manipulated or stratified conditions, such as temperature, pH/pCO2, nutrients, flow, depth strata, injury mechanism, lesion size class, lesion position, and lesion spacing.
- `observation` layer: numeric response rows, such as a rate, time-to-closure, initial/final wound size, time interval, sample size, and variance.
- `taxon_trait` layer: canonical species/genus/family and derived intrinsic traits, such as standardized growth form, skeletal porosity, tissue thickness, polyp size, and life-history strategy.

The existing `notebook_covariates_primary_geoaugmented.csv` remains useful as a source-level moderator and screening layer, but model-ready extraction should normalize out treatment, observation, and taxon-trait information.

## Tier 1: Extract Now

These covariates are both biologically important and generally recoverable from the papers.

| Covariate | Grain | Source | Rationale |
| --- | --- | --- | --- |
| `taxon_raw` / `taxon_canonical` | observation or treatment | paper + taxon lookup | Species identity is the base key for all trait joins. |
| `initial_wound_area_mm2` | treatment or observation | paper | Initial damage scale strongly controls closure rate and completeness. |
| `injury_mechanism_standard` | treatment | paper | Tool and injury type distinguish tissue abrasion, skeletal excavation, branch breakage, predation mimicry, disease, and natural scars. |
| `tissue_skeleton_involvement` | treatment | paper | Tissue-only versus tissue-plus-skeleton determines whether basal tissue remnants can contribute to repair. |
| `temperature_c` / `temperature_regime` | treatment or source | paper | Temperature is the dominant environmental stressor with high direct reporting. |
| `colony_size_value` / `colony_size_metric` | observation or treatment | paper | Colony or fragment size indexes energetic pool and tissue available for translocation. |
| `monitoring_duration_days` | source or treatment | paper | Rate estimates are not comparable without the time interval. |
| `timepoint_days` / `time_interval_days` | observation | paper or digitized data | Time series and initial/final conversions need exact interval data. |
| `sample_size` | observation or treatment | paper | Required for weighting and for distinguishing initial from analyzed sample sizes. |
| `variance_type` / `variance_value` | observation | paper or digitized data | Required for pooled effect sizes and independent QC. |
| `endpoint_definition` | source or treatment | paper | "Healed" can mean tissue cover, no visible skeleton, full polyp, pigmentation, or feeding-capable polyp. |
| `field_lab_mesocosm` | source | paper | Field, laboratory, and mesocosm studies have different background artifacts. |

## Tier 2: Extract If Present

These are useful, but either selectively reported, measured with inconsistent methods, or strongly context dependent.

| Covariate | Grain | Source | Rationale |
| --- | --- | --- | --- |
| `final_wound_area_mm2` | observation | paper, digitized figure, or derived | Often recoverable from percent healed or digitized figures. |
| `wound_shape_standard` | treatment | paper | Shape and perimeter-to-area ratio affect marginal healing. |
| `wound_perimeter_mm` / `perimeter_area_ratio` | observation or treatment | paper or derived | High value where reported, sparse elsewhere. |
| `lesion_depth_mm` | treatment | paper | Important but sometimes described only qualitatively. |
| `lesion_position_standard` | treatment | paper | Top, side, branch tip, base, apical, and underside affect light, flow, and sedimentation. |
| `num_lesions_per_colony` | treatment | paper | Multiple wounds can create colony-scale energetic drain. |
| `lesion_spacing_cm` / `lesion_configuration` | treatment | paper | High value for papers testing clustered versus dispersed wounds. |
| `depth_m` / `depth_range_m` | source or treatment | paper | Important field proxy for light, flow, temperature, and habitat zone. |
| `pH` / `pCO2_uatm` / `omega_arag` | treatment | paper | Critical in acidification studies, but sparse and scale-dependent. |
| `nutrient_treatment` / `nutrient_concentration` | treatment | paper | Needs nitrogen source and concentration, not just enriched/ambient. |
| `light_PAR` / `light_regime` | source or treatment | paper | Useful where light or depth is focal; often coarse. |
| `flow_speed` / `flow_method` | treatment or source | paper | Valuable but methods differ among clod cards, wave models, and flow meters. |
| `sedimentation` / `turbidity` | treatment or source | paper | Useful but method-specific. |
| `symbiotic_state` / `symbiont_density` | treatment or observation | paper | Essential in facultative or bleaching studies; not consistently reported across tropical systems. |
| `bleaching_status` / `disease_status` / `algal_competition` / `predator_context` | treatment or source | paper | High biological value but needs standardized categorical coding. |
| `season` | source or treatment | paper | Useful where seasonal experiments were explicit; hemisphere and local climatology matter. |

## Tier 3: Do Not Extract As Core Paper Fields

These should be populated through a taxon-trait table keyed by canonical taxon, with explicit provenance for the trait source.

| Covariate | Recommended Handling |
| --- | --- |
| `genus` | Parse from canonical species and validate through a taxonomic lookup. |
| `family` | Populate from WoRMS or another taxonomic authority. |
| `growth_form_standard` | Keep author raw text if useful, but standardize through a trait table. |
| `skeletal_porosity` / `perforate_status` | Use external morphology/trait references; do not treat `tissue_type` free text as model-ready. |
| `life_history_strategy` | Link to a published trait framework rather than extracting ad hoc labels from papers. |
| `tissue_thickness_mm` | Use species/genus-level literature or trait table values where defensible. |
| `polyp_size` / `corallite_size` | Use external morphometric traits unless directly measured in the paper. |

## NotebookLM Query Protocol

Use NotebookLM to discover and pre-fill candidates, then verify load-bearing numeric values against the PDF or digitized source image.

For each query batch, request a strict table with:

- `source_id`
- `paper_title`
- requested covariate fields
- `reported_status`: `reported`, `not_reported`, `inferred_from_text`, `external_lookup_needed`, or `not_applicable`
- `raw_value`
- `standardized_value`
- `units`
- `evidence_quote`
- `figure_or_table_label`
- `page_or_section`
- `confidence`: `high`, `medium`, or `low`
- `needs_pdf_verification`

Query in blocks of 8-12 sources or one covariate family at a time. The 57-paper all-source queries are useful for schema design, but row-level extraction should be smaller to reduce hallucinated completeness and missed qualifiers.

## Immediate Implementation

1. Build `taxon_trait` scaffolding from all unique taxa in the rate observations and covariate table.
2. Add treatment/observation covariate columns to the rate extraction layer rather than overloading the source-level NotebookLM table.
3. Re-query NotebookLM in focused batches for Tier 1 fields first: wound area, injury mechanism, tissue/skeleton involvement, temperature, colony size, duration, sample size, variance, and endpoint definition.
4. Only after Tier 1 is complete, fill Tier 2 fields where the paper made them explicit.
5. Keep family, skeletal porosity, life history, tissue thickness, and polyp size as trait joins with their own provenance. The current implemented handoff is `data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv`; genus-level family is populated from `notebook_covariates/taxon_trait_lookup.csv`, while skeletal porosity remains conservative and sparse until an external morphology/trait lookup is added.

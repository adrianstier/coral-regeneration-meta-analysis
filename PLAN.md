# Meta-Analysis Protocol: Coral Wound Healing & Tissue Regeneration

This document defines the scientific protocol for the coral regeneration meta-analysis. Operational source-of-truth and rebuild details live in `README.md` and `docs/pipeline/EXTRACTION_PIPELINE.md`.

## Current Repository Status

The project is in the screening, extraction, covariate completion, and figure/table digitization stage. In the current repository state:

- `data/screening/SCREENING_LOG_FINAL.csv` contains 156 adjudicated full-text records.
- The primary quantitative pool contains 76 records: 20 ready for table/text extraction and 56 requiring figure/table digitization.
- The mechanism-only narrative pool contains 20 records.
- The local primary-PDF pool is complete, and all 367 figure/table candidate rows now have independent audit coverage.
- The current figure-index audit reports zero structural errors: 76 queue rows have audited candidate evidence and 10 response rows have no valid figure/table candidate found.
- No effect-size calculation, `metafor`/`brms` model, forest/funnel plot, manuscript draft, or `renv` environment has been created yet.

## 0. Introduction to Meta-Analysis

Meta-analysis is a statistical method that combines data from multiple independent studies to identify patterns, estimate overall effect sizes, and detect sources of variability. It is particularly useful in ecology for resolving conflicting findings and revealing generalities across diverse systems.

### What this meta-analysis will accomplish:
- **Quantify average coral healing rates** across species, environments, and wound types.
- **Understand how coral traits** (taxonomy, morphology, tissue type) shape regeneration outcomes.
- **Test specific hypotheses** about environmental stressors and healing success.
- **Identify knowledge gaps** to guide future research priorities.
- **Create an open-access database** of coral healing metrics and metadata.

### Why PRISMA guidelines?
We follow **PRISMA (Preferred Reporting Items for Systematic Reviews and Meta-Analyses)** guidelines to ensure transparency and reproducibility. This means documenting every step so someone else could exactly reproduce our search, data collection, analysis, and figures.

---

## 1. Objectives & Scope

- **Primary Goal:** To systematically review and meta-analyze coral regeneration after wounding, focusing on healing rates, coral traits, environmental influences, wound types, and geographic patterns.
- **Taxonomic Scope:** Stony corals (**Scleractinia**) only. We explicitly exclude octocorals and other analog taxa.
- **Key Deliverables:**
    - Quantitative summary of coral wound healing across studies.
    - Identification of moderators of healing (species traits, environment, wound type).
    - Phylogenetic and morphological signals of regeneration capacity.
    - Open-access database of healing metrics and metadata for the community.

---

## 2. Research Questions & Hypotheses

### Primary Research Questions
1. What is the average rate and extent of coral wound healing?
2. How do coral traits (species, morphology, perforate/imperforate) influence regeneration?
3. What is the effect of wound type and geometry (e.g., perimeter-to-area ratio)?
4. How do environmental variables (temperature, nutrients, pH, sedimentation) moderate healing?
5. Are there biogeographic patterns in regeneration capacity?

### Key Hypotheses to Test
- **Trait-based hypothesis:** Imperforate corals regenerate faster than perforate corals.
- **Temperature hypothesis:** Elevated temperatures near bleaching thresholds reduce regeneration success.
- **Nutrient hypothesis:** Chronic low-level nutrient enrichment may enhance regeneration under some conditions.
- **Wound type hypothesis:** Grazing-type wounds result in faster tissue regrowth than structural injuries.
- **Geometry hypothesis:** Lesion geometry (perimeter-to-area ratio) predicts regeneration rate, with higher P/A leading to faster closure.
- **Colony integration hypothesis:** Resource translocation from healthy tissue supports healing of larger wounds.

---

## 3. Literature Search Strategy

**Databases:** Web of Science, Google Scholar

### Search Terms (adjust for each database):

| Search Type | Search String |
| :--- | :--- |
| **General (All Fields)** | `(ALL=(coral)) AND ALL=(wound* OR lesion* OR heal* OR regenerat* OR injury OR scrape* OR bite OR fragment* OR drill OR airbrush)` |
| **Title Search** | `(TI=(coral)) AND TI=(wound* OR lesion* OR heal*)` |
| **Abstract Search** | `(AB=(coral)) AND AB=(wound* OR lesion* OR heal*)` |

- **Current screening source of truth:** `data/screening/SCREENING_LOG_FINAL.csv`.
- **Historical working files:** `data/screening/SCREENING_LOG.csv`, `data/screening/SCREENING_LOG_V2.csv`, and `data/screening/SCREENING_REVIEW_QUEUE.csv` are retained for traceability only.
- **Generated PRISMA summary:** `pipeline/PRISMA_COUNTS.md` is rebuilt from `SCREENING_LOG_FINAL.csv` with `python3 tools/build_pipeline_outputs.py`. Do not hand-edit PRISMA counts.

---

## 4. Inclusion & Exclusion Criteria

### Include:
- Empirical studies on coral wound healing and tissue regeneration.
- Experimental or observational studies (lab, field, or mesocosm).
- Studies measuring healing rates, tissue regeneration, or regrowth metrics.
- Studies providing species-level identification.

### Exclude:
- Reviews, editorials, and conference abstracts without full data.
- Studies focused only on disease progression without regeneration data.
- Non-stony coral species (e.g., octocorals, hydrozoans, anemones).
- Modeling studies lacking empirical healing rate data.
- Studies without identifiable wound type or coral species ID.

---

## 5. Data Extraction Framework

Extract all available information, prioritizing healing outcomes and study design.

**Note: Variables are Tiered to prevent burnout.**
- **Tier 1 (Essential):** Must extract for all papers.
- **Tier 2 (Exploratory):** Extract only if easily available.

### 5.1 Study Identification (Tier 1)
| Variable | Description / Format |
| :--- | :--- |
| **Author** | First author surname et al. (e.g., "Smith et al.") |
| **Year** | Publication year |
| **DOI** | Persistent identifier |
| **Paper_Num** | Unique ID for each published study |
| **Substudy_Num** | ID for experiments within a single paper |

### 5.2 Study Context (Tier 1)
| Variable | Description / Format |
| :--- | :--- |
| **Study_Type** | Lab | Field | Mesocosm |
| **Location** | Ecoregion, reef name, or country |
| **Lat / Long** | Decimal degrees |
| **Depth_m** | Depth in meters |
| **Study_Year** | Year(s) the experiment was conducted |

### 5.3 Coral Traits (Tier 1)
| Variable | Description / Format |
| :--- | :--- |
| **Taxonomy** | Family / Genus / Species |
| **Growth_Form** | Branching | Massive | Encrusting | Foliose |
| **Tissue_Type** | Perforate | Imperforate (test key hypothesis) |
| **Colony_Size_cm** | Mean diameter or longest dimension (cm) |
| **Symbiont_Clade** | Symbiodiniaceae clade (A, C, D, etc.) |

### 5.4 Wound Characteristics (Tier 1)
| Variable | Description / Format |
| :--- | :--- |
| **Lesion_Source** | Natural | Experimental |
| **Method** | Airbrushing | Waterpik | Bone cutter | Air jet | Drill | Other |
| **Lesion_Type** | Tissue-only | Tissue+Skeleton | Fragmentation | Corallivore |
| **Area_mm2** | Initial wound area (mm²) |
| **Rel_Wound_Size** | Wound Area / Colony Area (if available) |
| **Perimeter_mm** | Wound perimeter (mm) - **CRITICAL for P/A ratio** |
| **Lesion_Depth** | Surface | Full-thickness | Partial-thickness |
| **Num_Lesions** | Number of wounds per colony |
| **Spacing_cm** | Distance between wounds (cm) |
| **Location** | Apical | Sub-apical | Distal | Basal | Lateral | Random |

### 5.5 Healing Outcomes (Tier 1)
| Outcome Metric | Description / Units |
| :--- | :--- |
| **Rate_Constant_k** | **PREFERRED:** Exponential decay rate constant (day⁻¹) |
| **Linear_Rate** | Linear healing rate: (D_initial - D_final) / Δt (mm/day) |
| **Areal_Rate** | Areal healing rate: (A_initial - A_final) / Δt (mm²/day) |
| **Proportional_Rate** | Percent closure per day: (% closure) / Δt (%/day) |
| **Time_to_Healing** | Days until 100% closure (can invert to get rate) |
| **Final_Extent** | Percentage healed at end of study (%) |
| **Duration_days** | Total monitoring period (days) |
| **Interval_days** | Frequency of observations |

### 5.6 Cellular & Molecular Observations (Tier 2)
| Variable | Description / Notes |
| :--- | :--- |
| **Histology** | Y/N - note healing phases (plug, granulation, maturation) |
| **Immune_Response** | Y/N - gene expression, phenoloxidase, melanin |
| **Resource_Transloc** | Y/N - 14C labeling or other tracer methods |
| **Stem_Cells** | Y/N - markers, cell clusters at margins (Levanoni et al. 2024) |
| **Symbiont_Reest** | Y/N - timing and density of re-colonization |
| **Microbiome** | Y/N - 16S sequencing or other microbial analysis |

### 5.7 Environmental Conditions (Tier 1)
| Variable | Description / Format |
| :--- | :--- |
| **Temperature_C** | Mean ± SD (°C) |
| **Temp_Manip** | Y/N - note if near bleaching threshold |
| **pCO2 / pH** | Ocean acidification treatment (µatm or pH units) |
| **Nutrient_Enrich** | Y/N - type (N, P, both) and concentration (µM) |
| **Duration** | Chronic | Pulse | Acute |
| **Light_PAR** | µmol photons m⁻² s⁻¹ |
| **Light_Regime** | Ambient | Shaded | Manipulated |
| **Sedimentation** | mg/cm²/day or turbidity (NTU) |
| **Flow_Regime** | Still | Flow-through | Wave action |

### 5.8 Experimental Design & Statistics (Tier 1)
| Variable | Description / Format |
| :--- | :--- |
| **Sample_Size** | Number of colonies or fragments per treatment |
| **Replication_Level** | Colony | Tank | Polyp | Site |
| **Randomization** | Y/N - note method if described |
| **Blocking** | Y/N - by genotype, site, tank, etc. |
| **Control** | Y/N - describe control conditions |
| **Variance** | SD | SE | CI | None (note which) |

---

## 5.9 Risk of Bias & Study Quality Assessment
Each study will be scored (1-3) on the following criteria to weight the meta-analysis:
1. **Replication Quality:** Are replicates true independent colonies or pseudoreplicates?
2. **Environmental Control:** Was the environment monitored (Field) or strictly controlled (Lab)?
3. **Outcome Resolution:** High-frequency imaging vs. single end-point measurement.
4. **Reporting:** Were raw data, variances, and sample sizes fully reported?
*Total Score will be used as a moderator or weighting factor.*

---

### 5.10 Quality Control & Flags
Use "?" flag for missing or uncertain data
Use "!" flag for suspect or potentially problematic data
Record any estimation methods in the Notes field
Track Extraction_Status: To-do | In-progress | Complete | Needs-review

---

## 6. Effect Size Calculation & Variance

### 6.1 Primary Healing Metrics & Standardization Strategy
To avoid fragmented analyses, we will prioritize the following hierarchy and apply standardization:
1. **Rate constant k:** (day⁻¹) from temporal area data.
2. **Log Response Ratio (lnRR):** If raw rates are not comparable, we will calculate effect sizes as ln(Mean_Treatment / Mean_Control).
3. **Standardized Mean Difference (SMD):** Use Hedges’ g to combine studies with different units (mm vs mm²).
4. **Geometric Conversion:** For circular/square wounds, we will use standard formulas to convert linear extension to areal closure where dimensions are provided.
*Note: A sensitivity analysis will be performed to test if results differ between 1D and 2D metrics.*

### 6.2 Secondary Outcomes
- **Growth rate:** Change in colony area or linear extension (cm/day or cm²/day)
- **Fecundity:** Larvae or eggs per colony or per polyp
- **Survival:** Proportion alive at end of study

---

## 7. Statistical Analysis Plan

### 7.1 Descriptive Analysis
- Summarize studies by taxa, wound type, location, and methodology.
- Create forest plots showing healing rates across studies.

### 7.2 Meta-Analytic Models
- **Grand mean healing rate:** Random-effects model with `rma.mv()` in `metafor`.
- **Heterogeneity tests:** Calculate I² and Q statistics.
- **Meta-regression:** Test moderators (species, wound size, P/A ratio, temp, etc.).
- **Publication bias:** Funnel plots and Egger's test.


### 7.4 Meta-Analysis of Single Means (Observational Studies)
For studies lacking a control group, we will perform a meta-analysis of single means (raw healing rates) to establish global baseline regeneration rates across taxa and environments. This will be analyzed separately from the treatment-effect (lnRR) models.

### 7.3 Advanced Analyses: Phylogenetic Control
- **Phylogenetic Meta-Analysis (MANDATORY):** We will use the Huang & Roy (2015) or newer coral tree to account for non-independence of species. Models will be run using `rma.mv()` with a phylogenetic covariance matrix.
- **Interaction effects:** Test temperature × tissue type, wound size × colony size, etc.

---

## 8. Extraction Workflow

Work from generated queues, but edit upstream source-of-truth tables rather than generated outputs.

### Current Execution Order

1. Update screening/adjudication in `data/screening/SCREENING_LOG_FINAL.csv`.
2. Rebuild the pipeline outputs:

```bash
python3 tools/build_pipeline_outputs.py
```

3. Update source-review and digitization aids:

```bash
python3 tools/build_extraction_review_artifacts.py
python3 tools/merge_figure_candidate_audits.py
python3 tools/render_audited_source_pages.py
python3 tools/build_figure_visual_reaudit.py
python3 tools/build_figure_crop_manifest.py
python3 tools/audit_figure_indexing.py
```

4. Work down `pipeline/EXTRACTION_WORKPLAN.csv` by `priority_rank`.
5. Use `digitization/source_review/FIGURE_QUEUE_AUDIT_STATUS.csv` and `digitization/figures/FIGURE_CROP_MANIFEST.csv` for figure/table clipping work.
6. Promote extracted values only after figure/table label, page, panel, units, variance source, sample-size source, clip path, digitized-data path, digitizer, reviewer, and QA status are recorded.

### Current Blockers Before Analysis

- 86 generated digitization-queue rows still have `digitization_status=needs_figure_id` in the upstream queue.
- The audited overlay has 76 queue rows with candidate evidence and 10 rows with no valid figure/table candidate found.
- `digitization/figures/FIGURE_INDEX_AUDIT_SUMMARY.md` currently reports zero structural figure-indexing errors.
- All 29 legacy extraction rows still need source provenance review before they can enter pooled analyses.
- Geometry remains the most data-starved moderator: `perimeter_mm` is present for 3 of 76 primary rows.

---

## 9. Key Insights from Elicit Review

### 9.1 Cellular & Molecular Mechanisms
- **Healing phases:** Plug formation → immune cell infiltration → granulation → tissue maturation → symbiont reestablishment.
- **Immune activation:** Toll-like receptor pathways, phenoloxidase activity, melanin synthesis.
- **Resource transport:** 14C labeling shows photosynthate translocation to injury sites.

### 9.2 Factors Influencing Healing
- **Lesion characteristics:** Small lesions heal faster; P/A ratio predicts healing rate.
- **Colony size & depth:** Larger, shallower colonies generally heal faster.
- **Environmental stressors:** Elevated temperature, ocean acidification, sedimentation negatively affect healing.

---

## 10. Tips for First-Time Meta-Analysts

1. **Start Small:** Extract 3-5 papers completely before scaling up.
2. **Be Conservative:** Only extract data you're confident about — flag everything else.
3. **Document Everything:** Keep a detailed log of decisions, conversions, and assumptions.
4. **Verify the pipeline:** Run `python3 -m unittest discover -s tests -p 'test_*.py'` after changing Python tools and inspect generated QA reports after changing data.
5. **Add R reproducibility when analysis starts:** create `renv.lock`, document R/package versions, and make the effect-size/model scripts reproducible before manuscript drafting.

---
Meta-analysis is iterative. Keep the protocol stable, but let the generated QA outputs define the next concrete extraction and documentation edits.

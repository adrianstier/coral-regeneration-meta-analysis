# Meta-Analysis Protocol: Coral Wound Healing & Tissue Regeneration

*A Beginner's Guide to Systematic Review and Meta-Analysis*

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
| **General (All Fields)** | `(ALL=(coral)) AND ALL=(wound* OR lesion* OR heal* OR injury OR scrape* OR bite OR fragment* OR drill OR airbrush)` |
| **Title Search** | `(TI=(coral)) AND TI=(wound* OR lesion* OR heal*)` |
| **Abstract Search** | `(AB=(coral)) AND AB=(wound* OR lesion* OR heal*)` |

- **Screening Tools:** Rayyan or `metagear` R package for citation management, abstract screening, and PDF retrieval.
- **Documentation:** Keep a detailed log of search dates, databases, number of results, and screening decisions (maintain a PRISMA flow diagram).

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

### 5.1 Study Identification
| Variable | Description / Format |
| :--- | :--- |
| **Author** | First author surname et al. (e.g., "Smith et al.") |
| **Year** | Publication year |
| **DOI** | Persistent identifier |
| **Paper_Num** | Unique ID for each published study |
| **Substudy_Num** | ID for experiments within a single paper |

### 5.2 Study Context
| Variable | Description / Format |
| :--- | :--- |
| **Study_Type** | Lab | Field | Mesocosm |
| **Location** | Ecoregion, reef name, or country |
| **Lat / Long** | Decimal degrees |
| **Depth_m** | Depth in meters |
| **Study_Year** | Year(s) the experiment was conducted |

### 5.3 Coral Traits (Species & Morphology)
| Variable | Description / Format |
| :--- | :--- |
| **Taxonomy** | Family / Genus / Species |
| **Growth_Form** | Branching | Massive | Encrusting | Foliose |
| **Tissue_Type** | Perforate | Imperforate (test key hypothesis) |
| **Colony_Size_cm** | Mean diameter or longest dimension (cm) |
| **Symbiont_Clade** | Symbiodiniaceae clade (A, C, D, etc.) |

### 5.4 Wound Characteristics
| Variable | Description / Format |
| :--- | :--- |
| **Lesion_Source** | Natural | Experimental |
| **Method** | Airbrushing | Waterpik | Bone cutter | Air jet | Drill | Other |
| **Lesion_Type** | Tissue-only | Tissue+Skeleton | Fragmentation | Corallivore |
| **Area_mm2** | Initial wound area (mm²) |
| **Perimeter_mm** | Wound perimeter (mm) - **CRITICAL for P/A ratio** |
| **Lesion_Depth** | Surface | Full-thickness | Partial-thickness |
| **Num_Lesions** | Number of wounds per colony |
| **Spacing_cm** | Distance between wounds (cm) |
| **Location** | Apical | Sub-apical | Distal | Basal | Lateral | Random |

### 5.5 Healing Outcomes (PRIMARY DATA)
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

### 5.6 Cellular & Molecular Observations
| Variable | Description / Notes |
| :--- | :--- |
| **Histology** | Y/N - note healing phases (plug, granulation, maturation) |
| **Immune_Response** | Y/N - gene expression, phenoloxidase, melanin |
| **Resource_Transloc** | Y/N - 14C labeling or other tracer methods |
| **Stem_Cells** | Y/N - markers, cell clusters at margins (Levanoni et al. 2024) |
| **Symbiont_Reest** | Y/N - timing and density of re-colonization |
| **Microbiome** | Y/N - 16S sequencing or other microbial analysis |

### 5.7 Environmental Conditions
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

---

## 6. Effect Size Calculation & Variance

### 6.1 Primary Healing Metrics
Hierarchy of metrics (preferred → fallback):
1. **Rate constant k:** Exponential decay rate from temporal area data (day⁻¹)
2. **Linear/areal rates:** (D_initial - D_final) / Δt or (A_initial - A_final) / Δt
3. **Proportional rate:** (% closure) / Δt
4. **Time to closure:** 1 / (days to 100% heal)

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

---

## 8. Extraction Workflow

### Weekly Schedule:
- **Weeks 1-2:** Background literature, finalize protocol, set up spreadsheets.
- **Weeks 3-4:** Trial searches, abstract screening, test extraction on 2-3 papers.
- **Weeks 5-8:** Full-text screening and extraction (aim for 1-2 papers/day).
- **Weeks 9-10:** QA/QC, resolve flags, fill missing data via author contact.
- **Weeks 11-12:** Preliminary analyses, descriptive stats, draft results section.

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
4. **Use R Tools:** `metafor`, `metagear`, `orchaRd`.

---
**Good luck with your meta-analysis!**
*Remember: Meta-analysis is iterative. Start simple, refine as you go.*
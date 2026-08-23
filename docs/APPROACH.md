# Multi-Bin Meta-Analysis Approach

This project uses a **Response-Specific Modular Extraction** strategy to maximize data recovery from diverse ecological literature.

## 1. Data Binning Logic
Instead of a single "Include/Exclude" status, every paper is evaluated for five response bins plus moderator layers. A paper enters the primary quantitative pool when it contributes to at least one extractable primary response (`rate`, `growth`, `reproduction`, or `survival`). Mechanism-only papers are retained for narrative synthesis, not pooled effect sizes.

- **Bin 1: Healing Rates:** Quantitative daily speed (mm2/d, k, %/d) + variance.
- **Bin 2: Somatic Cost (Growth):** Calcification or biomass change in Wounded vs. Control colonies.
- **Bin 3: Fitness Cost (Reproduction):** Fecundity, egg volume, or spawning success in Wounded vs. Control.
- **Bin 4: Survival:** Mortality counts or percentages following wounding events.
- **Bin 5: Cellular Mechanisms:** Qualitative/Mechanistic data (stem cells, immunity, histology).
- **Moderator layers:** Contextual data on temperature, nutrients, pH, flow, coral traits, wound geometry, geography, and study design. These live primarily in `notebook_covariates/`, not as a sixth pooled response table.

## 2. Extraction Protocol: "Trust but Verify"
1. **Query-First:** Use the NotebookLM notebook for accessibility discovery and candidate values. Query smaller source batches for row-level extraction, and preserve evidence quotes plus reported/inferred/not-reported status.
2. **Direct Scan:** For high-priority papers or where AI results are ambiguous, use pdftotext to manually verify raw values, variance types (SD vs. SE), and sample sizes.
3. **Cross-Reference:** Benchmark extracted rates against the Henry & Hart (2005) review. Flag discrepancies for manual PDF review.

## 3. Modular Output Files
- `data/extraction/EXTRACTION_RATES.csv`: Focused on Bin 1.
- `data/extraction/EXTRACTION_FITNESS.csv`: Focused on Bins 2 & 3 (Growth/Reproduction).
- `data/extraction/EXTRACTION_SURVIVAL.csv`: Focused on Bin 4.
- `data/screening/SCREENING_LOG_FINAL.csv`: The final source of truth for which paper belongs to which response bin.
- `pipeline/EXTRACTION_WORKPLAN.csv`: Generated task list for extraction and digitization.
- `notebook_covariates/notebook_covariates_primary_geoaugmented.csv`: Current primary-study moderator layer, including exact, approximate, and best-coordinate fields.
- `notebook_covariates/COVARIATE_EXTRACTION_STRATEGY.md`: Normalized moderator strategy derived from NotebookLM accessibility queries.
- `notebook_covariates/covariate_extraction_schema.csv`: Machine-readable tier, grain, and provenance schema for moderator extraction.

Every extraction row must carry `source_id`, `paper_title`, and `local_relpath`. Legacy extracted values without exact figure/table labels are retained but marked `qa_status=needs_source_provenance_review` until the figure/table label, page, panel, units, variance source, and sample-size source are verified.

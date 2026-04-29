# Multi-Bin Meta-Analysis Approach

This project uses a **Response-Specific Modular Extraction** strategy to maximize data recovery from diverse ecological literature.

## 1. Data Binning Logic
Instead of a single "Include/Exclude" status, every paper is evaluated for its contribution to six independent analysis bins. A paper is "Kept" if it contributes to at least one bin.

- **Bin 1: Healing Rates:** Quantitative daily speed (mm2/d, k, %/d) + variance.
- **Bin 2: Somatic Cost (Growth):** Calcification or biomass change in Wounded vs. Control colonies.
- **Bin 3: Fitness Cost (Reproduction):** Fecundity, egg volume, or spawning success in Wounded vs. Control.
- **Bin 4: Survival:** Mortality counts or percentages following wounding events.
- **Bin 5: Cellular Mechanisms:** Qualitative/Mechanistic data (stem cells, immunity, histology).
- **Bin 6: Environmental Moderators:** Contextual data on Temperature, Nutrients, pH, and Flow.

## 2. Extraction Protocol: "Trust but Verify"
1. **Query-First:** Use the nlm CLI to query the NotebookLM notebook for specific data points across all sources.
2. **Direct Scan:** For high-priority papers or where AI results are ambiguous, use pdftotext to manually verify raw values, variance types (SD vs. SE), and sample sizes.
3. **Cross-Reference:** Benchmark extracted rates against the Henry & Hart (2005) review. Flag discrepancies for manual PDF review.

## 3. Modular Output Files
- `data/extraction/EXTRACTION_RATES.csv`: Focused on Bin 1.
- `data/extraction/EXTRACTION_FITNESS.csv`: Focused on Bins 2 & 3 (Growth/Reproduction).
- `data/extraction/EXTRACTION_SURVIVAL.csv`: Focused on Bin 4.
- `data/screening/SCREENING_LOG_FINAL.csv`: The final source of truth for which paper belongs to which response bin.
- `pipeline/EXTRACTION_WORKPLAN.csv`: Generated task list for extraction and digitization.

Every extraction row must carry `source_id`, `paper_title`, and `local_relpath`. Legacy extracted values without exact figure/table labels are retained but marked `qa_status=needs_source_provenance_review` until the figure/table label, page, panel, units, variance source, and sample-size source are verified.

# Outstanding Issues - Coral Regeneration Meta-Analysis

Current as of 2026-08-06, based on `PRISMA_COUNTS`, `PIPELINE_QA_REPORT`, `EXTRACTION_REVIEW_SUMMARY`, `FIGURE_CANDIDATE_AUDIT_SUMMARY`, `FIGURE_VISUAL_REAUDIT_SUMMARY`, `FIGURE_CROP_SUMMARY`, `FIGURE_INDEX_AUDIT_SUMMARY`, `RATE_EXTRACTION_SUMMARY`, `RATE_EXTRACTION_AUDIT_SUMMARY`, and the geoaugmented Notebook covariate tables.

Previously recorded external resources:

- NotebookLM: `Coral regeneration all sources`, id `bb37eb1a-3b19-4f6c-9cc3-7df3a41e1388`, 128 sources.
- Zotero Web API collection: `Coral Regeneration`, key `HBLPBLFZ`, 158 items.
- Local literature: 152 PDFs under `literature/{META_ANALYSIS_POOL,MECHANISMS_ONLY,EXCLUDED_FINAL,DUPLICATES}/`.

## 1. Zotero Library Hygiene

These items still need a Zotero-side pass before clean citation export.

- [ ] Delete duplicates: `5VNAL3WX` (Buck-Wiese 2018), `HV29456C` (Rodriguez-Villalobos 2016), `7RQFHV2A` (Traylor-Knowles 2016).
- [ ] Fix author initials with no periods: Raymundo et al. 2016 (`8NUEJQAV`), Rodriguez-Villalobos et al. 2015 (`HII9WLN2`), Bak & Steward-Van 1980 (`H7YKN5WV`), Renegar et al. 2008 (`C7HNZZVZ`).
- [ ] Convert five titles to sentence case and italicize species names: Wesseling 2001, Renegar 2008, Levanoni 2021, Counsell 2018, Brush 2024.
- [ ] Fix `PCO2` to `pCO2` in Edmunds & Burgess 2016 (`F54AJIS5`).
- [ ] Add missing DOI `10.7717/peerj.2544` to Tsounis & Edmunds 2016 (`6MC64X8A`).
- [ ] Verify Buck-Wiese 2018 (`UE4UE89Q`) last author against the journal record.

## 2. Source Coverage

Primary local PDF coverage is now complete.

- [x] `Coral-Damsel-Wounding-Manuscript.pdf` is present under `literature/META_ANALYSIS_POOL/`.
- [x] `digitization/source_review/SOURCE_RETRIEVAL_QUEUE.csv` is empty after rebuilding source-review artifacts.
- [x] Primary local PDF coverage is 76/76.
- [ ] Four non-primary records still lack local PDFs in the full adjudicated library.
- [ ] Twenty-eight full-library records are still missing from the NotebookLM source set; the current primary pool has NotebookLM coverage.

## 3. Figure And Table Digitization

This remains the largest extraction blocker.

- [ ] Resolve 86 upstream rows in `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` still marked `needs_figure_id`.
- [x] Audit the 10 newly parsed figure/table candidate rows from `Coral-Damsel-Wounding-Manuscript.pdf`.
- [x] Resolve the 2 Coral-Damsel queue rows that were marked `needs_followup_review`; they now point to Figure 2 page 11 for rate and Figure 3A page 12 for growth.
- [x] Run the figure-index audit; `FIGURE_INDEX_AUDIT_SUMMARY.md` reports zero structural indexing errors.
- [ ] Re-check 10 queue rows marked `no_valid_candidate_found`; either find non-caption evidence or mark the response as not extractable from figures/tables.
- [ ] Visually confirm the 185 candidate replacements and 139 kept candidates already covered by independent audit before clipping.
- [ ] Human-QA 168 auto-crop proposals in `digitization/figures/crop_review/`; confirm crop boxes, panels, axes, units, variance source, and sample-size source.
- [ ] Digitize 102 quantitative plot candidates and transcribe 60 table candidates after crop QA.
- [ ] Resolve 6 mixed visual/quantitative candidates by deciding whether to extract from figure or table.

## 4. Rate Extraction Dataset

The rate-specific extraction workspace now exists under `data/extraction/rate/`.

- [x] Build a source-level index for all 57 primary rate-response papers in `RATE_SOURCE_INDEX.csv`.
- [x] Parse full text for 57/57 rate papers and write 622 ranked evidence rows to `RATE_TEXT_EVIDENCE.csv`.
- [x] Capture 63 provisional curated observation rows and 11 legacy/pilot seed rows.
- [x] Repair CSV row-width alignment in `RATE_EXTRACTED_OBSERVATIONS.csv`; all curated rows now parse with 21 fields.
- [x] Run `python3 tools/audit_rate_extraction_dataset.py`; `RATE_EXTRACTION_AUDIT_SUMMARY.md` reports 0 errors, 2 warnings, and 5 info rows.
- [ ] Independently QC the 63 curated observation rows before setting `analysis_ready=1`.
- [ ] Fill exact source provenance for the 11 rate seed rows before promoting any legacy/pilot values.
- [ ] Complete figure/table digitization for the 33 rate sources routed as `needs_figure_or_table_digitization`.
- [ ] Resolve the 1 `not_extractable_no_valid_figure_or_table_candidate` source and the 1 `not_rate_extractable_wrong_response_assignment` source with final adjudication notes before analysis.

## 5. Legacy Extraction Provenance

All 29 legacy extraction rows remain blocked from pooling until source provenance is filled.

- [ ] Fill `figure_or_table_label`, `page`, and `panel_label` for each legacy row.
- [ ] Fill axes/units, variance source, and sample-size source.
- [ ] Confirm each workplan crosswalk remains correct.
- [ ] Promote rows from `needs_source_provenance_review` to `qa_passed` only after reviewer signoff.

## 6. Notebook Covariate Gaps

Current primary covariate table: 76 rows in `notebook_covariates_primary_geoaugmented.csv`.

Hypothesis-critical geometry gaps:

- [ ] `perimeter_mm`: 73/76 missing. This is the dominant blocker for the geometry/P:A moderator.
- [ ] `rel_wound_size`: 55/76 missing.
- [ ] `area_mm2`: 23/76 missing.

Environmental moderator gaps:

- [ ] `temperature_c`: 42/76 missing.
- [ ] `temp_manip`: 66/76 missing.
- [ ] `ph_or_pco2`: 71/76 missing.
- [ ] `nutrient_enrich`: 66/76 missing.
- [ ] `sedimentation`: 72/76 missing.
- [ ] `light_par` / `light_regime`: 59/76 and 58/76 missing.
- [ ] `flow_regime`: 51/76 missing.

Geographic and design gaps:

- [ ] exact `latitude` / `longitude`: 32/76 missing.
- [ ] best coordinates: 1/76 missing after approximate georeferencing.
- [ ] depth: 11/76 missing.
- [ ] `symbiont_status`: 51/76 missing.
- [ ] `randomization`, `blocking`, `control_description`: 30/76, 59/76, and 23/76 missing.

## 7. Screening Manifest Cleanup

- [x] Cox 2014 (`Corallivory: The Coral's Point of View`) has been reclassified to `exclude_review`.
- [x] Folder placements currently have no review rows in `pipeline/PIPELINE_QA_REPORT.md`.
- [x] Current primary pool count is 76.
- [ ] Confirm all 76 `include_primary` records still contribute to at least one response bin after any future screening edits.

## 8. Statistical Analysis

The repository is not yet at the statistical meta-analysis stage.

- [ ] Implement effect-size standardization: rate constant `k`, lnRR, SMD/Hedges' g, and documented geometric conversions.
- [ ] Fit grand-mean healing-rate models with `metafor::rma.mv()`.
- [ ] Run heterogeneity diagnostics: I2, Q, and variance-component checks.
- [ ] Run moderator models for tissue type, temperature, nutrients, wound type, geometry/P:A, colony integration, depth, and latitude.
- [ ] Add phylogenetic meta-analysis after species-level extraction is stable.
- [ ] Add publication-bias and sensitivity analyses.
- [ ] Create `renv.lock` once R analysis scripts exist.

## 9. Manuscript Drafting

There is no manuscript draft on disk yet.

- [ ] Scaffold `manuscript/` after extraction and the first model pass are stable.
- [ ] Draft Methods first from `PLAN.md`, `docs/pipeline/EXTRACTION_PIPELINE.md`, and generated PRISMA outputs.
- [ ] Build the PRISMA flow diagram from `pipeline/PRISMA_COUNTS.md`.
- [ ] Draft figures after effect-size and moderator models exist.
- [ ] Run manuscript-code and citation-coherence checks before any external draft leaves the repo.

## 10. Cross-Cutting Reproducibility

- [ ] Confirm the generated-output chain is deterministic after the Coral-Damsel candidate audit rows and figure-index audit were added:

```bash
python3 tools/build_pipeline_outputs.py
python3 tools/build_extraction_review_artifacts.py
python3 tools/merge_figure_candidate_audits.py
python3 tools/render_audited_source_pages.py
python3 tools/build_figure_visual_reaudit.py
python3 tools/build_figure_crop_manifest.py
python3 tools/audit_figure_indexing.py
python3 tools/build_rate_extraction_dataset.py
python3 tools/audit_rate_extraction_dataset.py
```

- [ ] Run `python3 -m unittest discover -s tests -p 'test_*.py'` after tool changes.
- [ ] Add a license before public data/code release.
- [ ] Add fuller Python environment documentation if the Python tooling becomes part of an archival release.

## Triage

1. Re-check the 10 `no_valid_candidate_found` rows and record final extractability decisions.
2. QA the 168 crop proposals, then digitize/transcribe accepted values.
3. Re-run `python3 tools/audit_figure_indexing.py` after any crop or digitized-data path is promoted from placeholder to concrete file.
4. Independently QC the 63 provisional rate observations and fill provenance for the 11 rate seed rows.
5. Close the 29 legacy extraction provenance rows.
6. Fill the geometry and temperature covariate gaps that control the first moderator analyses.

# Literature Library

PDF folders encode final screening status only.

- `META_ANALYSIS_POOL/`: primary quantitative studies.
- `MECHANISMS_ONLY/`: mechanism and narrative synthesis papers.
- `EXCLUDED_FINAL/`: final scope and review exclusions.
- `DUPLICATES/`: duplicate aliases retained for traceability.

Extraction readiness lives in `data/screening/SCREENING_LOG_FINAL.csv` and `pipeline/EXTRACTION_WORKPLAN.csv`, not in folder names.

To reapply folder placement after screening changes:

```bash
python3 tools/organize_literature_from_screening.py --apply
python3 tools/build_pipeline_outputs.py
```

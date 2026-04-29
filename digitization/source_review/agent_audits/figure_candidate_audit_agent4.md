# Figure Candidate Audit - Agent 4

Assigned source list indices 034-044 were audited against local PDFs only using `pdftotext -layout` page extraction and keyword checks. All assigned PDFs were present locally.

## Counts

- Rows audited: 69
- keep: 23
- replace: 31
- remove: 15
- blocked_missing_pdf: 0
- needs_manual_visual_review status: 0
- Rows flagged for manual visual review: 0

## Key Corrections

- `a3b88246`: rate rows that pointed to fecundity or lesion setup were corrected to `Table 2` or `FIG. 3`; reproduction rows that pointed to colony/lesion setup were corrected to `FIG. 5`.
- `d7f996dc`: survival/tissue-loss corrections point to `Fig. 7` (injury size over time); ciliate colonization, map, and prevalence captions were not treated as survival outcomes.
- `3f852e08`: growth rows keep `Fig. 5`, `Fig. 6`, and `Table 1`; all survival rows were removed because no survival, mortality, or tissue-loss figure/table was found in the local PDF.
- `06ab1757`: all growth rows were removed as no growth figure/table was found; survival rows keep `Table 1` and `Fig. 2`, with histology/in-text panel references corrected to `Table 1`.
- `0ccdd954`: the `Table S3` row was an in-text supplemental reference, not a printed caption in the local PDF; rate corrections use `Figure 2` and `Table 1`.
- `002a60bc`: `Table 3` candidates were in-text/Symbiodiniaceae references, not the requested responses; rate was corrected to `Figure 5`, survival to `Figure 4`.
- `33d2bc0d`: all survival rows were removed because local figures/tables report bleaching recovery physiology, temperature, or symbiont state rather than survival, mortality, or tissue loss.
- `6da70b1c`: environmental-only captions (`Fig. 3`, `Table 5`) and the recovery photo (`Fig. 5`) were corrected to `Fig. 6`; `Table 2` and `Table 7` were kept as recovery-rate statistics.
- `2059b598`: rate rows keep `Fig. 3`, `Fig. 4`, and `Fig. 5`; the before/after photo and supplemental table reference were corrected to tissue-regeneration-rate figures.
- `9d6998fc`: `FIG. 2` was kept as the main growth/survival candidate; microbiome-only rows were corrected, while `Table 2` was kept where table contents include coral growth or tissue-loss correlations.

## Per-source Row Counts

- `002a60bc`: 2 rows
- `06ab1757`: 10 rows
- `0ccdd954`: 5 rows
- `2059b598`: 5 rows
- `33d2bc0d`: 5 rows
- `3f852e08`: 10 rows
- `6da70b1c`: 5 rows
- `6f750c49`: 2 rows
- `9d6998fc`: 10 rows
- `a3b88246`: 10 rows
- `d7f996dc`: 5 rows

No clip paths or extraction data were assigned.

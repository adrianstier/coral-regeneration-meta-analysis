# Figure/Table Candidate Audit - Agent 1

Assigned source list indices 001-011 were audited against local PDFs only. Evidence came from `pdftotext -layout`; the Cróquer et al. SciELO PDF required temporary rendered-page visual checks because image/table captions were not exposed by text extraction.

## Counts

| audit_status | count |
|---|---:|
| keep | 36 |
| replace | 43 |
| remove | 15 |
| blocked_missing_pdf | 0 |
| needs_manual_visual_review | 0 |
| rows needing manual visual review flag | 5 |

## Counts by Source

| source | keep | replace | remove | note |
|---|---:|---:|---:|---|
| dde85c3e | 3 | 5 | 0 | Growth should use Fig. 3; regeneration rate should use Fig. 4/Fig. 5. |
| 12e9e864 | 3 | 2 | 5 | Rate captions valid after Roman-label cleanup; no survival/mortality figure/table found. |
| daec544d | 0 | 6 | 0 | Original ranks missed the direct Figure 4/5 wound and tissue-cover captions. |
| 9f7a74ab | 2 | 8 | 0 | Rate should use Fig. 2; survival should use Fig. 3 tissue necrosis. |
| ec19aed9 | 4 | 1 | 5 | Rate rows mostly valid; no survival/mortality outcome figure/table found. |
| 034d4e10 | 0 | 5 | 0 | All original rows were in-text mentions; visual page render found Fig. 2, Fig. 3, Fig. 4, and Table 1. |
| 28b1e816 | 3 | 2 | 0 | Fig. 3/Table 1/Fig. 2 valid for recovery; Table 4 and Fig. 4 are not rate candidates. |
| 3d374a40 | 8 | 7 | 0 | Direct tables are Table 2 for growth, Table 3 for regeneration rate, Fig. 1/Fig. 2 for mortality. |
| c849a042 | 8 | 2 | 0 | Most growth/regeneration-budding captions are valid; rate should prioritize Table 2. |
| ad751939 | 1 | 4 | 5 | Rate should use Table 1 lesion recovery; no survival/mortality figure/table found. |
| e2191f69 | 4 | 1 | 0 | Fig. 1/Fig. 2/Fig. 3/Table 4 valid for regeneration; Table 1 is only background literature. |

## Most Important Corrections

- `034d4e10`: the CSV candidates were all text mentions, not captions. Rendered pages show Fig. 2 and Fig. 3 on PDF page 4, Fig. 4 on page 5, Table 1 on page 6, and Table 3 on page 8. For regeneration rate, Table 1 is the strongest candidate.
- `daec544d`: the ranked Figure 7/Figure 8 rows are chlorophyll or photosynthetic-efficiency captions. Use Figure 4 for wound surface-area recovery and Figure 5 for total colony tissue-cover change.
- `3d374a40`: false positives on page 4 should be redirected to Table 2 for growth, Table 3 for regeneration rate, Fig. 1 for mortality, or Fig. 2 for partial mortality.
- `ad751939`: Table 1 on page 4 is the lesion-recovery table. Table 2/Table 3 are 14C translocation tables, and Fig. 2C is only a panel mention.
- Survival queues for `12e9e864`, `ec19aed9`, and `ad751939` had no valid printed survival/mortality figure/table candidate in the local PDFs, so those rows were marked `remove` with `no_valid_candidate_found`.

## Evidence Notes

- Local PDFs were used from the `local_relpath` entries in `digitization/source_review/FIGURE_SOURCE_REVIEW.csv`.
- No clip paths, panel coordinates, or extraction data were assigned or inferred.
- `needs_manual_visual_review=true` is limited to the Cróquer et al. rows where captions were only verifiable from rendered pages rather than extracted text.

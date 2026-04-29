# Agent 3 Figure/Table Candidate Audit

Scope: source list indices 023-033 from `digitization/source_review/FIGURE_SOURCE_REVIEW.csv`.

All 11 assigned sources had local PDFs available. I audited 56 candidate rows using local PDF text extraction (`pdftotext -layout`/`pdftotext -raw`); for Okubo 2008, I also rendered the relevant table pages to verify the printed table contents where text extraction flattened the tables.

## Counts

| audit_status | count |
| --- | ---: |
| keep | 25 |
| replace | 29 |
| remove | 2 |
| blocked_missing_pdf | 0 |
| needs_manual_visual_review | 0 |

## Source-Level Summary

| source index | source_id prefix | rows | keep | replace | remove | main action |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 023 | d110a8f5 | 4 | 2 | 2 | 0 | Replaced photo-only Fig. 1 candidates with Fig. 3 for growth and Fig. 2 for survival-related surviving-tip output. |
| 024 | 070cf5f2 | 5 | 1 | 4 | 0 | Removed/corrected inline prose hits; original Fig. 4 was from an unrelated neighboring Nature article. |
| 025 | f7335f31 | 5 | 4 | 1 | 0 | Kept regeneration figures/tables; replaced site-map Fig. 1 with Fig. 2. |
| 026 | c84ce087 | 10 | 4 | 6 | 0 | Growth candidates corrected to Fig. 7/Table 3; rate candidates corrected to Fig. 5/Table 2. |
| 027 | 398d01aa | 5 | 5 | 0 | 0 | All candidates were printed and relevant to partial mortality/survival. |
| 028 | f46ad039 | 8 | 1 | 7 | 0 | Growth candidates corrected to Fig. 5A-C; survival candidates corrected to Fig. 2. |
| 029 | 8c205a55 | 1 | 1 | 0 | 0 | Fig. 2 was valid for lesion-recovery slopes. |
| 030 | b2eaa7a6 | 5 | 2 | 3 | 0 | Kept Fig. 1/Fig. 2; replaced physiology figures with direct lesion-recovery Fig. 1. |
| 031 | 9f560a14 | 4 | 2 | 2 | 0 | Kept infection Figures 1-2; replaced literature-review/inline Table 1 hits with Figure 1. |
| 032 | d17e3c0b | 4 | 2 | 0 | 2 | Growth tables kept; rate candidates removed because no printed figure/table reports wound-closure or regeneration rate. |
| 033 | 84a7b2a4 | 5 | 1 | 4 | 0 | Kept Table 3; replaced inline figure references and lesion-characteristic Fig. 2 with Table 1 percent lesion-area reduction. |

## Important Corrections

- Loya 1976 (`070cf5f2`): the rank-1 `Fig. 4` candidate is a real caption, but it belongs to an unrelated adjacent Nature article, not the coral regeneration paper. Corrected to `Fig. 1`/`Fig. 2`.
- Okubo 2008 (`d17e3c0b`): the `rate` queue has no valid printed figure/table candidate. Wound closure timing is reported in prose; Tables 1-2 report new polyps, survival, linear extension, spawning, and growth comparisons.
- Miller and Hay 1998 (`f46ad039`): `Fig. 5A` candidate text was an inline body reference. The printed growth caption is `Fig. 5A-C`; the printed survival result is `Fig. 2`.
- Oren et al. 1997 (`84a7b2a4`): most figure-label candidates were inline references. The direct rate table is `Table 1` with percent reduction of lesion areas across monthly intervals.
- Meesters et al. 1994 (`c84ce087`): several growth/rate candidates were methodological controls or growth-only tables. The direct growth response is `Fig. 7`/`Table 3`; the direct regeneration-rate evidence is `Fig. 5`/`Table 2`.

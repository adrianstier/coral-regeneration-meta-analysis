# Figure/Table Candidate Audit - Agent 2

Assigned source-list indices: 012-022. Local PDFs only.

## Counts

- Total candidate rows audited: 79
- keep: 24
- replace: 46
- remove: 9
- blocked_missing_pdf: 0
- needs_manual_visual_review: 0

## Key Corrections

- `2b8676ad` (Hall thesis): most original candidates used table-of-contents hits or truncated labels. Corrected labels/pages include `Table 3.4` p74, `Figure 4.2` p89, `Table 4.1` p90, `Table 4.4` p94, `Figure 5.2` p109, `Table 5.1` p111, `Table 5.2` p112, `Table 5.3` p113, and `Figure 5.3` p115.
- `45fcfd8e` (Jayewardene et al. 2009): no printed growth-response figure/table was found; all growth candidates were removed. Survival candidates were redirected to `Fig. 6` p7, the over-predation probability figure.
- `a67392b0` (Lenihan et al. 2015): growth candidates `FIG. 2`, `FIG. 3`, and `FIG. 5` were valid; no printed survival-response candidate was found, so all survival candidates were removed.
- `5f4a560f` (Horwitz and Fine 2014): the `Fig. 2` p4 row was an in-text/methods reference; the actual printed `Fig. 2` caption is on p5. `Fig. 4d` and `Table 1` were not rate-response candidates.
- `58b15640` and `40359446`: lesion-healing/rate rows were separated from growth rows where the queue had mixed growth and healing candidates.

## Evidence Method

Captions and pages were checked with `pdftotext -layout` and spot-checked with `pdftotext -raw`/`pdfinfo` against the local PDFs listed in `digitization/source_review/FIGURE_SOURCE_REVIEW.csv`. Table-of-contents entries and narrative in-text references were not counted as valid printed figure/table captions.

# Agent B — Resolve no_valid_candidate_found rows (§3b)

## Context

Coral regeneration meta-analysis at `/Users/adrianstier/coral-regeneration-meta-analysis/`. The digitization queue at `pipeline/DIGITIZATION_FIGURE_QUEUE.csv` has 86 rows; 10 of them are marked `queue_audit_status=no_valid_candidate_found`, meaning a previous round of 5 agent reviewers could not find a figure or table in the cited paper that reports the response variable (rate / growth / survival / reproduction / mechanism). Each of these 10 needs a final judgement: did the agents miss something, or is the paper actually unable to contribute to that response bin?

## Your assignment

For each of the 10 rows in `work/wave_2026_05_21/agent_B_input.csv`:

1. Open the local PDF at `local_relpath`.
2. The `response_type` column tells you what kind of figure/table to look for: `rate` → wound area or extent over time; `growth` → calcification or linear extension change; `survival` → mortality counts/percent; `reproduction` → fecundity/eggs/spawning; `mechanism` → histology/immunity/translocation.
3. Look in every figure caption (`grep -i "Fig\." `) AND every table caption (`grep -i "^Table"`) for content matching the response.
4. Decide one of:
   - `candidate_recovered` — you found a usable figure/table the prior agents missed. Provide `recovered_candidate_type` (figure | table), `recovered_candidate_label`, `recovered_candidate_page`, and a snippet of the caption.
   - `downgrade_to_not_for_extraction` — confirmed no usable visual in the paper for this response. Provide a clear reason (e.g., "Paper reports only colony-level survival as one number in Discussion; no figure/table.").
   - `wrong_response_assignment` — the paper does report something visual but for a different response than assigned. State which response it actually contributes to.

## Output

`work/wave_2026_05_21/outputs/B/no_valid_candidate_resolutions.csv` with these columns:
`queue_id, source_id, paper_title, response_type, resolution_status, recovered_candidate_type, recovered_candidate_label, recovered_candidate_page, caption_snippet, reason`.

Plus `work/wave_2026_05_21/outputs/B/REPORT.md` with a per-paper summary.

## Constraints

- Do NOT modify any file outside `work/wave_2026_05_21/outputs/B/`.
- Cite caption text verbatim (short quote) when proposing a recovered candidate.
- If a figure caption *mentions* the response variable but the actual data are buried in supplementary, flag it as `candidate_in_supplementary` (a new status) and provide the supplementary filename if visible.

## Working directory

`/Users/adrianstier/coral-regeneration-meta-analysis/`

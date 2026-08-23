# Parallel Worker Wave — 2026-05-21

Historical note, updated 2026-08-03: these briefs were dispatched against an older 77-primary-row covariate table. The current primary pool has 76 rows after Cox 2014 was reclassified to `exclude_review`; use current source-of-truth tables before launching any new worker wave.

Dispatched after OUTSTANDING_ISSUES.md was produced. Each subagent's brief
lives in this directory; outputs go to `work/wave_2026_05_21/outputs/<agent>/`.

Once all workers complete I'll merge their outputs back into the main
extraction / covariate / audit tables and re-run `tools/build_pipeline_outputs.py`.

## Worker assignments

| Agent | Task | Input file | Output target |
| --- | --- | --- | --- |
| A | §4 legacy extraction provenance fill (29 rows) | `agent_A_brief.md`, `agent_A_input.csv` | `outputs/A/legacy_provenance.csv` + report |
| B | §3b resolve 10 no_valid_candidate_found queue rows | `agent_B_brief.md`, `agent_B_input.csv` | `outputs/B/no_valid_candidate_resolutions.csv` + report |
| C | §5a perimeter_mm + rel_wound_size — primary batch 1 (~25 papers) | `agent_C_brief.md`, `agent_C_input.csv` | `outputs/C/geometry_batch_1.csv` + report |
| D | §5a perimeter_mm + rel_wound_size — primary batch 2 (~25 papers) | `agent_D_brief.md`, `agent_D_input.csv` | `outputs/D/geometry_batch_2.csv` + report |
| E | §5a perimeter_mm + rel_wound_size — primary batch 3 (~26 papers) | `agent_E_brief.md`, `agent_E_input.csv` | `outputs/E/geometry_batch_3.csv` + report |

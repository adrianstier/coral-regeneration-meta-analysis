# PROJECT_AUDIT.md — coral-regeneration-meta-analysis

Read-only health rubric for the coral-regeneration / density-dependence meta-analysis.
Auditor inspects against this; it does not modify repo code/content.

## Generic checklist
- [ ] README present, describes goal + how to rebuild pipeline outputs
- [ ] LICENSE present (open-access database is a stated objective → license matters)
- [ ] .gitignore covers `.DS_Store`, `__pycache__/`, transient artifacts
- [ ] No secrets/API keys/tokens committed (Zotero/Canvas keys must stay in env)
- [ ] Working tree clean; no stale uncommitted regenerated outputs
- [ ] Local branch not drifted far ahead of origin (unpushed work is at risk)
- [ ] No large/transient dirs tracked that should be ignored (`work/`, `archive/`)

## Focal checklist (systematic review / meta-analysis)
- [ ] Screened-studies dataset present + documented (SCREENING_LOG_FINAL.csv + rationale)
- [ ] Inclusion/exclusion criteria recorded (INCLUSION_EXCLUSION_RATIONALE.md)
- [ ] PRISMA counts documented and internally consistent across docs
- [ ] PRISMA_COUNTS.md / pipeline outputs fresh vs generating scripts (`tools/*.py`)
- [ ] Effect-size extraction tables present with defined schema (data/extraction/*)
- [ ] Effect-size CALC script exists + runs (escalc/lnRR/Hedges') — meta-analysis stage
- [ ] metafor/brms MODEL script exists + reproduces — meta-analysis stage
- [ ] Forest + funnel plots regenerate and are fresh vs scripts — meta-analysis stage
- [ ] Data provenance recorded (source IDs, PDF hashes, digitization audit trail)
- [ ] Pipeline reproducible: documented rebuild commands + passing test suite

## Known issues
- Project is at the screening/extraction/digitization stage. No R, no
  metafor/brms model, no escalc/effect-size calc, no forest/funnel plots yet.
  These focal items are EXPECTED-ABSENT (warn, not fail) at this stage.
- OUTSTANDING_ISSUES.md tracks open blockers (Zotero hygiene, no-valid-candidate
  figure rows, crop QA, legacy provenance, covariate gaps). Treat as the
  project's own TODO, not audit failures.
- Python tools (build_*/finalize_*) are infra/plotting-class scripts; covered by
  tests/test_regressions.py collectively — no per-script test required.

## Escalation rules
- HIGH: committed secret/key/token; data-loss risk (long unpushed history + dirty tree)
- MEDIUM: PRISMA counts inconsistent across docs; outputs staler than scripts;
  effect-size/model/plot scripts present but failing once analysis stage begins
- LOW: missing LICENSE; dirty regenerated outputs; untracked artifacts; missing PDFs
- Suppress as FALSE POSITIVE: this PROJECT_AUDIT.md as a dirty change; figure-caption
  text matching secret regexes; absence of R/metafor at pre-analysis stage.

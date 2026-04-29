# Coral Regeneration Meta-Analysis

## Goal
The primary goal of this project is to systematically review and meta-analyze coral regeneration after wounding, focusing on healing rates, coral traits, environmental influences, wound types, and geographic patterns.

### Objectives
- **Quantify average coral healing rates** across species, environments, and wound types.
- **Understand how coral traits** (taxonomy, morphology, tissue type) shape regeneration outcomes.
- **Test specific hypotheses** about environmental stressors and healing success.
- **Identify knowledge gaps** to guide future research priorities.
- **Create an open-access database** of coral healing metrics and metadata.

### Project Resources
- **Protocol:** See [PLAN.md](./PLAN.md) for the full meta-analysis protocol.
- **Extraction pipeline:** See [docs/pipeline/EXTRACTION_PIPELINE.md](./docs/pipeline/EXTRACTION_PIPELINE.md) for the source-of-truth hierarchy, PRISMA rebuild command, extraction workplan, and figure clipping requirements.
- **Generated QA outputs:** Rebuild `pipeline/` with `python3 tools/build_pipeline_outputs.py`, then rebuild extraction-review queues with `python3 tools/build_extraction_review_artifacts.py`; review `pipeline/PIPELINE_QA_REPORT.md` and `digitization/source_review/EXTRACTION_REVIEW_SUMMARY.md` before using manuscript counts or extracted values.
- **Instructions:** See [GEMINI.md](./GEMINI.md) for AI assistance guidelines.

---
*Follow PRISMA guidelines for all systematic review steps.*

<!-- lab-xref -->
## Lab cross-reference

**Drive folder:** `…/Coral-Regeneration/Projects/15. Meta_Analysis_Healing_Growth_Reproduction_2025/` — Project **P15** (PRISMA meta-analysis). Feeds synthesis stats into the regeneration review (Manuscript **A**, repo [`adrianstier/coral-regen-review`](https://github.com/adrianstier/coral-regen-review)).

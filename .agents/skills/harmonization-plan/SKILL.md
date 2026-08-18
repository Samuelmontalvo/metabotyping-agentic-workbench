---
name: harmonization-plan
description: Use when turning reviewed crosswalk results into a deterministic, review-gated ETL plan.
---

# Purpose
Separate accepted transformations from review-required and rejected mappings before any harmonized output is produced.

# Inputs
- `data/extracted/crosswalk.csv`
- `data/review/human_review_queue.csv`

# Steps
1. Bucket mappings by review status.
2. List approved identity or approved unit transforms.
3. List mappings requiring review.
4. List rejected and impossible harmonizations.
5. Document validation checks and failure conditions.

# Outputs
- `reports/aim2_harmonization_report.md`

# Validation Checks
- No rejected mapping appears in approved transforms.
- No review-required mapping enters deterministic ETL.

# Failure Modes
- Human decisions are missing.
- Transform is not in the approved transform registry.

# Human-Review Triggers
- Any mapping with `requires_human_review`.
- Any proposed unit conversion not already approved.

# Evaluation Gates
- FAIR: plans must retain source provenance, variable metadata, output formats, and reusable validation rules.
- Reproducibility: deterministic ETL must be regenerated only from declared accepted mappings and approved transforms.
- Critical evidence: distinguish approved transformations from proposals; do not implement unreviewed or rejected harmonizations.
- Skill quality rubric: pass only if inputs, outputs, validation checks, failure conditions, and human decisions are all explicit.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/harmonization/harmonization_plan.py`.

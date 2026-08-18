---
name: define-inclusion-criteria
description: Use when translating a metabolomics discovery question into auditable inclusion, enrichment, and exclusion criteria.
---

# Purpose
Define strict human metabolomics inclusion criteria and softer enrichment criteria for exercise, actigraphy, physical activity, genetics, CPET, body composition, and diet.

# Inputs
- User query or `data/examples/pilot_query.txt`
- Existing criteria JSON when refining a prior run

# Steps
1. Require `human` and `metabolomics`.
2. Extract preferred terms from the query.
3. Add complementary terms for partial modality overlap and enrichment datasets.
4. Add exclusions for animal-only, cell-only, and no-metabolomics records.
5. Save criteria as structured JSON.

# Outputs
- `data/extracted/criteria.json`

# Validation Checks
- Required terms include `human` and `metabolomics`.
- Exclusions include animal-only and no-metabolomics cases.
- Preferred terms are scientific modalities, not vague search words.

# Failure Modes
- Query is too broad to distinguish direct matches from enrichment candidates.
- Query requests participant-level data not present in synthetic fixtures.

# Human-Review Triggers
- The reviewer wants to change required terms.
- A new modality should alter ranking weights.

# Evaluation Gates
- FAIR: criteria must preserve metadata needs for findable datasets, accessible repository records, interoperable modality labels, and reusable provenance.
- Reproducibility: output must be regenerated from the declared query and deterministic parser rules.
- Critical evidence: distinguish explicit query terms from inferred complementary terms; do not promote inferred terms into required terms without human review.
- Skill quality rubric: pass only if required terms, preferred terms, exclusions, validation checks, and review triggers are all present.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/discovery/criteria.py`.

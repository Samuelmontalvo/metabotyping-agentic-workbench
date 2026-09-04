---
name: quality-scoring
description: Use when scoring dataset quality, metadata completeness, modality coverage, and harmonization feasibility.
---

# Purpose
Produce transparent 0-1 quality subscores and an overall metadata-readiness score for candidate datasets, on a scale defined for human MoTrPAC-style comparison planning.

# Inputs
- `data/extracted/dataset_cards.json`
- `data/extracted/study_cards.json`
- Optional custom weights

# Steps
1. Read the study card's three-valued `human` evidence and assign `scope_status`: `in_scope_human`, `out_of_scope_non_human`, or `human_status_unknown`.
2. Score study design rigor.
3. Score metadata completeness.
4. Score metabolomics and domain-specific modality quality.
5. Score temporal alignment and harmonization feasibility.
6. Compute the weighted overall score; withhold it (`null`) for a documented non-human study and keep the subscores visible, and flag an undocumented human status rather than scoring it down.

# Outputs
- `data/extracted/quality_scores.json`
- `reports/aim3_evaluation_report.md`

# Validation Checks
- All subscores are between 0 and 1.
- Overall score uses documented weights.
- `scope_status` is one of the three declared values and `overall_score` is null exactly when the study is documented non-human; every row validates against `schemas/quality_score.schema.json` before it is written.

# Failure Modes
- Dataset cards are missing required fields.
- Weights do not sum to interpretable coverage.

# Human-Review Triggers
- A high-value dataset scores poorly only because metadata was not machine-readable.
- Weight changes alter study ranking.
- A study is `human_status_unknown`: the triage score is reported, but the MoTrPAC comparison tier stays not feasible until human evidence is documented.

# Evaluation Gates
- FAIR: scores must reflect metadata completeness, codebook availability, accessibility, interoperability, and reusable provenance.
- Reproducibility: subscores and overall score must be regenerated from declared weights and metadata cards.
- Critical evidence: distinguish absent modality, documented absence, and missing evidence; do not over-penalize restricted but well-described metadata. Apply the same three-way distinction to human-participant evidence: documented non-human is out of scope, undocumented is flagged, and neither is silently scored as if human.
- Skill quality rubric: pass only if every subscore has transparent inputs, weights, rationale, and bounded 0-1 values.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/evaluation/quality_scoring.py`.

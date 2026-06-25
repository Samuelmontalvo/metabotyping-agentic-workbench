---
name: quality-scoring
description: Use when scoring dataset quality, metadata completeness, modality coverage, and harmonization feasibility.
---

# Purpose
Produce transparent 0-1 quality subscores and an overall score for candidate datasets.

# Inputs
- `data/extracted/dataset_cards.json`
- `data/extracted/study_cards.json`
- Optional custom weights

# Steps
1. Score study design rigor.
2. Score metadata completeness.
3. Score metabolomics and domain-specific modality quality.
4. Score temporal alignment and harmonization feasibility.
5. Compute weighted overall score.

# Outputs
- `data/extracted/quality_scores.json`
- `reports/aim3_evaluation_report.md`

# Validation Checks
- All subscores are between 0 and 1.
- Overall score uses documented weights.

# Failure Modes
- Dataset cards are missing required fields.
- Weights do not sum to interpretable coverage.

# Human-Review Triggers
- A high-value dataset scores poorly only because metadata was not machine-readable.
- Weight changes alter study ranking.

# Evaluation Gates
- FAIR: scores must reflect metadata completeness, codebook availability, accessibility, interoperability, and reusable provenance.
- Reproducibility: subscores and overall score must be regenerated from declared weights and metadata cards.
- Critical evidence: distinguish absent modality, documented absence, and missing evidence; do not over-penalize restricted but well-described metadata.
- Skill quality rubric: pass only if every subscore has transparent inputs, weights, rationale, and bounded 0-1 values.

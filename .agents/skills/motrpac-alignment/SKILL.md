---
name: motrpac-alignment
description: Use when evaluating whether candidate datasets can support MoTrPAC-like replication analyses.
---

# Purpose
Score replication feasibility using MoTrPAC-relevant human, omics, exercise, timing, platform, and phenotype criteria.

# Inputs
- `data/extracted/dataset_cards.json`
- `data/extracted/study_cards.json`

# Steps
1. Check human participants.
2. Check metabolomics availability.
3. Check exercise/activity phenotype.
4. Check biospecimen timing, sample matrix, and assay platform.
5. Count genetics only when it is available or explicitly listed as documented absent; treat missing documentation as unknown.
6. Check CPET, body composition, diet, and variable dictionary availability.
7. Apply human-participant evidence as a hard gate, then assign high, moderate, low, or not feasible tier.

# Outputs
- `reports/motrpac_alignment_report.md`
- `reports/motrpac_alignment.json`

# Validation Checks
- Score is based on explicit criteria count.
- Missing elements are listed.

# Failure Modes
- Dataset lacks exercise/activity phenotype.
- Biospecimen timing cannot support replication.

# Human-Review Triggers
- Dataset is near a tier boundary.
- Protocol evidence may upgrade or downgrade feasibility.

# Evaluation Gates
- FAIR: alignment must inspect metadata completeness, sample matrix, assay platform, timing, codebooks, and provenance.
- Reproducibility: tier assignment must be regenerated from declared MoTrPAC-style criteria and deterministic thresholds.
- Critical evidence: distinguish a missing modality from a documented absent modality; do not claim replication feasibility from omics alone.
- Skill quality rubric: pass only if met criteria, missing elements, score, tier, and rationale are all reported.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/evaluation/motrpac_alignment.py`.

---
name: grant-aims-refiner
description: Use when refining the workbench outputs into grant aims, milestones, deliverables, and evaluation criteria.
---

# Purpose
Translate MVP evidence into clearer aims for dataset discovery, meta-harmonization, and multi-domain evaluation.

# Inputs
- Pilot reports
- Benchmark results
- Human review packet
- User-provided grant context

# Steps
1. Preserve the three-aim structure.
2. Identify reproducible deliverables and benchmarks.
3. State human-review gates as scientific safeguards.
4. Separate MVP evidence from future live-repository work.

# Outputs
- Draft aim refinements
- Milestone and evaluation language

# Validation Checks
- Claims are supported by generated artifacts.
- Future work does not imply completed live data integration.

# Failure Modes
- Overstates automation as expert curation.
- Hides review gates as implementation details.

# Human-Review Triggers
- Any change to scientific scope, evaluation endpoints, or funding claims.

# Evaluation Gates
- FAIR: grant language must preserve dataset-access, metadata, provenance, and reuse commitments as scientific deliverables.
- Reproducibility: aims must be regenerated from declared pilot reports, benchmark metrics, and human-review artifacts as evidence.
- Critical evidence: distinguish completed MVP capabilities, missing evidence, and proposed future live-repository integrations; do not overclaim automation.
- Skill quality rubric: pass only if aims, milestones, evaluation criteria, risks, and human-review safeguards are explicit.

# Implementation
- Execution status: agent-only scientific synthesis; no deterministic module is claimed, and all aims require author review.

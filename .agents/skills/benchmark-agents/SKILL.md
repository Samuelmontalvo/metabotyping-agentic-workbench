---
name: benchmark-agents
description: Use when comparing deterministic or agentic outputs against synthetic expert-curated fixtures.
---

# Purpose
Benchmark mapping and scoring outputs against local gold standards.

# Inputs
- `data/extracted/crosswalk.csv`
- `data/examples/expert_variable_mappings.csv`
- `data/extracted/quality_scores.json`
- `data/examples/expert_quality_scores.csv`

# Steps
1. Compare predicted candidate mappings with expert non-rejected candidates.
2. Compute candidate precision, recall, and F1 with explicit denominators.
3. Separately compute automatic-accept precision/recall and unsafe-auto-accept rate.
4. Compute review-required capture and exact review-status accuracy.
5. Compute quality-score agreement within tolerance over gold studies not declared out of scope, and scope-status accuracy over gold studies with a declared `scope_status`; a study the expert declares out of scope is compared on scope, never on a number.
6. Render benchmark report.

# Outputs
- `data/extracted/benchmark_results.json`
- `reports/benchmark_report.md`

# Validation Checks
- Candidate and automatic-accept metrics define distinct denominators.
- Unsafe automatic accepts are counted even when the proposed mapping is a plausible review candidate.
- Rejected expert mappings are not counted as positives.
- A withheld predicted score (`null`) is accepted only for a row declared `out_of_scope_non_human`; any other null fails closed before output.

# Failure Modes
- Predicted files are stale relative to fixtures.
- Expert fixture schema changes.

# Human-Review Triggers
- Benchmark disagreement reflects a possible expert fixture error.
- Tolerance should change for a new benchmark phase.

# Evaluation Gates
- FAIR: benchmark artifacts must preserve predicted source, expert source, metric definitions, and reusable denominators.
- Reproducibility: metrics must be regenerated from declared predicted and gold-standard files without hidden state.
- Critical evidence: distinguish model error, missing evidence, and fixture ambiguity; do not report aggregate scores without denominator context.
- Skill quality rubric: pass only if candidate precision/recall/F1, auto-accept precision/recall, unsafe-accept rate, review capture, status accuracy, quality agreement, scope-status accuracy, and disagreement review are documented.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/evaluation/benchmark.py`.

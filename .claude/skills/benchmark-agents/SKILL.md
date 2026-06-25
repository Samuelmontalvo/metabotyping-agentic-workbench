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
1. Compare predicted positive mappings with expert positives.
2. Compute precision, recall, and F1.
3. Compute review-status accuracy.
4. Compute quality-score agreement within tolerance.
5. Render benchmark report.

# Outputs
- `data/extracted/benchmark_results.json`
- `reports/benchmark_report.md`

# Validation Checks
- Metrics define their denominator.
- Rejected expert mappings are not counted as positives.

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
- Skill quality rubric: pass only if precision, recall, F1, accuracy, quality agreement, and disagreement review are documented.

---
name: human-review-packet
description: Use when packaging uncertain harmonization decisions and scientific risks for human adjudication.
---

# Purpose
Create a concise packet for expert review of uncertain mappings, mirages, and missing metadata.

# Inputs
- `data/review/human_review_queue.csv`
- Crosswalk evidence
- Mirage flags

# Steps
1. List each review-required or rejected mapping.
2. Explain the scientific reason for review.
3. Separate overrideable concerns from hard exclusions.
4. Provide reviewer instructions.

# Outputs
- `reports/human_review_packet.md`

# Validation Checks
- Each review item has a concrete decision question.
- VO2max/VO2peak items call out endpoint evidence.

# Failure Modes
- Review packet repeats raw data without decision framing.
- Accepted mappings are mixed with uncertain mappings.

# Human-Review Triggers
- Always triggered for this skill.

# Evaluation Gates
- FAIR: review packets must preserve source metadata, provenance, access status, and reusable decision context.
- Reproducibility: queue contents must be regenerated from declared crosswalk statuses and mirage flags.
- Critical evidence: distinguish overrideable uncertainty from hard incompatibility; do not ask reviewers vague questions.
- Skill quality rubric: pass only if every item has a concrete decision, evidence, risk, and expected reviewer action.

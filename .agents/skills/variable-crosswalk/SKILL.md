---
name: variable-crosswalk
description: Use when proposing confidence-scored cross-study variable mappings with scientific guardrails.
---

# Purpose
Map source variables to common variables while preventing unsafe name-only harmonization.

# Inputs
- `data/examples/mock_variable_dictionary.csv`
- `data/extracted/variable_inventory.csv`
- Synonym dictionary in `harmonization/crosswalk.py`

# Steps
1. Normalize source names and labels.
2. Match exact names and curated synonyms.
3. Check units, modality, and timing.
4. Apply the VO2max/VO2peak guardrail.
5. Assign confidence and review status.

# Outputs
- `data/extracted/crosswalk.csv`
- `data/extracted/crosswalk.json`

# Validation Checks
- Accepted mappings have confidence >= 0.90.
- Review-required mappings are not ETL-ready.
- Rejected mappings include evidence.

# Failure Modes
- Unit is missing or incompatible.
- Source variable has ambiguous biological meaning.

# Human-Review Triggers
- Confidence is between 0.40 and 0.89.
- VO2peak is proposed as VO2max.
- Unit conversion requires domain confirmation.

# Evaluation Gates
- FAIR: mappings must preserve source variable metadata, units, timing, modality, and provenance for reusable harmonization.
- Reproducibility: confidence and review status must be regenerated from declared synonym, unit, timing, and modality rules.
- Critical evidence: distinguish equivalent, related, and weak evidence; do not accept mappings based only on names.
- Skill quality rubric: pass only if accepted, review-required, and rejected outcomes all have explicit evidence and scores.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/harmonization/crosswalk.py`.

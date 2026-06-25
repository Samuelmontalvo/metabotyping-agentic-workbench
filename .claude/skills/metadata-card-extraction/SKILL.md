---
name: metadata-card-extraction
description: Use when extracting study cards, dataset cards, and variable cards from synthetic fixtures or reviewed local CSVs.
---

# Purpose
Create auditable metadata cards that preserve source provenance and distinguish study-level from dataset-level evidence.

# Inputs
- Publication CSV
- Repository CSV
- Variable dictionary CSV

# Steps
1. Build study cards from publication records.
2. Build dataset cards from repository records.
3. Build variable cards from source dictionaries.
4. Validate required fields against local schemas.
5. Save combined and per-study artifacts.

# Outputs
- `data/extracted/study_cards.json`
- `data/extracted/dataset_cards.json`
- `data/extracted/variable_cards.json`
- `data/extracted/variable_inventory.csv`

# Validation Checks
- Cards include source paths and row keys.
- Missing values use `unknown`, `not_reported`, or `not_available`.

# Failure Modes
- Codebooks use inconsistent units or timing labels.
- Publication and repository identifiers do not align.

# Human-Review Triggers
- A card contains conflicting modality or timing evidence.
- A variable has insufficient description for harmonization.

# Evaluation Gates
- FAIR: cards must carry machine-readable metadata, stable identifiers when available, reusable provenance, and standard modality names.
- Reproducibility: extraction must be regenerated from declared publication, repository, and variable dictionary inputs.
- Critical evidence: distinguish missing, not reported, and unknown fields; do not fill gaps with assumptions.
- Skill quality rubric: pass only if study, dataset, and variable cards each include validation checks and provenance.

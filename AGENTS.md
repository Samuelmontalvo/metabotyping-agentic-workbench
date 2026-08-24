# Codex Project Instructions

This repository is an offline, synthetic-data MVP for a human-in-the-loop metabolomics curation and harmonization workbench.

## Operating Principles

- Preserve provenance for every extracted study, dataset, and variable.
- Prefer deterministic Python logic over ad hoc free-text decisions.
- Treat agent outputs as reviewable scientific artifacts, not ground truth.
- Never merge variables only because names look similar.
- Route uncertain mappings to human review.
- Do not require network access or API keys for the MVP.
- Use synthetic/mock data for the offline MVP and its tests; real public records are confined to `data/live/` and `reports_live/`.
- Keep network access inside the declared allowlist enforced by `tests/test_network_boundary.py`; no other module, script, or test may import a network client.
- The allowlist is `scripts/fetch_live_records.py`, `scripts/volcano_compare.py`, `src/metabotyping_agentic/live_sources/literature_search.py`, `src/metabotyping_agentic/live_sources/metabolomics_workbench.py`, and `src/metabotyping_agentic/live_sources/motrpac_volcano_compare.py`. Literature retrieval (Europe PMC, PubMed, Crossref, bioRxiv/medRxiv) stays inside `literature_search.py`; screening and appraisal run offline in `src/metabotyping_agentic/discovery/literature_review.py`.

## Scientific Scope

The workbench supports three aims:

1. Discover and recommend studies/datasets with human metabolomics plus exercise, actigraphy, physical activity, genetics, CPET, body composition, diet, or adjacent phenotypes.
2. Extract metadata cards, variable inventories, confidence-scored crosswalks, and review-gated harmonization plans.
3. Score metadata-backed dataset readiness for curation triage and evaluate
   MoTrPAC-like comparison-planning metadata readiness.

## Review Rules

- Mark direct exercise/activity/metabolomics/genetics matches as high priority when repository metadata and codebooks are available.
- Flag mirages when accessions, metadata, codebooks, data files, assay platforms, or biospecimen timing are missing.
- Keep `vo2max` machine-readable and use `VO₂max` in human reports.
- Do not automatically collapse `VO2max` and `VO2peak`; require protocol/end-point evidence.
- Treat domain-review packets as advisory evidence inventories: require human adjudication and never emit executable actions or pooling permission.

## Useful Commands

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli run-pilot --out reports
PYTHONPATH=src python3 scripts/evaluate_skills.py
PYTHONPATH=src python3 scripts/evaluate_scientific_readiness.py
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Skill Evaluation

Evaluate `.agents/skills` and `.claude/skills` with `scripts/evaluate_skills.py`. The rubric is based on local LabClaw guidance for FAIR data, reproducibility, scientific critical thinking, human-review gates, and structured scoring. Keep `docs/skill_evaluation_report.md` current after skill edits.

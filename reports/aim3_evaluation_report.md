# Aim 3 Evaluation Report

## Dataset-Readiness Scores

| study_id | scope_status | overall_score | study_design_rigor | metadata_completeness | metabolomics_quality | harmonization_feasibility |
| --- | --- | --- | --- | --- | --- | --- |
| SYN-METEX-GEN | in_scope_human | 0.885 | 1.0 | 1.0 | 1.0 | 0.85 |
| SYN-ACTI-MET | in_scope_human | 0.772 | 1.0 | 1.0 | 1.0 | 0.85 |
| SYN-OMICS-GEN | in_scope_human | 0.629 | 0.8 | 0.857 | 0.8 | 0.85 |
| SYN-EXER-NODATA | in_scope_human | 0.484 | 0.9 | 0.143 | 0.4 | 0.25 |
| SYN-ANIMAL-MET | out_of_scope_non_human | not reported (out of scope) | 0.7 | 1.0 | 1.0 | 0.85 |
| SYN-MET-NOCODEBOOK | in_scope_human | 0.546 | 0.7 | 0.857 | 1.0 | 0.25 |
| SYN-CPET-RICH | in_scope_human | 0.818 | 1.0 | 1.0 | 1.0 | 0.85 |
| SYN-MOTRPAC-LIKE | in_scope_human | 0.9 | 1.0 | 1.0 | 1.0 | 0.85 |
| SYN-DIET-BODY | in_scope_human | 0.66 | 0.8 | 1.0 | 1.0 | 0.85 |
| SYN-RESTRICTED-META | in_scope_human | 0.606 | 0.8 | 0.857 | 0.8 | 0.85 |


## Interpretation

Scores are transparent, metadata-backed rule-based subscores from 0 to 1. They are curation and harmonization triage signals, not validated judgments of overall study quality, risk of bias, assay validity, or biological evidence strength.

The scale is defined for human MoTrPAC-style comparison planning. A study documented as non-human is out of scope and receives no overall score (its subscores stay visible); a study whose human-participant status is not documented keeps a triage score and is flagged `human_status_unknown`, because undocumented is not documented absent.

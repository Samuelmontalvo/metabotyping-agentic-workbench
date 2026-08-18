# Human Review Packet

## Queue

| source_study | source_variable | proposed_common_variable | confidence | human_review_reason |
| --- | --- | --- | --- | --- |
| SYN-ACTI-MET | daily_steps | steps_per_day | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-ACTI-MET | mvpa_min | mvpa_minutes | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-ACTI-MET | total_fat_mass | fat_mass | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-OMICS-GEN | participant_age | age | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-OMICS-GEN | glucose_fasting | fasting_glucose | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-OMICS-GEN | fasting_insulin | insulin | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-EXER-NODATA | peak_vo2 | vo2max | 0.76 | Confirm exercise test protocol and whether endpoint was VO2max or VO2peak. |
| SYN-CPET-RICH | vo2peak | vo2max | 0.78 | Confirm exercise test protocol and whether endpoint was VO2max or VO2peak. |
| SYN-CPET-RICH | total_lean_mass | lean_mass | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-DIET-BODY | body_mass_index | bmi | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-DIET-BODY | dxa_lean_mass | lean_mass | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-RESTRICTED-META | gender | sex | 0.88 | Human review required because confidence or metadata completeness is insufficient. |
| SYN-MET-NOCODEBOOK | metab_feature_001 | not_mapped | 0.2 | Rejected by deterministic guardrail; only override with documented expert rationale. |
| SYN-DIET-BODY | diet_score | not_mapped | 0.2 | Rejected by deterministic guardrail; only override with documented expert rationale. |


## Reviewer Instructions

- Accept only when biological meaning, unit, modality, timing, and protocol are sufficiently documented.
- Reject mappings that rely only on superficial name similarity.
- Require protocol confirmation before treating VO₂max and VO₂peak as equivalent.
- Approved decisions may be converted into deterministic ETL; review-required decisions may not.

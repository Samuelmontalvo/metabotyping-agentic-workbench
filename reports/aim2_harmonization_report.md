# Aim 2 Harmonization Plan

## Inputs

- Crosswalk: `data/extracted/crosswalk.csv`
- Synthetic source variable dictionary: `data/examples/mock_variable_dictionary.csv`

## Outputs

- Harmonized analysis table: `data/harmonized/harmonized_variables.csv`
- Human review queue: `data/review/human_review_queue.csv`
- Audit log: `data/harmonized/harmonization_audit.json`

## Approved Transformations

| source_study | source_variable | proposed_common_variable | transform | confidence |
| --- | --- | --- | --- | --- |
| SYN-METEX-GEN | vo2max | vo2max | identity | 0.96 |
| SYN-METEX-GEN | age | age | identity | 0.96 |
| SYN-METEX-GEN | sex | sex | identity | 0.96 |
| SYN-METEX-GEN | bmi | bmi | identity | 0.96 |
| SYN-METEX-GEN | fasting_glucose | fasting_glucose | identity | 0.96 |
| SYN-CPET-RICH | insulin | insulin | identity | 0.96 |
| SYN-MOTRPAC-LIKE | vo2max | vo2max | identity | 0.96 |
| SYN-MOTRPAC-LIKE | steps_per_day | steps_per_day | identity | 0.96 |
| SYN-MOTRPAC-LIKE | mvpa_minutes | mvpa_minutes | identity | 0.96 |
| SYN-MOTRPAC-LIKE | lean_mass | lean_mass | identity | 0.96 |
| SYN-MOTRPAC-LIKE | fat_mass | fat_mass | identity | 0.96 |
| SYN-RESTRICTED-META | age | age | identity | 0.96 |


## Proposed Mappings Requiring Review

| source_study | source_variable | proposed_common_variable | confidence | evidence |
| --- | --- | --- | --- | --- |
| SYN-ACTI-MET | daily_steps | steps_per_day | 0.88 | Matched steps_per_day via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-ACTI-MET | mvpa_min | mvpa_minutes | 0.88 | Matched mvpa_minutes via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-ACTI-MET | total_fat_mass | fat_mass | 0.88 | Matched fat_mass via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-OMICS-GEN | participant_age | age | 0.88 | Matched age via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-OMICS-GEN | glucose_fasting | fasting_glucose | 0.88 | Matched fasting_glucose via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-OMICS-GEN | fasting_insulin | insulin | 0.88 | Matched insulin via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-EXER-NODATA | peak_vo2 | vo2max | 0.76 | Matched vo2max via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is missing. VO2peak and VO2max are not accepted as equivalent without protocol evidence. |
| SYN-CPET-RICH | vo2peak | vo2max | 0.78 | Matched vo2max via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. VO2peak and VO2max are not accepted as equivalent without protocol evidence. |
| SYN-CPET-RICH | total_lean_mass | lean_mass | 0.88 | Matched lean_mass via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-DIET-BODY | body_mass_index | bmi | 0.88 | Matched bmi via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-DIET-BODY | dxa_lean_mass | lean_mass | 0.88 | Matched lean_mass via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. |
| SYN-RESTRICTED-META | gender | sex | 0.78 | Matched sex via name_or_label_synonym. Source variable is a synonym or related label. Unit is compatible. Modality is compatible. Timing is reported. Gender and sex are distinct constructs; confirm whether the source variable recorded biological sex or gender identity. |


## Rejected Mappings

| source_study | source_variable | proposed_common_variable | confidence | evidence |
| --- | --- | --- | --- | --- |
| SYN-MET-NOCODEBOOK | metab_feature_001 | not_mapped | 0.2 | No supported scientific synonym or mapping rule matched. |
| SYN-DIET-BODY | diet_score | not_mapped | 0.2 | No supported scientific synonym or mapping rule matched. |


## Missing Metadata

| source_study | source_variable | source_unit | source_timing | source_modality |
| --- | --- | --- | --- | --- |
| SYN-EXER-NODATA | peak_vo2 | mL/kg/min | unknown | cpet |
| SYN-MET-NOCODEBOOK | metab_feature_001 | unknown | unknown | metabolomics |


## Impossible Harmonizations

| source_study | source_variable | proposed_common_variable | transform | review_status |
| --- | --- | --- | --- | --- |
| SYN-MET-NOCODEBOOK | metab_feature_001 | not_mapped | not_available | rejected |
| SYN-DIET-BODY | diet_score | not_mapped | not_available | rejected |


## Validation Checks

- Confirm each approved source variable exists in the input dictionary.
- Confirm units match the proposed common unit or an approved transform exists.
- Confirm timing is present for longitudinal or exercise-response variables.
- Confirm no rejected or review-required mappings enter deterministic ETL.

## Failure Conditions

- Missing source files.
- Missing source variable during ETL.
- Unapproved transform.
- Human-review mapping appears in approved ETL input.
- VO₂max/VO₂peak endpoint cannot be documented.

## Human Decisions Required

| source_study | source_variable | proposed_common_variable | human_review_reason |
| --- | --- | --- | --- |
| SYN-ACTI-MET | daily_steps | steps_per_day | Human review required because confidence or metadata completeness is insufficient. |
| SYN-ACTI-MET | mvpa_min | mvpa_minutes | Human review required because confidence or metadata completeness is insufficient. |
| SYN-ACTI-MET | total_fat_mass | fat_mass | Human review required because confidence or metadata completeness is insufficient. |
| SYN-OMICS-GEN | participant_age | age | Human review required because confidence or metadata completeness is insufficient. |
| SYN-OMICS-GEN | glucose_fasting | fasting_glucose | Human review required because confidence or metadata completeness is insufficient. |
| SYN-OMICS-GEN | fasting_insulin | insulin | Human review required because confidence or metadata completeness is insufficient. |
| SYN-EXER-NODATA | peak_vo2 | vo2max | Confirm exercise test protocol and whether endpoint was VO2max or VO2peak. |
| SYN-CPET-RICH | vo2peak | vo2max | Confirm exercise test protocol and whether endpoint was VO2max or VO2peak. |
| SYN-CPET-RICH | total_lean_mass | lean_mass | Human review required because confidence or metadata completeness is insufficient. |
| SYN-DIET-BODY | body_mass_index | bmi | Human review required because confidence or metadata completeness is insufficient. |
| SYN-DIET-BODY | dxa_lean_mass | lean_mass | Human review required because confidence or metadata completeness is insufficient. |
| SYN-RESTRICTED-META | gender | sex | Confirm whether the source variable records biological sex or gender identity; the two are distinct constructs and are not interchangeable. |


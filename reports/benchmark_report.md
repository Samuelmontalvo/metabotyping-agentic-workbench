# Benchmark Report

## Metrics

| metric_name | value | numerator | denominator | applicability | wilson_95_interval |
| --- | --- | --- | --- | --- | --- |
| candidate_precision | 1.0 | 24 | 24 | applicable | [0.862024, 1.0] |
| candidate_recall | 1.0 | 24 | 24 | applicable | [0.862024, 1.0] |
| candidate_f1 | 1.0 | 48 | 48 | applicable | not applicable |
| auto_accept_precision | 1.0 | 12 | 12 | applicable | [0.757506, 1.0] |
| auto_accept_recall | 1.0 | 12 | 12 | applicable | [0.757506, 1.0] |
| unsafe_auto_accept_rate | 0.0 | 0 | 12 | applicable | [0.0, 0.242494] |
| review_capture_rate | 1.0 | 12 | 12 | applicable | [0.757506, 1.0] |
| review_status_accuracy | 1.0 | 26 | 26 | applicable | [0.871271, 1.0] |
| quality_score_agreement_within_0.15 | 0.889 | 8 | 9 | applicable | [0.565, 0.980109] |
| scope_status_accuracy | 1.0 | 10 | 10 | applicable | [0.722467, 1.0] |


Wilson score intervals are 95% intervals for direct proportions. Candidate F1 is derived from candidate error counts rather than a binomial proportion and therefore has no Wilson interval.

## Denominators

| metric_name | definition | undefined_reason |
| --- | --- | --- |
| candidate_precision | Exact predicted study, source-variable, common-variable, and review-status candidate tuples confirmed by a non-rejected expert tuple, divided by all predicted accepted or review-required mapped candidates. |  |
| candidate_recall | Exact predicted study, source-variable, common-variable, and review-status candidate tuples confirmed by a non-rejected expert tuple, divided by all non-rejected mapped expert candidates. |  |
| candidate_f1 | Two times the exact candidate true positives, divided by two times true positives plus candidate false positives and false negatives. This F1 score is derived and does not receive a Wilson interval. |  |
| auto_accept_precision | Exact predicted automatic accepts that experts also marked accepted, divided by all predicted mapped automatic accepts. |  |
| auto_accept_recall | Exact predicted automatic accepts that experts also marked accepted, divided by all mapped expert accepts. |  |
| unsafe_auto_accept_rate | Predicted mapped automatic accepts not confirmed as the same accepted expert mapping, divided by all predicted mapped automatic accepts. |  |
| review_capture_rate | Exact expert review-required mappings routed to review by the prediction, divided by all mapped expert review-required cases. |  |
| review_status_accuracy | Gold mapping entities with both the exact expert common variable and exact expert review status, divided by all gold mapping entities; missing predictions are incorrect and extras are reported separately. |  |
| quality_score_agreement_within_0.15 | Gold quality-score studies not declared out of scope with a reported prediction within an inclusive Decimal tolerance of 0.15, divided by all gold quality-score studies not declared out of scope; missing or withheld predictions are failures. |  |
| scope_status_accuracy | Gold quality-score studies with a declared scope status whose predicted scope status matches exactly, divided by all gold quality-score studies with a declared scope status; missing predictions are failures. |  |


## Disagreements

| case_type | source_study | source_variable | reason_codes | gold | predicted | gold_review_status | predicted_review_status | gold_scope_status | predicted_scope_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quality | SYN-EXER-NODATA |  | quality_score_outside_tolerance | 0.33 | 0.484 |  |  | in_scope_human | in_scope_human |


Disagreements are review artifacts rather than automatic scientific adjudications. A case's `outcome` is its first reason under the manifest's fixed precedence; `reason_codes` retains every applicable classification. The complete flattened evidence is in `benchmark_disagreements.csv`; the full mapping and quality unions are in `benchmark_case_results.json`.

## Provenance

- Manifest version: 1.0.0
- Scoring rule-set version: not available
- Benchmark rule-set version: 0.3.0
- Software version: 0.2.1
- Quality-score tolerance: 0.15 (inclusive)

### Inputs

| role | path | state | row_count | columns | sha256 |
| --- | --- | --- | --- | --- | --- |
| predicted_crosswalk | crosswalk.csv | present | 26 | source_study, source_variable, source_label, source_unit, source_timing, source_modality, proposed_common_variable, proposed_common_unit, transform, confidence, evidence, review_status | f6fe8339cd33bfdba90650dbb9d90b91dd1d339ae8aa39e3f57e6459f95acea2 |
| predicted_quality_scores | quality_scores.json | present | 10 | activity_quality, body_composition_quality, cpet_quality, diet_quality, genetics_quality, harmonization_feasibility, metabolomics_quality, metadata_completeness, overall_score, rationale, scope_status, study_design_rigor, study_id, temporal_alignment, weights | a3cb9698f70cc5cf216baa3e15f867b20c035e084fa6358e62df2adb6ce66abc |
| gold_variable_mappings | expert_variable_mappings.csv | present | 26 | source_study, source_variable, common_variable, review_status | c79917770842e8f55985491d186132cb774854b0670f7efa293fb7b1c54ef0bf |
| gold_quality_scores | expert_quality_scores.csv | present | 10 | study_id, overall_score, scope_status | 56a597e6537332daddf4ab5ab6ac3729a42e736d2825fc8230ae89d3c2d508df |


The manifest is written after this report is finalized and records SHA-256 hashes for the metrics, full case union, flattened disagreements, and this report.

## Scope

The benchmark compares deterministic MVP outputs against synthetic expert fixtures for exact variable mappings, automatic-accept safety, review routing, exact review statuses, and quality-score agreement. Missing predictions and unexpected predictions remain visible in the full case union. Aggregate metrics are regression evidence, not ground truth.

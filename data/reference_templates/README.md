# Independent harmonization reference template

Use `harmonization_reference_template.csv` to prepare an independently curated
comparison file. The header is the contract; the checked-in template deliberately
contains no reference rows and makes no claim that any person supplied or approved
a gold standard.

Required columns:

- `source_study` (or the supported alias `study_id`): stable study identifier.
- `source_variable`: stable source-variable identifier. Together with the study,
  this must be unique.
- `common_variable`: the curator's proposed common variable. Use an explicit value
  such as `not_mapped` for a rejected mapping; do not leave the cell blank.
- `review_status`: exactly one of `accepted`, `rejected`, or
  `requires_human_review`.

Before comparison, copy `reference_manifest.template.json`, replace every
placeholder, record the CSV SHA-256 digest, and state the evaluation universe.
The reference must cover exactly the same `(source_study, source_variable)` keys
as the agent crosswalk before any accuracy or safety headline is permitted.
Duplicate keys, contradictory duplicate decisions, partial datasets, and extra
datasets are not silently scored. Preserve unresolved curator disagreements as
review-required evidence rather than forcing consensus.


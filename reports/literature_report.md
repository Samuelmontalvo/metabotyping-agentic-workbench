# Literature Screening Report (offline pilot)

Screening and appraisal of retrieved bibliographic records. Retrieval provenance is preserved per
source; screening flags state whether they came from a structured field or from title/abstract text.
No relevance, quality, or replication claim is made from a bibliographic hit alone.

## Query

- Query: `human metabolomics datasets with exercise or actigraphy and genetics for MoTrPAC-style metadata readiness`
- Name variants searched: none
- Context terms: none
- Records after cross-source deduplication: 10
- Records requiring human review: 4

## Retrieval provenance

| source | status | reported hits | retrieved | complete sweep | detail |
| --- | --- | --- | --- | --- | --- |
| local_synthetic_fixture | ok | 10 | 10 | yes | offline pilot fixture; no network access and no live index queried |


### Retrieval gaps

- Every queried index answered, and each reported result set was retrieved in full.

## Screening classes

| screen class | records |
| --- | --- |
| direct_human_exercise | 4 |
| human_non_exercise_context | 5 |
| non_relevant_context | 1 |


## Evidence tiers

| evidence tier | records |
| --- | --- |
| peer_reviewed_primary | 10 |


## Species scope of the retrieved evidence

| species scope | records |
| --- | --- |
| human | 9 |
| non_human_or_unstated | 1 |


Species scope is inferred from retrieved title and abstract text unless the basis column says
`structured_field`. `not_stated_in_retrieved_text` means the text carried no species term; it does not
mean the study had no species.

## Subject-name evidence and homonym risk

Declared subject terms: none declared

| subject-name evidence | records |
| --- | --- |
| not_applicable_no_subject_term_declared | 10 |

| homonym risk | records |
| --- | --- |
| not_applicable_no_subject_term_declared | 10 |


A record matched by a full-text index whose retrieved title and abstract never name the queried subject
cannot be confirmed as subject evidence from the record alone. Where the name appears only alongside
materials-science context terms, the string may denote a different chemical entity that shares the
abbreviation; those records are escalated rather than counted as subject evidence.

_No record carries a materials-science reading of the queried name._


## Direct human exercise records

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unknown | Synthetic CPET and targeted metabolomics training study | unknown | peer_reviewed_primary | human | interventional_exercise_bout_or_program | declared:MWB-SYN-007 | requires_human_review | https://doi.org/10.0000/syn.cpet.rich |
| unknown | Synthetic exercise metabolomics abstract without repository | unknown | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.0000/syn.exer.nodata |
| unknown | Synthetic training metabolome and genotype cohort | unknown | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | declared:MWB-SYN-001 | requires_human_review | https://doi.org/10.0000/syn.metex.gen |
| unknown | Synthetic MoTrPAC-like multi-domain exercise trial | unknown | peer_reviewed_primary | human | not_stated_in_retrieved_text | declared:MWB-SYN-008 | requires_human_review | https://doi.org/10.0000/syn.motrpac.like |


## Human, non-exercise context

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unknown | Synthetic actigraphy linked plasma metabolomics study | unknown | peer_reviewed_primary | human | not_stated_in_retrieved_text | declared:MWB-SYN-002 | advisory_only | https://doi.org/10.0000/syn.acti.met |
| unknown | Synthetic diet body composition metabolomics cohort | unknown | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | declared:MWB-SYN-009 | advisory_only | https://doi.org/10.0000/syn.diet.body |
| unknown | Synthetic public metabolomics study without codebook | unknown | peer_reviewed_primary | human | not_stated_in_retrieved_text | declared:MWB-SYN-006 | advisory_only | https://doi.org/10.0000/syn.met.nocodebook |
| unknown | Synthetic nonexercise metabolomics genetics reference | unknown | peer_reviewed_primary | human | not_stated_in_retrieved_text | declared:DBGAP-SYN-003 | advisory_only | https://doi.org/10.0000/syn.omics.gen |
| unknown | Synthetic restricted metabolomics genetics cohort | unknown | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | declared:DBGAP-SYN-010 | advisory_only | https://doi.org/10.0000/syn.restricted.meta |


## Animal or in-vitro mechanistic background

Retained as mechanistic background. These records never satisfy a human required term.

_None._


## Secondary synthesis (reviews, meta-analyses)

_None._


## Unscreenable records

Retrieved records that could not be screened: either no abstract was returned, or the abstract names no
species and carries no decisive modality signal. The `screen_basis` column in the screened CSV gives the
reason per record. These are unresolved, not excluded.

_None._


## Accession bridge to retrievable data

9 of 10 records name a repository accession in the retrieved text. Namespace counts:
| namespace | records |
| --- | --- |
| declared | 9 |

| accessions | screen class | year | title | url |
| --- | --- | --- | --- | --- |
| declared:MWB-SYN-007 | direct_human_exercise | unknown | Synthetic CPET and targeted metabolomics training study | https://doi.org/10.0000/syn.cpet.rich |
| declared:MWB-SYN-001 | direct_human_exercise | unknown | Synthetic training metabolome and genotype cohort | https://doi.org/10.0000/syn.metex.gen |
| declared:MWB-SYN-008 | direct_human_exercise | unknown | Synthetic MoTrPAC-like multi-domain exercise trial | https://doi.org/10.0000/syn.motrpac.like |
| declared:MWB-SYN-002 | human_non_exercise_context | unknown | Synthetic actigraphy linked plasma metabolomics study | https://doi.org/10.0000/syn.acti.met |
| declared:MWB-SYN-009 | human_non_exercise_context | unknown | Synthetic diet body composition metabolomics cohort | https://doi.org/10.0000/syn.diet.body |
| declared:MWB-SYN-006 | human_non_exercise_context | unknown | Synthetic public metabolomics study without codebook | https://doi.org/10.0000/syn.met.nocodebook |
| declared:DBGAP-SYN-003 | human_non_exercise_context | unknown | Synthetic nonexercise metabolomics genetics reference | https://doi.org/10.0000/syn.omics.gen |
| declared:DBGAP-SYN-010 | human_non_exercise_context | unknown | Synthetic restricted metabolomics genetics cohort | https://doi.org/10.0000/syn.restricted.meta |
| declared:MWB-SYN-005 | non_relevant_context | unknown | Synthetic mouse endurance metabolomics experiment | https://doi.org/10.0000/syn.animal.met |


A record with no accession in its retrieved text is an open question about deposition, not a confirmed
deposition gap: bibliographic text is not a data availability statement.

## Human-review escalations

1 escalation(s) raised. The full queue is in `data/extracted/literature_escalations.csv`; the counts below are
the queue by type, followed by the first 25 rows.

| escalation | records | decision_needed |
| --- | --- | --- |
| unresolved_data_deposition | 1 | check the full-text data availability statement before recording a deposition gap |


| escalation | reason | decision_needed | title | record_url |
| --- | --- | --- | --- | --- |
| unresolved_data_deposition | no repository accession appears in the retrieved bibliographic text; absence here is not evidence of no deposition | check the full-text data availability statement before recording a deposition gap | Synthetic exercise metabolomics abstract without repository | https://doi.org/10.0000/syn.exer.nodata |


## Evaluation gates

| gate | status |
| --- | --- |
| FAIR provenance | pass — every record keeps source system, source URL, and identifiers |
| reproducibility | pass — screening is regenerated offline from the declared record set with deterministic rules |
| critical evidence | pass — structured evidence, text inference, and unknown-for-lack-of-text are distinct values |
| human review | pass — 1 escalation(s) raised |
| mirage detection | pass — unreachable and truncated sources are reported as availability gaps, never as zero hits |

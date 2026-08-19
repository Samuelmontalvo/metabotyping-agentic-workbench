# Aim 1 Catalog Report

## Candidate Study Ranking

| study_id | recommendation_class | match_class | score | rationale |
| --- | --- | --- | --- | --- |
| SYN-MOTRPAC-LIKE | direct_match | direct | 0.95 | Required inclusion criteria satisfied. Requested exercise phenotype present. Requested actigraphy phenotype present. Both intervention exercise and actigraphy are present. Requested genetics evidence present. Repository accession reported. |
| SYN-METEX-GEN | direct_match | direct | 0.79 | Required inclusion criteria satisfied. Requested exercise phenotype present. Requested genetics evidence present. Repository accession reported. |
| SYN-CPET-RICH | direct_match | direct | 0.69 | Required inclusion criteria satisfied. Requested exercise phenotype present. Repository accession reported. |
| SYN-ACTI-MET | direct_match | direct | 0.69 | Required inclusion criteria satisfied. Requested actigraphy phenotype present. Repository accession reported. |
| SYN-OMICS-GEN | enrichment_candidate | enrichment | 0.65 | Required inclusion criteria satisfied. Requested genetics evidence present. Repository accession reported. |
| SYN-RESTRICTED-META | enrichment_candidate | enrichment | 0.65 | Required inclusion criteria satisfied. Requested genetics evidence present. Repository accession reported. |
| SYN-DIET-BODY | enrichment_candidate | enrichment | 0.57 | Required inclusion criteria satisfied. Repository accession reported. |
| SYN-EXER-NODATA | mirage | mirage | 0.54 | Required inclusion criteria satisfied. Requested exercise phenotype present. Flagged as a mirage risk because usable repository assets are incomplete. |
| SYN-MET-NOCODEBOOK | mirage | mirage | 0.54 | Required inclusion criteria satisfied. Repository accession reported. Flagged as a mirage risk because usable repository assets are incomplete. |
| SYN-ANIMAL-MET | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: human. |


## Mirage Risks

| study_id | score | mirage_flags |
| --- | --- | --- |
| SYN-OMICS-GEN | 0.65 | no_data_files |
| SYN-RESTRICTED-META | 0.65 | no_data_files |
| SYN-EXER-NODATA | 0.54 | no_repository_accession, repository_data_not_available, no_downloadable_metadata, no_variable_dictionary_or_codebook, no_data_files, unclear_assay_platform, unclear_biospecimen_timing |
| SYN-MET-NOCODEBOOK | 0.54 | no_variable_dictionary_or_codebook |


## Decision Rationale

Ranking rewards required human metabolomics criteria, direct exercise/activity matches, genetics, CPET, body composition, diet, repository accessions, metadata, codebooks, sample size, assay platform, biospecimen timing, and MoTrPAC-like modality coverage.

# Aim 1 Catalog Report

## Candidate Study Ranking

| study_id | recommendation_class | match_class | score | rationale |
| --- | --- | --- | --- | --- |
| SYN-MOTRPAC-LIKE | direct_match | direct | 0.62 | Required inclusion criteria satisfied. Requested diet evidence present. Repository accession reported. |
| SYN-METEX-GEN | direct_match | direct | 0.62 | Required inclusion criteria satisfied. Requested diet evidence present. Repository accession reported. |
| SYN-OMICS-GEN | enrichment_candidate | enrichment | 0.6 | Required inclusion criteria satisfied. Requested diet evidence present. Repository accession reported. |
| SYN-RESTRICTED-META | enrichment_candidate | enrichment | 0.55 | Required inclusion criteria satisfied. Repository accession reported. |
| SYN-CPET-RICH | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: genetics. |
| SYN-ACTI-MET | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: genetics. |
| SYN-DIET-BODY | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: genetics. |
| SYN-EXER-NODATA | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: genetics. |
| SYN-ANIMAL-MET | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: human, genetics. |
| SYN-MET-NOCODEBOOK | excluded | excluded | 0.0 | Excluded because required criteria were not satisfied: genetics. |


## Mirage Risks

| study_id | score | mirage_flags |
| --- | --- | --- |
| SYN-OMICS-GEN | 0.6 | no_data_files |
| SYN-RESTRICTED-META | 0.55 | no_data_files |
| SYN-EXER-NODATA | 0.0 | no_repository_accession, repository_data_not_available, no_downloadable_metadata, no_variable_dictionary_or_codebook, no_data_files, unclear_assay_platform, unclear_biospecimen_timing |
| SYN-MET-NOCODEBOOK | 0.0 | no_variable_dictionary_or_codebook |


## Decision Rationale

Ranking rewards required human metabolomics criteria, direct exercise/activity matches, genetics, CPET, body composition, diet, repository accessions, metadata, codebooks, sample size, assay platform, biospecimen timing, and MoTrPAC-like modality coverage.

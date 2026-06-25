---
name: study-dataset-discovery
description: Use when ranking publications and repository records for direct, complementary, enrichment, mirage, or excluded status.
---

# Purpose
Identify candidate studies and datasets for human metabolomics-associated exercise and phenotype discovery, with
Metabolomics Workbench candidates constrained to blood-derived sample matrices.

# Inputs
- `data/examples/mock_publications.csv`
- `data/examples/mock_repository_records.csv`
- `data/extracted/criteria.json`

# Steps
1. Load publications and repository records.
2. Exclude non-human or no-metabolomics records.
3. For Metabolomics Workbench records, exclude candidates unless repository metadata shows at least one blood-derived
   sample matrix: blood, plasma, or serum. Treat muscle-only, urine-only, feces-only, cell-only, or unknown MW matrices
   as excluded until source metadata is manually supplied.
4. Score preferred modalities and repository usability.
5. Detect mirage risks.
6. Emit ranked recommendations.

# Outputs
- `data/extracted/recommendations.csv`
- `data/extracted/recommendations.json`
- `reports/aim1_catalog_report.md`

# Validation Checks
- Direct matches include human metabolomics plus exercise, actigraphy, or CPET.
- Metabolomics Workbench direct matches include observed blood, plasma, or serum matrix evidence in repository metadata.
- Mirage flags are visible in the catalog report.
- Excluded records remain in the audit trail.

# Failure Modes
- Repository accession is present but metadata/codebook is absent.
- Study title suggests relevance but structured fields contradict it.
- A Metabolomics Workbench title suggests exercise relevance but repository sample matrix is non-blood-derived or unknown.

# Human-Review Triggers
- A mirage should be rescued by manually supplied metadata.
- A complementary dataset should be promoted to direct match.
- A Metabolomics Workbench candidate with missing or ambiguous sample matrix evidence should not be promoted until a
  reviewer confirms blood, plasma, or serum from source metadata.

# Evaluation Gates
- FAIR: every recommendation must expose accession, metadata, codebook, availability, and provenance evidence when present.
- Reproducibility: rankings must be regenerated from declared publication and repository inputs without network access.
- Critical evidence: distinguish observed repository evidence from title-based inference; do not hide missing data behind high modality overlap.
- Human review: review triggers must preserve ambiguous Metabolomics Workbench matrix evidence for reviewer decisions.
- Skill quality rubric: pass only if direct, complementary, enrichment, mirage, and excluded classes are auditable.

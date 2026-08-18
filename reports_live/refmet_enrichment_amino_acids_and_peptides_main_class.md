# RefMet hierarchy enrichment — `Amino acids and peptides` (main_class)

- Effect tables scanned: 3
- Matching RefMet labels: **1**
- Significance threshold: FDR < 0.05
- Background: local MW and MoTrPAC effect rows with a RefMet annotation for the selected hierarchy level.
- Interpretation: over-representation of significant effect rows, not a pathway or mechanism claim.

## Enrichment summary

| RefMet label | n rows | n sig | up sig | down sig | sig fraction | enrichment ratio | Fisher p | sources |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Amino acids and peptides | 383 | 124 | 22 | 102 | 0.32 | 1.04 | 2.82e-01 | Metabolomics Workbench;MoTrPAC DataHub |

## Provenance
- **ST004303** (Metabolomics Workbench) — `data/live/volcano_human_ST004303.csv`
- **human-precovid-sed-adu** (MoTrPAC DataHub) — `data/live/volcano_motrpac_human_plasma_endur_post.csv`
- **pass1b06** (MoTrPAC DataHub) — `data/live/volcano_motrpac_pass1b06_plasma_8w.csv`

## Notes
- RefMet hierarchy columns come from `data/live/refmet_annotations.csv` (`super_class`, `main_class`, `sub_class`).
- Rows without a RefMet hierarchy label are excluded from the enrichment background for that hierarchy level.
- Small classes and classes without significant effects are flagged in `missing_evidence`.
- Use the row-level metabolite report before making harmonization, pathway, or mechanistic claims.
# RefMet hierarchy enrichment — `Amino acids and peptides` (main_class)

- Effect tables scanned: 3
- Matching RefMet labels: **9**
- Analysis strata represented: **9**
- Significance threshold: FDR < 0.05
- Background: each test uses only RefMet-annotated rows from its declared study × species × sample matrix × assay/panel × contrast × subgroup analysis stratum.
- Human MW, human MoTrPAC panels, and rat strata are never pooled as exchangeable observations.
- Multiple testing: Benjamini-Hochberg across all tested RefMet labels within each analysis stratum.
- Interpretation: over-representation of significant effect rows, not a pathway or mechanism claim.

## Enrichment summary

| study | species | assay/panel | subgroup | RefMet label | n rows | background n | n sig | ratio | Fisher p | BH q | tests | review |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Amino acids and peptides | 9 | 98 | 8 | 1.48 | 6.29e-02 | 5.35e-01 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-t-amines | all_or_not_reported | Amino acids and peptides | 28 | 31 | 21 | 1.01 | 6.06e-01 | 9.89e-01 | 4 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | male | Amino acids and peptides | 80 | 299 | 3 | 2.24 | 1.21e-01 | 1.00e+00 | 45 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Amino acids and peptides | 59 | 236 | 28 | 1.08 | 3.24e-01 | 1.00e+00 | 44 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rppos | all_or_not_reported | Amino acids and peptides | 35 | 94 | 17 | 1.04 | 4.80e-01 | 1.00e+00 | 25 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Amino acids and peptides | 66 | 340 | 35 | 1.00 | 5.49e-01 | 1.00e+00 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Amino acids and peptides | 25 | 59 | 12 | 0.91 | 8.06e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrppos | all_or_not_reported | Amino acids and peptides | 1 | 5 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 5 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | female | Amino acids and peptides | 80 | 299 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 45 | requires_human_review |

## Provenance
- **ST004303** (Metabolomics Workbench) — `data/live/volcano_human_ST004303.csv`
- **human-precovid-sed-adu** (MoTrPAC DataHub) — `data/live/volcano_motrpac_human_plasma_endur_post.csv`
- **pass1b06** (MoTrPAC DataHub) — `data/live/volcano_motrpac_pass1b06_plasma_8w.csv`

## Notes
- RefMet hierarchy columns, IDs, annotation provenance, and release fields come from `data/live/refmet_annotations.csv`; the current snapshot does not record a RefMet release.
- Rows without a RefMet hierarchy label are excluded from the enrichment background for that hierarchy level.
- A name-resolved RefMet annotation does not confirm source-feature identity; those rows remain `requires_human_review` unless the source row carries a consistent stable RefMet identifier.
- Enrichment decisions are scoped to within-stratum class over-representation and are explicitly ineligible as metabolite harmonization evidence.
- Fisher p-values are BH-adjusted only against class tests from the same `analysis_stratum`; q-values from different strata are reported side by side but are not a pooled analysis.
- Small classes and classes without significant effects are flagged in `missing_evidence`.
- Use the row-level metabolite report before making harmonization, pathway, or mechanistic claims.
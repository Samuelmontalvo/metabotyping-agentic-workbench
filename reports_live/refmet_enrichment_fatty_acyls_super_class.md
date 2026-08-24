# RefMet hierarchy enrichment — `Fatty acyls` (super_class)

- Effect tables scanned: 3
- Matching RefMet labels: **8**
- Analysis strata represented: **8**
- Significance threshold: FDR < 0.05
- Background: each test uses only RefMet-annotated rows from its declared study × species × sample matrix × assay/panel × contrast × subgroup analysis stratum.
- Human MW, human MoTrPAC panels, and rat strata are never pooled as exchangeable observations.
- Multiple testing: Benjamini-Hochberg across all tested RefMet labels within each analysis stratum.
- Interpretation: over-representation of significant effect rows, not a pathway or mechanism claim.

## Enrichment summary

| study | species | assay/panel | subgroup | RefMet label | n rows | background n | n sig | ratio | Fisher p | BH q | tests | review |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Fatty Acyls | 41 | 340 | 30 | 1.38 | 4.13e-03 | 5.37e-02 | 13 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrpneg | all_or_not_reported | Fatty Acyls | 32 | 37 | 12 | 0.99 | 7.31e-01 | 7.31e-01 | 2 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Fatty Acyls | 53 | 236 | 26 | 1.11 | 2.50e-01 | 8.74e-01 | 14 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rppos | all_or_not_reported | Fatty Acyls | 6 | 94 | 3 | 1.07 | 5.98e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Fatty Acyls | 46 | 98 | 26 | 0.94 | 8.18e-01 | 1.00e+00 | 8 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | female | Fatty Acyls | 76 | 299 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 11 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | male | Fatty Acyls | 76 | 299 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 11 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-t-oxylipneg | all_or_not_reported | Fatty Acyls | 2 | 2 | 0 | nan | 1.00e+00 | 1.00e+00 | 1 | requires_human_review |

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
# RefMet hierarchy enrichment — `all` (main_class)

- Effect tables scanned: 3
- Matching RefMet labels: **254**
- Analysis strata represented: **13**
- Significance threshold: FDR < 0.05
- Background: each test uses only RefMet-annotated rows from its declared study × species × sample matrix × assay/panel × contrast × subgroup analysis stratum.
- Human MW, human MoTrPAC panels, and rat strata are never pooled as exchangeable observations.
- Multiple testing: Benjamini-Hochberg across all tested RefMet labels within each analysis stratum.
- Interpretation: over-representation of significant effect rows, not a pathway or mechanism claim.

## Enrichment summary

| study | species | assay/panel | subgroup | RefMet label | n rows | background n | n sig | ratio | Fisher p | BH q | tests | review |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Phosphosphingolipids | 21 | 340 | 20 | 1.80 | 1.94e-05 | 9.72e-04 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Fatty esters | 32 | 340 | 26 | 1.53 | 5.04e-04 | 1.26e-02 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Bile acids | 16 | 98 | 15 | 1.56 | 1.76e-03 | 2.99e-02 | 17 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | female | Keto acids | 3 | 299 | 1 | 99.67 | 1.00e-02 | 4.52e-01 | 45 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Amino acids and peptides | 9 | 98 | 8 | 1.48 | 6.29e-02 | 5.35e-01 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrpneg | all_or_not_reported | Sterols | 1 | 37 | 1 | 2.64 | 3.78e-01 | 8.66e-01 | 3 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrpneg | all_or_not_reported | Fatty acids | 32 | 37 | 12 | 0.99 | 7.31e-01 | 8.66e-01 | 3 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrpneg | all_or_not_reported | Sterols/Bile acids(In-silico) | 4 | 37 | 1 | 0.66 | 8.66e-01 | 8.66e-01 | 3 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-t-amines | all_or_not_reported | Amino acids and peptides | 28 | 31 | 21 | 1.01 | 6.06e-01 | 9.89e-01 | 4 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-t-amines | all_or_not_reported | Amines | 1 | 31 | 1 | 1.35 | 7.42e-01 | 9.89e-01 | 4 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-t-amines | all_or_not_reported | Phosphate esters | 1 | 31 | 1 | 1.35 | 7.42e-01 | 9.89e-01 | 4 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Fatty esters | 7 | 236 | 6 | 1.95 | 3.00e-02 | 1.00e+00 | 44 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | male | Ornithine alkaloids | 4 | 299 | 1 | 14.95 | 6.56e-02 | 1.00e+00 | 45 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Purines | 8 | 236 | 6 | 1.70 | 7.64e-02 | 1.00e+00 | 44 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | male | Amino acids and peptides | 80 | 299 | 3 | 2.24 | 1.21e-01 | 1.00e+00 | 45 | requires_human_review |
| pass1b06 | Rattus norvegicus | metabolomics_timewise | male | TCA acids | 8 | 299 | 1 | 7.48 | 1.28e-01 | 1.00e+00 | 45 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Steroids | 3 | 340 | 3 | 1.89 | 1.47e-01 | 1.00e+00 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Triradylglycerols | 3 | 340 | 3 | 1.89 | 1.47e-01 | 1.00e+00 | 50 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Glycerophosphocholines | 15 | 236 | 9 | 1.36 | 1.55e-01 | 1.00e+00 | 44 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rppos | all_or_not_reported | Purines | 11 | 94 | 7 | 1.36 | 1.93e-01 | 1.00e+00 | 25 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Glycerophosphates | 2 | 236 | 2 | 2.27 | 1.93e-01 | 1.00e+00 | 44 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Steroids | 2 | 236 | 2 | 2.27 | 1.93e-01 | 1.00e+00 | 44 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Ceramides | 15 | 340 | 10 | 1.26 | 2.06e-01 | 1.00e+00 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rppos | all_or_not_reported | Steroids | 2 | 94 | 2 | 2.14 | 2.16e-01 | 1.00e+00 | 25 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Pyrimidines | 7 | 59 | 5 | 1.36 | 2.56e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Glycerophosphoserines | 2 | 340 | 2 | 1.89 | 2.80e-01 | 1.00e+00 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Isoprenoids | 2 | 340 | 2 | 1.89 | 2.80e-01 | 1.00e+00 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Organonitrogen compounds | 2 | 340 | 2 | 1.89 | 2.80e-01 | 1.00e+00 | 50 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Amino acids and peptides | 59 | 236 | 28 | 1.08 | 3.24e-01 | 1.00e+00 | 44 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Fatty acids | 4 | 340 | 3 | 1.42 | 3.57e-01 | 1.00e+00 | 50 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Pyrimidines | 5 | 236 | 3 | 1.36 | 3.89e-01 | 1.00e+00 | 44 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-hilicpos | all_or_not_reported | Diradylglycerols | 6 | 340 | 4 | 1.26 | 3.99e-01 | 1.00e+00 | 50 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rppos | all_or_not_reported | Tryptophan alkaloids | 7 | 94 | 4 | 1.22 | 4.28e-01 | 1.00e+00 | 25 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Purines | 10 | 59 | 6 | 1.14 | 4.34e-01 | 1.00e+00 | 12 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Fatty acids | 41 | 236 | 19 | 1.05 | 4.39e-01 | 1.00e+00 | 44 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rppos | all_or_not_reported | Fatty acids | 5 | 94 | 3 | 1.28 | 4.39e-01 | 1.00e+00 | 25 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Benzamides | 1 | 236 | 1 | 2.27 | 4.41e-01 | 1.00e+00 | 44 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Isoprenoids | 1 | 236 | 1 | 2.27 | 4.41e-01 | 1.00e+00 | 44 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Keto acids | 1 | 236 | 1 | 2.27 | 4.41e-01 | 1.00e+00 | 44 | requires_human_review |
| ST004303 | Homo sapiens | AN007160 | all_or_not_reported | Octadecanoids | 1 | 236 | 1 | 2.27 | 4.41e-01 | 1.00e+00 | 44 | requires_human_review |

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
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
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Hydroxy acids | 1 | 98 | 1 | 1.66 | 6.02e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Phenylacetic acids | 1 | 98 | 1 | 1.66 | 6.02e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Phenylpropanoids | 3 | 98 | 2 | 1.11 | 6.52e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Benzoic acids | 5 | 98 | 3 | 1.00 | 6.90e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Fatty acids | 46 | 98 | 26 | 0.94 | 8.18e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Tryptophan alkaloids | 2 | 98 | 1 | 0.83 | 8.44e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Steroids | 3 | 98 | 1 | 0.55 | 9.40e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Purines | 4 | 98 | 1 | 0.42 | 9.77e-01 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Keto acids | 2 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Anthranilic acid alkaloids | 1 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Isoprenoids | 1 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Pyrimidines | 1 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Quinones and hydroquinones | 1 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | Sphingoid bases | 1 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-rpneg | all_or_not_reported | TCA acids | 1 | 98 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 17 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Pyrimidines | 7 | 59 | 5 | 1.36 | 2.56e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Purines | 10 | 59 | 6 | 1.14 | 4.34e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Flavins | 1 | 59 | 1 | 1.90 | 5.25e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Organic phosphoric acids | 1 | 59 | 1 | 1.90 | 5.25e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Phenylpropanoids | 1 | 59 | 1 | 1.90 | 5.25e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Phosphate esters | 1 | 59 | 1 | 1.90 | 5.25e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Short-chain acids | 4 | 59 | 2 | 0.95 | 7.32e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Amino acids and peptides | 25 | 59 | 12 | 0.91 | 8.06e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Monosaccharides | 3 | 59 | 1 | 0.63 | 8.99e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | TCA acids | 4 | 59 | 1 | 0.48 | 9.55e-01 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Azoles | 1 | 59 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-ionpneg | all_or_not_reported | Sulfonic acids | 1 | 59 | 0 | 0.00 | 1.00e+00 | 1.00e+00 | 12 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrppos | all_or_not_reported | Bilirubins | 1 | 5 | 1 | 1.67 | 6.00e-01 | 1.00e+00 | 5 | requires_human_review |
| human-precovid-sed-adu | Homo sapiens | metab-u-lrppos | all_or_not_reported | Carnitines | 1 | 5 | 1 | 1.67 | 6.00e-01 | 1.00e+00 | 5 | requires_human_review |

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
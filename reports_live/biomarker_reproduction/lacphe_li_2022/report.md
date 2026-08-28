# Li et al. Lac-Phe post-hoc directional corroboration

**Outcome:** `supports_directional_claim_requires_identity_review`

This exploratory evaluation tests whether a post-hoc selected Metabolomics Workbench dataset shows the same *direction* as the 2022 Li et al. claim that circulating Lac-Phe increases after exercise. Cohort independence is not established. It does not use the paper's datasets and does not reproduce its causal feeding or obesity results.

## Evidence contract

- Paper DOI: `10.1038/s41586-022-04828-5` (verified in the cached record)
- External dataset: `ST003662` — Metabolome trajectory of exercise physiology- a comprehensive study of healthy male and female athletes
- Scientific scope: `post_hoc_external_dataset_directional_corroboration`
- Cohort independence: `not_established`
- Dataset selection: `post_hoc_exploratory`
- Analyte: Lactoyl Phenylalanine / N-Lactoyl phenylalanine (`RM0131640`)
- RefMet release status: `not_recorded_in_cached_annotation_file`
- Contrast: post-exercise vs pre-exercise (Collectionpoint After vs Before)
- Orientation: positive log2fc = higher post-exercise
- Exact paper dataset: `false`

## Assay and source metadata

- Analysis: `AN006016` — Reversed phase UNSPECIFIED ION MODE
- Analysis type/chromatography: MS / Reversed phase
- MS instrument: Orbitrap — Thermo Q Exactive HF hybrid Orbitrap
- Analysis units: umol/L whole blood
- Retrieval match basis: normalized name containment across source name columns
- Source license: CC BY 4.0
- Study link: https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662

## Recomputed paired result

- Queried rows: 137
- Complete positive pairs: 116
- Excluded incomplete/nonpositive pairs: 21
- Mean paired log2 change: 1.1586
- Geometric mean fold change: 2.23241 (`computed_finite`)
- Responders: 92/116 (0.793103)
- Exact two-sided sign-test p-value: 1.41818e-10 (1472724669120866632480669/10384593717069655257060992658440192)
- Cached all-stratum log2FC: 1.1586; absolute recomputation difference 2.22045e-16 (tolerance 1e-12)
- Cached p-value: 2.73242e-15 (`not_independently_recomputed`)
- Cached FDR: 2.50472e-14 (`not_independently_recomputed`)
- Cached -log10(p) internal consistency: `true`

## Acceptance checks

- `minimum_complete_positive_pairs_met`: pass
- `mean_paired_log2_change_above_threshold`: pass
- `responder_proportion_above_threshold`: pass
- `exact_sign_test_p_value_within_threshold`: pass
- `identity_review_gate_preserved`: pass
- `matrix_mismatch_caveat_preserved`: pass

## Required limitations

- Identity status remains `requires_human_review`; the RefMet name match is not permission to merge or pool assays.
- Matrix caveat: ST003662 reports whole-blood abundance, whereas Li et al. describes circulating Lac-Phe using distinct cohorts and assays; matrix and quantitative comparability are not established.
- Timing caveat: ST003662 Collectionpoint Before/After does not report exercise modality, intensity, duration, or post-exercise sampling delay; only a directional post-vs-pre comparison is supported.
- Selection caveat: ST003662 was selected post hoc after the Li et al. claim was known; cohort independence from the paper is not established, so this is exploratory directional corroboration only.

## Interpretation boundary

This is a post-hoc external-dataset directional corroboration in ST003662, not an exact reproduction of the Li et al. datasets or causal feeding/obesity findings. Dataset selection was exploratory, cohort independence is not established, metabolite identity still requires human review, and whole-blood comparability plus exercise sampling timing remain unresolved.

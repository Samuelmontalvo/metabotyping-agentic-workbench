# Li et al. Lac-Phe post-hoc repository After-vs-Before directional check

**Outcome:** `supports_repository_after_vs_before_direction_requires_identity_and_timing_review`

This exploratory evaluation tests whether a post-hoc selected Metabolomics Workbench dataset shows a positive repository-derived After-versus-Before direction consistent with the 2022 Li et al. claim. The cached source calls the contrast post-versus-pre exercise, but the raw factor/codebook snapshot is not bound, so that timing interpretation and cohort independence are not established. It does not use the paper's datasets or reproduce its causal feeding or obesity results.

## Evidence contract

- Paper DOI: `10.1038/s41586-022-04828-5` (verified in the cached record)
- Screened paper evidence: `peer_reviewed_primary`; PMID `35705806`; PMCID `PMC9767481`; review status `requires_human_review`
- Direction evidence: `abstract` phrases verified in the matched Europe PMC record
- Paper record: https://europepmc.org/article/MED/35705806
- Original-paper data availability: `no_accession_in_retrieved_text`; original paper dataset not used
- External dataset: `ST003662` — Metabolome trajectory of exercise physiology- a comprehensive study of healthy male and female athletes
- Scientific scope: `post_hoc_repository_after_vs_before_directional_check`
- Cohort independence: `not_established`
- Dataset selection: `post_hoc_exploratory`
- Analyte: Lactoyl Phenylalanine / N-Lactoyl phenylalanine (`RM0131640`)
- RefMet release status: `not_recorded_in_cached_annotation_file`
- Contrast: repository-derived Collectionpoint After vs Before; exercise-timing interpretation unverified
- Orientation: positive log2fc = higher repository-derived After vs Before
- Exact paper dataset: `false`

## Assay and source metadata

- Analysis: `AN006016` — Reversed phase UNSPECIFIED ION MODE
- Analysis type/chromatography: MS / Reversed phase
- MS instrument: Orbitrap — Thermo Q Exactive HF hybrid Orbitrap
- Analysis units: umol/L whole blood
- MetStat locator: `ST003662/AN006016`; N-Lactoyl phenylalanine; `metstat_row_links_analyte_study_and_analysis`
- MetStat locator review: `requires_human_review`; `requires_assay_identity_review`
- Retrieval match basis: normalized name containment across source name columns
- Source license: CC BY 4.0
- Study link: https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662
- Cached source contrast assertion: post-exercise vs pre-exercise (Collectionpoint After vs Before)
- Timing interpretation status: `repository_derived_before_after_labels_raw_factor_context_not_bound`

## Recomputed paired result

- Queried rows: 137
- Complete positive pairs: 116
- Excluded incomplete/nonpositive pairs: 21
- Mean paired log2 change: 1.1586
- Geometric mean fold change: 2.23241 (`computed_finite`)
- Responders: 92/116 (0.793103)
- Sign-test denominator: 116 non-tied pairs; 0 ties excluded
- Exact two-sided sign-test p-value: 1.41818e-10 (`computed_finite`; exact fraction 1472724669120866632480669/10384593717069655257060992658440192)
- Cached all-stratum log2FC: 1.1586; absolute recomputation difference 2.22045e-16 (tolerance 1e-12)
- Cached/recomputed arithmetic mean pre: 0.539199 / 0.539199; absolute difference 0
- Cached/recomputed arithmetic mean post: 0.755262 / 0.755262; absolute difference 2.22045e-16 (tolerance 1e-12)
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
- `timing_review_gate_preserved`: pass

## Required limitations

- Identity status remains `requires_human_review`; the RefMet name match is not permission to merge or pool assays.
- Matrix caveat: ST003662 reports whole-blood abundance, whereas Li et al. describes circulating Lac-Phe using distinct cohorts and assays; matrix and quantitative comparability are not established.
- Timing caveat: The cached ST003662 sample table contains repository-derived Before/After labels, but the raw factor/codebook snapshot is not bound; the exercise relationship, modality, intensity, duration, and sampling delay are not independently verified.
- Selection caveat: ST003662 was selected post hoc after the Li et al. claim was known; cohort independence from the paper is not established, so this is a hypothesis-generating repository After-versus-Before directional check only.

## Interpretation boundary

This is a post-hoc repository After-versus-Before directional check in ST003662, not an established corroboration or exact reproduction of the Li et al. datasets or causal feeding/obesity findings. The cached source calls the contrast post-versus-pre exercise, but no raw factor/codebook snapshot is bound, so that exercise-timing interpretation is not independently verified. Dataset selection was exploratory, cohort independence is not established, metabolite identity still requires human review, and whole-blood comparability remains unresolved.

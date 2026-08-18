---
name: metabolite-effect-search
description: Use when a user provides a metabolite or RefMet super_class, main_class, or sub_class label and wants row-level MW/MoTrPAC effects or annotation-backed enrichment summaries.
---

# Purpose
Find metabolites matching a user-supplied metabolite name or RefMet hierarchy label, then report either row-level MW/MoTrPAC effects or enrichment-style summaries across RefMet `super_class`, `main_class`, and `sub_class` annotations.

# Inputs
- User query term and optional query type: metabolite, class, superclass, super class, subclass, enrichment, pathway, or unknown.
- RefMet hierarchy level for enrichment: `super_class`, `main_class`, or `sub_class`.
- Local effect tables, when present:
  - `data/live/volcano_human_ST004303.csv`
  - `data/live/volcano_motrpac_human_plasma_endur_post.csv`
  - `data/live/volcano_motrpac_pass1b06_plasma_8w.csv`
  - Future MW or MoTrPAC effect tables under `data/live/`, `data/extracted/`, or `data/harmonized/`.
- RefMet annotation table:
  - `data/live/refmet_annotations.csv` with `name`, `super_class`, `main_class`, `sub_class`, and `refmet_id`.
  - Preserve the annotation source, provenance file, and declared release/version. If the local snapshot has no release field, emit `not_recorded_in_local_snapshot`; never substitute a file timestamp for a scientific database release.
- Provenance and study metadata, when present:
  - `data/live/volcano_provenance.json`
  - `data/live/provenance.json`
  - `data/live/publications.csv`
  - `data/live/repository_records.csv`
  - `reports_live/mw_vs_motrpac_catalog.md`
- Optional supplemental metabolite annotation files, when present, with columns such as `metabolite`, `refmet_name`, `hmdb_id`, `pubchem_id`, `inchikey`, `class`, `superclass`, `super_class`, `subclass`, `lipid_class`, `pathway`, or `source`.

# Steps
1. Normalize the query and preserve the original spelling.
   - Lowercase for matching, trim whitespace, normalize punctuation, and keep a `query_original` field.
   - Treat exact `metabolite` and `refmet_name` matches as stronger retrieval evidence than substring matches, but not as confirmed chemical identity.
   - A name-only exact hit remains `requires_human_review`. A stable identifier carried by the source row (for example `refmet_id`) may support an `accepted_curated` retrieval/annotation match when it resolves without conflict, but it does not establish MSI-level assay identity or harmonization eligibility.
   - Do not merge variables or metabolites only because names look similar.
2. Determine the query type and mode.
   - If the user names a specific compound, search `metabolite` and `refmet_name`.
   - If the user names a class, superclass, super class, or subclass, require an explicit annotation column when available.
   - If the user requests enrichment, use RefMet `super_class`, `main_class`, or `sub_class` as the grouping variable and keep the hierarchy level explicit.
   - If no annotation table exists, use only transparent deterministic name-pattern rules and label them as `inferred_name_pattern`.
3. Load all relevant MW and MoTrPAC effect tables.
   - Record the source system, file path, study or contrast identifier, study title, species, platform, assay or panel, sex or subgroup, sample matrix, and intervention timing when available.
   - Declare a machine-readable analysis stratum from source/study, species, sample matrix, assay or panel, contrast, and subgroup. Do not silently replace an unavailable panel with a more specific assay claim.
   - For MW records, preserve the MW accession and link pattern `https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=<STUDY_ID>`.
   - For MoTrPAC records, preserve the contrast name, tissue or sample matrix, species or arm, and platform.
4. Annotate effect rows with RefMet hierarchy.
   - Resolve each row through `refmet_name` or the best available metabolite label.
   - Preserve `super_class`, `main_class`, `sub_class`, `refmet_id`, annotation source, annotation provenance, and annotation release when available.
   - Keep the source-carried `refmet_id` separate from a `refmet_id` assigned through an exact-name annotation lookup. Record the annotation match basis and whether a stable identifier supports identity.
   - A RefMet hierarchy annotation obtained by exact name can support class assignment for screening, but it does not by itself confirm that the measured feature is that chemical entity.
   - Mark rows without RefMet hierarchy evidence in `missing_evidence`; do not assign them to an enrichment group.
5. Match metabolites conservatively.
   - Use exact normalized name or curated identifier matches first.
   - Use class/superclass/subclass annotations only when the annotation source is declared.
   - Use name patterns only for broad, auditable families such as acylcarnitines, LPC, PC, amino acids, fatty acids, bile acids, kynurenine/tryptophan metabolites, and nucleotides, and mark the confidence as review-required unless an annotation confirms the class.
   - Do not collapse lipid isomers, adduct-specific features, unknown features, or shorthand labels unless a curated identifier supports the merge.
6. Run RefMet enrichment when requested.
   - Define a separate background within each declared study × species × sample-matrix × assay/panel × contrast × subgroup analysis stratum, using only rows with a RefMet annotation for the selected hierarchy level.
   - Never pool human MW, human MoTrPAC panels, rat rows, different assays, or different analysis subgroups as exchangeable observations in one enrichment test.
   - Group rows by one hierarchy level at a time: `super_class`, `main_class`, or `sub_class`.
   - Count total rows, FDR-significant rows, up-significant rows, and down-significant rows per label.
   - Use a deterministic one-sided Fisher/hypergeometric test for over-representation of significant rows.
   - Test every eligible label in the stratum, apply Benjamini-Hochberg adjustment across that complete within-stratum family, and only then apply a user label filter. Emit the Fisher p-value, BH q-value, test count, adjustment method, and adjustment scope.
   - Report enrichment as an evidence-screening summary, not as a mechanistic pathway claim.
7. Extract reported effects.
   - Report `log2fc`, `p_value`, `fdr`, `neg_log10_p`, platform, sex or subgroup, and any available contrast direction.
   - Define direction from the declared contrast: positive log2fc means higher in the numerator or post/intervention side; negative means lower.
   - If contrast orientation is missing, mark direction as `orientation_unknown` rather than inferring a biological interpretation.
8. Summarize evidence across studies.
   - Group by source system, study/accession, contrast, matched metabolite, and match basis.
   - Count significant and non-significant hits using declared thresholds; default to FDR < 0.05 only when no project-specific threshold is declared.
   - Report concordance across MW and MoTrPAC only for exact or curated-equivalent metabolite matches.
9. Route uncertain results to review.
   - Add `review_status` values such as `accepted_curated`, `requires_human_review`, or `rejected_unsupported`. Never use `accepted_exact` for name-only evidence.
   - Scope `accepted_curated` to retrieval and annotation matching only; emit `harmonization_eligibility=requires_assay_identity_review` for every effect row.
   - Mark enrichment results as ineligible for metabolite harmonization decisions.
   - Include `missing_evidence` for absent class annotations, absent timing, absent contrast orientation, absent sample matrix, or absent provenance.

# Outputs
- Markdown report: `reports/metabolite_effects_<query_slug>.md` or `reports_live/metabolite_effects_<query_slug>.md`.
- RefMet enrichment report: `reports_live/refmet_enrichment_<query_slug>_<level>.md`.
- Machine-readable tables:
  - `data/extracted/metabolite_effects_<query_slug>.csv`
  - `data/extracted/metabolite_effects_<query_slug>.json`
  - `data/extracted/refmet_enrichment_<query_slug>_<level>.csv`
  - `data/extracted/refmet_enrichment_<query_slug>_<level>.json`
- Recommended output columns:
  - `query_original`
  - `query_type`
  - `matched_term`
  - `match_basis`
  - `match_confidence`
  - `review_status`
  - `decision_scope`
  - `harmonization_eligibility`
  - `identity_evidence_level`
  - `source_system`
  - `study_id`
  - `study_title`
  - `accession_or_contrast`
  - `study_link`
  - `sample_matrix`
  - `species`
  - `assay_panel`
  - `analysis_stratum`
  - `analysis_stratum_fields`
  - `intervention_timing`
  - `platform`
  - `sex_or_subgroup`
  - `metabolite`
  - `refmet_name`
  - `refmet_id`
  - `source_refmet_id`
  - `refmet_annotation_match_basis`
  - `identity_stable_identifier_supported`
  - `refmet_annotation_source`
  - `refmet_annotation_release`
  - `refmet_annotation_provenance`
  - `class`
  - `superclass`
  - `subclass`
  - `log2fc`
  - `p_value`
  - `fdr`
  - `direction`
  - `significance_call`
  - `effect_interpretation`
  - `provenance_file`
  - `missing_evidence`
- Additional enrichment output columns:
  - `refmet_level`
  - `refmet_label`
  - `n_class_rows`
  - `n_class_significant`
  - `n_class_up_significant`
  - `n_class_down_significant`
  - `class_significant_fraction`
  - `n_background_rows`
  - `n_background_significant`
  - `n_nonclass_background_rows`
  - `n_nonclass_background_significant`
  - `background_significant_fraction`
  - `enrichment_ratio`
  - `fisher_exact_p`
  - `fisher_exact_q`
  - `bh_test_count`
  - `multiple_testing_method`
  - `multiple_testing_scope`
  - `enrichment_significance_call`
  - `source_systems`
  - `study_ids`
  - `source_files`
  - `example_metabolites`
  - `significance_threshold`
  - `interpretation`

# Validation Checks
- Every row has a source file, study or contrast identifier, and provenance evidence.
- Exact metabolite matches are separated from inferred class, superclass, super class, or subclass matches.
- Exact name matches without a consistent source-carried stable identifier remain review-required, even when exact-name lookup supplies a RefMet ID and hierarchy.
- A source-carried identifier may support a curated retrieval match, but every effect row remains review-required for MSI identity and assay harmonization; enrichment rows are never harmonization evidence.
- RefMet-annotated rows expose the RefMet ID, annotation match basis, annotation source/provenance, and release or explicit release missingness.
- Direction and effect interpretation explicitly name the contrast orientation.
- Class-level searches state whether coverage is complete, annotation-backed, or pattern-based and incomplete.
- Enrichment searches state the RefMet hierarchy level, analysis stratum, background size, class size, significant-row counts, enrichment ratio, Fisher p value, within-stratum BH q value, and within-stratum test count.
- Every enrichment row has one study, species, assay/panel, contrast, and subgroup; aggregated `source_systems` or `study_ids` must not contain multiple exchangeable sources.
- Enrichment groups include only rows with RefMet evidence for the selected hierarchy level.
- MW and MoTrPAC effects are not combined unless metabolite identity evidence supports the merge.
- Missing p values, FDR, timing, sample matrix, or class annotations are visible in `missing_evidence`.

# Failure Modes
- Class, superclass, super class, or subclass query is treated as complete without an annotation file.
- RefMet enrichment mixes `super_class`, `main_class`, and `sub_class` in the same statistical background.
- RefMet enrichment pools studies, species, assays/panels, contrasts, or sex/subgroup strata into a single background.
- BH correction is applied only after filtering to the user-requested label, or across labels from different analysis strata.
- A RefMet ID assigned by name lookup is presented as if it were a stable identifier supplied by the source assay.
- Enrichment claims are described as pathway activation or mechanism instead of over-representation of significant effect rows.
- Metabolites are merged by loose substring matching, abbreviation similarity, or lipid shorthand alone.
- Positive and negative log2fc values are reported without the contrast orientation.
- MW accession, MoTrPAC contrast, or source file provenance is dropped.
- Reported statistical effects are described as mechanistic effects without supporting source evidence.

# Human-Review Triggers
- Query is a class, superclass, super class, subclass, enrichment, or pathway and no explicit annotation source is available.
- Match uses only an inferred name pattern or substring match.
- Enrichment class size is small, directionality is mixed, or the user wants to use enrichment for a biological/pathway claim.
- Multiple identifiers, isomers, lipid species, or platform-specific features may refer to related but non-identical analytes.
- RefMet annotation release is unavailable, the source stable identifier is missing/unresolved, or a source identifier conflicts with the row name.
- MW and MoTrPAC show discordant direction, sex-specific direction, or platform-specific direction.
- The user wants the result used for harmonization, grant claims, pathway interpretation, or mechanistic conclusions.

# Evaluation Gates
- FAIR: every effect row must expose metadata, accession or contrast, source file, study link when available, sample matrix, timing, and provenance for reusable review.
- Reproducibility: search results must be regenerated from declared query terms, local files, deterministic matching rules, declared analysis-stratum fields, complete within-stratum BH test families, and declared significance thresholds.
- Critical evidence: distinguish exact, curated, inferred, missing, and uncertain evidence; do not claim class coverage, pathway activity, or biological mechanism from unsupported name matches or enrichment summaries.
- Human review: ambiguous matches, missing annotations, missing contrast orientation, and inferred class assignments must trigger reviewer decisions.
- Skill quality rubric: pass only if reports include match score or confidence, effect statistics, enrichment background when applicable, source provenance, missing evidence, review status, and a concise interpretation for each reported effect or enrichment result.

# Implementation
- Deterministic implementation: `scripts/run_metabolite_effect_search.py`.

---
name: metabolite-effect-search
description: Use when a user provides a metabolite, biochemical class, superclass, super class, or subclass and wants to find matching metabolites and reported study effects across Metabolomics Workbench and/or MoTrPAC effect tables.
---

# Purpose
Find metabolites matching a user-supplied metabolite name, class, superclass, super class, or subclass, then report their observed study effects across available MW and MoTrPAC evidence.

# Inputs
- User query term and optional query type: metabolite, class, superclass, super class, subclass, pathway, or unknown.
- Local effect tables, when present:
  - `data/live/volcano_human_ST004303.csv`
  - `data/live/volcano_motrpac_human_plasma_endur_post.csv`
  - `data/live/volcano_motrpac_pass1b06_plasma_8w.csv`
  - Future MW or MoTrPAC effect tables under `data/live/`, `data/extracted/`, or `data/harmonized/`.
- Provenance and study metadata, when present:
  - `data/live/volcano_provenance.json`
  - `data/live/provenance.json`
  - `data/live/publications.csv`
  - `data/live/repository_records.csv`
  - `reports_live/mw_vs_motrpac_catalog.md`
- Optional metabolite annotation files, when present, with columns such as `metabolite`, `refmet_name`, `hmdb_id`, `pubchem_id`, `inchikey`, `class`, `superclass`, `super_class`, `subclass`, `lipid_class`, `pathway`, or `source`.

# Steps
1. Normalize the query and preserve the original spelling.
   - Lowercase for matching, trim whitespace, normalize punctuation, and keep a `query_original` field.
   - Treat exact `metabolite` and `refmet_name` matches as stronger evidence than substring matches.
   - Do not merge variables or metabolites only because names look similar.
2. Determine the query type.
   - If the user names a specific compound, search `metabolite` and `refmet_name`.
   - If the user names a class, superclass, super class, or subclass, require an explicit annotation column when available.
   - If no annotation table exists, use only transparent deterministic name-pattern rules and label them as `inferred_name_pattern`.
3. Load all relevant MW and MoTrPAC effect tables.
   - Record the source system, file path, study or contrast identifier, study title, platform, sex or subgroup, sample matrix, and intervention timing when available.
   - For MW records, preserve the MW accession and link pattern `https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=<STUDY_ID>`.
   - For MoTrPAC records, preserve the contrast name, tissue or sample matrix, species or arm, and platform.
4. Match metabolites conservatively.
   - Use exact normalized name or curated identifier matches first.
   - Use class/superclass/subclass annotations only when the annotation source is declared.
   - Use name patterns only for broad, auditable families such as acylcarnitines, LPC, PC, amino acids, fatty acids, bile acids, kynurenine/tryptophan metabolites, and nucleotides, and mark the confidence as review-required unless an annotation confirms the class.
   - Do not collapse lipid isomers, adduct-specific features, unknown features, or shorthand labels unless a curated identifier supports the merge.
5. Extract reported effects.
   - Report `log2fc`, `p_value`, `fdr`, `neg_log10_p`, platform, sex or subgroup, and any available contrast direction.
   - Define direction from the declared contrast: positive log2fc means higher in the numerator or post/intervention side; negative means lower.
   - If contrast orientation is missing, mark direction as `orientation_unknown` rather than inferring a biological interpretation.
6. Summarize evidence across studies.
   - Group by source system, study/accession, contrast, matched metabolite, and match basis.
   - Count significant and non-significant hits using declared thresholds; default to FDR < 0.05 only when no project-specific threshold is declared.
   - Report concordance across MW and MoTrPAC only for exact or curated-equivalent metabolite matches.
7. Route uncertain results to review.
   - Add `review_status` values such as `accepted_exact`, `accepted_curated`, `requires_human_review`, or `rejected_unsupported`.
   - Include `missing_evidence` for absent class annotations, absent timing, absent contrast orientation, absent sample matrix, or absent provenance.

# Outputs
- Markdown report: `reports/metabolite_effects_<query_slug>.md` or `reports_live/metabolite_effects_<query_slug>.md`.
- Machine-readable tables:
  - `data/extracted/metabolite_effects_<query_slug>.csv`
  - `data/extracted/metabolite_effects_<query_slug>.json`
- Recommended output columns:
  - `query_original`
  - `query_type`
  - `matched_term`
  - `match_basis`
  - `match_confidence`
  - `review_status`
  - `source_system`
  - `study_id`
  - `study_title`
  - `accession_or_contrast`
  - `study_link`
  - `sample_matrix`
  - `intervention_timing`
  - `platform`
  - `sex_or_subgroup`
  - `metabolite`
  - `refmet_name`
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

# Validation Checks
- Every row has a source file, study or contrast identifier, and provenance evidence.
- Exact metabolite matches are separated from inferred class, superclass, super class, or subclass matches.
- Direction and effect interpretation explicitly name the contrast orientation.
- Class-level searches state whether coverage is complete, annotation-backed, or pattern-based and incomplete.
- MW and MoTrPAC effects are not combined unless metabolite identity evidence supports the merge.
- Missing p values, FDR, timing, sample matrix, or class annotations are visible in `missing_evidence`.

# Failure Modes
- Class, superclass, super class, or subclass query is treated as complete without an annotation file.
- Metabolites are merged by loose substring matching, abbreviation similarity, or lipid shorthand alone.
- Positive and negative log2fc values are reported without the contrast orientation.
- MW accession, MoTrPAC contrast, or source file provenance is dropped.
- Reported statistical effects are described as mechanistic effects without supporting source evidence.

# Human-Review Triggers
- Query is a class, superclass, super class, subclass, or pathway and no explicit annotation source is available.
- Match uses only an inferred name pattern or substring match.
- Multiple identifiers, isomers, lipid species, or platform-specific features may refer to related but non-identical analytes.
- MW and MoTrPAC show discordant direction, sex-specific direction, or platform-specific direction.
- The user wants the result used for harmonization, grant claims, pathway interpretation, or mechanistic conclusions.

# Evaluation Gates
- FAIR: every effect row must expose metadata, accession or contrast, source file, study link when available, sample matrix, timing, and provenance for reusable review.
- Reproducibility: search results must be regenerated from declared query terms, local files, deterministic matching rules, and declared significance thresholds.
- Critical evidence: distinguish exact, curated, inferred, missing, and uncertain evidence; do not claim class coverage or biological mechanism from unsupported name matches.
- Human review: ambiguous matches, missing annotations, missing contrast orientation, and inferred class assignments must trigger reviewer decisions.
- Skill quality rubric: pass only if reports include match score or confidence, effect statistics, source provenance, missing evidence, review status, and a concise interpretation for each reported effect.

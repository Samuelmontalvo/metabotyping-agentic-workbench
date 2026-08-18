---
name: motrpac-plotting
description: Use when preparing or rendering MoTrPAC-style metabolomics volcano, heatmap, single-feature, pathway, or RefMet hierarchy views with auditable statistics and metadata.
---

# Purpose
Create reviewable MoTrPAC-style metabolomics visualizations with explicit contrast semantics, multiple-testing scope, identity and annotation gates, coverage, assay/platform context, missingness and censoring, palette provenance, and reproducible data exports.

# Inputs
- Normalized differential-result or longitudinal tables with source study/dataset, canonical feature ID, effect, unadjusted p-value, FDR, confidence interval, assay, platform, missingness, below-LOD fraction, group, sex, tissue, timepoint, and omics metadata.
- Explicit numerator, denominator, effect scale, FDR method, FDR family, alpha, and feature threshold for each contrast.
- Reviewed mapping and annotation statuses plus canonical RefMet `sub_class`, `main_class`, and `super_class` or pathway labels when hierarchy views are requested.
- Expected feature universe for each hierarchy set when coverage-gated aggregation is requested.
- Repo-local Python and R helpers and established MoTrPAC palette objects.

# Steps
1. Validate the contrast orientation, effect scale, unadjusted p-value, FDR method, FDR scope, and number of tested features before drawing a differential plot.
2. Recompute Benjamini-Hochberg FDR only when requested and retain both p-value and adjusted value; never label a nominal p-value as FDR.
3. For cross-dataset heatmaps, require an accepted canonical mapping, reject duplicate canonical feature-by-contrast cells, and leave uncertain cells visibly unplotted.
4. For single-metabolite views, retain assay/platform and confidence-interval semantics; summarize trajectories without implicit imputation or longitudinal-model claims.
5. For pathway and RefMet hierarchy views, require reviewed annotations and an expected universe, report tested and expected counts, and suppress low-coverage cells.
6. Treat hierarchy medians as descriptive summaries only; do not invent pathway/class p-values, enrichment, or independence.
7. Search for repo-local palette or theme objects before adding colors and prefer existing MoTrPAC functions or helpers over inline hex codes.
8. Use exercise-group colors only for explicit group metadata:
   `EE`, `Endurance`, `ADUEndur`; `RE`, `Resistance`, `ADUResist`; `CON`, `Control`, `ADUControl`.
9. Use sex colors only for explicit sex metadata and treat Metabolomics Workbench like MoTrPAC only when source factors support the mapping.
10. Export plot-ready CSVs, metadata, checksums, and figures with stable ordering and auditable palette sources.

# Outputs
- Volcano plots with explicit direction and FDR semantics.
- Cross-dataset feature heatmaps, single-metabolite effect plots, and single-metabolite mean-plus/minus-SE trajectories.
- Coverage-gated pathway, `sub_class`, `main_class`, and `super_class` heatmaps.
- Checksummed plot bundle containing normalized plot-ready CSVs, contrast and aggregation metadata, palette provenance, source metadata, validation flags, and figure files.
- Reports stating that descriptive visual similarity is not harmonized replication or pathway inference.

# Validation Checks
- Contrast labels expose numerator, denominator, effect scale, FDR method, FDR scope, alpha, and test count.
- Duplicate canonical feature-by-contrast cells, mixed effect scales, invalid probabilities, and conflicting hierarchy aliases fail closed.
- Cross-study heatmaps contain only accepted mappings; uncertain mappings remain in the audit table but not colored cells.
- Hierarchy cells report annotation, identity, missingness, LOD, expected-universe, feature-count, and coverage gates and contain no invented aggregate p-value.
- EE/RE/CON, sex, tissue, omics, and timepoint colors match repo-local mappings and use redundant marker or line-style encodings when appropriate.
- Legends are stable and do not imply missing metadata; plot and CSV outputs are non-empty and checksummed.

# Failure Modes
- Nominal p-values are presented as FDR, the multiple-testing family is hidden, or contrast direction is ambiguous.
- Duplicate or uncertain metabolite mappings are averaged into a cross-study cell.
- Pathway/class activity or enrichment is inferred from a descriptive median without a declared background and dedicated statistical model.
- Missing or below-LOD values are silently imputed, or longitudinal summaries are presented as modeled inference.
- Ad hoc code silently reassigns established MoTrPAC colors or infers MW group labels from titles or biology.
- Plot dependencies are unavailable; preserve plot-ready CSV/report outputs and fail rendering clearly.

# Human-Review Triggers
- Identity or hierarchy annotation status is missing, ambiguous, or only name-derived.
- Assay/platform duplicates produce more than one value for a canonical feature and contrast.
- A pathway/class set lacks a declared expected universe or fails minimum feature/coverage thresholds.
- A color mapping depends on ambiguous labels, inferred biology, or a nonstandard treatment abbreviation.
- A plot combines studies where visual similarity could be mistaken for validated harmonization or replication.

# Evaluation Gates
- FAIR: preserve plot data provenance, accession, contrast, assay/platform, annotation, quality flags, expected universe, palette source, and checksummed outputs.
- Reproducibility: plot tables and figures must be regenerated from declared inputs, explicit statistical semantics, deterministic ordering, and versioned helper functions.
- Critical evidence: distinguish nominal significance, FDR, descriptive hierarchy summaries, enrichment, and harmonized replication; do not hide missing, censored, ambiguous, or inferred metadata.
- Human review: ambiguous identity, annotation, duplicate cells, inadequate coverage, and unsupported group/color mappings must remain visible for reviewer decisions.
- Skill quality rubric: pass only if volcano, heatmap, single-feature, pathway, class, subclass, and superclass outputs are auditable; unsafe mappings are excluded; FDR and coverage gates are explicit; and plot data remain available when rendering is unavailable.

# Implementation
- R palette and theme implementation: `src/metabotyping_agentic/plotting/motrpac_plot_helpers.R`.
- Deterministic preparation and rendering: `src/metabotyping_agentic/plotting/metabolomics.py`.
- Offline synthetic workflow: `scripts/render_synthetic_motrpac_plot_suite.py`.

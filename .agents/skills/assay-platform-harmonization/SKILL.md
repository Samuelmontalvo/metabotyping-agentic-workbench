---
name: assay-platform-harmonization
description: Use when determining whether metabolite measurements from different assays or platforms can be pooled, transformed, or synthesized as study-specific effects.
---

# Purpose
Produce an assay-aware harmonization plan that separates chemical identity, quantitative scale, analytical compatibility, QA/QC, missingness and censoring, and permissible statistical synthesis.

# Inputs
- Validated metabolite assay records with identity, platform, method, sample matrix, units, scale, calibration, internal standard, limits, missingness, batch/QC metadata, and provenance.
- Declared policy thresholds and any independently validated bridge identifiers.
- Human decisions for evidence that deterministic rules cannot resolve.

# Steps
1. Resolve identity independently from quantitative comparability.
2. Assess platform, method, sample-matrix, calibration, unit, scale, internal-standard, and validated-bridge compatibility.
3. Evaluate mQACC-style pooled QC, reference materials, blanks, run-order randomization, drift, batch correction, and feature-level precision.
4. Preserve LOD/LOQ censoring and missing-reason codes; prefer unimputed values and reject irreversible substitution.
5. Permit raw-value pooling only for exact MSI level 1 identities measured as compatible linear absolute concentrations with adequate QA/QC.
6. Keep semi-quantitative, relative-abundance, ratio, and feature-intensity values study/platform specific and specify effect-estimate meta-analysis when identity is adequate.
7. Emit accepted transforms, review queue, non-combinable ledger, heterogeneity plan, audit trail, and deterministic digests.

# Outputs
- `reports/aim2_assay_harmonization_plan.json`.
- `data/harmonized/approved_assay_harmonization.json` and `data/harmonized/assay_harmonization_audit.json`.
- `data/review/assay_harmonization_review_queue.json` and `data/review/non_combinable_assay_pairs.json`.
- COMETS-style heterogeneity requirements including platform/study strata, Q, I², tau², moderator analysis, and leave-one-platform-out sensitivity checks.

# Validation Checks
- No review-required or non-combinable decision contains executable transforms.
- Raw pooling requires accepted exact identity, compatible biological matrix and method, linear absolute concentration, compatible units, and adequate QA/QC.
- Relative or intensity values are never pooled across studies; only explicit study-specific effects may be synthesized.
- Cross-study batch correction, zero or half-limit substitution, undocumented imputation, and unvalidated method bridges fail closed.
- Unit transforms come only from the approved registry, preserve dimensional families, and record their order and parameters.
- Every decision retains source artifacts, hashes, feature IDs, rule-set version, and pair digest.

# Failure Modes
- ComBat, normalization, or batch correction is applied jointly across studies or platforms without a validated design.
- Different matrices, isomers, units, quantitative scales, assay generations, or calibration regimes are pooled because names match.
- Below-limit values are converted to biological zero or silently imputed.
- A bridge regression or cross-platform conversion is claimed without independent validation and uncertainty estimates.
- Heterogeneity is hidden by pooling or a platform moderator is omitted from cross-platform synthesis.

# Human-Review Triggers
- Exact identity is unresolved or conflicts across identifier systems.
- Sample matrix, timing, assay version, calibration traceability, internal standard, QC precision, missingness, LOD/LOQ, batch scope, or bridge evidence is absent or incompatible.
- Molar-to-mass conversion depends on uncertain molecular form, or unit dimensionality is unclear.
- Platform heterogeneity, influence diagnostics, or leave-one-platform-out results materially change interpretation.

# Evaluation Gates
- FAIR: preserve assay metadata, identity resolution, units, limits, QC, source hashes, provenance, and machine-readable decisions.
- Reproducibility: regenerate plans and transform registries from declared records, policy, rule-set version, stable ordering, and content digests.
- Critical evidence: distinguish value pooling, within-study processing, and effect meta-analysis; do not infer comparability from names, correlation, or normalization alone.
- Human review: incomplete identity, assay, quantitative, QC, missingness, bridge, or heterogeneity evidence must trigger a reviewer decision.
- Skill quality rubric: pass only if all accepted transformations are registry-approved, every nonaccepted pair is non-executable, unsafe pooling is zero in adversarial tests, and sensitivity requirements are explicit.

# Implementation
- Typed assay model: `src/metabotyping_agentic/harmonization/assay_models.py`.
- Deterministic implementation: `src/metabotyping_agentic/harmonization/assay_harmonization.py`.
- Executable artifact builder: `scripts/build_assay_harmonization_plan.py`.


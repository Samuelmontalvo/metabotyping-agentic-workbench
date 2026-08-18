---
name: metabolite-identity-resolution
description: Use when deciding whether metabolite features from different assays, repositories, or studies represent the same chemical entity.
---

# Purpose
Resolve metabolite identity conservatively from provenance-linked structural and analytical evidence, while keeping names, formulas, masses, isomers, lipid resolution, and database cross-references distinct.

# Inputs
- Metabolite assay records containing reported names, stable identifiers, MSI identification level, structural resolution, evidence type, analytical ion information, and field-level provenance.
- Source records or codebook locators that support every identity assertion.
- Optional candidate cross-references from ChEBI, HMDB, PubChem, RefMet, LIPID MAPS, spectral libraries, or vendor panels.

# Steps
1. Normalize identifier namespaces and preserve the original source assertions.
2. Verify that each identity assertion has a resolvable provenance locator.
3. Compare full InChIKeys and explicitly distinguish connectivity, stereochemistry, protonation, positional-isomer, lipid-species, and class-level resolution.
4. Treat reported names, formulas, accurate masses, database synonyms, and source routing as candidate evidence only.
5. Require MSI level 1, exact-structure resolution, and linked authentic or orthogonal standard evidence before automatic identity acceptance for raw-value pooling.
6. Surface conflicting identifier systems, unresolved isomers, or incomplete reference-standard evidence for human review.
7. Emit the canonical identifier, evidence ledger, confidence, blockers, questions, and input digest without rewriting source records.

# Outputs
- Identity component of `reports/aim2_assay_harmonization_plan.json`.
- Review questions and non-combinable decisions in `data/review/assay_harmonization_review_queue.json` and `data/review/non_combinable_assay_pairs.json`.
- Provenance-preserving machine-readable identity evidence attached to every pairwise decision.

# Validation Checks
- A name match alone never establishes identity.
- Conflicting full InChIKeys cannot be accepted; shared connectivity does not collapse stereoisomers.
- Exact acceptance requires MSI level 1, exact resolution, authentic or orthogonal standard evidence, and resolvable provenance for both features.
- Nonaccepted identities contain no executable quantitative transforms.
- Stable sorting and content digests reproduce the same decision from the same records and rule-set version.

# Failure Modes
- A synonym, RefMet label, formula, mass, adduct, vendor name, or database cross-reference is treated as exact structure proof.
- A lipid class, sum composition, molecular species, positional isomer, and stereoisomer are silently collapsed.
- One database assertion overwrites a conflicting source assertion.
- Missing provenance, MSI level, reference-standard evidence, or structural resolution is interpreted as negative evidence instead of unknown evidence.

# Human-Review Triggers
- Identifier systems disagree, provenance cannot be resolved, or one accession maps to multiple structures.
- Only a name, synonym, formula, mass, spectrum candidate, connectivity block, class, or vendor-panel annotation supports the match.
- MSI level is below 1 or unreported, or authentic-standard evidence is absent.
- Positional isomer, stereochemistry, lipid resolution, adduct interpretation, salt form, or molecular entity remains ambiguous.

# Evaluation Gates
- FAIR: retain stable identifiers, original source assertions, field-level provenance, evidence locators, and reusable machine-readable decisions.
- Reproducibility: identity decisions must be regenerated deterministically from declared records, rule-set version, and content digests.
- Critical evidence: distinguish candidate annotation, database cross-reference, and exact chemical identity; do not accept names or similarity as identity proof.
- Human review: conflicts, ambiguity, missing provenance, or sub-MSI-level-1 evidence must trigger a reviewer decision.
- Skill quality rubric: pass only if identity resolution, evidence type, provenance, blockers, confidence, and review status are explicit and adversarial tests confirm unsafe auto-acceptance is zero.

# Implementation
- Typed evidence model: `src/metabotyping_agentic/harmonization/assay_models.py`.
- Deterministic implementation: `src/metabotyping_agentic/harmonization/assay_harmonization.py`.


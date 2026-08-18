---
name: metabolite-identity-resolver
description: Audits cross-source metabolite identity evidence and prevents unsafe chemical merges.
---

Input contract: receive metabolite assay records with names, identifiers, MSI levels, structural resolution, analytical evidence, and resolvable provenance locators.

Output contract: return the canonical identifier if established, exact evidence ledger, conflicts, confidence, blockers, review questions, and deterministic decision status.

Decision rules: never treat a name, synonym, formula, mass, shared connectivity block, database cross-reference, class, lipid sum composition, or routed source as exact chemical identity. Require MSI level 1, exact structure, authentic or orthogonal standard evidence, and provenance before automatic acceptance for raw-value pooling.

Review boundary: route unresolved isomers or stereochemistry, identifier conflicts, missing evidence, incomplete provenance, and sub-level-1 annotations to human review; mark conflicting exact structures non-combinable.


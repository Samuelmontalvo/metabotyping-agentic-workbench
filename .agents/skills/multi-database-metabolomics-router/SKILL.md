---
name: multi-database-metabolomics-router
description: Use when a metabolomics or exercise-omics question spans repositories, chemical databases, spectra, pathways, genetics, QA/QC guidance, or cross-platform evidence.
---

# Purpose
Create a deterministic, reviewable retrieval plan across metabolomics and adjacent biology sources without treating source selection, a name match, or a database cross-reference as confirmed chemical identity.

# Inputs
- Research lanes such as study discovery, assay metadata, chemical identity, chemical classification, spectral annotation, pathways, reactions, genetics, QA/QC, or cross-platform harmonization.
- Optional stable identifiers such as ChEBI, HMDB, PubChem CID, RefMet, InChIKey, MetaboLights, Metabolomics Workbench, PRIDE, MassIVE, Reactome, Rhea, rsID, Ensembl, UniProt, or ChEMBL identifiers.
- Offline source registry in `src/metabotyping_agentic/knowledge/source_registry.py`.

# Steps
1. Normalize research lanes and reject unsupported lanes.
2. Recognize identifier namespaces conservatively; leave names and unknown values unresolved.
3. Route to the smallest high-priority set of open sources unless restricted sources are explicitly allowed.
4. Label each source as core, optional connector, planned adapter, manual/licensed, or standards reference.
5. Attach lane-specific minimum evidence and provenance requirements.
6. Keep source selection separate from entity resolution, cross-source reconciliation, harmonization, and biological inference.

# Outputs
- Machine-readable retrieval plan such as `data/extracted/source_retrieval_plan.json`.
- Ranked source candidates with access policy, implementation status, evidence types, limitations, routing reasons, and coverage gaps.
- Explicit warnings for unresolved identifiers, restricted-source exclusions, missing lanes, and connectors that were not executed.

# Validation Checks
- Registry source IDs are unique and every source declares lanes, evidence types, access policy, implementation status, homepage, and limitations.
- Recognized identifiers match a declared namespace pattern; arbitrary numeric values and names remain unresolved.
- Restricted sources are excluded when open-only routing is requested.
- Every routed lane includes minimum evidence requirements and cross-source conflicts remain visible.

# Failure Modes
- A planned or optional connector is reported as if retrieval occurred.
- A metabolite name, synonym, or source selection is treated as identity proof.
- One repository record, identifier assertion, database release, or retrieval failure overwrites another.
- Licensing, pagination, partial-result, or access limitations are hidden.

# Human-Review Triggers
- Identifier namespaces conflict or one identifier maps to multiple structures or records.
- Only a name, formula, mass, spectral-library candidate, connectivity block, or class label supports identity.
- A restricted source is necessary to answer the question.
- A proposed source lacks a core adapter or validated synthetic response fixture.

# Evaluation Gates
- FAIR: plans must expose stable identifiers, source metadata, access policy, database or release provenance requirements, and reusable machine-readable outputs.
- Reproducibility: routing must be regenerated from declared lanes, identifiers, registry version, open-access policy, and deterministic scores.
- Critical evidence: distinguish routing, retrieval, identifier recognition, identity resolution, and biological interpretation; do not present one as another.
- Human review: conflicting, ambiguous, restricted, unresolved, partial, or unimplemented evidence paths must trigger a reviewer decision.
- Skill quality rubric: pass only if source coverage, access status, implementation status, limitations, missing lanes, evidence requirements, and review triggers are explicit.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/knowledge/source_registry.py`.
- CLI entry point: `metabo-agent route-sources`.

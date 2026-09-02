# Scientific Readiness Report

This report executes the repository's offline deterministic behavioral gates over synthetic fixtures and checksum-bound cached public artifacts. It complements the structural skill/agent audit and is not independent validation on external cohorts or analytical platforms.

## Result

- Strict synthetic release gate: **PASS**.
- Tests run: 295.
- Counts: passed=295, failed=0, error=0, skipped=0, expected_failure=0, unexpected_success=0.

## Behavioral gates

| Gate | Status | Tests | Passed | Failed | Errors | Skipped | Purpose |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `identity_and_assay_harmonization` | PASS | 13 | 13 | 0 | 0 | 0 | Blocks name-only identity, unresolved isomers, unsafe pooling, cross-study batch correction, and irreversible imputation. |
| `discovery_and_core_model_contracts` | PASS | 11 | 11 | 0 | 0 | 0 | Validates stable core-model serialization, inclusion criteria, repository-aware recommendation rules, and mirage detection. |
| `provenance_and_multi_repository_safety` | PASS | 27 | 27 | 0 | 0 | 0 | Retains explicit source provenance, one-to-many repository records, conservative source routing, and checksum-bound unseen-cohort inputs. |
| `statistical_and_review_safety` | PASS | 14 | 14 | 0 | 0 | 0 | Keeps uncertain mappings or annotations review-gated and validates effect-search multiplicity semantics. |
| `dataset_readiness_and_motrpac_alignment` | PASS | 12 | 12 | 0 | 0 | 0 | Validates deterministic dataset-readiness scoring and evidence-aware MoTrPAC metadata-alignment gates. |
| `motrpac_style_plotting` | PASS | 26 | 26 | 0 | 0 | 0 | Validates MoTrPAC contrast/FDR semantics, release and coverage gates, hierarchy views, deterministic exports, and optional renderers. |
| `skill_and_agent_contracts` | PASS | 10 | 10 | 0 | 0 | 0 | Checks paired Codex/Claude skill contracts, implementation links, and agent review boundaries. |
| `benchmark_integrity_and_reproducibility` | PASS | 33 | 33 | 0 | 0 | 0 | Validates explicit benchmark denominators, independent-reference universe checks, CLI parity and isolation, provenance, and byte-reproducible pilot outputs. |
| `biomarker_directional_check_integrity` | PASS | 28 | 28 | 0 | 0 | 0 | Validates checksum-bound paper-direction evidence, repository-derived After-versus-Before analysis, measurement location, numerical safety, and explicit identity, timing, matrix, selection, and dataset-independence boundaries. |
| `predictive_model_integrity` | PASS | 14 | 14 | 0 | 0 | 0 | Validates cold-cohort split isolation, leakage controls, abstention behavior, metric denominators, and synthetic-only classifier labeling. |
| `domain_review_contract_safety` | PASS | 14 | 14 | 0 | 0 | 0 | Validates advisory-only domain review packets, complete evidence-state coverage, and non-executable review boundaries. |
| `scientific_readiness_gate_integrity` | PASS | 11 | 11 | 0 | 0 | 0 | Validates required-module collection, import-error attribution, and unique gate ownership. |
| `literature_evidence_integrity` | PASS | 24 | 24 | 0 | 0 | 0 | Validates that an unreachable literature index is recorded as unavailable rather than as zero hits, that truncated or relevance-ranked sweeps are never declared complete, that unscreenable records and unlocated subject names stay unresolved instead of excluded, and that preprint, peer-reviewed and retracted records keep separate evidence tiers. |
| `gene_centric_annotation_integrity` | PASS | 54 | 54 | 0 | 0 | 0 | Validates that a gene-to-metabolite annotation is never emitted as a measurement, that an unreachable source, a zero-row answer, an unannotated gene, an ambiguous server error, an indeterminate empty body and an unrequested context stay distinct states, that KEGG-derived rows are withheld until the licence question is settled, and that an unverified adduct or a rejected request is never written as a match or as a coverage gap. |
| `network_boundary_integrity` | PASS | 4 | 4 | 0 | 0 | 0 | Validates that only allowlisted live-ingestion modules import a network client, that offline pilot modules stay offline, and that the documented allowlist matches the enforced one. |

## Nonpassing tests

- None.

## Gate integrity

- Every discovered test module has exactly one configured gate owner, and every configured module collected at least one test.

## Interpretation limits

- Passing does not validate performance on independent real studies, assay platforms, species, or cohorts.
- Database routing tests do not execute optional or planned external connectors.
- Hierarchy plots are descriptive; dedicated pathway enrichment and cross-platform meta-analysis models remain separate work.
- Skill contract scores measure structure and linkage, not empirical scientific validity.

The release gate should be rerun after scientific code, schemas, fixtures, skills, agents, or validation rules change.

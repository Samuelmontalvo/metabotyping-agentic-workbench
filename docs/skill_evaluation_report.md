# Skill and Agent Evaluation Report

This deterministic audit evaluates project-scoped skill and agent contracts. It checks structure, scientific guardrails, exact normalized Codex/Claude contract parity, declared implementation paths, canonical and deprecated-alias inventories, one-hop alias safety, duplicate logical agent names, and explicit input/output/review boundaries. It does not substitute for executing every scientific workflow against independent real-world data.

## Summary

- Skill files: 46 (23 paired skill names).
- Mean skill structural score: 1.000.
- Mean skill operational-linkage score: 1.000.
- Canonical agent files: 42 (21 paired canonical names).
- Mean agent contract score: 1.000.
- Deprecated alias files: 4 (2 paired alias names).
- Mean deprecated-alias contract score: 1.000.
- Host-addressable manifests: 46 (23 names).
- Inventory issues: 0.

## Inventory Issues

- None.

## Skill Results

| Skill file | Structural | Operational | Overall | Pair | Implementation | Issues |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `.agents/skills/assay-platform-harmonization/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/benchmark-agents/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/biospecimen-preanalytics-reviewer/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/define-inclusion-criteria/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/exercise-phenotype-harmonization-reviewer/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/grant-aims-refiner/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | agent_only_declared | none |
| `.agents/skills/harmonization-plan/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/harmonization-skeptic/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/human-review-packet/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/metabolite-effect-search/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/metabolite-identity-resolution/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/metadata-card-extraction/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/motrpac-alignment/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/motrpac-plotting/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/multi-database-metabolomics-router/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/plot-motrpac-bag3/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/quality-scoring/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/recommendation-engine/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/repository-intake/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/statistical-estimand-and-synthesis-skeptic/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/study-dataset-discovery/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/study-design-population-context-reviewer/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.agents/skills/variable-crosswalk/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/assay-platform-harmonization/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/benchmark-agents/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/biospecimen-preanalytics-reviewer/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/define-inclusion-criteria/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/exercise-phenotype-harmonization-reviewer/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/grant-aims-refiner/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | agent_only_declared | none |
| `.claude/skills/harmonization-plan/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/harmonization-skeptic/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/human-review-packet/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/metabolite-effect-search/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/metabolite-identity-resolution/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/metadata-card-extraction/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/motrpac-alignment/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/motrpac-plotting/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/multi-database-metabolomics-router/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/plot-motrpac-bag3/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/quality-scoring/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/recommendation-engine/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/repository-intake/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/statistical-estimand-and-synthesis-skeptic/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/study-dataset-discovery/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/study-design-population-context-reviewer/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |
| `.claude/skills/variable-crosswalk/SKILL.md` | 1.000 | 1.000 | 1.000 | pass | linked | none |

## Canonical Agent Results

| Agent file | Contract score | Pair | Issues |
| --- | ---: | --- | --- |
| `.codex/agents/assay-harmonization-skeptic.toml` | 1.000 | pass | none |
| `.codex/agents/benchmark-agent.toml` | 1.000 | pass | none |
| `.codex/agents/biospecimen-preanalytics-reviewer.toml` | 1.000 | pass | none |
| `.codex/agents/cross-field-consistency-arbitrator.toml` | 1.000 | pass | none |
| `.codex/agents/dataset-readiness-reviewer.toml` | 1.000 | pass | none |
| `.codex/agents/discovery-orchestrator.toml` | 1.000 | pass | none |
| `.codex/agents/exercise-phenotype-harmonization-reviewer.toml` | 1.000 | pass | none |
| `.codex/agents/harmonization-skeptic.toml` | 1.000 | pass | none |
| `.codex/agents/literature-retrieval.toml` | 1.000 | pass | none |
| `.codex/agents/metabolite-identity-resolver.toml` | 1.000 | pass | none |
| `.codex/agents/metabolomics-visualization-analyst.toml` | 1.000 | pass | none |
| `.codex/agents/metadata-extraction-critic.toml` | 1.000 | pass | none |
| `.codex/agents/metadata-extractor.toml` | 1.000 | pass | none |
| `.codex/agents/motrpac-metadata-readiness-analyst.toml` | 1.000 | pass | none |
| `.codex/agents/multi-source-orchestrator.toml` | 1.000 | pass | none |
| `.codex/agents/pipeline-builder.toml` | 1.000 | pass | none |
| `.codex/agents/repository-discovery.toml` | 1.000 | pass | none |
| `.codex/agents/source-registry-librarian.toml` | 1.000 | pass | none |
| `.codex/agents/statistical-estimand-and-synthesis-skeptic.toml` | 1.000 | pass | none |
| `.codex/agents/study-design-population-context-reviewer.toml` | 1.000 | pass | none |
| `.codex/agents/variable-crosswalk.toml` | 1.000 | pass | none |
| `.claude/agents/assay-harmonization-skeptic.md` | 1.000 | pass | none |
| `.claude/agents/benchmark-agent.md` | 1.000 | pass | none |
| `.claude/agents/biospecimen-preanalytics-reviewer.md` | 1.000 | pass | none |
| `.claude/agents/cross-field-consistency-arbitrator.md` | 1.000 | pass | none |
| `.claude/agents/dataset-readiness-reviewer.md` | 1.000 | pass | none |
| `.claude/agents/discovery-orchestrator.md` | 1.000 | pass | none |
| `.claude/agents/exercise-phenotype-harmonization-reviewer.md` | 1.000 | pass | none |
| `.claude/agents/harmonization-skeptic.md` | 1.000 | pass | none |
| `.claude/agents/literature-retrieval.md` | 1.000 | pass | none |
| `.claude/agents/metabolite-identity-resolver.md` | 1.000 | pass | none |
| `.claude/agents/metabolomics-visualization-analyst.md` | 1.000 | pass | none |
| `.claude/agents/metadata-extraction-critic.md` | 1.000 | pass | none |
| `.claude/agents/metadata-extractor.md` | 1.000 | pass | none |
| `.claude/agents/motrpac-metadata-readiness-analyst.md` | 1.000 | pass | none |
| `.claude/agents/multi-source-orchestrator.md` | 1.000 | pass | none |
| `.claude/agents/pipeline-builder.md` | 1.000 | pass | none |
| `.claude/agents/repository-discovery.md` | 1.000 | pass | none |
| `.claude/agents/source-registry-librarian.md` | 1.000 | pass | none |
| `.claude/agents/statistical-estimand-and-synthesis-skeptic.md` | 1.000 | pass | none |
| `.claude/agents/study-design-population-context-reviewer.md` | 1.000 | pass | none |
| `.claude/agents/variable-crosswalk.md` | 1.000 | pass | none |

## Deprecated Agent Aliases

| Agent file | Contract score | Pair | Issues |
| --- | ---: | --- | --- |
| `.codex/agents/data-quality-reviewer.toml` | 1.000 | pass | none |
| `.codex/agents/motrpac-replication-analyst.toml` | 1.000 | pass | none |
| `.claude/agents/data-quality-reviewer.md` | 1.000 | pass | none |
| `.claude/agents/motrpac-replication-analyst.md` | 1.000 | pass | none |

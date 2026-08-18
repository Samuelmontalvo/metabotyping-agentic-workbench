---
title: "MetaboTyping AI Workbench: Public-Data Discovery and Evidence Synthesis for Exercise Metabolomics"
---

**Authors:** Samuel Montalvo^1,2,3^; Eric Leslie^1,2,3^; Laurens van de Wiel^1,2,3^; Matthew T. Wheeler^1,2,3^

^1^ Division of Cardiovascular Medicine, Department of Medicine, Stanford University School of Medicine, Stanford, CA, USA  
^2^ Wu Tsai Human Performance Alliance, Stanford University, Stanford, CA, USA  
^3^ Stanford Cardiovascular Institute, Stanford University, Stanford, CA, USA

## Purpose

Metabolites provide a time-sensitive readout of the physiological response to exercise. Human studies have identified coordinated changes in circulating carbohydrates, lipids, amino acids, and related pathways after acute exercise, with patterns linked to substrate use, fitness, and cardiometabolic state (Lewis et al., 2010; Contrepois et al., 2020). Metabolite data therefore complement genomic and transcriptomic measurements by connecting an exercise bout to the body's immediate functional response.

The main barrier to reuse is harmonization. Studies differ in biospecimen handling, collection timing, assay platform, units, normalization, metabolite naming, and contrast definition. Standards initiatives and interlaboratory studies show that shared metadata, identifiers, and quality-control rules are needed before results can be compared or combined (Sumner et al., 2007; Salek et al., 2015; Siskos et al., 2017).

We propose to extend the MetaboTyping Agentic Workbench into the MetaboTyping AI Workbench. Its agents and skills will compile public records, clean and standardize metadata, harmonize variables and metabolite names, and package accepted mappings and summary statistics for analysis. The AI component may summarize cited material or draft a reviewer question, but deterministic rules and domain reviewers control what enters the analysis.

**Data boundary.** Only synthetic fixtures and already publicly released study-level metadata, documentation, and precomputed aggregate statistics are eligible. A catalog listing or anticipated release is not sufficient. Participant records, sample-level factor tables or matrices, identifiers, controlled-access, embargoed, unpublished, or data-use-agreement materials are prohibited. Public downloadability does not make sample-level data eligible.

## Specific aims

**Aim 1 - Find and rank public exercise metabolomics resources.** Each search will use eligibility criteria for human exercise metabolomics, specimen type, timing, assay, phenotype coverage, repository evidence, and access status. Records will be labeled as direct matches, possible enrichment sources, mirages, or exclusions. Each result will retain its source, accession, retrieval date, access statement, and reason for the decision.

**Aim 2 - Build reviewed metadata and summary-effect comparisons.** The workbench will create structured study, variable, analyte, and contrast records. Mappings will be labeled `accepted`, `requires_human_review`, or `rejected`; only accepted mappings may enter analysis. Public summary effects will be compared only when metabolite identity, matrix, timing, population, assay, and contrast direction are sufficiently compatible.

**Aim 3 - Test accuracy, safety, reproducibility, and usefulness.** Independent reviewers will assess held-out records and mappings without seeing workbench decisions. We will measure discovery and mapping accuracy, provenance completeness, safety errors, and deterministic reproducibility. A small manual-versus-assisted curation pilot may follow institutional review.

## Data and workflow

| Source | Use in this project | Excluded material |
|---|---|---|
| MoTrPAC Data Hub | Public release documentation and inspected group-level Analysis Results from `human-precovid-sed-adu` | Quant-ID, participant or sample metadata, feature-by-sample files, identifiers, raw trajectories, restricted or unpublished data |
| Metabolomics Workbench | Public study summaries, accessions, protocols, assay descriptions, access statements, and deposited aggregate results | `/factors`, `/data`, participant rows, sample matrices, and locally calculated summaries from those matrices |
| CFDE | Public catalog records, resource descriptions, identifiers, links, and access labels | Controlled workspace data; a catalog entry alone will not establish data eligibility |
| MetaboLights, RefMet, and publications | Public study metadata, protocols, nomenclature, accessions, and aggregate results | Participant-level extraction, sample matrices, and unsupported identity assignments |

MoTrPAC will provide the exercise-centered reference. Before ingestion, each summary table must identify its release, tissue or matrix, assay, time point, exercise group, contrast direction, analyte, and statistic. Files with an unknown aggregation level will be rejected. Metabolomics Workbench access will be limited to allowlisted study-level content and cannot retrieve sample tables. CFDE will be used for discovery and linking, not as permission to access underlying data.

The workflow has four steps:

1. Freeze the eligibility rules, source versions, schemas, prompts, scoring rules, and software version.
2. Search public records, confirm repository access, and flag missing codebooks, unclear timing, uncertain matrices, or inaccessible data.
3. Create structured evidence records and send uncertain phenotype, metabolite, unit, timing, or contrast mappings to review.
4. Compare only reviewed summary statistics and release each output with its source manifest, transformation record, software version, and decision state.

## Evaluation and deliverables

### Preliminary work

The completed offline MVP uses synthetic fixtures and does not access live participant data. As of July 12, 2026, 45 tests passed. A pilot with 10 publication records, 10 linked repository records, and 26 variable rows produced 4 direct matches, 3 enrichment candidates, 2 mirages, and 1 exclusion. Its crosswalk contained 12 accepted, 12 review-required, and 2 rejected variables. Mapping precision, recall, F1, and review-state accuracy were 1.00 against rule-derived fixtures. These results show that the workflow and safeguards run as intended; they do not establish external accuracy.

### Validation targets

Development examples will remain separate from the held-out evaluation set. Two reviewers will independently assess each item, with disagreements resolved by a third reviewer or consensus. Rules and software will be locked before adjudication.

| Domain | Measure | Target |
|---|---|---|
| Discovery | Precision and recall against an independently assembled public-resource set | Recall >= 0.90; precision >= 0.80 |
| Metadata and mappings | Field agreement, mapping F1, and review-state accuracy | Mapping F1 >= 0.85; review-state accuracy >= 0.85 |
| Safety | Prohibited intake, fabricated accessions, unsupported access claims, lost contrast direction, and unsafe mapping acceptance | Zero governance errors; unsafe mapping autoacceptance <= 0.05 |
| Reproducibility and utility | Regeneration of deterministic outputs; reviewer time and accuracy in the optional pilot | Identical outputs from frozen inputs; no loss of accuracy in assisted review |

Every accepted mapping, comparison, and published artifact must have complete provenance. Incomplete records will remain quarantined. The project-defined MoTrPAC-informed feasibility rubric will describe reuse potential; it is not an official MoTrPAC instrument or consortium endorsement.

### Schedule and products

| Period | Products |
|---|---|
| Months 1-3 | Final data policy, schemas, source manifests, adapters, and independent discovery reference set |
| Months 4-6 | Public-resource catalog, evidence records, mapping benchmark, reviewer packets, and MoTrPAC summary allowlist |
| Months 7-9 | Held-out accuracy and safety evaluation, reviewed summary comparisons, reproducibility audit, and internal Stanford presentations |
| Months 10-12 | Optional reviewer pilot, public software and benchmark release, external presentation series, and methods manuscript |

The publication and all internal Stanford and external presentations will report only synthetic examples or outputs derived from already publicly released study-level metadata and aggregate statistics. No controlled-access, embargoed, unpublished, participant-level, or sample-level data will appear in manuscripts, figures, tables, slides, demonstrations, or shared files.

The reviewer pilot will not begin until Stanford provides the appropriate determination and the protocol addresses consent, privacy, compensation, retention, and supervisory conflicts. The project will not attempt re-identification, participant linkage, clinical prediction, or individual risk assessment.

**Selected references:** Lewis GD, et al. *Science Translational Medicine*. 2010;2:33ra37; Contrepois K, et al. *Cell*. 2020;181:1112-1130.e16; Sumner LW, et al. *Metabolomics*. 2007;3:211-221; Salek RM, et al. *Metabolomics*. 2015;11:1587-1597; Siskos AP, et al. *Analytical Chemistry*. 2017;89:656-665; Sanford JA, et al. *Cell*. 2020;181:1464-1474; MoTrPAC Study Group. *Journal of Applied Physiology*. 2024;137:473-493; NIH Common Fund Data Ecosystem public portal and FAQ; MoTrPAC Data Hub and Metabolomics Workbench API documentation. Online resources accessed July 2026.

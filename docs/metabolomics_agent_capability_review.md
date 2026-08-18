# Metabolomics agent capability and scientific quality review

- Review date: 2026-07-23
- Repository version reviewed: local `0.2.0` pre-release snapshot
- External capability comparator: installed Life Science Research plugin `1.0.3`

## Executive conclusion

This repository now has a credible, unusually rigorous **offline metabolomics curation and planning core**: deterministic source routing, one-to-many repository preservation, review-gated chemical identity decisions, assay-aware harmonization planning, provenance-bearing artifacts, and a MoTrPAC-style plotting workflow. Its strongest differentiator is not database count; it is the explicit separation of identity evidence, assay compatibility, quantitative scale, QA/QC, missingness, and human approval.

It is not yet scientifically supportable to call the workbench the “most comprehensive” metabolomics agent system. That claim would require a reproducible head-to-head benchmark against named alternatives and external expert-annotated datasets. The installed Life Science Research plugin is broader for live, focused biological-database retrieval. This workbench is deeper for deterministic metabolomics review artifacts and fail-closed harmonization. The two are complementary.

The main blockers to a production-quality superlative are:

1. most sources in the registry do not yet have native, tested live adapters;
2. cross-database chemical reconciliation is not yet ontology- and structure-backed end to end;
3. harmonization rules have only synthetic validation and do not estimate assay bridges or commutability;
4. cross-platform meta-analysis diagnostics are specified but not calculated;
5. pathway inference is not implemented, and current class summaries must not be presented as pathway evidence;
6. plotting has not been numerically and visually validated against a frozen MoTrPAC reference release;
7. there is no independent, real-world external validation set.

## Scope and evidence standard

This is a capability review, not an exhaustive market survey. It compares:

- the repository’s code, tests, schemas, scripts, paired agent/skill contracts, and synthetic fixtures;
- the installed Life Science Research router and its ChEBI, HMDB, PubChem, MetaboLights, Reactome, and PRIDE skill contracts;
- the scientific expectations represented by [mQACC](https://www.mqacc.org/) and its [QA/QC best-practices paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9420093/), the [Metabolomics Standards Initiative chemical-analysis reporting framework](https://pmc.ncbi.nlm.nih.gov/articles/PMC3853013/), [COMETS cross-platform methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC8897993/), [RefMet classification](https://www.metabolomicsworkbench.org/databases/refmet/refmet_classification.php), the [Lipidomics Standards Initiative](https://lipidomicstandards.org/), and the [MoTrPAC endurance-training molecular map](https://www.nature.com/articles/s41586-023-06877-w).

No external API was executed for this review. “Plugin capability” below means the installed skill contract describes a compact REST workflow; it does not mean that connector behavior or database availability was independently validated here.

Status terms used in this document:

- **Implemented/tested**: executable local logic with focused tests.
- **Implemented/synthetic-only**: executable and tested, but validation evidence is synthetic or local.
- **Optional connector**: available through the installed Life Science Research plugin, not a native offline adapter in this repository.
- **Routed/reference-only**: represented in a deterministic plan or standards registry, but not retrieved or computed by that component.
- **Experimental/local**: executable and tested against local tables, but not externally validated for general use.
- **Planned**: required for scientific completeness and not yet implemented.

### Repository agent/skill architecture reviewed

The paired Codex/Claude skill contracts cover four connected layers:

- discovery and routing: inclusion criteria, study/dataset discovery, repository intake, recommendation, and multi-database metabolomics routing;
- extraction and identity: metadata cards, metabolite-effect search, variable inventories/crosswalks, and metabolite identity resolution;
- harmonization and QA: assay-platform harmonization, harmonization plans,
  metadata-backed dataset-readiness scoring, skeptical review, and human-review
  packets;
- evaluation and communication: MoTrPAC alignment, MoTrPAC plotting, focused BAG3 plotting, grant-aim refinement, and agent benchmarking.

The 18 canonical paired agent roles provide discovery, extraction,
source-orchestration, crosswalk, identity-resolution, assay-skeptic,
dataset-readiness, pipeline, metabolomics-visualization, MoTrPAC metadata,
benchmark-audit, study-design/population, exercise-phenotype, biospecimen
preanalytics, and statistical-estimand/synthesis perspectives. The four domain
reviewers share an advisory-only evidence-packet contract and cannot make
executable scientific decisions. Two deprecated role-name aliases remain
addressable only through 0.2.x. These files are scientific workflow contracts
and role prompts; their presence is not proof that every capability is executed
autonomously. The implementation links and behavioral tests cited below
determine actual readiness.

## Multi-database biology comparison

The Life Science Research router classifies broad questions into a small number of evidence lanes, normalizes core entities, selects a minimal set of downstream skills, optionally parallelizes independent lookups, and synthesizes evidence with caveats. Its source-specific skills are deliberately narrow REST clients. The workbench router instead emits a deterministic, machine-readable retrieval plan with implementation status, access policy, limitations, and minimum evidence requirements. Routing does not execute a source and does not resolve chemical identity.

| Capability | Installed Life Science Research ecosystem | This workbench | Grounded assessment and next action |
|---|---|---|---|
| Broad research orchestration | Router supports multi-lane biology questions, entity normalization, source selection, optional parallel retrieval, and evidence synthesis. | **Implemented/tested** in `knowledge/source_registry.py` for deterministic metabolomics-oriented lane and identifier routing. | Plugin is broader for live biological synthesis; workbench is more auditable for offline route planning. Add an execution manifest that records every attempted source, response version, failure, and fallback. |
| ChEBI | Optional connector supports search, compound records, ontology parents/children, and structure metadata. | **Optional connector** plus registry routing; no native cached ChEBI adapter or reconciliation engine. | Route stable `CHEBI:` identifiers, but do not claim ontology-backed identity resolution until response fixtures, releases, conflict rules, and tests exist. |
| HMDB | Optional connector supports metabolite, protein, disease, and pathway searches. | **Optional connector** plus registry routing; no native HMDB record normalizer. | Record HMDB release/version and verify targeted records. Search results and synonyms must never authorize a merge. |
| PubChem | Optional connector supports compound properties/descriptions, assay summaries, and substance metadata. | **Optional connector** plus registry routing; no native PUG response normalizer. | Keep PubChem Compound and Substance assertions distinct; require structure-layer agreement for automatic identity decisions. |
| MetaboLights | Optional connector supports archive browsing and study-level records. | **Optional connector** plus registry routing; native live study ingestion is not implemented. | Add paginated study/file inventory retrieval, ISA metadata normalization, partial-failure reporting, and frozen response fixtures. |
| Reactome | Optional connector supports event, pathway, participant, search, and diagram-related data. | **Optional connector** plus registry routing; no native participant-to-metabolite pathway analysis. | Require species, stable entity identifiers, pathway release, assay-specific background, coverage, ambiguity, and multiple-testing correction before inferential use. |
| PRIDE | Optional connector supports project discovery and project-level proteomics metadata. | **Optional connector** plus registry routing for multi-omics context. | Preserve the evidence boundary: proteomics supports context but is not metabolite evidence. Add explicit cross-omics provenance and entity-mapping tests before integration. |
| Metabolomics Workbench | Not one of the comparator skills reviewed here. | **Implemented/tested** live metadata intake plus offline fixtures; study metadata, sample-matrix gating, and MoTrPAC comparison workflows exist. | This is the most mature native source adapter. Production release still needs pagination/completeness manifests, API-version capture, retry/failure tests, and external validation. |
| MoTrPAC Data Hub | Not a focused connector in the reviewed plugin subset. | **Implemented/tested** specialized local comparison and plotting inputs; registry describes release-aware requirements. | Freeze release, tissue, assay, sex, group, timepoint, and contrast identifiers in every artifact. Do not treat visual agreement as replication. |
| RefMet | Not a focused connector in the reviewed plugin subset. | **Implemented/local snapshot** for standard names and super/main/sub-class annotations; plotting and effect-search workflows consume the hierarchy. | Record the snapshot release. A RefMet name/class annotation is classification evidence, not structural identity evidence. |
| Other registered sources | Broader plugin includes many other biology-specific skills beyond this review. | Registry includes MetaboBank, GNPS/MassIVE, LIPID MAPS, MassBank, MoNA, Rhea, WikiPathways, KEGG, GWAS Catalog, GTEx, UniProt, ChEMBL, and standards references. | Registry breadth is not adapter breadth. Keep every `implementation_status` visible and never report a routed/planned source as queried. |

### What the workbench adds beyond source lookup

| Scientific capability | Current evidence | Status | Remaining requirement |
|---|---|---|---|
| One study in multiple repositories | All repository rows are grouped and retained; singular indexing fails on duplicates; study cards list all accessions; dataset-card names and row provenance are collision-safe. | **Implemented/tested** | Validate record linkage across repositories without assuming matching titles/accessions identify the same cohort. |
| Candidate study discovery and mirage detection | Deterministic inclusion criteria, modality scoring, access/codebook/data checks, metadata cards, and review artifacts. | **Implemented/synthetic-only** | Benchmark sensitivity and false-discovery rate on independently curated public studies. |
| Chemical identity merge control | Names are explicitly non-identity evidence; shared stable identifiers, InChIKey conflicts/layers, structural resolution, MSI level, authentic-standard evidence, and provenance are checked. | **Implemented/synthetic-only** | Add structure-aware normalization, ontology mappings, adduct/salt/tautomer policies, identifier-release provenance, one-to-many reconciliation, and expert gold sets. |
| Assay/platform harmonization | Typed identity, method, platform, matrix, scale, unit, calibration, internal/reference standard, batch, pooled QC, drift, blank, LOD/LOQ, missingness, censoring, and provenance fields feed a fail-closed decision engine. | **Implemented/synthetic-only** | Validate policies on real LC-MS, GC-MS, NMR, direct-infusion, and commercial-kit bridges; estimate commutability rather than merely accepting a declared bridge ID. |
| Raw-value pooling | Allowed only for accepted MSI-level-1 exact identities, linear absolute concentrations, compatible matrices and units, adequate QA/QC, and compatible or prevalidated methods. | **Implemented/synthetic-only** | Confirm that local QC-CV and missingness thresholds are study-approved policies, not universal mQACC mandates; add sensitivity analyses. |
| Relative abundance/intensity combination | Raw pooling is blocked; compatible cases are limited to study-specific effects. | **Implemented/synthetic-only** | Implement effect-size standardization rules and verify comparable estimands, contrast orientation, variance estimates, and dependence structure. |
| Cross-platform meta-analysis | Decisions carry a plan for Cochran’s Q, I², τ², platform moderator, leave-one-study-out, and leave-one-platform-out checks. | **Routed/reference-only** | Compute and test the diagnostics, propagate mapping uncertainty, define fixed/random-effect selection, and prevent pooling when estimands differ. |
| Dataset-readiness scoring | Structured metadata-completeness and reuse-readiness logic is present; its legacy field names remain stable for API compatibility. It is not an overall study-quality, risk-of-bias, assay-validity, or evidence-strength assessment. | **Implemented/synthetic-only** | Validate scoring weights and thresholds against blinded expert curation-triage ratings; distinguish “not reported” from “failed.” |
| Behavioral benchmarking | Candidate precision/recall/F1, automatic-accept precision/recall, unsafe-auto-accept rate, review capture, review-status accuracy, and quality agreement are separated; direct proportions include Wilson intervals, every union case is classified, and deterministic manifests preserve input/output provenance. | **Implemented/synthetic-only** | Add external challenge sets for isomers/platforms/missingness and multi-curator adjudication; the benchmark agent audits canonical deterministic results rather than recomputing them. |
| Pathway inference | Source registry routes Reactome/Rhea/WikiPathways/KEGG; plotting accepts supplied pathway labels. | **Planned** | Implement stable-ID/species mapping, explicit measured background, ambiguity weights, coverage, pathway versioning, dependence-aware testing, BH scope, and sensitivity analyses. |
| RefMet class enrichment | Local effect-search code uses a separate background for each source/study, species, matrix, assay/panel, contrast, and subgroup stratum; tests all labels before query filtering; applies BH within stratum; and reports stable-ID support plus annotation provenance/release gaps. | **Experimental/local** | Current effect tables lack source-carried RefMet IDs, so all identity-dependent rows remain review-required. Freeze the RefMet release; address duplicate/correlated feature rows and class-size sensitivity; validate background/exchangeability assumptions; add dependence-aware or permutation sensitivity analyses and external validation. Do not call this pathway analysis. |
| Human-review boundary | Accepted, review-required, and non-combinable artifacts are separate; transforms are withheld from unaccepted decisions. | **Implemented/tested** | Add signed reviewer identity, decision timestamp outside deterministic payloads, rationale/version history, and invalidation when source evidence changes. |

## Standards alignment and gaps

### mQACC QA/QC

The assay record and decision logic operationalize many fields emphasized by mQACC-oriented QA/QC practice: pooled QC samples and frequency, reference materials, blanks, run order, drift evaluation/correction, internal standards, calibration, feature QC precision, LOD/LOQ, censoring, missingness, and batch scope. Missing evidence is review-gated rather than silently treated as acceptable.

This is alignment, not certification. The workbench’s QC-CV and missingness cutoffs are local policy defaults. They should be versioned, justified per platform and intended use, and evaluated in sensitivity analyses. mQACC guidance is not itself a study-level quality score.

### MSI identification and reporting

The harmonization engine requires exact structural resolution, linked evidence, and MSI-level-1 declarations before automatic identity acceptance for raw-value pooling. It blocks or reviews name-only matches, unresolved stereochemistry/positional isomers, and conflicting InChIKeys.

The remaining weakness is upstream evidence verification: the current synthetic records declare the identification level and standard evidence. A production resolver must validate authentic-standard, retention, MS/MS, instrument, and provenance evidence against source records rather than trusting a label.

### RefMet nomenclature and hierarchy

RefMet labels and super/main/sub-class fields are retained for nomenclature and descriptive grouping. The workbench correctly keeps classification separate from identity. Release provenance is not consistently present in the local snapshot and is therefore an explicit blocker for production-grade reproducibility.

The local effect-search interpretation boundary is especially important:

- current source effect CSVs do not contain source-carried RefMet IDs; IDs found by exact name lookup are annotation aids, and current identity-dependent matches remain `requires_human_review`;
- only a source-carried, resolvable, non-conflicting stable identifier can pass the local curated retrieval/annotation gate; the emitted decision scope explicitly does not satisfy MSI assay identity or harmonization eligibility;
- the missing snapshot release is emitted as `not_recorded_in_local_snapshot` rather than inferred from a file timestamp;
- rat `metabolomics_timewise` is an aggregate result-block label, not feature-level physical-platform metadata;
- enrichment is feature-row over-representation within a declared stratum, reusing source FDR calls; it is not pathway activation, meta-analysis, or proof that rows are independent biological observations;
- BH q values cover the complete class-test family within one stratum; q values from different strata are not a pooled testing family.

Pathway is not a RefMet hierarchy level. Any pathway column in the plotting workflow is input annotation from another curated source and needs its own source, species, version, and membership provenance.

### Lipidomics Standards Initiative

LSI is present as a standards reference, and the assay model can distinguish exact structure, unresolved stereochemistry/positional isomers, lipid-species resolution, chemical class, and feature-only evidence. However, the repository does not yet implement an LSI checklist validator or a complete lipid nomenclature/structural-resolution grammar. It must not promote sum composition, fatty-acyl composition, positional information, or stereochemistry beyond what the assay established.

### COMETS cross-platform analysis

The harmonization plan follows the central COMETS lesson that platform heterogeneity should be modeled rather than erased: raw relative/intensity values are not pooled, and study-specific effects carry heterogeneity and platform-sensitivity requirements. The diagnostics are currently a plan only. No release claim should imply COMETS-equivalent meta-analysis until Q, I², τ², platform moderation, and leave-one-platform-out results are actually computed and tested.

### MoTrPAC comparison

The local Python plotting workflow covers the requested visual families:

- contrast-explicit volcano plots with nominal p values, FDR, effect thresholds, direction labels, and quality flags;
- metabolite-by-contrast effect heatmaps with duplicate-cell and mixed-scale rejection;
- single-metabolite effect panels;
- single-metabolite time trajectories with explicit group/timepoint order and missing/LOD denominators;
- descriptive pathway, sub-class, main-class, and super-class heatmaps with accepted-annotation, accepted-mapping, minimum-feature, and expected-universe coverage gates;
- deterministic plot-ready CSVs and a checksummed provenance manifest.

These are **MoTrPAC-style and reviewable**, not a certified reproduction of MoTrPAC’s statistical pipeline or figures. The workflow consumes effect estimates; it does not fit MoTrPAC’s models from raw data. Hierarchy cells are unweighted descriptive medians, not normalized enrichment scores or inferential pathway statistics. Current gaps include repeated-measures/covariate modeling, uncertainty display for effect estimates, pathway-level inference, exact release/palette/ordering validation, and numerical/visual regression against frozen MoTrPAC reference results.

## Scientific release gates

All gates below should be machine-checked where possible. A structural skill-contract score is necessary but not sufficient.

### Gate 1 — retrieval and provenance completeness

- Every executed source has database/API version or release, query/endpoint, retrieval status, accession/entity ID, artifact hash, and license/access notes.
- Pagination and file inventories are complete or explicitly partial.
- Source failures, empty responses, rate limits, and fallbacks remain visible; no silent source substitution.
- Every study retains all repository/accession assertions and any record-linkage uncertainty.

### Gate 2 — chemical identity safety

- Unsafe name-only automatic merges: **zero** in all challenge and external-validation sets.
- Accepted identity decisions have stable identifier and structure-resolution evidence with resolvable provenance.
- Conflicting identifiers, stereochemistry, positional isomers, adducts, salts, tautomers, and lipid resolution are either resolved by documented rules or routed to review.
- Database and ontology releases are frozen; one-to-many and obsolete-ID mappings remain explicit.

### Gate 3 — assay and quantitative compatibility

- Matrix, collection timing, assay/method/version, platform, acquisition, quantitation type, unit, scale, calibration, internal/reference standard, LOD/LOQ, missingness, censoring, and batch/QC evidence are present or review-blocking.
- Raw pooling occurs only after identity, quantitative, QA/QC, and method-bridge gates all pass.
- Relative abundance, normalized intensity, and feature intensity never enter a pooled concentration table.
- No cross-study batch correction and no irreversible imputation hidden from the decision record.
- Every transform is registered, ordered, reversible or traceable, unit-tested, and withheld from review/non-combinable pairs.

### Gate 4 — statistical analysis

- Estimand, numerator/denominator, model, covariates, repeated-measures structure, effect scale, variance, and test family are explicit.
- FDR method, scope, and number of tests are recorded; partial adjusted-value columns are not silently completed.
- Cross-platform synthesis calculates and reports Q, I², τ², platform moderation, leave-one-study-out, and leave-one-platform-out diagnostics.
- Pathway/class inference declares stable-ID membership, species, database release, measured background, coverage, ambiguous mappings, minimum size, multiplicity correction, and sensitivity analyses.
- Descriptive aggregation is labeled descriptive and contains no invented category p value.

### Gate 5 — plotting integrity

- Figure direction, effect scale, significance rule, FDR scope, matrix/tissue, timepoint, sex/group, assay, platform, and source release are reviewable from the artifact bundle.
- Cross-dataset heatmaps include only accepted canonical mappings; excluded/review-gated cells are visible.
- Missingness, below-LOD burden, low coverage, and untestable cells cannot be mistaken for null effects.
- Numerical tables and rendered figures pass deterministic regression checks against frozen expected outputs.
- A domain reviewer verifies a MoTrPAC reference-reproduction packet before “MoTrPAC-comparable” is used without the qualifier “style.”

### Gate 6 — external validation and agent comparison

- Evaluate independent real studies spanning targeted LC-MS, untargeted LC-MS, GC-MS, NMR, direct infusion, and commercial panels without adding their participant data to repository fixtures.
- Use at least two blinded metabolomics curators with adjudication; report agreement and unresolved cases.
- Report candidate recall separately from automatic-accept precision, unsafe-auto-accept rate, and review capture, with confidence intervals.
- Benchmark this workbench and named alternatives on the same frozen tasks, sources, evidence budget, and scoring rubric.
- Do not make a “most comprehensive” claim unless the benchmark, coverage definition, failure analysis, and reproducible artifacts are public.

## Recommended implementation order

1. Build frozen-response native adapters for MetaboLights, ChEBI, HMDB, PubChem, and Reactome, with source execution manifests and failure tests.
2. Add an ontology/structure reconciliation layer that preserves every database assertion and emits one-to-many conflict sets rather than a single guessed identity.
3. Validate assay policies and bridge requirements against independent expert-curated multi-platform examples.
4. Implement effect-size synthesis and the heterogeneity diagnostics already named in harmonization decisions.
5. Implement pathway inference separately from plotting, with explicit species, universe, version, coverage, ambiguity, and multiplicity controls.
6. Freeze a MoTrPAC reference release and create numeric plus image-regression tests for volcano, feature heatmap, single-feature trajectory, and pathway/class outputs.
7. Publish a capability benchmark and scientific-readiness report that clearly separates contract structure, synthetic behavior, external validity, and unresolved limitations.

## Bottom line

The present system is best described as a **scientifically conservative, metabolomics-specific agentic workbench with broad source routing and unusually explicit harmonization/plotting review gates**. It is already deeper than a generic multi-database router for assay compatibility and artifact provenance. It remains narrower than a mature multi-database biology ecosystem for live retrieval and is not yet externally validated. Closing the release gates above—not adding unverified database names—is the path to a defensible claim of comprehensive metabolomics capability.

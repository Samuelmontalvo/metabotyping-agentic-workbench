---
title: "MetaboTyping Agentic Workbench: Review-Gated Research Software for Metabolomics Dataset Curation and Harmonization"
bibliography: references.bib
csl: nlm-citation-sequence.csl
link-citations: true
reference-section-title: References
---

Samuel Montalvo^1,2,3^, Eric Leslie^1,2,3^, Laurens van de Wiel^1,2,3^, and Matthew T. Wheeler^1,2,3^

^1^ Division of Cardiovascular Medicine, Department of Medicine, Stanford University School of Medicine, Stanford, CA, USA  
^2^ Wu Tsai Human Performance Alliance, Stanford University, Stanford, CA, USA  
^3^ Stanford Cardiovascular Institute, Stanford University, Stanford, CA, USA

Corresponding author: Samuel Montalvo, Division of Cardiovascular Medicine, Department of Medicine, Stanford University School of Medicine, Stanford, CA, USA. Email: smontal@stanford.edu

## Abstract

Public metabolomics studies are difficult to reuse when the publication, repository record, variable definitions, chemical identity evidence, assay characteristics, and sampling context are incomplete or distributed across sources. We developed MetaboTyping Agentic Workbench, a review-gated software system that converts these inputs into provenance-bearing study cards, source plans, variable crosswalks, assay-compatibility decisions, review queues, and plot-ready tables. Deterministic Python modules make the reported decisions; agent and skill files provide optional interfaces to those modules and are not the source of scientific results. The current version was evaluated with synthetic records because no participant-level data are distributed with the software. The complete suite passed 81 tests. In a 10-study pilot, the workflow retained 26 study-specific variables, accepted 12 variable mappings, routed 12 to review, and rejected two. In five synthetic assay-pair challenges, one pair met all stated requirements for pooling individual values, one required review, and three were non-combinable for raw-value pooling. These results establish reproducible behavior on local fixtures, not accuracy on external repositories or analytical platforms. The software is intended to support expert curation before cross-study analysis; it does not establish metabolite identity from names, fit biological models from raw data, or replace expert review.

**Keywords:** metabolomics; data harmonization; exercise; research software; chemical identity; provenance; human review

## Problem statement and objectives

Public metabolomics data can support secondary analyses only when the biological and analytical context needed to interpret each measurement is recoverable. A study accession or processed metabolite table does not by itself specify who was studied, the intervention or exposure, specimen matrix and collection time, analytical platform, metabolite-identification evidence, quantitative scale, missing-data process, or quality-control results. Recent work on metabolomics reuse and pan-repository reanalysis identifies incomplete or inconsistent metadata as a continuing barrier even as the number of deposited datasets grows [@gouveia2024reuse; @elabiead2025panredu]. Common data models help standardize computational objects, but they do not determine whether two study variables or assay measurements are scientifically equivalent [@mitchell2024commonmodels].

This problem is pronounced in exercise studies. The Molecular Transducers of Physical Activity Consortium (MoTrPAC) measures molecular responses across tissues, time points, exercise conditions, and assay platforms [@sanford2020motrpac; @motrpac2024temporal]. Its human protocol also links molecular assays to cardiopulmonary exercise testing (CPET), activity, body composition, and other phenotypes [@motrpac2024humanprotocol]. A secondary comparison with a public study therefore requires more than detecting the words "exercise" and "metabolomics." The analyst must determine whether the population, intervention, specimen timing, matrix, assay, phenotype definition, and effect contrast are sufficiently compatible for the proposed analysis.

Metabolomics Workbench and MetaboLights provide repositories for data, metadata, and protocols [@sud2016workbench; @haug2020metabolights]. RefMet supplies a reference nomenclature and hierarchy [@fahy2020refmet], and MetaboAnalyst provides data-processing and analysis functions [@pang2024metaboanalyst]. These resources address different parts of the reuse process. They do not, on their own, produce a question-specific record of why a dataset was included, why an identity or variable mapping was accepted, or why values from two assays may or may not be combined. Retrospective harmonization guidance similarly requires definitions, units, timing, populations, and measurement procedures to be compared before variables are pooled [@fortier2017maelstrom].

MetaboTyping Agentic Workbench was developed to examine whether these curation decisions can be represented as reproducible software artifacts. The system has three objectives. First, it identifies candidate studies and records the repository evidence needed to assess reuse. Second, it separates variable equivalence, metabolite identity, and assay compatibility so that uncertainty in one domain cannot be hidden by agreement in another. Third, it produces reviewable feasibility summaries and MoTrPAC-style visual outputs without treating visual agreement as biological replication. The target user is a researcher or data curator preparing a cross-study metabolomics analysis. The system is not designed for causal inference, autonomous biological interpretation, or clinical decisions.

## Software design and methods

### Evidence model and workflow

The software is a Python 3.11 package with a command-line interface. A text question is converted into a serialized inclusion-criteria record. The default required criteria are human participants and metabolomics; exercise, actigraphy, physical activity, genetics, CPET, body composition, and diet can be specified as preferred attributes. Publication and repository rows remain separate and are joined by study identifier. When one study has records in more than one repository, every record is retained rather than collapsed into a single accession.

The discovery module records whether repository metadata, a variable dictionary, data files, sample matrix, assay platform, biospecimen timing, and sample size were observed. Candidate scores begin at 0.40 after the two required criteria are met and add fixed increments of 0.01-0.12 for requested modalities and repository evidence. The score is a deterministic ranking heuristic, not a probability of eligibility or scientific quality. In this manuscript, candidates that lack required repository assets are described by the specific missing evidence. The historical internal code label for that state is not used as a scientific construct.

A source registry can route a request to study, chemical-identity, assay, pathway, genetics, or multi-omics evidence sources. The output is a retrieval plan with implementation status and access limitations. Routing is distinct from source execution. The current repository includes a native Metabolomics Workbench metadata intake, specialized local MoTrPAC inputs, and an offline RefMet snapshot. Several other databases are represented as optional connectors, standards references, or planned adapters; a routed source is not reported as queried.

The extraction layer writes study, dataset, and variable cards. Each card contains a source path and row key. JSON Schema checks enforce required structure before artifacts are written. The harmonization layer then evaluates variable definitions, chemical identifiers, structural resolution, assay method, specimen matrix, quantitative scale, units, calibration, batch handling, quality assurance and quality control (QA/QC), limits of detection and quantification, missingness, censoring, and source provenance. Decisions are emitted as `accepted`, `requires_human_review`, or `non_combinable`; only accepted transformations can enter an approved individual-value plan.

Figure 1 summarizes the evidence flow. The optional agent interfaces invoke the same deterministic modules. The evaluated offline workflow does not call a language model.

### Quantitative decision rules

Table 1 reports the principal thresholds used in version 0.1.0. They are software policy values chosen for conservative synthetic testing. They have not been calibrated against external curator decisions or downstream replication success.

**Table 1. Principal decision rules in the evaluated software version.**

| Component | Implemented rule | Interpretation and limitation |
| --- | --- | --- |
| Study ranking | Human and metabolomics are required. Fixed increments of 0.01-0.12 are added for requested modalities and documented repository assets; the score is capped at 1.00. | Orders candidates for review; it is not a probability or validated quality measure. |
| Variable crosswalk | Automatic acceptance requires score >=0.90, compatible modality and unit, and reported timing. Incompatible modality is rejected. Other supported proposals are reviewed. | The score is a rule-based evidence summary. Its weights are not learned or externally calibrated. |
| CPET endpoint | `vo2peak` and `peak_vo2` may be proposed as `vo2max`, but their score is capped at 0.78 and cannot be accepted without protocol and endpoint evidence. | VO₂peak and VO₂max remain distinct unless a reviewer verifies the exercise-test criteria used to define the endpoint. |
| Assay pooling | Both records must have exact-structure evidence, Metabolomics Standards Initiative level 1 identification, linear absolute concentrations, compatible matrix and units, adequate QA/QC, and a validated bridge when methods differ. | A matching metabolite name or class never authorizes pooling [@sumner2007msi]. Relative abundance and feature intensity remain study-specific. |
| Missingness and QC | Missing fraction >0.20 triggers review and >0.50 blocks combination. Default pooled-QC coefficient-of-variation limits are 20% for targeted assays and 30% for other assays. | These are versioned local defaults, not universal mQACC requirements. The source study must report its own acceptance criteria [@kirwan2022mqacc]. |
| Dataset readiness heuristic | The weighted sum uses ten subscores with weights from 0.05 to 0.15. The internal `study_design_rigor` field awards points for human status, sample size, and combined activity/metabolomics evidence. | This is a metadata and analysis-readiness heuristic. It is not a risk-of-bias instrument or a validated assessment of study design. |
| MoTrPAC feasibility | Eleven binary criteria are averaged. Tiers are high (>=0.85), moderate (>=0.65), low (>=0.40), or not feasible; documented human participation is required for any feasible tier. | Screens metadata completeness for a specified comparison. It does not demonstrate replication or biological comparability. |

The assay rules distinguish raw-value pooling from synthesis of study-specific effect estimates. Cross-platform metabolomics studies can retain comparable effects even when raw concentrations or intensities cannot be placed in one table, but the estimand, contrast orientation, uncertainty, and platform heterogeneity must remain explicit [@temprosa2022comets]. The current software records a plan for Cochran's Q, I², τ², platform moderation, and leave-one-platform-out analyses; it does not calculate those statistics.

### Agent and skill interfaces

The current worktree contains 18 paired skill names represented by 36 Codex and Claude skill files, and 14 paired agent roles represented by 28 role manifests. The contracts cover source routing, dataset discovery, metadata extraction, metabolite identity, variable and assay harmonization, quality review, MoTrPAC-oriented evaluation and plotting, and benchmark reporting. Each contract declares inputs, outputs, failure conditions, evidence requirements, and points that require expert review.

These files are interfaces and operating instructions. They are not trained models, and their presence does not show that an interactive model will follow the instructions. Reported pilot outputs come from the Python modules. This distinction is necessary because fluent agent output can create unwarranted confidence when the underlying evidence is incomplete [@messeri2024illusions].

### Example questions and prompts

Table 2 illustrates questions that can be routed through the agent-facing interfaces. Each prompt requests an artifact and states a boundary on interpretation.

**Table 2. Example questions and prompts for the agent-facing interfaces.**

| Research question | Example prompt | Expected artifact |
| --- | --- | --- |
| Which studies meet the question and have usable repository evidence? | "Find human metabolomics studies with exercise or actigraphy. Require a repository record, matrix, assay, timing, metadata, and codebook. List each missing item; do not infer availability." | Ranked candidates with criterion-level rationale and source provenance. |
| Which sources should be queried? | "Plan sources for study metadata, chemical identity, assay QA/QC, and pathway context. Mark each source as native, optional, planned, restricted, or reference-only. Do not report a routed source as queried." | Machine-readable source plan with access and implementation status. |
| Do two features represent the same metabolite? | "Compare the reported names, stable identifiers, InChIKeys, structural resolution, MSI level, standard evidence, and provenance. A name match alone must remain unresolved." | Identity decision with evidence, blockers, and a reviewer question. |
| Can two assay outputs be combined? | "Assess matrix, method, platform, quantitation type, unit, calibration, QC CV, missingness, censoring, and method bridge. State whether raw pooling, effect-only synthesis, review, or no combination is allowed." | Assay decision, permitted analysis, transforms, and audit record. |
| Can CPET variables be harmonized? | "Evaluate `peak_vo2`, `vo2peak`, and `vo2max`. Report units, timing, exercise protocol, and endpoint criteria. Do not accept VO₂peak as VO₂max without protocol evidence." | Variable crosswalk with acceptance or review status. |
| How can local Metabolomics Workbench-style and MoTrPAC-style effects be visualized? | "Create a contrast-explicit volcano plot and a heatmap restricted to accepted metabolite mappings. Export plot-ready CSV files and a provenance manifest. Do not describe visual agreement as replication." | Validated plotting tables, figures, and checksummed manifest. |

### Literature context and citation management

A targeted literature update was performed on 16 July 2026 using PubMed, Crossref, official journal pages, the NIST publication record, and the MoTrPAC Data Hub citation page. Searches covered metabolomics reuse, repository harmonization, common data models, QA/QC reporting, cross-platform analysis, and exercise multi-omics. Recent peer-reviewed publications from 2022-2025 were added where they directly supported the problem statement or implementation limits; foundational standards and repository papers were retained for their original definitions. The search was not systematic. Queries and selection rules are recorded in `docs/manuscript/literature_search_log.md`. References are maintained in `docs/manuscript/references.bib`, verified against DOI records, and rendered with Pandoc citeproc using the Vancouver citation-sequence style required by the proposed journal.

## Quality control and results

![Figure 1. Evidence flow and review boundaries in MetaboTyping Agentic Workbench. Research questions and source records are converted into explicit evidence models before deterministic eligibility, crosswalk, identity, assay, feasibility, and plotting decisions are made. Accepted, review-required, and non-combinable outputs remain separate. Every artifact records source location, rule version, rationale, and unresolved evidence. Agent and skill contracts invoke the modules, but the evaluated offline workflow does not call a language model.](figures/metabotyping_agentic_workbench_architecture.png){width=6.6in}

### Evaluation design

All evaluation data were synthetic. The full test suite was run on 16 July 2026 and passed 81 of 81 tests, with no failures, errors, skips, expected failures, or unexpected successes. Five predefined scientific-risk gates contained 61 of these tests; the remaining 20 covered models, discovery criteria, live-source parsers with mocked responses, command-line execution, and other integration behavior. Table 3 separates software behavior from interpretation.

**Table 3. Synthetic evaluation results for version 0.1.0.**

| Evaluation | Result | Interpretation |
| --- | --- | --- |
| Complete regression suite | 81/81 passed | Deterministic behavior matched the committed fixtures; this does not estimate accuracy on independent studies or platforms. |
| Identity and assay gate | 13/13 passed | Name-only identity, unresolved isomers, unsafe pooling, cross-study batch correction, and irreversible imputation were blocked in challenge fixtures; complete chemical reconciliation and assay commutability remain unvalidated. |
| Provenance and multi-repository gate | 24/24 passed | Multiple repository records were retained and duplicate keys did not silently overwrite evidence; linkage of independently curated real records remains untested. |
| Statistical and review gate | 11/11 passed | Candidate accuracy, automatic acceptance, and review capture were reported separately, and uncertain items remained review-gated; downstream meta-analysis validity was not tested. |
| MoTrPAC-style plotting gate | 10/10 passed | Contrast, false-discovery-rate, mapping, coverage, export, and rendering checks passed on synthetic effects; MoTrPAC models and reference figures were not reproduced. |
| Contract audit | 36 skill files and 28 agent files; no inventory issue | Paired files had required sections, implementation links, and review boundaries; this does not test instruction-following or scientific validity of an interactive agent. |

### Synthetic pilot

The pilot processed 10 publication records, 10 repository records, and 26 variable rows. Four records met the direct exercise/activity criteria, three were retained as enrichment candidates, two met the topic criteria but lacked repository evidence required for reuse, and one animal-only record was excluded. The variable crosswalk accepted 12 mappings, routed 12 to human review, and rejected two. No reviewed or rejected mapping entered the approved transformation plan.

Against synthetic expert fixtures, candidate precision, recall, and F1 were 1.00; automatic-accept precision and recall were 1.00; unsafe automatic acceptance was 0; review capture was 1.00; and review-status accuracy was 1.00. Agreement of the readiness score within an absolute tolerance of 0.15 was 0.80. These are regression statistics against fixtures constructed for the same rule set. They should not be interpreted as estimates of performance on external data.

The assay challenge contained five record pairs. One pair met all requirements for pooling individual absolute concentrations. One pair required human review before study-specific effect synthesis. Three pairs were non-combinable for raw values; one of these still allowed a plan for study-specific effect meta-analysis because the identity and effect-scale evidence was sufficient even though raw assay values were incompatible. The MoTrPAC metadata screen assigned three datasets to the high tier, three to moderate, two to low, and two to not feasible. One not-feasible record lacked sufficient metadata, and the animal record was set to not feasible by the human-participant requirement.

### Visual output examples

The plotting workflow consumes reviewed effect estimates; it does not fit differential models from raw observations. Figure 2 shows a contrast-explicit synthetic volcano plot. The numerator and denominator are stated in the title and caption, the vertical lines show the effect threshold, and the horizontal line shows the false-discovery-rate threshold. Figure 3 shows a heatmap restricted to accepted mappings. Symbols distinguish unreviewed harmonization, unreported values, and missingness or limit-of-detection concerns.

![Figure 2. Synthetic MoTrPAC-style volcano plot produced by the current plotting workflow. Positive log2 fold change indicates higher abundance 10 minutes after endurance exercise than before exercise. Selection uses Benjamini-Hochberg false discovery rate <=0.05 across six measured metabolites and an absolute log2 fold-change threshold of 0.5. The values test plotting semantics only and are not biological results.](figures/synthetic_motrpac_plot_suite/figures/volcano_syn_ee_post10_vs_pre.png){width=6.4in}

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

![Figure 3. Synthetic metabolite-by-contrast heatmap produced by the current plotting workflow. Cells contain log2 fold changes only for accepted metabolite mappings. The multiplication sign marks an unreviewed harmonization, a dash marks an unreported value, and an exclamation mark marks a missingness or limit-of-detection concern. Visual similarity is not evidence of biological replication.](figures/synthetic_motrpac_plot_suite/figures/effect_heatmap.png){width=6.4in}

The complete plotting example exports 19 audited artifacts: plot-ready comma-separated-value files, eight figures, and a checksummed provenance manifest. It includes volcano plots, an effect heatmap, a single-metabolite effect plot, a time trajectory, and descriptive pathway and RefMet hierarchy summaries. The hierarchy summaries are medians of accepted feature effects. They are not pathway-enrichment tests and do not produce category-level p values.

## Relation to existing software

The workbench operates before statistical synthesis. Metabolomics Workbench and MetaboLights hold studies and data [@sud2016workbench; @haug2020metabolights], while Pan-ReDU harmonizes metadata and indexes raw mass-spectrometry files across repositories [@elabiead2025panredu]. MetaboAnalyst and other analysis packages process and interpret metabolomics matrices [@pang2024metaboanalyst]. COMETS Analytics supports consortium meta-analysis after studies and metabolites have been matched [@temprosa2022comets]. MetaboTyping Agentic Workbench does not replace these systems. It records the eligibility, identity, assay, and review decisions required before their outputs can be combined for a defined research question.

## Reuse potential

The software can be reused as a template for projects that need explicit evidence boundaries before cross-study analysis. A repository adapter can emit the existing study and dataset cards; a variable domain can add reviewed synonyms and transformations; and an assay domain can add a versioned policy with focused tests. Because accepted, review-required, and non-combinable decisions are stored separately, investigators can change a policy without silently rewriting prior evidence.

The plotting layer can also be used independently when an analysis already has reviewed mappings and contrast-level effect estimates. Each plot bundle retains the source study, dataset, matrix, contrast, effect scale, adjustment method, mapping status, and input hashes. This follows reproducible-computing principles by linking figures to their numerical inputs rather than treating the image as the primary result [@sandve2013reproducible].

## Limitations

The principal limitation is external validity. The discovery, crosswalk, identity, assay, and scoring rules have been tested against synthetic fixtures created within the same project. Perfect fixture agreement is therefore expected behavior, not evidence that the software will agree with independent metabolomics curators. A defensible validation study would use frozen public records spanning targeted liquid chromatography-mass spectrometry, untargeted liquid chromatography-mass spectrometry, gas chromatography-mass spectrometry, nuclear magnetic resonance spectroscopy, direct-infusion methods, and commercial panels, with at least two blinded curators and adjudication.

The source registry is broader than the executed adapter set. MetaboLights, ChEBI, HMDB, PubChem, Reactome, PRIDE, and other entries may be available through optional connectors or represented as planned sources, but they were not queried in the offline evaluation. Chemical identity resolution currently evaluates declared identifiers and evidence; it does not retrieve and reconcile every ontology, structure, salt, tautomer, adduct, stereoisomer, positional isomer, or lipid-resolution assertion. The local RefMet snapshot also lacks a recorded release identifier.

The assay thresholds are local policy defaults and have not been validated as universal acceptance criteria. Method bridges are declared rather than estimated for commutability. Cross-platform heterogeneity analyses are specified but not computed. The dataset readiness score is not a risk-of-bias instrument, and its weights have not been calibrated to expert ratings or replication outcomes. The MoTrPAC feasibility tier measures the presence of 11 metadata elements; it does not measure biological similarity.

The plotting workflow consumes effect estimates and supplied annotations. It does not fit repeated-measures models, select covariates, estimate effects from raw data, or perform pathway inference. Numerical and image regression against a frozen MoTrPAC release has not been completed. Because the evaluated offline workflow does not call a language model, it also does not estimate hallucination frequency or instruction-following performance. The skill and agent audit measures file structure and implementation linkage only.

## Software availability and reproducibility

The evaluated source tree reports version 0.1.0 and requires Python 3.11 or later. It includes an MIT license, `CITATION.cff`, contribution guidance, a support policy, synthetic inputs, expected outputs, tests, and a GitHub Actions workflow. The core evaluation can be reproduced from the repository root with:

```bash
pip install -e ".[dev,plotting]"
PYTHONPATH=src python3 -m metabotyping_agentic.cli run-pilot --out reports
PYTHONPATH=src python3 scripts/build_assay_harmonization_plan.py
PYTHONPATH=src python3 scripts/evaluate_skills.py
PYTHONPATH=src python3 scripts/evaluate_scientific_readiness.py
PYTHONPATH=src python3 scripts/render_synthetic_motrpac_plot_suite.py --out reports/synthetic_motrpac_plot_suite
MPLBACKEND=Agg PYTHONPATH=src python3 scripts/render_manuscript_architecture_figure.py
```

The local source tree does not yet have a configured public repository URL, archived release, or software DOI. A reviewed public release should be archived before journal submission. Zenodo can provide the persistent release DOI; the manuscript bibliography is maintained separately in BibTeX format.

**Table 4. Software metadata for the evaluated version.**

| Field | Value |
| --- | --- |
| Software name | MetaboTyping Agentic Workbench |
| Version | 0.1.0 local pre-release |
| Language | Python 3.11 or later; repository-local R and Python plotting helpers |
| License | MIT |
| Operating systems tested | macOS for this revision; continuous integration configured for Ubuntu |
| Public code repository | Not yet assigned |
| Archived release DOI | Not yet assigned |
| Synthetic sample data | `data/examples/` and `tests/fixtures/` |
| Test command | `PYTHONPATH=src python3 -m unittest discover -s tests` |
| Support | `SUPPORT.md`; smontal@stanford.edu before public release |

## Ethics statement

The offline evaluation uses synthetic study, repository, variable, assay, and effect records. It contains no participant-level data or protected health information and did not require human-participant review.

## Author contributions

Samuel Montalvo: Conceptualization, Methodology, Software, Validation, Visualization, and Writing - original draft. Eric Leslie: Methodology and Writing - review and editing. Laurens van de Wiel: Methodology and Writing - review and editing. Matthew T. Wheeler: Supervision, Methodology, and Writing - review and editing.

## Funding

No external funding is declared for this software manuscript draft.

## Competing interests

The authors declare no competing interests.

# Reviewer revision summary

Revision date: 16 July 2026

## Scientific framing

- Rewrote the title, abstract, introduction, methods, results, limitations, and reuse sections as a research-software metapaper rather than a product description.
- Added a problem statement, target user, three explicit objectives, and boundaries on what the software does not establish.
- Introduced the name **MetaboTyping Agentic Workbench** and removed all uses of “MVP” and “minimum viable product.”
- Distinguished deterministic Python decisions from optional agent and skill interfaces. The synthetic evaluation is presented as regression testing, not external validation.

## Terminology and quantitative detail

- Removed “mirage” terminology. The literature search log records why the reviewed Mirage preprint does not describe the evaluated offline workflow.
- Defined cardiopulmonary exercise testing (CPET) at first use.
- Replaced qualitative “guardrail” language with a table of versioned rules, including mapping confidence, unit/modality/timing requirements, missingness limits, QC coefficient-of-variation limits, metabolite-identification evidence, and MoTrPAC feasibility thresholds.
- Removed version-narration terms such as “new” and “now,” and removed promotional modifiers including “transparent.”

## Evidence and citations

- Re-searched recent literature through PubMed, Crossref, and journal or repository sources on 16 July 2026.
- Added recent literature on metabolomics reuse, pan-repository reanalysis, common data models, MoTrPAC, MetaboAnalyst, and quality control.
- Moved references to a BibTeX library and rendered them with the NLM/Vancouver CSL style. Sixteen sources are cited in the manuscript; the library contains one additional verified FAIR-data reference for future use.
- Recorded queries, selection decisions, DOI checks, and the citation-management approach in `literature_search_log.md`. Zenodo is identified separately as the appropriate service for archiving a future public software release and issuing a DOI.

## Current software evaluation

- Re-audited the latest worktree: 18 paired skills and 14 paired agent roles.
- Re-ran the full suite: 81 of 81 tests passed.
- Re-ran the strict synthetic readiness gate, skill audit, pilot, assay-harmonization challenge, and MoTrPAC plotting workflow.
- Added exact synthetic pilot counts and explicitly limited their interpretation to local fixtures.

## Figures and examples

- Replaced the prior aims graphic with a central evidence-flow figure inside the Results section.
- Added current synthetic MoTrPAC-style volcano and metabolite-by-contrast heatmap outputs with explicit contrast, thresholds, mapping status, and biological-interpretation caveats.
- Added six example research questions and prompts covering study discovery, CPET-variable review, metabolite effects, assay compatibility, MoTrPAC feasibility, and plot generation.

## Requested document changes

- Applied affiliations 1, 2, and 3 to every author.
- Changed the corresponding email to `smontal@stanford.edu`.
- Removed the Author Note and AI-use disclosure.
- Embedded all three figures in both DOCX and PDF, with descriptive alternative text in the DOCX.
- Kept each figure with its full caption and visually inspected all 11 rendered pages.

## Journal recommendation

The recommended venue remains the **Journal of Open Research Software** as a Software Metapaper. Submission should wait until the repository is public, the reviewed software version is archived with a DOI, and installation and pilot reproduction have been confirmed from a clean environment.

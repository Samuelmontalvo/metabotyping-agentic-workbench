# Literature search and citation verification log

## Scope

This targeted search was performed on 16 July 2026 to update the scientific context for the MetaboTyping Agentic Workbench software manuscript. It was not designed or reported as a systematic review. The search focused on public metabolomics reuse, repository-scale harmonization, metabolite identity, assay quality assurance and quality control, cross-platform analysis, exercise multi-omics, and reproducible research software.

## Sources searched

- PubMed and PubMed Central for peer-reviewed biomedical articles and metadata.
- Crossref for DOI metadata and BibTeX verification.
- Official journal pages, the NIST publication record, and the MoTrPAC Data Hub citation page when group authorship or publication metadata required confirmation.
- Journal of Open Research Software author instructions for the required Vancouver citation style.

## Targeted queries

- `metabolomics data reuse metadata harmonization repository 2022:2026`
- `pan-repository public metabolomics metadata harmonization`
- `metabolomics quality assurance quality control mQACC reporting`
- `cross-platform metabolomics meta-analysis COMETS`
- `common metabolomics data models Python`
- `MoTrPAC exercise metabolomics protocol multi-omic 2024`
- `RefMet nomenclature metabolite identity`
- `retrospective data harmonization guidelines`

## Selection and verification

Recent peer-reviewed methods, software, standards, and perspective papers from 2022-2025 were added when they directly supported the manuscript's problem statement or implementation boundaries. Foundational repository, FAIR, Metabolomics Standards Initiative, RefMet, and retrospective-harmonization papers were retained when no newer source replaced their specific role. Every cited journal article was checked against its DOI record; PubMed or an official publisher/consortium page was used to confirm titles, years, pagination, and group authorship where available.

The managed bibliography is `docs/manuscript/references.bib`. The manuscript is rendered with Pandoc citeproc and the Zotero/National Library of Medicine Vancouver citation-sequence style in `docs/manuscript/nlm-citation-sequence.csl`. The BibTeX file can be imported into Zotero or another reference manager. Zenodo is reserved for archiving a reviewed software release and assigning a persistent DOI; it is not a citation manager.

## Reviewer terminology note

The manuscript no longer uses `mirage` as a scientific outcome. The repository's historical internal label described a candidate record that appeared relevant but lacked required repository evidence. That use is unrelated to the 2026 `mirage reasoning` preprint on visual-language models generating image-specific findings without image input. The manuscript reports the observed repository evidence gaps directly. It also does not estimate language-model hallucination because the evaluated offline workflow does not call a language model.

---
name: gene-centric-metabolite-lookup
description: Use when starting from a gene, protein, transcript, compound identifier, or m/z and asking what the Metabolomics Workbench tool family (MetGENE, compound, gene/protein, moverz, exactmass) reports for it.
---

# Purpose
Turn a gene identifier into an auditable annotation ledger — which compounds a gene product is
annotated to act on, which KEGG reactions carry that annotation, which Metabolomics Workbench studies
are reachable from those compounds by standardized name, and how many pathways the source counts —
while keeping every hop labeled as an inference so an annotation is never read as a measurement. The
same lane resolves compound identifiers, gene and protein annotation records, and precursor-ion mass
queries against the Metabolomics Workbench REST contexts.

# Inputs
- A gene identifier plus its type: `SYMBOL`, `SYMBOL_OR_ALIAS`, `ALIAS`, `ENTREZID`, `GENENAME`,
  `ENSEMBL`, `REFSEQ`, `UNIPROT`, or `HGNC`. Symbols are case sensitive and are not case folded.
- A species from the accepted set: `human`, `hsa`, `mouse`, `mmu`, `rat`, `rno`.
- Optional anatomy and disease filter terms, whose vocabularies the source neither publishes nor validates.
- Optional compound identifiers (`regno`, `pubchem_cid`, `inchi_key`, `hmdb_id`, `kegg_id`, `lm_id`,
  and the undocumented `chebi_id` and `metacyc_id`) for the compound context.
- Optional gene, protein, transcript, or MGP identifiers for the human gene/protein annotation contexts.
- Optional m/z, adduct, and tolerance for a precursor search, or a lipid abbreviation for an exact mass.

# Steps
1. Confirm `metgene`, `mw_compound_database`, and `mw_metabolome_gene_protein` are registered in
   `src/metabotyping_agentic/knowledge/source_registry.py` under the `gene_metabolite_association`,
   `chemical_identity`, `mass_spectral_search`, and `gene_annotation` lanes. An unregistered lane is a
   blocking escalation, not a usable source.
2. Settle the licence posture before persisting anything. MetGENE output is KEGG-derived and its terms
   permit personal, non-commercial use only, so KEGG-derived rows are written only after a reviewer
   passes `--acknowledge-licence-review`.
3. Retrieve with `live-lookup-gene-metabolites`, one gene per request, across the four contexts the
   source actually serves: `summary`, `metabolites`, `reactions`, `studies`. Record each context status
   separately.
4. Record the pathway listing as `not_retrievable_by_api`. The source exposes no pathway context and
   its pathway page ignores query parameters, so only a precomputed integer count exists.
5. Label every hop — gene to reaction, reaction to compound, compound to standardized name,
   standardized name to study accession — as a separate annotation inference with an explicit
   statement of what it does not establish.
6. Re-fetch every annotation-derived study accession from Metabolomics Workbench with
   `live-intake-metabolomics-workbench` before describing what that study measured or reported.
7. Resolve compound, gene, protein, and mass queries with `live-lookup-compound`,
   `live-lookup-mw-gene-protein`, and `live-search-mass`, normalizing identifiers before querying and
   verifying the echoed adduct against the requested adduct.
8. Emit the inference ledger, the coverage ledger, and the escalation queue, then hand chemical
   identity questions to `metabolite-identity-resolution` and reviewer decisions to
   `human-review-packet`.

# Outputs
- `data/live/metgene/<slug>/metgene_summary.csv`, `metgene_metabolites.csv`, `metgene_reactions.csv`,
  and `metgene_study_candidates.csv` — one file per context that was actually requested, and only
  once the licence question is acknowledged. A context that was not requested writes no file.
- `data/live/metgene/<slug>/metgene_provenance.json` and `metgene_escalations.csv`, always written
- `gene_metabolite_inference_ledger.csv`, `gene_metabolite_coverage_ledger.csv`, and
  `gene_metabolite_review.json` — written by the offline appraisal step, which runs only when the
  licence question is acknowledged, into `--review-out` when given and beside the records otherwise
- `data/live/mw_compound/<slug>/mw_compound_records.csv` and `mw_compound_provenance.json`
- `data/live/mw_mgp/<slug>/mw_mgp_records.csv` and `mw_mgp_provenance.json`
- `data/live/mw_mass/<slug>/mw_moverz_matches.csv` or `mw_exactmass.csv`, with their provenance JSON

# Validation Checks
- Every row carries the query that produced it, the source system, and the exact source URL, so the
  FAIR trail names the metadata and the endpoint. Gene-centric rows additionally carry the queried
  species and an echoed-identifier status of `echo_matches_query`, `echo_differs_from_query`, or
  `no_echo_returned`; a row with no echo is never recorded as a verified match.
- Unreachable source, zero-row answer, unannotated gene, ambiguous server error, and indeterminate
  empty body are five distinct recorded statuses, never collapsed into one. A context that was never
  requested is a sixth state, `not_requested`, and writes no table and no row count.
- The pathway listing is recorded as not retrievable and the pathway integer is labeled a precomputed count.
- Every emitted mass match has an echoed adduct equal to the requested adduct.
- Identifier normalizations applied before querying are recorded, so a formatting miss is not logged
  as an absence.
- No row asserts that a metabolite was measured: `measurement_established` is `not_established` everywhere.
- Every ledger hop states what it does not establish and what evidence would close the gap.

# Failure Modes
- A gene-product or pathway annotation is read as evidence that a metabolite was measured or changed.
- A zero-row answer is reported as "this gene has no metabolites" when the source was unreachable.
- An HTTP 500 caused by a wrong-case gene symbol is reported as a biological absence.
- A typo'd tissue filter returns an empty body and is read as "no studies in this tissue".
- An unrecognised adduct is silently computed as neutral and the resulting masses are reported as matches.
- A rodent result is presented as a human result, or a human annotation is projected onto a rat gene.
- KEGG-derived content is persisted or republished before the licensing decision is made.
- A study accession reached by name annotation is described as a study that measured the metabolite.
- Human-only gene and protein annotation records are queried for rat or mouse and the empty answer is
  recorded as a coverage gap for that species.
- A narrowed context request writes empty tables, so "never asked" reads as "the source holds nothing".
- The appraisal is run against a record set whose rows were withheld for licence reasons, turning a
  withheld chain into an apparently empty one.

# Human-Review Triggers
- The licence question is unresolved, so a reviewer decides whether KEGG-derived rows may be persisted.
- A gene returned an ambiguous server error, so a reviewer decides whether it is a bad identifier or an outage.
- A gene resolves in one species but not in the ortholog, so a reviewer decides on cross-species transfer.
- The echoed identifier differs from the queried identifier and a reviewer must confirm the entity.
- An annotated compound has no standardized-name mapping, so the study bridge cannot be built.
- A filter term cannot be validated against any published vocabulary, so an empty result is uninterpretable.
- A formula, mass, or cross-identifier query returns multiple candidate records, which is a reviewer
  decision and never an automatic merge.

# Evaluation Gates
- FAIR: every row must expose its source, accession, identifier namespace, endpoint URL, and licence
  posture, with retrieval provenance and source metadata preserved per context.
- Reproducibility: the inference and coverage ledgers must be regenerated deterministically offline
  from the declared retrieved records, with no network access and no timestamps in the derived artifacts.
- Critical evidence: unavailable sources, unannotated genes, ambiguous server errors, and
  indeterminate empty bodies must stay distinguishable from a documented absence; do not emit an
  approved gene-to-metabolite claim from an uncertain, inferred, or assumption-based annotation hop.
- Human review: every unresolved species transfer, identifier mismatch, candidate set, and licence
  question must be routed to a named reviewer decision and never silently resolved by inference.
- Skill quality rubric: pass only if every output row carries its declared inputs, a labeled inference
  hop, explicit evidence of what was and was not established, and a validation status.

# Implementation
- Gene-centric retrieval, network-allowlisted: `src/metabotyping_agentic/live_sources/metgene.py`.
- Compound, gene, protein, moverz, and exactmass contexts:
  `src/metabotyping_agentic/live_sources/metabolomics_workbench.py`.
- Offline inference labeling, coverage ledger, and escalation:
  `src/metabotyping_agentic/discovery/gene_metabolite_evidence.py`.

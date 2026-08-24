---
name: literature-evidence-review
description: Use when finding, screening, and appraising published and preprint literature for a metabolite, phenotype, or dataset question across Europe PMC, PubMed, Crossref, and bioRxiv/medRxiv.
---

# Purpose
Turn a discovery question into an auditable literature evidence base: which indexes were queried, which
were actually reachable, which records are peer-reviewed versus preprint, which describe human versus
animal or in-vitro work, and which name a repository accession that bridges back to retrievable data.
Retrieval is separated from appraisal so a bibliographic hit is never read as a scientific finding.

# Inputs
- A subject query plus explicit name variants (for example `N-Lactoyl phenylalanine` with `Lac-Phe`).
- Optional context terms that narrow the sweep (for example `exercise`, `physical activity`).
- Inclusion criteria from `define-inclusion-criteria`, or the query the criteria were derived from.
- For offline re-screening: an existing `literature_records.json` or `literature_records.csv` plus its
  `literature_provenance.json`.

# Steps
1. Confirm every retrieval lane is registered in `src/metabotyping_agentic/knowledge/source_registry.py`
   under the `literature` lane. An unregistered index is a blocking escalation, not a usable source.
2. Retrieve with `live-search-literature`: Europe PMC (which indexes MEDLINE/PubMed, PMC, and preprints),
   PubMed E-utilities, Crossref, and the bioRxiv/medRxiv detail API for preprint version and
   published-journal linkage.
3. Record per-source status, query expression, endpoint URL, reported hit count, retrieved count, and
   pagination completeness in `literature_provenance.json`. A source that could not be reached is
   `unavailable`, never zero hits.
4. Deduplicate across sources by DOI, PMID, and PMCID transitively, then by normalized title and year.
   Preserve field disagreements between sources as conflicts.
5. Appraise offline: evidence tier, species scope, intervention design, modality evidence, subject-name
   location, homonym risk, and repository accessions found in the record text.
6. Escalate unresolved records and render the literature report.

# Outputs
- `data/live/literature/<slug>/literature_records.csv` and `literature_records.json`
- `data/live/literature/<slug>/literature_provenance.json`
- `data/live/literature/<slug>/literature_screened.csv` and `literature_review.json`
- `data/live/literature/<slug>/literature_escalations.csv`
- `reports_live/literature/<slug>_literature_report.md`
- Offline pilot equivalent: `reports/literature_report.md` from the synthetic publication fixtures.

# Validation Checks
- Every retrieved record keeps its source system, source URL, and identifiers; the FAIR provenance trail
  names the accession, index, and endpoint that produced it.
- An unreachable index appears as `status: unavailable` with its error detail, and the report states that
  its coverage is unknown.
- A truncated or relevance-ranked sweep is never described as complete.
- Peer-reviewed, preprint, secondary-synthesis, editorial, and retracted records occupy separate tiers.
- Screening flags carry their basis: `structured_field`, `text_inference`, or `unknown:no_abstract_text`.
- Records whose retrieved text never names the queried subject are flagged, not counted as evidence.

# Failure Modes
- An index blocks the request and the empty result is read as "no such literature exists".
- A preprint is cited as though it were peer reviewed.
- A full-text index match is treated as subject evidence when the queried name is a homonym of an
  unrelated entity, such as a copolymer abbreviation that matches a metabolite abbreviation.
- A record with no abstract is silently dropped, converting unknown into absent.
- A missing accession in an abstract is reported as a confirmed data-deposition gap.
- Citation counts are read as evidence quality.

# Human-Review Triggers
- A record cannot be screened from the retrieved text; a reviewer decides whether to obtain full text.
- Sources disagree on title, year, or journal for the same identifier.
- A preprint has no linked journal publication but its claim would change a conclusion.
- The queried name appears only in a materials-science or otherwise non-metabolite context.
- A retrieval lane was unavailable, so the reviewer must decide whether the sweep may be relied on.
- A direct human match names no accession, so the deposition question stays open for a reviewer decision.

# Evaluation Gates
- FAIR: every record must expose its source index, endpoint URL, identifiers, and any accession found in
  its text, with retrieval provenance preserved per source.
- Reproducibility: screening and appraisal must be regenerated deterministically offline from the
  declared record set, with no network access and no timestamps in the review artifacts.
- Critical evidence: unavailable sources, unscreenable records, unlocated subject names, and absent
  accessions must stay distinguishable from negative findings; do not convert an uncertain or missing
  value into an exclusion.
- Human review: every escalation must name the decision a reviewer has to make and the record it applies
  to; triggers must not be resolved by inference.
- Skill quality rubric: pass only if the report separates retrieval availability from screening outcome,
  keeps evidence tiers distinct, labels every inferred flag, and shows the escalation queue with the
  validation basis for each claim.

# Implementation
- Retrieval (network-allowlisted): `src/metabotyping_agentic/live_sources/literature_search.py`.
- Screening and appraisal (offline): `src/metabotyping_agentic/discovery/literature_review.py`.
- Reporting: `src/metabotyping_agentic/reports/render.py`.

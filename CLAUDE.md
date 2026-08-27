# Claude Code Project Memory

This project implements a reproducible scientific curation and harmonization workbench for metabolomics-associated public dataset discovery.

Use the `.claude/skills/*/SKILL.md` workflows and `.claude/agents/*.md` subagent definitions when decomposing work. The Claude assets mirror the Codex assets under `.agents/skills` and `.codex/agents`.

## Non-Negotiables

- The **offline pilot** (`run-pilot`) must run offline against synthetic fixtures only, and must stay byte-reproducible. Do not point `run-pilot` at live data.
- Preserve source provenance for every record, synthetic or live.
- Escalate uncertain mappings to human review.
- Do not generate deterministic ETL for unapproved mappings.
- Treat missing repository metadata/codebooks as scientific risk, not a formatting issue.

## Live Ingestion Mode (supported)

Live ingestion of real public records is permitted as a **separate, opt-in mode**, distinct from the offline pilot. Rules:

- Network access is confined to the declared network-boundary allowlist: `scripts/fetch_live_records.py`, `scripts/volcano_compare.py`, `src/metabotyping_agentic/live_sources/literature_search.py`, `src/metabotyping_agentic/live_sources/metabolomics_workbench.py`, `src/metabotyping_agentic/live_sources/metgene.py`, and `src/metabotyping_agentic/live_sources/motrpac_volcano_compare.py`. These are reachable only through `scripts/fetch_live_records.py` and the `live-*` CLI subcommands. No other module, script, or test may import a network client or open a socket. `tests/test_network_boundary.py` enforces the allowlist by AST scan; adding a module to it is a reviewed change to this file.
- Live data is written under `data/live/` and live reports under `reports_live/`. Never overwrite `data/examples/` (synthetic fixtures) or `reports/` (offline pilot output).
- Sources are public, released, openly licensed records only (e.g. Metabolomics Workbench REST; MoTrPAC metabolomics hosted on MW; Europe PMC, PubMed E-utilities, Crossref, and bioRxiv/medRxiv for bibliographic records). Record exact source URLs in `data/live/provenance.json`.
- **One reviewed exception to the open-licence rule:** MetGENE (`bdcw.org`) is public and released but is *not* openly licensed — its output is KEGG-derived and its terms permit personal, non-commercial use only. It is registered with `open_access=False`, so default routing excludes it, and its adapter writes no KEGG-derived row to disk unless a reviewer passes `--acknowledge-licence-review`. See the gene-centric lane below.
- Do not fabricate records for embargoed/access-controlled data (e.g. the human MoTrPAC DataHub arm). Represent unavailable data as an availability gap / mirage risk, never as a synthetic stand-in.
- All scientific guardrails (mirage detection, human-review escalation, missing-codebook = risk) apply identically to live records.

Run:

```bash
python3 scripts/fetch_live_records.py            # fetch curated real studies -> data/live/
# or: python3 scripts/fetch_live_records.py ST004303 ST003807 ST002916
```

### Single-metabolite lane

Find which public studies report a metabolite, then extract its effects and check MoTrPAC rat coverage:

```bash
# 1. Which MW studies report the metabolite (RefMet resolution + metstat search)
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-metabolite-studies \
  --query "N-Lactoyl phenylalanine" --name-variants "Lac-Phe" \
  --out data/live/metabolite_search_lacphe

# 2. Human pre/post effects for chosen studies + rat pass1b-06 coverage scan
PYTHONPATH=src python3 scripts/volcano_compare.py --metabolite-scan "N-Lactoyl phenylalanine" \
  --name-variants "Lac-Phe;N-lactoylphenylalanine" --mw-studies ST003662

# 3. Offline figures + report -> reports_live/lacphe/
python3 scripts/render_lacphe_figures.py   # figure suite + one backing CSV per figure
python3 scripts/render_lacphe_report.py    # markdown report (reads the same live tables)
```

The scan lane persists sample-level values for the queried metabolite only (never the full abundance
matrix), so participant-level responses can be plotted offline. Use `--scan-skip-rat` to skip the rat
coverage scan; the skip is recorded in provenance so a partial run cannot be read as a rat result.

A metabolite absent from a source feature space is recorded as a coverage gap. Never substitute a
synthetic row, a nearby analyte, or a precursor for the queried metabolite.

### Literature lane

Find, screen, and appraise the published record for a topic across Europe PMC (which indexes
MEDLINE/PubMed, PMC, and preprints), PubMed E-utilities, Crossref, and the bioRxiv/medRxiv detail API:

```bash
# retrieve + screen + report in one live command
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-literature \
  --query "N-Lactoyl phenylalanine" \
  --name-variants "Lac-Phe;N-lactoylphenylalanine" \
  --context-terms "exercise;physical activity;training" \
  --out data/live/literature/lacphe

# re-screen an existing record set offline (no network)
PYTHONPATH=src python3 -m metabotyping_agentic.cli review-literature \
  --records data/live/literature/lacphe --query "..." --out data/live/literature/lacphe \
  --reports-out reports_live/literature
```

Retrieval (`live_sources/literature_search.py`, allowlisted) is separate from screening and appraisal
(`discovery/literature_review.py`, offline). Lane rules:

- A source that could not be reached is recorded as `status: unavailable`, never as zero hits. An
  unreachable index and an index with no matching papers are different scientific facts.
- Every query expression, endpoint URL, reported hit count, retrieved count, and pagination truncation
  is written to `literature_provenance.json`; a truncated sweep may not be described as complete.
- Peer-reviewed, preprint, secondary-synthesis, and retracted/corrected records stay in separate
  evidence tiers. A preprint is never presented as peer-reviewed evidence.
- Species, design, and modality flags taken from title/abstract text are labeled as text inference.
  A record with no abstract is classified `screening_uncertain_insufficient_text` and escalated; it is
  never silently excluded.
- A missing accession in bibliographic text is an unresolved deposition question, not a confirmed
  deposition gap. Bibliographic text is not a data availability statement.
- All four literature sources are registered in `knowledge/source_registry.py` under the `literature`
  lane; an unregistered retrieval lane is a blocking escalation, not a usable source.

Set `METABOTYPING_CONTACT_EMAIL` for polite-pool identification and `NCBI_API_KEY` for a higher
E-utilities rate limit. Neither is required, and neither is sent anywhere except the queried API.

### Gene-centric lane (MetGENE) and the Metabolomics Workbench tool contexts

Start from a gene and ask which compounds, reactions, and MW studies are *annotated* to it, and
crosswalk compound identifiers or an m/z against the MW metabolite database:

```bash
# MetGENE: gene -> reactions, compounds, MW study candidates, precomputed pathway count.
# Without --acknowledge-licence-review only provenance and escalations are written.
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-lookup-gene-metabolites \
  --gene HMGCR --species hsa --gene-id-type SYMBOL

# MW compound context: identifier crosswalk (regno, pubchem_cid, inchi_key, hmdb_id, kegg_id, lm_id, ...)
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-lookup-compound \
  --input-item hmdb_id --value HMDB0000122

# MW gene/protein (MGP) annotation records - human only
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-lookup-mw-gene-protein \
  --context protein --input-item uniprot_id --value Q13085

# MW moverz precursor search, or the exactmass calculator for a lipid abbreviation
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-mass --mz 255.2 --adduct M+H --tolerance 0.02
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-mass --abbreviation "PC(34:1)" --adduct M+H
```

Retrieval (`live_sources/metgene.py` and the compound/gene/protein/moverz/exactmass helpers in
`live_sources/metabolomics_workbench.py`, both allowlisted) is separate from appraisal
(`discovery/gene_metabolite_evidence.py`, offline). Lane rules:

- An annotation is not a measurement. Every emitted row across the lane carries
  `measurement_established=not_established`, and the appraisal ledger records each hop — gene to reaction, reaction to compound, compound to
  standardized name, name to study accession — as a separate labeled inference with an explicit
  "does not establish" statement. A MetGENE study accession is an annotation-derived candidate and
  must be re-fetched from Metabolomics Workbench before anything is said about what the study reported.
- MetGENE exposes no REST pathways context. Only a precomputed integer pathway count is retrievable;
  the listing is recorded as `not_retrievable_by_api`, never inferred.
- MetGENE distinguishes six retrieval states: `ok`, `no_hits`, `gene_not_annotated`,
  `gene_unresolved_or_source_error` (HTTP 500, returned both for a wrong-case symbol and for an
  outage), `indeterminate_empty_body` (a zero-length 200 that an unrecognised anatomy term also
  produces), and `unavailable` (the source could not be reached, so its coverage is unknown). None
  of them is evidence of absence. A context excluded from the request is recorded separately as
  `not_requested`, writes no table, and gets no row count — "never asked" is not "answered with
  nothing".
- The MW REST contexts return every application error as HTTP 200, so classification reads the
  content type and body, never the status code. An unrecognised adduct is silently computed as the
  neutral mass, so every emitted mass match has its echoed ion label verified against the request.
- The MW gene/protein (MGP) tables are human-only and hold no compound field, so they cannot link a
  gene to a metabolite; a non-human taxid is refused as `species_not_covered_by_source` rather than
  queried and reported as empty.
- `metgene`, `mw_compound_database`, and `mw_metabolome_gene_protein` are registered in
  `knowledge/source_registry.py` under the `gene_metabolite_association`, `chemical_identity`,
  `mass_spectral_search`, and `gene_annotation` lanes.

## Pilot

Run:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli run-pilot --out reports
```

Expected reports:

- `reports/aim1_catalog_report.md`
- `reports/aim2_harmonization_report.md`
- `reports/aim3_evaluation_report.md`
- `reports/human_review_packet.md`
- `reports/literature_report.md`
- `reports/motrpac_alignment_report.md`
- `reports/benchmark_results.json`
- `reports/benchmark_case_results.json`
- `reports/benchmark_disagreements.csv`
- `reports/benchmark_report.md`
- `reports/benchmark_manifest.json`

## Skill Evaluation

Run:

```bash
PYTHONPATH=src python3 scripts/evaluate_skills.py
```

This evaluates Codex and Claude skills against FAIR data, reproducibility, critical-evidence, human-review, and scoring gates. Keep `docs/skill_evaluation_report.md` current after changing skills.

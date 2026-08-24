# MetaboTyping Agentic Workbench

Offline MVP for human-in-the-loop metabolomics-associated dataset discovery,
metadata extraction, multi-database routing, variable and assay-platform
harmonization review, dataset-readiness scoring, MoTrPAC-style analysis plots
and metadata-readiness assessment, and benchmarking.

The repository is designed for both Codex and Claude Code. The current worktree contains
22 canonical paired agent roles and 24 paired skill contracts for both runtimes:

- Codex: `AGENTS.md`, `.agents/skills/*/SKILL.md`, `.codex/agents/*.toml`
- Claude Code: `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/agents/*.md`, `.claude/commands/*.md`

The core MVP and its tests use synthetic fixtures and require no network access or API keys. Optional public-source commands are explicitly separate from the offline workflow.

Four canonical roles are advisory scientific reviewers for study
design/population context, exercise-phenotype harmonization, biospecimen
preanalytics, and statistical estimands/synthesis. They emit the shared,
versioned `DomainReviewPacket`; they cannot accept or reject data, authorize
transforms or pooling, calculate risk-of-bias scores, or bypass human
adjudication.

## Install

```bash
pip install -e ".[dev]"
```

Install the optional rendering stack for PNG heatmaps, volcano plots, and single-feature figures:

```bash
pip install -e ".[dev,plotting]"
```

The implementation is intentionally deterministic. The core offline pilot can run through the standard-library compatibility layer, but the complete test suite and metabolite-effect workflow require the declared project dependencies.

## CLI

```bash
metabo-agent define-criteria --query "human metabolomics datasets with exercise or actigraphy and genetics"
metabo-agent discover --criteria data/extracted/criteria.json --out data/extracted
metabo-agent extract-metadata --records data/examples/mock_repository_records.csv --out data/extracted
metabo-agent build-crosswalk --variables data/examples/mock_variable_dictionary.csv --out data/extracted
metabo-agent review-crosswalk --crosswalk data/extracted/crosswalk.csv --out data/review
metabo-agent build-harmonization-plan --crosswalk data/extracted/crosswalk.csv --out reports
metabo-agent score-quality --metadata data/extracted --out data/extracted
metabo-agent align-motrpac --metadata data/extracted --out reports
metabo-agent benchmark --predicted data/extracted --gold data/examples --out reports
metabo-agent route-sources --lanes identity,pathway,assay --identifiers CHEBI:17234,HMDB0000122 --out data/extracted/source_retrieval_plan.json
metabo-agent run-pilot --out reports
```

`route-sources` writes a deterministic retrieval plan. It labels native, optional-plugin, planned, restricted, and standards-reference sources; it does not query those sources or establish metabolite identity.

Build the synthetic assay/platform harmonization plan and its separate accepted, review-required, non-combinable, and provenance-audit artifacts:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_assay_harmonization_plan.py
```

Render the complete synthetic MoTrPAC-style metabolomics plot suite (volcano, effect heatmap, single-metabolite effect and trajectory, plus pathway and RefMet sub/main/super-class views):

```bash
PYTHONPATH=src .venv/bin/python scripts/render_synthetic_motrpac_plot_suite.py --out reports/synthetic_motrpac_plot_suite
```

Use `--skip-plots` to export deterministic plot-ready CSVs and the checksummed manifest without Matplotlib.

For a no-install smoke run from the repo root:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli run-pilot --out reports
```

Optional live-source smoke tests are explicit and should write outside tracked
fixtures. For example, this pulls public Metabolomics Workbench metadata for a
human exercise study, normalizes it into local CSV/card artifacts, and runs
quality plus MoTrPAC-style alignment without persisting sample-level factors or
quantitative data matrices:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-intake-metabolomics-workbench --study-id ST001789 --out /private/tmp/metabotyping-live/ST001789
```

Metabolomics Workbench live intake requires an observed blood-derived sample
matrix by default (`blood`, `plasma`, or `serum`). Use
`--allow-non-blood-derived-sample-matrix` only for explicit manual-review
exceptions.

To compare that MW exercise study with public MoTrPAC human pre-COVID
summary-level metabolomics and render side-by-side volcano PNGs:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-compare-mw-motrpac-volcano --mw-study-id ST001789 --out /private/tmp/metabotyping-live/comparisons/mw_ST001789_vs_motrpac_human_precovid
```

To ask which public studies report one metabolite, then extract its effects and
check MoTrPAC rat coverage, use the single-metabolite lane. The search resolves
the name through RefMet and queries MW `metstat`; the scan computes pre/post
effects for the named studies and scans rat pass1b-06 for the same metabolite:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-metabolite-studies \
  --query "N-Lactoyl phenylalanine" --name-variants "Lac-Phe" \
  --out data/live/metabolite_search_lacphe

PYTHONPATH=src python3 scripts/volcano_compare.py --metabolite-scan "N-Lactoyl phenylalanine" \
  --name-variants "Lac-Phe;N-lactoylphenylalanine" --mw-studies ST003662
```

The scan persists sample-level values for the queried metabolite only, never the
full abundance matrix, so participant-level responses can be plotted offline.
`--scan-skip-rat` skips the rat coverage scan and records the skip in provenance,
so a partial run cannot be read as a rat coverage result. A metabolite absent
from a source feature space is reported as a coverage gap; no synthetic row,
nearby analyte, or precursor is ever substituted for it.

Offline renderers turn those tables into figures and a report under
`reports_live/lacphe/`:

```bash
python3 scripts/render_lacphe_figures.py
python3 scripts/render_lacphe_report.py
```

Any report can also be rendered as a PDF or as a single self-contained HTML file with
its figures inlined, so the same Markdown source is the only source of truth:

```bash
python3 scripts/render_markdown_pdf.py \
  reports_live/lacphe/lacphe_report.md reports_live/lacphe/lacphe_report.pdf
python3 scripts/render_markdown_html.py \
  reports_live/lacphe/lacphe_report.md reports_live/lacphe/lacphe_report.html
```

## Worked example: repository-scale evidence report

The repository includes a five-page worked example that combines a frozen
Metabolomics Workbench corpus audit, RefMet hierarchy summaries, a Lac-Phe case
study, a review-gated MW-MoTrPAC label-overlap screen, and a concise inventory of
the workbench's agents and skills. The HTML is self-contained, while the R
Markdown source, derived metrics, and frozen-source manifest keep the result
auditable and reproducible.

- [Final five-page PDF](output/pdf/metabotyping_agentic_workbench_final_report.pdf)
- [Self-contained HTML report](reports_live/final_workbench_report/final_report.html)
- [R Markdown source](reports_live/final_workbench_report/final_report.Rmd)
- [Audited evidence bundle](reports_live/final_workbench_report/data/report_metrics.json)
- [Frozen Metabolomics Workbench provenance manifest](data/live/mw_corpus_snapshot/manifest.json)

Rebuild the derived tables and figures from the frozen local evidence, then
render the two report formats:

```bash
MPLCONFIGDIR=/private/tmp/metabotyping-mpl \
  python3 scripts/build_final_workbench_report.py
python3 scripts/render_markdown_html.py \
  reports_live/final_workbench_report/final_report.Rmd \
  reports_live/final_workbench_report/final_report.html
python3 scripts/render_markdown_pdf.py \
  reports_live/final_workbench_report/final_report.Rmd \
  output/pdf/metabotyping_agentic_workbench_final_report.pdf
```

The worked example is an evidence snapshot, not benchmark ground truth. Its
reported MW feature total is analysis-level feature incidence rather than a
unique-metabolite count, RefMet entries are reference nomenclature rather than
MW observations, and every MW-MoTrPAC name overlap remains identity-review
required.

To ask what the published record says about the same subject, use the literature
lane. Retrieval covers Europe PMC (which indexes MEDLINE/PubMed, PMC and
preprints), PubMed E-utilities, Crossref, and the bioRxiv/medRxiv detail API for
preprint version and journal-publication linkage:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-literature \
  --query "N-Lactoyl phenylalanine" \
  --name-variants "Lac-Phe;N-lactoylphenylalanine" \
  --out data/live/literature/lacphe
```

Retrieval is allowlisted and separate from screening: appraisal runs offline and
can be re-run on a cached record set without touching the network.

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli review-literature \
  --records data/live/literature/lacphe --query "N-Lactoyl phenylalanine" \
  --out data/live/literature/lacphe --reports-out reports_live/literature
```

An index that could not be reached is recorded as `status: unavailable`, never as
zero hits, and a relevance-ranked or truncated sweep is never described as
complete. Peer-reviewed, preprint, secondary-synthesis, editorial and retracted
records stay in separate evidence tiers; species, design and modality flags taken
from title/abstract text are labeled as inference; a record with no abstract is
escalated as unscreenable rather than dropped; and a repository accession found in
record text is reported as a bridge to retrievable data, while its absence is an
open deposition question rather than a confirmed gap. Because a name match is not
an identity claim, records whose retrieved text never names the queried subject —
and records where the name appears only in a materials-science context, such as a
copolymer that shares an abbreviation with a metabolite — are escalated instead of
counted as subject evidence. The offline pilot renders the same report shape from
the synthetic publication fixtures at `reports/literature_report.md`.

Set `METABOTYPING_CONTACT_EMAIL` for polite-pool identification and `NCBI_API_KEY`
for a higher E-utilities rate limit. Both are optional and are sent only to the
queried API.

For the full test suite after installation:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Evaluate Codex and Claude skills and agent contracts for scientific sections, implementation linkage, pair parity, duplicates, and review boundaries:

```bash
PYTHONPATH=src python3 scripts/evaluate_skills.py
```

The current deterministic contract audit is tracked at `docs/skill_evaluation_report.md`. A passing contract audit is not evidence of real-world scientific validity.

Run the stricter behavioral scientific-readiness gate:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_scientific_readiness.py
```

This command runs the complete offline regression suite and groups tests by scientific-risk domain. It exits nonzero for any failure, error, skip, expected failure, unexpected success, or empty required gate. Its scope is deliberately synthetic and local: passing does not establish external validity on real cohorts, assay platforms, or live database connectors. Results are tracked in the [scientific readiness report](docs/scientific_readiness_report.md) and [machine-readable readiness results](docs/scientific_readiness_results.json).

## Agent-name migration

Release 0.2.0 makes two role names more precise. The old hyphenated names remain
behavior-equivalent, deprecated aliases for the 0.2.x series only.

| Deprecated 0.2.x alias | Canonical name | Removal |
| --- | --- | --- |
| `data-quality-reviewer` | `dataset-readiness-reviewer` | 0.3.0 |
| `motrpac-replication-analyst` | `motrpac-metadata-readiness-analyst` | 0.3.0 |

The machine-readable registry is `.agents/agent_aliases.toml`. Alias resolution
is one hop, and the deleted underscore-form manifest filenames are not restored
or treated as aliases. Consumers should migrate to the canonical names before
0.3.0.

## Scientific Guardrails

- Human review gates are explicit.
- Domain-review packets have advisory-only authority, require human adjudication, and contain no executable actions.
- Low-confidence harmonization is never converted into deterministic ETL.
- `VO2max` and `VO2peak` are treated as related but not automatically equivalent.
- Synthetic fixtures avoid participant-level data.
- Mirage detection flags studies that look relevant but lack data, metadata, accessions, or codebooks.
- Serialized inclusion criteria control discovery eligibility and scoring.
- Generated study, dataset, variable, recommendation, and alignment artifacts are checked against JSON Schemas before they are written.
- MoTrPAC alignment distinguishes documented modality absence from unknown evidence and applies human-participant evidence as a hard gate.
- Source routing is explicitly separate from source execution and chemical identity resolution.
- Multiple repository records for one study are preserved; singular indexing fails rather than silently dropping a record.
- Reported metabolite names never authorize automatic identity merging.
- A source-carried RefMet ID can support a curated retrieval/annotation match, but every effect-search row still requires assay-identity review before harmonization or raw-value pooling.
- Raw assay values pool only after exact-identity, quantitative-scale, unit, matrix/method, QA/QC, and provenance gates pass.
- Relative abundance and feature intensity remain study/platform specific; any cross-study synthesis is limited to compatible effect estimates.
- Cross-dataset heatmaps require accepted canonical mappings, and pathway/class displays are labeled descriptive unless a separate inferential analysis exists.

## Current scientific limitations

- The multi-database registry is broader than the native adapter set. MetaboLights, ChEBI, HMDB, PubChem, Reactome, PRIDE, and many other sources are optional-plugin or planned capabilities, not offline executed retrievals.
- Chemical reconciliation does not yet perform complete ontology- and structure-backed resolution across databases, salts, tautomers, adducts, stereoisomers, positional isomers, and lipid resolution levels.
- Assay harmonization policies and thresholds have synthetic validation only. Declared method bridges are not estimated or independently checked for commutability.
- Harmonization decisions specify Q, I², τ², platform-moderator, and leave-one-platform-out diagnostics, but the meta-analysis engine does not yet calculate them.
- The plotting workflow consumes effect estimates; it does not fit MoTrPAC statistical models from raw data. Pathway/class heatmaps are descriptive medians, not pathway enrichment or normalized enrichment scores.
- RefMet effect enrichment is within-stratum feature-row over-representation that reuses source FDR calls. Current effect tables lack source-carried RefMet IDs and the local snapshot lacks a declared release, so name-resolved identity-dependent rows remain review-required.
- Literature retrieval covers Europe PMC, PubMed, Crossref and bioRxiv/medRxiv bibliographic records only. It does not read full text, so data availability statements, methods-level assay identity, and reported effect sizes are not extracted; screening flags from title/abstract text are inference, and PubMed E-utilities blocks some shared network egresses, which is recorded as an availability gap rather than an empty result.
- Real-world multi-platform external validation and a head-to-head benchmark against named agent systems are still required. See `docs/metabolomics_agent_capability_review.md` for the release gates and evidence-based comparison.

## Release status

Version `0.2.0` is a local pre-release snapshot. It adds advisory domain-review
contracts, deterministic benchmark disagreement/provenance artifacts, and
stricter scientific-readiness gates. Canonical benchmark computation remains
deterministic; hidden-gold agent execution, handoff tracing, independent
evaluator subagents, and a behavioral multi-agent harness are deferred. The
manuscript, DOCX, PDF, and publication figure bundles remain frozen descriptions
of the evaluated 0.1.0 snapshot. The code is licensed under MIT and includes
citation, contribution, support, CI, synthetic inputs, and example outputs. A
public repository URL and archived release DOI have not yet been assigned; they
are required before journal submission.

## Outputs

The pilot and the focused workflows above write:

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
- `reports/aim2_assay_harmonization_plan.json`
- `reports/synthetic_motrpac_plot_suite/plot_bundle_manifest.json`
- `data/extracted/metadata_cards/*.json`
- `data/extracted/source_retrieval_plan.json`
- `data/extracted/variable_inventory.csv`
- `data/extracted/crosswalk.csv`
- `data/extracted/quality_scores.json`
- `data/extracted/literature_screened.csv`
- `data/extracted/literature_review.json`
- `data/extracted/literature_escalations.csv`
- `data/harmonized/approved_assay_harmonization.json`
- `data/harmonized/assay_harmonization_audit.json`
- `data/review/assay_harmonization_review_queue.json`
- `data/review/non_combinable_assay_pairs.json`

As of 0.2.0, benchmark artifacts are written only beneath the evaluation
command's requested `--out` directory. The workbench does not write a new
`data/extracted/benchmark_results.json` and never deletes a legacy file already
present there.

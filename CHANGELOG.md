# Changelog

Notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

Scientific review of 2026-09-01 (`docs/scientific_review_2026-09-01.md`). No
benchmark metric changed; the fixes below correct defects in how evidence was
labeled, paired, or plotted, and close the reproducibility gap between the
committed pilot artifacts and the documented command.

### Fixed — scientific labeling and pairing

- **The MoTrPAC rat pass1b-06 volcano pooled the male and female strata into one
  plot.** The source table is sex-stratified (1077 rows per sex, every RefMet
  name twice), so the single figure double-counted every feature and its
  contrast id claimed "male". `scripts/render_exercise_studies_refmet_volcanoes.py`
  now renders one figure per sex, labels the contrast as 8-week trained versus
  sex-matched sedentary control, excludes the 21 internal-standard rows per sex
  from the biological volcano, and records that the table has no retrieval
  provenance record.
- **The MoTrPAC human volcano declared a study-wide FDR scope over eleven
  platform DA tables** whose `adj_p_value` was adjusted per platform. The scope
  is now recorded as per-platform and the figure is labeled as an overlay of
  eleven test families.
- **Volcano feature ids used the RefMet name**, which isomers, repeat features
  and multi-platform measurements share (10 duplicates in ST004303, 226 in the
  MoTrPAC human table, and one source label reported under two RefMet lipid
  names within one rat sex). Feature identity is now the (source label, RefMet
  name) pair, and `prepare_volcano_data` rejects a duplicate feature id within a
  contrast instead of plotting it twice.
- **`classify_mw_timepoint` matched bare substrings**, so `Diagnosis:prediabetes`,
  `Treatment:prednisone` and `Sample source:Blood` (via `:b`) classified as
  pre-exercise samples and `CTR2` as a time-0 sample — enough to pair samples
  into a contrast the study never ran. Fallback tokens are now matched on
  alphanumeric-token boundaries, with the first test coverage for the function.
- **`mw_exercise_studies.csv` presented a keyword sweep as an exercise-study list.**
  Of its 66 titles, 44 contain no exercise term (sleep-apnea, cardiolipin,
  cardiomyocyte and cardiomyopathy studies retrieved by "cardio"), 3 match only
  an ambiguous phrase ("training set", "biosignature training", "fitness to
  hypoxia"), and 19 support an exercise context. `scripts/screen_mw_exercise_study_titles.py`
  writes the per-title screen with every row routed to human review and records
  that the list has no retrieval query or endpoint on file.
- **Unit conversions were not analyte-specific.** `choose_transform` applied the
  glucose molar-mass factor (18.0182) to any mmol/L to mg/dL pair; it is now
  keyed by common variable, so a non-glucose analyte with that unit pair routes
  to review instead of being converted with the wrong factor.
- **`gender` reached `sex` as a plain synonym.** The mapping stays proposable but
  is capped at 0.78 with an explicit construct caveat, and the review packet
  now asks whether the source recorded biological sex or gender identity rather
  than citing "insufficient confidence".
- A `not_reported` assay platform was described as "reported" in the quality
  rationale and earned repository-completeness credit in the recommender; both
  now use one unreported-value set.

### Changed — scoring rule set 0.3.0, benchmark rule set 0.3.0

- **The dataset-readiness scorer now has a scope gate.** The scale is defined
  for human MoTrPAC-style comparison planning, but a documented non-human study
  (`SYN-ANIMAL-MET`, rat muscle) scored 0.688 — above a 1200-participant human
  cohort — while the recommender excluded the same study as out of scope.
  `QualityScore` gains `scope_status` (`in_scope_human`,
  `out_of_scope_non_human`, `human_status_unknown`) from the study card's
  three-valued `human` evidence; a documented non-human study's
  `overall_score` is withheld (`null`) with its subscores kept visible, and an
  undocumented human status keeps a triage score but is flagged rather than
  scored down — the same documented-absent / not-documented distinction the
  mirage detector and MoTrPAC alignment already draw. Rows are validated against
  `schemas/quality_score.schema.json` before they are written.
- **The benchmark compares scope before numbers.** `expert_quality_scores.csv`
  gains a `scope_status` column (the expert's 0.20 for the rat study encoded
  exactly this judgement); `quality_score_agreement_within_0.15` is now defined
  over gold studies not declared out of scope (8/9 = 0.889, previously 8/10),
  and a tenth metric, `scope_status_accuracy`, reports 10/10. A withheld
  prediction is accepted only for a row declared out of scope; any other null
  fails closed. New case reason codes `scope_status_mismatch` and
  `quality_score_not_reported`; the manifest schema pins both rule-set versions
  at 0.3.0. The one remaining numeric disagreement is the no-data mirage
  (`SYN-EXER-NODATA` 0.484 vs 0.33), which the availability-gate proposal in the
  review document addresses and this release does not.

### Fixed — reproducibility

- **Committed `data/extracted/` did not match `run-pilot`.** The ten study cards
  lacked the `publication_evidence` provenance key the code has emitted since
  the initial import, and ten unsuffixed `dataset_SYN-*.json` cards from the
  initial import were never produced by the current code. Regenerated with the
  documented command and removed the legacy cards. Verified byte-identical
  output with and without `pydantic` installed (the `_compat` fallback), so the
  gap was a regeneration omission, not an environment effect.

### Known limitations

- The dataset-readiness scorer still credits modality subscores regardless of
  data availability, which is why the no-data mirage (`SYN-EXER-NODATA` 0.484
  vs expert 0.33) remains the one numeric benchmark disagreement. An
  availability gate is proposed, not applied, in the review document.
- The rat pass1b-06 volcano table and 25 of 29 `data/live` provenance files
  still carry no retrieval record or licence field respectively.

## [0.2.1] — 2026-08-24

First release intended for use outside the authoring group. No scientific
conclusions changed; the fixes below are about a stranger being able to install
this, trust its outputs, and reproduce them.

### Fixed — reproducibility

- **A published quality score depended on the Python version.** `score_quality`
  accumulated weighted subscores with the builtin `sum()`. CPython 3.12 gave
  `sum()` Neumaier compensated summation for floats, so the ten terms for
  `SYN-CPET-RICH` totalled `0.8174999999999998` on 3.11 and `0.8175000000000000`
  on 3.12+, landing either side of a rounding boundary and scoring 0.817 or
  0.818. The project declares `requires-python >=3.11` and CI runs 3.11, so the
  score depended on who ran it. Now uses `math.fsum`, which is exactly rounded on
  every version. Verified byte-identical pilot output on 3.11.15 and 3.14.4.
- **`reports/render.py` could not be imported on Python 3.11**, the declared
  minimum: it used a backslash escape inside an f-string expression, legal only
  from 3.12. This was invisible because the lint gate failed before the tests ran.
- **The test suite rewrote a committed scientific artifact.** `discover` and
  `score-quality` rendered their reports into a hardcoded `reports/` directory,
  ignoring `--out`. Running `python -m unittest` therefore overwrote
  `reports/aim1_catalog_report.md` with results from a test query, so a reviewer
  diffing `reports/` saw scores that no documented command produces. Both
  commands now write only inside `--out`, the smoke test runs the pilot in a
  temporary workspace, and a regression test asserts `discover` creates no
  `reports/` tree.
- **Three committed RefMet enrichment reports pooled human Metabolomics
  Workbench, human MoTrPAC, and rat rows into a single background** with no
  per-stratum multiple-testing correction, which is the pooling the codebase
  forbids elsewhere. Regenerated: 254 labels across 13 declared strata, BH `q`
  within each stratum, and an explicit statement that human and rat strata are
  never treated as exchangeable.

- **The benchmark manifest schema pinned `software_version` to the literal
  `0.2.0`**, so any release bump made `benchmark` fail schema validation. It is
  now a semver-shaped string. `rule_set_version` and `benchmark_rule_set_version`
  stay pinned, because those must move only when the scoring rules change. The
  matching test now asserts against `metabotyping_agentic.__version__` rather
  than a literal.
- Worth knowing when verifying locally: `jsonschema` is a core dependency, but if
  it is missing from your environment `validate_against_schema` silently degrades
  to a required-keys check. A venv without it will pass tests that CI fails.
  Install with the project rather than ad hoc.

### Fixed — credentials

- **Removed a hardcoded MoTrPAC API key** from `scripts/volcano_compare.py` and
  its test fixture. The key is public (MoTrPAC ships it in their web bundle) but
  it is their credential, it goes stale on rotation, and it trips secret scanners
  on every clone. It is now discovered from the published bundle at run time,
  overridable with `MOTRPAC_API_KEY`. **The key remains in git history and should
  be treated as exposed; rotation is the source owner's call.**
- **`NCBI_API_KEY` and `METABOTYPING_CONTACT_EMAIL` no longer reach provenance
  files.** Endpoint URLs recorded in `literature_provenance.json` are published
  with the results, and the E-utilities URLs embedded both values verbatim. They
  are now masked as `<redacted>` in the recorded copy while the outbound request
  still carries the real values. `CLAUDE.md` previously claimed they were never
  written anywhere; corrected.
- **`review-literature` no longer overwrites the offline pilot.** Its defaults
  were `--out data/extracted` and `--reports-out reports`, so a no-flag run
  replaced the pilot's synthetic `reports/literature_report.md` with live output.
  Defaults are now `data/live/literature` and `reports_live/literature`.

### Fixed — installability

- `scipy` was undeclared, so `scripts/volcano_compare.py` — step 2 of the
  flagship single-metabolite lane and an allowlisted network entry point — could
  not start after any documented install. Added to the `plotting` extra, with a
  new `docs` extra for `python-docx` and `pillow`.
- `README.md` told new users to `pip install -e ".[dev]"`, which leaves matplotlib
  missing; because the strict gate fails on any skip, the project's own readiness
  gate then reported `FAIL`. The README now gives `[dev,plotting]`, matching
  `CONTRIBUTING.md` and CI, and explains the consequence.
- A missing optional dependency in `tests/test_metabolite_effect_search.py` raised
  an `ImportError` at collection instead of skipping, so an environment gap was
  indistinguishable from a scientific failure. It now skips with the reason named.
- Restored the CI lint gate, which had been failing and therefore preventing the
  test, audit, reproducibility, and drift steps from running at all. `UP042`
  (`StrEnum`) and `B905` (`zip(strict=)`) are ignored with a stated reason: both
  change runtime behaviour and these values are serialized into byte-reproducible
  artifacts. `ruff` is pinned to `>=0.16,<0.17` so a new release cannot re-break
  the gate.

### Added

- `docs/QUICKSTART.md`: one question end to end on offline fixtures, with every
  command verified against a clean clone.
- `README.md` section on activating the agents and skills in Claude Code and
  Codex. Previously the only guidance was a path inventory, which left the
  project's distinguishing contribution undiscoverable.
- `data/README.md`: licence terms stated separately for the synthetic fixtures
  (MIT, ours) and the 68 MB of redistributed MoTrPAC and Metabolomics Workbench
  records (not ours to relicense). Records that only 4 of 29 provenance files
  currently carry a licence field, and treats the rest as unresolved rather than
  absent.
- Eight advisory and critic agents now declare `tools: Read, Grep, Glob, Bash`,
  so a contract that says "Never execute a scientific or data action" is not
  dispatched holding `Write` and `Edit`. `scripts/evaluate_skills.py` previously
  rejected `tools` and `model` as unsupported frontmatter, meaning the audit
  scored a contract 1.000 for *not* constraining itself. Defence in depth only:
  the real boundary stays `review/validation.py` at ingest.
- The literature evidence lane (Europe PMC, PubMed E-utilities, Crossref,
  bioRxiv/medRxiv) with offline screening and appraisal held separate from
  retrieval, its skill and agent contracts, and 23 tests.

### Fixed — defects found by independent verification of the above

Four verifiers re-checked the fixes above from clean clones. These were wrong or
incomplete and are now corrected:

- **`review-literature` was only half fixed.** The argparse defaults moved, but
  the typer command still pointed at `data/extracted` and `reports/`. typer is a
  required dependency, so that was the live path and a no-flag run still
  overwrote four committed offline-pilot artifacts. Both frontends now agree, and
  `tests/test_cli_frontend_parity.py` asserts every shared option default matches
  and that no live lane defaults into a protected tree.
- **Redaction was too narrow.** It covered the endpoints list only. The NCBI key
  still reached provenance through raised error text, and the contact email
  reached every record through `source_url`, then propagated into the screened
  CSVs and the rendered report. Redaction now happens at all five error sites and
  every `source_url`, with an end-to-end test that drives the lane under both
  environment variables and asserts neither value reaches disk.
- **Three more float accumulations fed published numbers**, not just the quality
  score: the paired-effect variance, the Pearson r behind the Lac-Phe
  lactate-coupling result, and the Fisher enrichment p-value. The first two now
  use `math.fsum`. The Fisher p needed more — even with `fsum`, the x86_64 and
  arm64 `libm` builds of `math.exp`/`math.lgamma` disagreed in the 13th digit, so
  the divergence was upstream of the sum. It now uses exact integer arithmetic
  via `math.comb` with a single final division, and is bit-identical on 3.11.15
  arm64, 3.12.8 x86_64 and 3.14.4 arm64.
- **`metabolite_effects_leucine.md` published two mappings as `accepted_exact`
  that the current code classifies `requires_human_review`** — a published
  classification more permissive than the code produces, against the stated
  escalation non-negotiable. Regenerated, along with the acylcarnitine and
  kynurenine reports and the enrichment artifacts affected by the Fisher change.
- **`docs/QUICKSTART.md` claimed `--out` is honoured strictly by every
  subcommand.** It is not: `run-pilot` always writes `data/extracted/` and
  `data/review/` relative to the working directory and discards uncommitted edits
  there. Documented the real behaviour with a scratch-directory recipe instead.
- **`data/live/refmet_annotations.csv` had no provenance record at all** — 16 MB
  and 205,948 rows backing every RefMet class and enrichment result, with no
  source URL, retrieval date, or release. Added
  `refmet_annotations_provenance.json`, which records the RefMet identification
  as a text inference from the `RM` identifier namespace and states the missing
  fields as unresolved rather than reconstructing a plausible endpoint.

### Known limitations

- The Google API key removed above is still present in git history, including in
  `.pyc` blobs committed in an earlier commit. Only rotation by MoTrPAC actually
  revokes it.
- 25 of 29 `data/live` provenance files do not record a licence, and
  `refmet_annotations.csv` has no recorded retrieval provenance or RefMet
  release, so its class assignments are reproducible here by checksum but not
  attributable to a named RefMet version.
- Each live lane has exactly one worked example (Lac-Phe, plus one literature
  query), so generalisation to other studies' factor conventions is untested. The
  Metabolomics Workbench timepoint classifier infers "pre-exercise" from a bare
  `pre` or `:b` substring and has no test coverage.
- Reproducibility is verified on CPython 3.11.15 (arm64), 3.12.8 (x86_64) and
  3.14.4 (arm64). Figure binaries depend on the matplotlib version and are not
  byte-reproducible across matplotlib releases.
- No DOI and no git tag yet, so there is nothing citable to pin a manuscript to.

## [0.2.0]

Expanded the agent and skill roster to 22 canonical paired agent roles and 24
paired skill contracts; added the four advisory `DomainReviewPacket` reviewers
with deterministic validation; made the network boundary real and enforced it by
AST scan in `tests/test_network_boundary.py`; added the Lac-Phe cross-species
worked example and the MoTrPAC-style plotting lane.

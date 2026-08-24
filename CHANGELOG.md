# Changelog

Notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

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
  records (not ours to relicense). Records that only 3 of 28 provenance files
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

### Known limitations

- The Google API key removed above is still present in git history.
- 25 of 28 `data/live` provenance files do not record a licence.
- Each live lane has exactly one worked example (Lac-Phe, plus one literature
  query), so generalisation to other studies' factor conventions is untested. The
  Metabolomics Workbench timepoint classifier infers "pre-exercise" from a bare
  `pre` or `:b` substring and has no test coverage.
- Reproducibility is verified on Python 3.11 and 3.14 only.
- No DOI yet.

## [0.2.0]

Expanded the agent and skill roster to 22 canonical paired agent roles and 24
paired skill contracts; added the four advisory `DomainReviewPacket` reviewers
with deterministic validation; made the network boundary real and enforced it by
AST scan in `tests/test_network_boundary.py`; added the Lac-Phe cross-species
worked example and the MoTrPAC-style plotting lane.

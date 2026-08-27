# Quickstart

Thirty minutes, no network, no API keys. Every command here runs against the
synthetic fixtures in `data/examples/`, so you can see the whole pipeline and its
review gates before pointing anything at real data.

If you only have five minutes, run step 2 and read
`reports/human_review_packet.md`. That file is the point of the project.

## 1. Install

Requires Python 3.11 or newer.

```bash
git clone https://github.com/Samuelmontalvo/metabotyping-agentic-workbench.git
cd metabotyping-agentic-workbench
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,plotting]"
```

Use `[dev,plotting]`, not `[dev]`. The figure renderers and the paired-effect
statistics need matplotlib, numpy, and scipy, and the strict release gate fails
on any skipped test.

Check the install:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

You should see `OK` with no failures, errors, or skips.

## 2. Run the offline pilot

```bash
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli run-pilot --out reports
```

This runs the full arc on synthetic studies: inclusion criteria, discovery,
metadata extraction, variable crosswalk, review gating, harmonization planning,
readiness scoring, MoTrPAC-style alignment, literature screening, and
benchmarking against expert fixtures. It writes into `reports/` and
`data/extracted/`.

Read these four, in this order:

| File | What to look for |
|---|---|
| `reports/aim1_catalog_report.md` | Studies classified `direct_match`, `enrichment_candidate`, `mirage`, or `excluded`, each with the rationale that produced the class |
| `reports/human_review_packet.md` | Every mapping the system refused to decide, with the reason a human must decide it |
| `reports/aim3_evaluation_report.md` | Readiness subscores and the weights behind each overall score |
| `reports/benchmark_report.md` | Agreement against expert-curated fixtures, with explicit denominators |

Two things are worth noticing. `SYN-EXER-NODATA` is classified `mirage`: the
publication looks usable and the repository record has no usable assets, which is
the failure mode the project exists to catch. And in the review packet, mappings
sitting at confidence 0.88 are still escalated rather than accepted, because
confidence alone is not evidence of construct equivalence.

The pilot is byte-reproducible. Run it twice into different directories and
compare:

```bash
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli run-pilot --out /tmp/pilot-a
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli run-pilot --out /tmp/pilot-b
diff -r /tmp/pilot-a /tmp/pilot-b && echo "byte-identical"
```

## 3. Run one step at a time

Each stage is a separate subcommand, so you can inspect intermediate state.

```bash
# Turn a research question into auditable inclusion criteria
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli define-criteria \
  --query "human metabolomics with exercise and genetics" \
  --out /tmp/criteria.json

# Rank the fixture corpus against those criteria
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli discover \
  --criteria /tmp/criteria.json --out /tmp/discovery

# Which databases would answer a multi-lane question, and which lanes are unregistered
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli route-sources \
  --lanes "repository,literature" --out /tmp/plan.json
```

Change a required term in `/tmp/criteria.json`, rerun `discover`, and watch
studies move between classes. That is the auditability claim: the classification
is a function of stated criteria, not a model's opinion.

The single-stage subcommands above honour `--out` strictly: `discover`,
`score-quality`, and `review-literature` write only inside the directory you give
them, which is what keeps a stray run from overwriting the committed pilot report.

`run-pilot` is the exception, and it is worth knowing before you use it.
`--out` controls where the *reports* go, but the pipeline's intermediate state is
always written to `data/extracted/` and `data/review/` relative to the current
working directory, whatever `--out` says. Running it from a checkout therefore
regenerates those trees in place and discards any uncommitted edits you have made
there. If you are experimenting with `data/extracted/criteria.json`, copy it
somewhere else first, or run the pilot from a scratch directory:

```bash
mkdir -p /tmp/pilot-run && cp -R data/examples /tmp/pilot-run/
cd /tmp/pilot-run && PYTHONPATH=<repo>/src python -m metabotyping_agentic.cli run-pilot --out reports
```

## 4. Check the project's own gates

```bash
# Skill and agent contract audit: structure, parity, declared implementations
PYTHONPATH=src .venv/bin/python scripts/evaluate_skills.py

# Strict scientific-readiness gate: fails on any failure, error, or skip
PYTHONPATH=src .venv/bin/python scripts/evaluate_scientific_readiness.py
```

Both regenerate their reports under `docs/`. On an unmodified clone they
regenerate byte-identically, so `git status` stays clean; CI enforces exactly
that.

## 5. Use the agents and skills

Open the repository root in Claude Code or Codex. Nothing to install; see
[Activating the agents and skills](../README.md#activating-the-agents-and-skills).

Good first prompts:

- "Score the fixture datasets for MoTrPAC-like replication feasibility and tell
  me which ones fail a hard gate."
- "Challenge the crosswalk in `data/extracted/crosswalk.csv`. Which mappings
  would you refuse and why?"
- "Build inclusion criteria for a question about acute exercise and plasma
  acylcarnitines, then tell me what evidence is missing."

Expect the system to refuse things. A skeptic that declines to approve a mapping,
or a reviewer that reports `not_reported` instead of guessing, is working
correctly. The advisory reviewers emit a typed `DomainReviewPacket` that
`review/validation.py` rejects outright if it smuggles in an acceptance, a
confidence score, a pooling permission, or a pooled estimate.

## 6. Going live (optional)

Live ingestion is a separate opt-in mode. It queries public released records
only, writes to `data/live/` and `reports_live/`, and never touches
`data/examples/` or `reports/`. Network access is confined to five allowlisted
modules, enforced by an AST scan in `tests/test_network_boundary.py`.

Read the "Live Ingestion Mode" section of `CLAUDE.md` before running any
`live-*` subcommand. The worked example is Lac-Phe:
`reports_live/lacphe/lacphe_report.md` shows the identity resolution, the human
effect, the rat coverage gap, and the nine escalations that stopped it from being
reported as a cross-species replication.

## What this does not do

It does not decide anything scientific for you. It ranks, extracts, flags,
scores, and refuses. Every uncertain mapping, every missing codebook, and every
unresolved identity is routed to a human, and a passing gate measures structure
and reproducibility rather than scientific validity. See "Current scientific
limitations" in the README.

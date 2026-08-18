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

- The only networked entry point is `scripts/fetch_live_records.py`. No other module may make network calls.
- Live data is written under `data/live/` and live reports under `reports_live/`. Never overwrite `data/examples/` (synthetic fixtures) or `reports/` (offline pilot output).
- Sources are public, released, openly licensed records only (e.g. Metabolomics Workbench REST; MoTrPAC metabolomics hosted on MW). Record exact source URLs in `data/live/provenance.json`.
- Do not fabricate records for embargoed/access-controlled data (e.g. the human MoTrPAC DataHub arm). Represent unavailable data as an availability gap / mirage risk, never as a synthetic stand-in.
- All scientific guardrails (mirage detection, human-review escalation, missing-codebook = risk) apply identically to live records.

Run:

```bash
python3 scripts/fetch_live_records.py            # fetch curated real studies -> data/live/
# or: python3 scripts/fetch_live_records.py ST004303 ST003807 ST002916
```

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

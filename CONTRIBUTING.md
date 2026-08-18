# Contributing

MetaboTyping Agentic Workbench is an offline synthetic-data MVP. Contributions should preserve provenance, deterministic behavior, and human review boundaries.

## Development setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,plotting]"
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python scripts/evaluate_skills.py
PYTHONPATH=src .venv/bin/python scripts/evaluate_scientific_readiness.py
```

## Change requirements

- Use only synthetic or mock data in tracked fixtures and tests.
- Add or update focused tests for behavioral changes.
- Preserve explicit unknown, missing, unavailable, and documented-absent states.
- Never accept variable mappings solely from name similarity.
- Keep `vo2max` machine-readable and use `VO2max` or `VO₂max` only in human-facing text.
- Do not collapse `VO2max` and `VO2peak` without protocol and endpoint evidence.
- Update `docs/skill_evaluation_report.md` after changing project skills or agent contracts.
- Run the full unit-test suite before requesting review.

## Pull requests

Describe the scientific assumption being changed, the affected artifacts, the human-review implications, and the verification commands used. Do not include credentials, participant-level data, generated caches, or local history files.

# Score Datasets

Run quality and MoTrPAC alignment scoring:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli score-quality --metadata data/extracted --out data/extracted
PYTHONPATH=src python3 -m metabotyping_agentic.cli align-motrpac --metadata data/extracted --out reports
```

Interpret scores as triage evidence, not final scientific adjudication.


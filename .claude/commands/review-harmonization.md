# Review Harmonization

Inspect:

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli review-crosswalk --crosswalk data/extracted/crosswalk.csv --out data/review
```

Then review `reports/human_review_packet.md`. Do not move review-required mappings into ETL without explicit expert acceptance.


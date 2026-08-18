"""Synthetic publication loading."""

from __future__ import annotations

from pathlib import Path

from ..io import parse_bool, read_csv_rows
from ..models import PublicationRecord


def load_publications(path: str | Path) -> list[PublicationRecord]:
    records: list[PublicationRecord] = []
    for row in read_csv_rows(path):
        records.append(
            PublicationRecord(
                study_id=row["study_id"],
                title=row["title"],
                doi=row.get("doi") or "not_reported",
                pmid=row.get("pmid") or "not_reported",
                human=parse_bool(row.get("human")),
                exercise=parse_bool(row.get("exercise")),
                actigraphy=parse_bool(row.get("actigraphy")),
                metabolomics=parse_bool(row.get("metabolomics")),
                genetics=parse_bool(row.get("genetics")),
                cpet=parse_bool(row.get("cpet")),
                body_composition=parse_bool(row.get("body_composition")),
                diet=parse_bool(row.get("diet")),
                repository_accession=row.get("repository_accession") or "not_available",
                notes=row.get("notes") or "",
            )
        )
    return records


def modalities_from_publication(record: PublicationRecord) -> list[str]:
    modalities = []
    for name in [
        "metabolomics",
        "exercise",
        "actigraphy",
        "genetics",
        "cpet",
        "body_composition",
        "diet",
    ]:
        if getattr(record, name):
            modalities.append(name)
    return modalities


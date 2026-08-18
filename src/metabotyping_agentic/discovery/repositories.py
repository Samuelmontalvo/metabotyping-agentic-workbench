"""Repository record loading."""

from __future__ import annotations

from pathlib import Path

from ..io import parse_bool, parse_int, parse_modalities, read_csv_rows
from ..models import DataAvailability, RepositoryRecord


def parse_data_availability(value: str) -> DataAvailability:
    normalized = (value or "unknown").strip().lower()
    aliases = {
        "public": DataAvailability.PUBLIC,
        "open": DataAvailability.PUBLIC,
        "restricted_metadata_only": DataAvailability.RESTRICTED_METADATA_ONLY,
        "restricted": DataAvailability.RESTRICTED_METADATA_ONLY,
        "not_available": DataAvailability.NOT_AVAILABLE,
        "none": DataAvailability.NOT_AVAILABLE,
        "unknown": DataAvailability.UNKNOWN,
    }
    return aliases.get(normalized, DataAvailability.UNKNOWN)


def load_repository_records(path: str | Path) -> list[RepositoryRecord]:
    records: list[RepositoryRecord] = []
    for row in read_csv_rows(path):
        documented_absent = [
            modality
            for modality in parse_modalities(row.get("documented_absent_modalities", ""))
            if modality.value != "unknown"
        ]
        records.append(
            RepositoryRecord(
                study_id=row["study_id"],
                repository=row.get("repository") or "unknown",
                accession=row.get("accession") or "not_available",
                public_status=parse_data_availability(row.get("public_status", "unknown")),
                has_metadata=parse_bool(row.get("has_metadata")),
                has_codebook=parse_bool(row.get("has_codebook")),
                has_data_files=parse_bool(row.get("has_data_files")),
                assay_platform=row.get("assay_platform") or "unknown",
                sample_matrix=row.get("sample_matrix") or "unknown",
                biospecimen_timing=row.get("biospecimen_timing") or "unknown",
                sample_size=parse_int(row.get("sample_size")),
                modalities=parse_modalities(row.get("modalities", "")),
                documented_absent_modalities=documented_absent,
            )
        )
    return records


def repository_by_study(records: list[RepositoryRecord]) -> dict[str, RepositoryRecord]:
    """Index unique repository records by study.

    This legacy singular index is intentionally strict: silently retaining the
    last record would discard evidence when one study is represented in more
    than one repository. Multi-repository callers must use
    :func:`repositories_by_study`.
    """

    grouped = repositories_by_study(records)
    duplicates = {study_id: len(items) for study_id, items in grouped.items() if len(items) > 1}
    if duplicates:
        details = ", ".join(
            f"{study_id} ({count} records)" for study_id, count in sorted(duplicates.items())
        )
        raise ValueError(
            "repository_by_study requires unique study_id values; duplicate repository "
            f"records found for: {details}. Use repositories_by_study for one-to-many evidence."
        )
    return {study_id: items[0] for study_id, items in grouped.items()}


def repositories_by_study(records: list[RepositoryRecord]) -> dict[str, list[RepositoryRecord]]:
    """Group all repository records by study without dropping input order or duplicates."""

    grouped: dict[str, list[RepositoryRecord]] = {}
    for record in records:
        grouped.setdefault(record.study_id, []).append(record)
    return grouped

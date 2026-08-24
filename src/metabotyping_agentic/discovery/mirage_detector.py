"""Detect studies that look relevant but lack usable data assets."""

from __future__ import annotations

from ..models import DataAvailability, PublicationRecord, RepositoryRecord

UNKNOWN_VALUES = {"", "unknown", "not_available", "not_reported", None}


def detect_mirage_flags(
    publication: PublicationRecord | None = None,
    repository: RepositoryRecord | None = None,
) -> list[str]:
    flags: list[str] = []
    accession = None
    if repository is not None:
        accession = repository.accession
    elif publication is not None:
        accession = publication.repository_accession

    if accession in UNKNOWN_VALUES:
        flags.append("no_repository_accession")

    if repository is None:
        if publication is not None and publication.metabolomics:
            flags.append("no_repository_record")
        return flags

    if repository.public_status == DataAvailability.RESTRICTED_METADATA_ONLY and not repository.has_metadata:
        flags.append("restricted_data_without_metadata")
    if repository.public_status == DataAvailability.NOT_AVAILABLE:
        flags.append("repository_data_not_available")
    if not repository.has_metadata:
        flags.append("no_downloadable_metadata")
    if not repository.has_codebook:
        flags.append("no_variable_dictionary_or_codebook")
    if not repository.has_data_files:
        flags.append("no_data_files")
    if repository.assay_platform in UNKNOWN_VALUES:
        flags.append("unclear_assay_platform")
    if repository.biospecimen_timing in UNKNOWN_VALUES:
        flags.append("unclear_biospecimen_timing")
    if repository.sample_size is None:
        flags.append("sample_size_not_reported")
    return flags


def is_mirage(flags: list[str]) -> bool:
    severe = {
        "no_repository_accession",
        "no_downloadable_metadata",
        "no_variable_dictionary_or_codebook",
        "restricted_data_without_metadata",
        "repository_data_not_available",
    }
    return any(flag in severe for flag in flags)


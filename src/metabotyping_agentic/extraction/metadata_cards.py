"""Create structured metadata cards from synthetic CSV fixtures."""

from __future__ import annotations

import re
from pathlib import Path

from ..discovery.literature import load_publications
from ..discovery.mirage_detector import detect_mirage_flags
from ..discovery.recommender import score_publication
from ..discovery.repositories import load_repository_records, repositories_by_study
from ..io import ensure_dir, to_plain, write_json
from ..models import DatasetCard, Modality, PublicationRecord, StudyCard
from ..schemas import project_schema_path, validate_or_raise

UNKNOWN_ACCESSIONS = {"", "unknown", "not_available", "not_reported"}
MATCH_CLASS_PRIORITY = {
    "direct": 5,
    "enrichment": 4,
    "complementary": 3,
    "mirage": 2,
    "excluded": 1,
    "unknown": 0,
}


def _plain_enum(value: object) -> str:
    return str(value.value if hasattr(value, "value") else value)


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _repository_accessions(
    repositories: list,
    publication: PublicationRecord | None,
) -> list[str]:
    values: list[str] = []
    if publication is not None and publication.repository_accession not in UNKNOWN_ACCESSIONS:
        values.append(publication.repository_accession)
    values.extend(repo.accession for repo in repositories if repo.accession not in UNKNOWN_ACCESSIONS)
    return _ordered_unique(values)


def _primary_repository_accession(
    publication: PublicationRecord | None,
    accessions: list[str],
) -> str:
    if publication is not None and publication.repository_accession not in UNKNOWN_ACCESSIONS:
        return publication.repository_accession
    return accessions[0] if accessions else "not_available"


def _repository_quality_key(repository: object, index: int) -> tuple[int, int]:
    known_metadata = sum(
        [
            bool(repository.has_metadata),
            bool(repository.has_codebook),
            bool(repository.has_data_files),
            repository.assay_platform not in {"", "unknown", "not_reported"},
            repository.sample_matrix not in {"", "unknown", "not_reported"},
            repository.biospecimen_timing not in {"", "unknown", "not_reported"},
            repository.sample_size is not None,
        ]
    )
    return known_metadata, -index


def _representative_repository(repositories: list):
    return max(
        enumerate(repositories),
        key=lambda item: _repository_quality_key(item[1], item[0]),
    )[1]


def _best_publication_evidence(publication: PublicationRecord, repositories: list):
    candidates = []
    for index, repository in enumerate(repositories):
        recommendation = score_publication(publication, repository)
        match_class = _plain_enum(recommendation.match_class)
        candidates.append(
            (
                MATCH_CLASS_PRIORITY.get(match_class, 0),
                float(recommendation.score),
                -index,
                recommendation,
                repository,
            )
        )
    return max(candidates, key=lambda item: item[:3])[3:]


def _combined_modalities(repositories: list) -> list[Modality]:
    values: list[Modality] = []
    seen: set[str] = set()
    for repository in repositories:
        for modality in repository.modalities:
            key = _plain_enum(modality)
            if key in seen:
                continue
            seen.add(key)
            values.append(modality)
    return values or [Modality.UNKNOWN]


def _filename_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-._")
    return token or "unknown"


def _repository_row_key(repository: object, source_row_number: int) -> str:
    return (
        f"{repository.study_id}::{repository.repository}::{repository.accession}::"
        f"row-{source_row_number}"
    )


def _dataset_card_filename(repository: object, source_row_number: int) -> str:
    return (
        f"dataset_{_filename_token(repository.study_id)}__"
        f"{_filename_token(repository.repository)}__"
        f"{_filename_token(repository.accession)}__r{source_row_number}.json"
    )


def modalities_from_publication(record: PublicationRecord) -> list[Modality]:
    modalities: list[Modality] = []
    for flag, modality in [
        (record.metabolomics, Modality.METABOLOMICS),
        (record.exercise, Modality.EXERCISE),
        (record.actigraphy, Modality.ACTIGRAPHY),
        (record.genetics, Modality.GENETICS),
        (record.cpet, Modality.CPET),
        (record.body_composition, Modality.BODY_COMPOSITION),
        (record.diet, Modality.DIET),
    ]:
        if flag:
            modalities.append(modality)
    return modalities or [Modality.UNKNOWN]


def extract_metadata_cards(
    records_path: str | Path,
    out_dir: str | Path,
    publications_path: str | Path | None = None,
) -> tuple[list[StudyCard], list[DatasetCard]]:
    out_dir = Path(out_dir)
    card_dir = ensure_dir(out_dir / "metadata_cards")
    repositories = load_repository_records(records_path)
    repos_by_study = repositories_by_study(repositories)
    publications: list[PublicationRecord] = []
    if publications_path and Path(publications_path).exists():
        publications = load_publications(publications_path)
    pub_by_study = {publication.study_id: publication for publication in publications}

    study_cards: list[StudyCard] = []
    dataset_cards: list[DatasetCard] = []

    source_row_by_record = {id(repo): index + 2 for index, repo in enumerate(repositories)}

    for study_id, study_repositories in repos_by_study.items():
        publication = pub_by_study.get(study_id)
        accessions = _repository_accessions(study_repositories, publication)
        repository_row_keys = [
            _repository_row_key(repo, source_row_by_record[id(repo)]) for repo in study_repositories
        ]
        if publication is not None:
            recommendation, representative = _best_publication_evidence(publication, study_repositories)
            study_card = StudyCard(
                study_id=publication.study_id,
                title=publication.title,
                human=publication.human,
                modalities=modalities_from_publication(publication),
                repository_accession=_primary_repository_accession(publication, accessions),
                repository_accessions=accessions,
                match_class=recommendation.match_class,
                mirage_flags=recommendation.mirage_flags,
                provenance={
                    "source": str(publications_path),
                    "row_key": publication.study_id,
                    "repository_row_keys": repository_row_keys,
                    "representative_repository": {
                        "repository": representative.repository,
                        "accession": representative.accession,
                    },
                },
                notes=publication.notes,
            )
        else:
            representative = _representative_repository(study_repositories)
            study_card = StudyCard(
                study_id=study_id,
                title="unknown",
                human=True,
                modalities=_combined_modalities(study_repositories),
                repository_accession=_primary_repository_accession(None, accessions),
                repository_accessions=accessions,
                match_class="unknown",
                mirage_flags=detect_mirage_flags(None, representative),
                provenance={
                    "source": str(records_path),
                    "row_key": study_id,
                    "repository_row_keys": repository_row_keys,
                    "representative_repository": {
                        "repository": representative.repository,
                        "accession": representative.accession,
                    },
                },
                notes="Publication metadata was not supplied to this extraction command.",
            )
        study_payload = to_plain(study_card)
        validate_or_raise(
            study_payload,
            project_schema_path("study_card.schema.json"),
            label=f"study card {study_id}",
        )
        study_cards.append(study_card)
        write_json(card_dir / f"study_{_filename_token(study_id)}.json", study_payload)

        for repo in study_repositories:
            source_row_number = source_row_by_record[id(repo)]
            flags = detect_mirage_flags(publication, repo)
            dataset_card = DatasetCard(
                study_id=repo.study_id,
                repository=repo.repository,
                accession=repo.accession,
                data_availability=repo.public_status,
                has_metadata=repo.has_metadata,
                has_codebook=repo.has_codebook,
                has_data_files=repo.has_data_files,
                assay_platform=repo.assay_platform,
                sample_matrix=repo.sample_matrix,
                biospecimen_timing=repo.biospecimen_timing,
                sample_size=repo.sample_size,
                modalities=repo.modalities,
                documented_absent_modalities=repo.documented_absent_modalities,
                mirage_flags=flags,
                provenance={
                    "source": str(records_path),
                    "row_key": _repository_row_key(repo, source_row_number),
                    "source_row_number": source_row_number,
                },
            )
            dataset_payload = to_plain(dataset_card)
            validate_or_raise(
                dataset_payload,
                project_schema_path("dataset_card.schema.json"),
                label=f"dataset card {repo.study_id}::{repo.repository}::{repo.accession}",
            )
            dataset_cards.append(dataset_card)
            write_json(
                card_dir / _dataset_card_filename(repo, source_row_number),
                dataset_payload,
            )

    write_json(out_dir / "study_cards.json", [to_plain(card) for card in study_cards])
    write_json(out_dir / "dataset_cards.json", [to_plain(card) for card in dataset_cards])
    return study_cards, dataset_cards

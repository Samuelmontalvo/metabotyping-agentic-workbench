"""Rule-based study and dataset recommendation."""

from __future__ import annotations

from ..models import (
    InclusionCriteria,
    MatchClass,
    PublicationRecord,
    Recommendation,
    RecommendationClass,
    RepositoryRecord,
)
from ..sample_matrix import (
    has_blood_derived_sample_matrix,
    is_metabolomics_workbench_repository,
    looks_like_metabolomics_workbench_accession,
)
from .mirage_detector import UNKNOWN_VALUES, detect_mirage_flags, is_mirage

DEFAULT_PREFERRED_TERMS = {
    "exercise",
    "actigraphy",
    "genetics",
    "cpet",
    "body_composition",
    "diet",
}


def _normalize_term(term: str) -> str:
    return term.strip().lower().replace("-", "_").replace(" ", "_")


def _term_present(publication: PublicationRecord, term: str) -> bool:
    normalized = _normalize_term(term)
    if normalized == "physical_activity":
        return publication.exercise or publication.actigraphy
    supported = {
        "human",
        "metabolomics",
        "exercise",
        "actigraphy",
        "genetics",
        "cpet",
        "body_composition",
        "diet",
    }
    if normalized not in supported:
        raise ValueError(f"Unsupported inclusion-criteria term: {term!r}")
    return bool(getattr(publication, normalized))


def score_publication(
    publication: PublicationRecord,
    repository: RepositoryRecord | None = None,
    criteria: InclusionCriteria | None = None,
) -> Recommendation:
    flags = detect_mirage_flags(publication, repository)
    required_terms = criteria.required_terms if criteria is not None else ["human", "metabolomics"]
    unmet_required = [term for term in required_terms if not _term_present(publication, term)]
    if unmet_required:
        rationale = "Excluded because required criteria were not satisfied: " + ", ".join(unmet_required) + "."
        return Recommendation(
            study_id=publication.study_id,
            recommendation_class=RecommendationClass.EXCLUDED,
            match_class=MatchClass.EXCLUDED,
            score=0.0,
            rationale=rationale,
            mirage_flags=flags,
        )

    if repository is None and looks_like_metabolomics_workbench_accession(publication.repository_accession):
        rationale = (
            "Excluded because Metabolomics Workbench candidates require repository metadata with observed "
            "blood-derived sample matrix evidence."
        )
        return Recommendation(
            study_id=publication.study_id,
            recommendation_class=RecommendationClass.EXCLUDED,
            match_class=MatchClass.EXCLUDED,
            score=0.0,
            rationale=rationale,
            mirage_flags=flags,
        )

    is_mw_repository = repository is not None and (
        is_metabolomics_workbench_repository(repository.repository)
        or looks_like_metabolomics_workbench_accession(repository.accession)
    )
    if is_mw_repository:
        if not has_blood_derived_sample_matrix(repository.sample_matrix):
            rationale = (
                "Excluded because Metabolomics Workbench candidates must have a blood-derived "
                f"sample matrix; observed sample_matrix={repository.sample_matrix!r}."
            )
            return Recommendation(
                study_id=publication.study_id,
                recommendation_class=RecommendationClass.EXCLUDED,
                match_class=MatchClass.EXCLUDED,
                score=0.0,
                rationale=rationale,
                mirage_flags=flags,
            )

    preferred_terms = {
        _normalize_term(term)
        for term in (criteria.preferred_terms if criteria is not None else DEFAULT_PREFERRED_TERMS)
    }
    score = 0.40
    rationale_parts = ["Required inclusion criteria satisfied."]
    if "exercise" in preferred_terms and publication.exercise:
        score += 0.12
        rationale_parts.append("Requested exercise phenotype present.")
    if "actigraphy" in preferred_terms and publication.actigraphy:
        score += 0.12
        rationale_parts.append("Requested actigraphy phenotype present.")
    if "physical_activity" in preferred_terms and (publication.exercise or publication.actigraphy):
        score += 0.08
        rationale_parts.append("Requested physical-activity evidence present.")
    if {"exercise", "actigraphy"}.issubset(preferred_terms) and publication.exercise and publication.actigraphy:
        score += 0.04
        rationale_parts.append("Both intervention exercise and actigraphy are present.")
    if "genetics" in preferred_terms and publication.genetics:
        score += 0.10
        rationale_parts.append("Requested genetics evidence present.")
    if "cpet" in preferred_terms and publication.cpet:
        score += 0.08
        rationale_parts.append("Requested CPET/cardiorespiratory fitness evidence present.")
    if "body_composition" in preferred_terms and publication.body_composition:
        score += 0.05
        rationale_parts.append("Requested body-composition evidence present.")
    if "diet" in preferred_terms and publication.diet:
        score += 0.05
        rationale_parts.append("Requested diet evidence present.")
    if publication.repository_accession not in {"", "not_available", "not_reported"}:
        score += 0.05
        rationale_parts.append("Repository accession reported.")

    if repository is not None:
        if repository.has_metadata:
            score += 0.03
        if repository.has_codebook:
            score += 0.03
        if repository.has_data_files:
            score += 0.02
        if repository.sample_size is not None:
            score += 0.02
        if repository.assay_platform not in UNKNOWN_VALUES:
            score += 0.01
        if repository.biospecimen_timing not in UNKNOWN_VALUES:
            score += 0.01

    score = min(round(score, 3), 1.0)

    direct = publication.exercise or publication.actigraphy or publication.cpet
    if is_mirage(flags):
        rec_class = RecommendationClass.MIRAGE
        match_class = MatchClass.MIRAGE
        rationale_parts.append("Flagged as a mirage risk because usable repository assets are incomplete.")
    elif direct:
        rec_class = RecommendationClass.DIRECT_MATCH
        match_class = MatchClass.DIRECT
    elif publication.genetics or publication.body_composition or publication.diet:
        rec_class = RecommendationClass.ENRICHMENT_CANDIDATE
        match_class = MatchClass.ENRICHMENT
    else:
        rec_class = RecommendationClass.COMPLEMENTARY
        match_class = MatchClass.COMPLEMENTARY

    return Recommendation(
        study_id=publication.study_id,
        recommendation_class=rec_class,
        match_class=match_class,
        score=score,
        rationale=" ".join(rationale_parts),
        mirage_flags=flags,
    )


def build_recommendations(
    publications: list[PublicationRecord],
    repositories: dict[str, RepositoryRecord],
    criteria: InclusionCriteria | None = None,
) -> list[Recommendation]:
    recommendations = [
        score_publication(publication, repositories.get(publication.study_id), criteria)
        for publication in publications
    ]
    publication_by_id = {publication.study_id: publication for publication in publications}

    def sort_key(item: Recommendation) -> tuple[float, int, int]:
        publication = publication_by_id[item.study_id]
        modality_count = sum(
            bool(value)
            for value in [
                publication.exercise,
                publication.actigraphy,
                publication.genetics,
                publication.cpet,
                publication.body_composition,
                publication.diet,
            ]
        )
        repository = repositories.get(item.study_id)
        usable_assets = 0
        if repository is not None:
            usable_assets = sum([repository.has_metadata, repository.has_codebook, repository.has_data_files])
        return (item.score, modality_count, usable_assets)

    return sorted(recommendations, key=sort_key, reverse=True)

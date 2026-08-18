"""Typed, advisory-only packets for bounded scientific domain review.

The packet records evidence coverage and questions for a human adjudicator.  It
deliberately has no acceptance, rejection, confidence, transform, or execution
fields: review agents using this contract cannot authorize scientific actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .._compat import ConfigDict
from ..models import WorkbenchModel


DOMAIN_REVIEW_SCHEMA_VERSION = "1.0.0"
DOMAIN_REVIEW_CONTRACT_VERSION = "1.0.0"


class DomainReviewRole(str, Enum):
    """Supported bounded review roles, synchronized with paired manifests."""

    STUDY_DESIGN_POPULATION_CONTEXT_REVIEWER = (
        "study-design-population-context-reviewer"
    )
    EXERCISE_PHENOTYPE_HARMONIZATION_REVIEWER = (
        "exercise-phenotype-harmonization-reviewer"
    )
    BIOSPECIMEN_PREANALYTICS_REVIEWER = "biospecimen-preanalytics-reviewer"
    STATISTICAL_ESTIMAND_AND_SYNTHESIS_SKEPTIC = (
        "statistical-estimand-and-synthesis-skeptic"
    )


class EvidenceState(str, Enum):
    """Explicit state of evidence submitted for a review dimension."""

    REPORTED = "reported"
    DOCUMENTED_ABSENT = "documented_absent"
    NOT_REPORTED = "not_reported"
    NOT_AVAILABLE = "not_available"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class DecisionAuthority(str, Enum):
    ADVISORY_ONLY = "advisory_only"


class HumanAdjudicationStatus(str, Enum):
    REQUIRED = "required"


# Complete coverage of these dimensions is a contract-integrity check, not a
# scientific score or suitability decision.  A missing item must still be
# represented by an EvidenceItem with an explicit missing/unresolved state.
ROLE_REVIEW_DIMENSIONS: dict[str, tuple[str, ...]] = {
    DomainReviewRole.STUDY_DESIGN_POPULATION_CONTEXT_REVIEWER.value: (
        "study_design",
        "population",
        "recruitment",
        "eligibility",
        "intervention",
        "exposure",
        "arms_or_comparator",
        "participant_flow",
        "attrition",
        "analysis_set",
        "allocation_and_blinding",
        "confounding",
        "site_context",
        "calendar_context",
    ),
    DomainReviewRole.EXERCISE_PHENOTYPE_HARMONIZATION_REVIEWER.value: (
        "construct",
        "codebook_definition",
        "protocol",
        "exercise_mode",
        "device_analyzer_and_calibration",
        "endpoint",
        "maximality_criteria",
        "unit",
        "normalization_basis",
        "derivation_rules",
        "assessment_timing",
        "actigraphy_processing",
        "repeated_trial_handling",
        "training_status",
    ),
    DomainReviewRole.BIOSPECIMEN_PREANALYTICS_REVIEWER.value: (
        "specimen_derivative",
        "collection_timing_relative_to_exercise",
        "food_context",
        "circadian_context",
        "posture",
        "tube_or_additive",
        "processing_delay",
        "processing_temperature",
        "centrifugation",
        "aliquoting",
        "storage",
        "freeze_thaw",
        "shipping",
        "sop",
        "deviations",
    ),
    DomainReviewRole.STATISTICAL_ESTIMAND_AND_SYNTHESIS_SKEPTIC.value: (
        "estimand",
        "population",
        "intervention_or_exposure",
        "comparator",
        "outcome",
        "timepoint",
        "effect_scale",
        "effect_orientation",
        "model",
        "covariates",
        "repeated_measures_or_clustering",
        "uncertainty",
        "sample_counts",
        "missing_data_handling",
        "multiplicity",
        "dependencies",
        "upstream_mapping_status",
        "upstream_assay_status",
        "heterogeneity_plan",
        "sensitivity_plan",
    ),
}


class _DomainReviewModel(WorkbenchModel):
    """Base model that rejects undeclared fields in every runtime."""

    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    def __init__(self, **data: Any) -> None:
        allowed_fields: set[str] = set()
        for cls in self.__class__.mro():
            if cls is WorkbenchModel:
                break
            allowed_fields.update(
                name
                for name in getattr(cls, "__annotations__", {})
                if name != "model_config"
            )
        unsupported = sorted(set(data) - allowed_fields)
        if unsupported:
            raise ValueError(
                "unsupported domain-review fields: " + ", ".join(unsupported)
            )
        super().__init__(**data)


class ReferencedEntities(_DomainReviewModel):
    """Identifiers in existing workbench artifacts that define packet scope."""

    study_ids: list[str]
    dataset_ids: list[str]
    variable_ids: list[str]
    effect_ids: list[str]


class ProvenanceRecord(_DomainReviewModel):
    """Resolvable source information for submitted domain evidence."""

    provenance_id: str
    source_artifact: str
    record_locator: str
    source_sha256: str
    extraction_method: str


class EvidenceItem(_DomainReviewModel):
    """Evidence coverage for one role-specific review dimension."""

    evidence_id: str
    dimension: str
    state: EvidenceState
    detail: str
    provenance_ids: list[str]


class ReviewLimitation(_DomainReviewModel):
    limitation_id: str
    description: str
    evidence_ids: list[str]


class ReviewBlocker(_DomainReviewModel):
    blocker_id: str
    description: str
    evidence_ids: list[str]


class HumanReviewQuestion(_DomainReviewModel):
    question_id: str
    question: str
    evidence_ids: list[str]


class DomainReviewPacket(_DomainReviewModel):
    """A deterministic evidence ledger that always requires human adjudication."""

    schema_version: str
    contract_version: str
    packet_id: str
    scope_version: str
    role: DomainReviewRole
    research_question: str
    intended_use: str
    referenced_entities: ReferencedEntities
    provenance: list[ProvenanceRecord]
    evidence: list[EvidenceItem]
    limitations: list[ReviewLimitation]
    blockers: list[ReviewBlocker]
    human_review_questions: list[HumanReviewQuestion]
    decision_authority: DecisionAuthority
    human_adjudication_status: HumanAdjudicationStatus
    executable_actions: list[str]
    packet_digest: str

    @classmethod
    def model_validate(cls, value: Any) -> "DomainReviewPacket":
        """Construct nested models in both Pydantic and dependency-free runs."""

        if isinstance(value, cls):
            return value
        data = dict(value)
        entities = data.get("referenced_entities")
        if not isinstance(entities, ReferencedEntities):
            data["referenced_entities"] = ReferencedEntities.model_validate(entities)
        data["provenance"] = [
            item
            if isinstance(item, ProvenanceRecord)
            else ProvenanceRecord.model_validate(item)
            for item in data.get("provenance", [])
        ]
        data["evidence"] = [
            item if isinstance(item, EvidenceItem) else EvidenceItem.model_validate(item)
            for item in data.get("evidence", [])
        ]
        data["limitations"] = [
            item
            if isinstance(item, ReviewLimitation)
            else ReviewLimitation.model_validate(item)
            for item in data.get("limitations", [])
        ]
        data["blockers"] = [
            item if isinstance(item, ReviewBlocker) else ReviewBlocker.model_validate(item)
            for item in data.get("blockers", [])
        ]
        data["human_review_questions"] = [
            item
            if isinstance(item, HumanReviewQuestion)
            else HumanReviewQuestion.model_validate(item)
            for item in data.get("human_review_questions", [])
        ]
        return cls(**data)

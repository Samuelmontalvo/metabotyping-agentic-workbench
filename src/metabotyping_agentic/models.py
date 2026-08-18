"""Pydantic-style models for study discovery, harmonization, and evaluation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from ._compat import BaseModel, ConfigDict, Field


class Modality(str, Enum):
    METABOLOMICS = "metabolomics"
    EXERCISE = "exercise"
    ACTIGRAPHY = "actigraphy"
    PHYSICAL_ACTIVITY = "physical_activity"
    GENETICS = "genetics"
    CPET = "cpet"
    BODY_COMPOSITION = "body_composition"
    DIET = "diet"
    DEMOGRAPHICS = "demographics"
    CLINICAL = "clinical"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class RecommendationClass(str, Enum):
    DIRECT_MATCH = "direct_match"
    COMPLEMENTARY = "complementary"
    ENRICHMENT_CANDIDATE = "enrichment_candidate"
    MIRAGE = "mirage"
    EXCLUDED = "excluded"


class ReplicationFeasibilityTier(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NOT_FEASIBLE = "not_feasible"


class DataAvailability(str, Enum):
    PUBLIC = "public"
    RESTRICTED_METADATA_ONLY = "restricted_metadata_only"
    NOT_AVAILABLE = "not_available"
    UNKNOWN = "unknown"


class MatchClass(str, Enum):
    DIRECT = "direct"
    COMPLEMENTARY = "complementary"
    ENRICHMENT = "enrichment"
    MIRAGE = "mirage"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


class WorkbenchModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class InclusionCriteria(WorkbenchModel):
    query: str
    required_terms: list[str] = Field(default_factory=lambda: ["human", "metabolomics"])
    preferred_terms: list[str] = Field(default_factory=list)
    complementary_terms: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=lambda: ["animal-only", "cell-only", "no metabolomics"])
    notes: list[str] = Field(default_factory=list)


class PublicationRecord(WorkbenchModel):
    study_id: str
    title: str
    doi: str = "not_reported"
    pmid: str = "not_reported"
    human: bool = False
    exercise: bool = False
    actigraphy: bool = False
    metabolomics: bool = False
    genetics: bool = False
    cpet: bool = False
    body_composition: bool = False
    diet: bool = False
    repository_accession: str = "not_available"
    notes: str = ""


class RepositoryRecord(WorkbenchModel):
    study_id: str
    repository: str = "unknown"
    accession: str = "not_available"
    public_status: DataAvailability = DataAvailability.UNKNOWN
    has_metadata: bool = False
    has_codebook: bool = False
    has_data_files: bool = False
    assay_platform: str = "unknown"
    sample_matrix: str = "unknown"
    biospecimen_timing: str = "unknown"
    sample_size: int | None = None
    modalities: list[Modality] = Field(default_factory=list)
    documented_absent_modalities: list[Modality] = Field(default_factory=list)


class StudyCard(WorkbenchModel):
    study_id: str
    title: str
    human: bool
    modalities: list[Modality]
    repository_accession: str
    match_class: MatchClass
    repository_accessions: list[str] = Field(default_factory=list)
    mirage_flags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class DatasetCard(WorkbenchModel):
    study_id: str
    repository: str
    accession: str
    data_availability: DataAvailability
    has_metadata: bool
    has_codebook: bool
    has_data_files: bool
    assay_platform: str
    sample_matrix: str
    biospecimen_timing: str
    sample_size: int | None
    modalities: list[Modality]
    documented_absent_modalities: list[Modality] = Field(default_factory=list)
    mirage_flags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class VariableCard(WorkbenchModel):
    study_id: str
    source_variable: str
    label: str
    unit: str = "unknown"
    timing: str = "unknown"
    modality: Modality = Modality.UNKNOWN
    description: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)


class VariableMapping(WorkbenchModel):
    source_study: str
    source_variable: str
    source_label: str
    source_unit: str
    source_timing: str
    source_modality: str
    proposed_common_variable: str
    proposed_common_unit: str
    transform: str
    confidence: float
    evidence: str
    review_status: ReviewStatus


class HarmonizationDecision(WorkbenchModel):
    source_study: str
    source_variable: str
    proposed_common_variable: str
    review_status: ReviewStatus
    decision_rationale: str
    approved_transform: str = "not_available"
    required_human_decision: str = "not_available"


class QualityScore(WorkbenchModel):
    study_id: str
    study_design_rigor: float
    metadata_completeness: float
    metabolomics_quality: float
    genetics_quality: float
    activity_quality: float
    cpet_quality: float
    body_composition_quality: float
    diet_quality: float
    temporal_alignment: float
    harmonization_feasibility: float
    overall_score: float
    weights: dict[str, float] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)


class MoTrPACAlignment(WorkbenchModel):
    study_id: str
    score: float
    tier: ReplicationFeasibilityTier
    met_criteria: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    rationale: str = ""


class Recommendation(WorkbenchModel):
    study_id: str
    recommendation_class: RecommendationClass
    match_class: MatchClass
    score: float
    rationale: str
    mirage_flags: list[str] = Field(default_factory=list)


class BenchmarkResult(WorkbenchModel):
    metric_name: str
    value: float | None
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCaseResult(WorkbenchModel):
    """One mapping or quality-score case in the benchmark union."""

    case_type: str
    source_study: str
    source_variable: str | None = None
    common_variable: str | None = None
    outcome: str
    reason_codes: list[str] = Field(default_factory=list)
    gold: dict[str, Any] | None = None
    predicted: dict[str, Any] | None = None
    absolute_difference: float | None = None
    within_tolerance: bool | None = None


class BenchmarkArtifactDigest(WorkbenchModel):
    """Portable provenance for one benchmark input or output artifact."""

    role: str
    path: str
    state: str
    row_count: int | None = None
    columns: list[str] = Field(default_factory=list)
    sha256: str | None = None


class BenchmarkManifest(WorkbenchModel):
    """Deterministic benchmark provenance without machine-specific metadata."""

    manifest_version: str
    rule_set_version: str
    benchmark_rule_set_version: str
    software_version: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    metric_names: list[str] = Field(default_factory=list)
    case_counts: dict[str, int] = Field(default_factory=dict)
    inputs: list[BenchmarkArtifactDigest] = Field(default_factory=list)
    outputs: list[BenchmarkArtifactDigest] = Field(default_factory=list)
    human_readable_output: str

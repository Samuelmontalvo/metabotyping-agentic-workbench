"""Typed artifacts for assay-aware metabolite harmonization.

The models deliberately separate chemical identity, analytical assay metadata,
quantitative representation, quality control, missingness, and provenance.  A
reported metabolite name is descriptive metadata only; it is never a chemical
identity key.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from .._compat import Field
from ..models import WorkbenchModel


class IdentificationLevel(str, Enum):
    """Metabolomics Standards Initiative-compatible identification levels."""

    MSI_LEVEL_1 = "msi_level_1"
    MSI_LEVEL_2 = "msi_level_2"
    MSI_LEVEL_3 = "msi_level_3"
    MSI_LEVEL_4 = "msi_level_4"


class IdentityResolution(str, Enum):
    EXACT_STRUCTURE = "exact_structure"
    STEREOCHEMISTRY_UNRESOLVED = "stereochemistry_unresolved"
    POSITIONAL_ISOMER_UNRESOLVED = "positional_isomer_unresolved"
    LIPID_SPECIES = "lipid_species"
    CHEMICAL_CLASS = "chemical_class"
    FEATURE_ONLY = "feature_only"


class IdentityEvidenceType(str, Enum):
    AUTHENTIC_STANDARD = "authentic_standard"
    ORTHOGONAL_STANDARD = "orthogonal_standard"
    MSMS_LIBRARY = "msms_library"
    RETENTION_INDEX = "retention_index"
    ACCURATE_MASS = "accurate_mass"
    VENDOR_PANEL = "vendor_panel"
    DATABASE_ANNOTATION = "database_annotation"
    MANUAL_CURATION = "manual_curation"


class PlatformFamily(str, Enum):
    LC_MS_TARGETED = "lc_ms_targeted"
    LC_MS_UNTARGETED = "lc_ms_untargeted"
    GC_MS = "gc_ms"
    NMR = "nmr"
    DIRECT_INFUSION_MS = "direct_infusion_ms"
    COMMERCIAL_KIT = "commercial_kit"
    OTHER = "other"


class QuantitationType(str, Enum):
    ABSOLUTE_CONCENTRATION = "absolute_concentration"
    SEMI_QUANTITATIVE = "semi_quantitative"
    NORMALIZED_RELATIVE_ABUNDANCE = "normalized_relative_abundance"
    FEATURE_INTENSITY = "feature_intensity"
    INTERNAL_STANDARD_RATIO = "internal_standard_ratio"


class QuantitativeScale(str, Enum):
    LINEAR = "linear"
    LOG2 = "log2"
    LOG10 = "log10"
    NATURAL_LOG = "natural_log"
    Z_SCORE = "z_score"
    RANK = "rank"
    UNKNOWN = "unknown"


class CensoringPolicy(str, Enum):
    EXPLICIT_LEFT_CENSORING = "explicit_left_censoring"
    SET_MISSING = "set_missing"
    HALF_LIMIT_IMPUTED = "half_limit_imputed"
    ZERO_IMPUTED = "zero_imputed"
    MINIMUM_VALUE_IMPUTED = "minimum_value_imputed"
    NONE_EXPECTED = "none_expected"
    UNKNOWN = "unknown"


class BatchCorrectionScope(str, Enum):
    WITHIN_STUDY = "within_study"
    CROSS_STUDY = "cross_study"
    NONE = "none"
    UNKNOWN = "unknown"


class HarmonizationStatus(str, Enum):
    ACCEPTED = "accepted"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    NON_COMBINABLE = "non_combinable"


class PermittedAnalysis(str, Enum):
    POOLED_INDIVIDUAL_VALUES = "pooled_individual_values"
    STUDY_SPECIFIC_EFFECTS_META_ANALYSIS = "study_specific_effects_meta_analysis"
    NONE_PENDING_REVIEW = "none_pending_review"
    NONE = "none"


class StandardIdentifier(WorkbenchModel):
    scheme: str
    value: str
    resolution: IdentityResolution
    provenance_ref: str


class IdentityEvidence(WorkbenchModel):
    evidence_type: IdentityEvidenceType
    description: str
    provenance_ref: str


class MetaboliteIdentity(WorkbenchModel):
    reported_name: str
    standard_identifiers: list[StandardIdentifier] = Field(default_factory=list)
    identification_level: IdentificationLevel
    resolution: IdentityResolution
    evidence: list[IdentityEvidence] = Field(default_factory=list)
    formula: str = "not_reported"
    adduct: str = "not_applicable"
    ion_mode: str = "not_applicable"
    mz: float | None = None
    retention_time_seconds: float | None = None


class BatchMetadata(WorkbenchModel):
    batch_count: int
    batch_id_variable: str
    run_order_variable: str
    run_order_randomized: bool | None
    pooled_qc_present: bool
    pooled_qc_frequency: str
    reference_material: str
    blank_types: list[str] = Field(default_factory=list)
    blank_acceptance_documented: bool
    drift_evaluated: bool
    drift_correction_method: str
    batch_correction_method: str
    correction_scope: BatchCorrectionScope
    qc_cv_percent: float | None = None


class AssayMetadata(WorkbenchModel):
    assay_id: str
    method_id: str
    assay_version: str
    platform_family: PlatformFamily
    instrument_vendor: str
    instrument_model: str
    chromatography: str
    acquisition_mode: str
    laboratory: str
    sample_matrix: str
    extraction_protocol_id: str
    validated_bridge_ids: list[str] = Field(default_factory=list)
    batch: BatchMetadata


class LimitMetadata(WorkbenchModel):
    lod: float | None = None
    loq: float | None = None
    unit: str
    censoring_policy: CensoringPolicy
    below_limit_code: str
    raw_censoring_flags_available: bool


class MissingnessMetadata(WorkbenchModel):
    feature_missing_fraction: float
    encoded_missing_values: list[str] = Field(default_factory=list)
    missing_reason_variable: str
    imputation_method: str
    unimputed_values_available: bool
    biological_zero_distinguished: bool


class QuantitativeMetadata(WorkbenchModel):
    quantitation_type: QuantitationType
    unit: str
    scale: QuantitativeScale
    calibration_model: str
    calibration_traceability: str
    internal_standard: str
    normalization_method: str
    molecular_weight_g_mol: float | None = None
    limits: LimitMetadata
    missingness: MissingnessMetadata


class RecordProvenance(WorkbenchModel):
    source_artifact: str
    source_record_locator: str
    source_sha256: str
    extraction_method: str
    evidence_locators: dict[str, str] = Field(default_factory=dict)


class MetaboliteAssayRecord(WorkbenchModel):
    study_id: str
    feature_id: str
    identity: MetaboliteIdentity
    assay: AssayMetadata
    quantitative: QuantitativeMetadata
    provenance: RecordProvenance

    @classmethod
    def model_validate(cls, value: Any) -> "MetaboliteAssayRecord":
        """Validate nested input with Pydantic or the dependency-free fallback.

        The repository intentionally supports offline smoke runs without
        Pydantic.  The small compatibility model cannot resolve postponed nested
        annotations, so construction is explicit here.
        """

        if isinstance(value, cls):
            return value
        data = dict(value)
        identity_data = dict(data["identity"])
        identity_data["standard_identifiers"] = [
            StandardIdentifier.model_validate(item)
            for item in identity_data.get("standard_identifiers", [])
        ]
        identity_data["evidence"] = [
            IdentityEvidence.model_validate(item) for item in identity_data.get("evidence", [])
        ]
        data["identity"] = MetaboliteIdentity(**identity_data)

        assay_data = dict(data["assay"])
        assay_data["batch"] = BatchMetadata.model_validate(assay_data["batch"])
        data["assay"] = AssayMetadata(**assay_data)

        quantitative_data = dict(data["quantitative"])
        quantitative_data["limits"] = LimitMetadata.model_validate(quantitative_data["limits"])
        quantitative_data["missingness"] = MissingnessMetadata.model_validate(
            quantitative_data["missingness"]
        )
        data["quantitative"] = QuantitativeMetadata(**quantitative_data)
        data["provenance"] = RecordProvenance.model_validate(data["provenance"])
        return cls(**data)


class DecisionEvidence(WorkbenchModel):
    code: str
    conclusion: str
    detail: str
    provenance_refs: list[str] = Field(default_factory=list)


class HarmonizationTransform(WorkbenchModel):
    order: int
    registry_key: str
    applies_to: list[str]
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str


class HeterogeneityPlan(WorkbenchModel):
    analysis_level: str
    stratify_by: list[str] = Field(default_factory=list)
    required_diagnostics: list[str] = Field(default_factory=list)
    interpretation_rule: str


class DecisionProvenance(WorkbenchModel):
    source_feature_ids: list[str]
    source_artifacts: list[str]
    source_sha256: list[str]
    rule_set_version: str
    pair_input_digest: str


class AssayHarmonizationDecision(WorkbenchModel):
    left_feature_id: str
    right_feature_id: str
    status: HarmonizationStatus
    identity_status: HarmonizationStatus
    quantitative_status: HarmonizationStatus
    qa_qc_status: HarmonizationStatus
    confidence: float
    raw_values_combinable: bool
    permitted_analysis: PermittedAnalysis
    canonical_identity: str
    common_unit: str
    evidence: list[DecisionEvidence] = Field(default_factory=list)
    transforms: list[HarmonizationTransform] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    review_questions: list[str] = Field(default_factory=list)
    heterogeneity_plan: HeterogeneityPlan
    provenance: DecisionProvenance


class AssayHarmonizationPlan(WorkbenchModel):
    schema_version: str
    rule_set_version: str
    input_digest: str
    policy: dict[str, Any]
    summary: dict[str, int]
    decisions: list[AssayHarmonizationDecision]
    approved_transform_registry: list[str]
    validation_checks: list[str]
    failure_conditions: list[str]

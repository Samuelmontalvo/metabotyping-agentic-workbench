"""Deterministic, review-gated metabolite assay harmonization.

This module plans harmonization; it does not silently rewrite measurements.
Automatic value pooling is intentionally narrow: both records must represent an
MSI level 1 exact chemical identity, absolute concentrations on compatible
linear units, compatible matrices/methods, and sufficiently documented QA/QC.
Other quantitative representations remain study/platform specific and may only
enter an effect-estimate meta-analysis when identity is adequate.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..io import read_json, to_plain, write_json
from .assay_models import (
    AssayHarmonizationDecision,
    AssayHarmonizationPlan,
    DecisionEvidence,
    DecisionProvenance,
    HarmonizationStatus,
    HarmonizationTransform,
    HeterogeneityPlan,
    MetaboliteAssayRecord,
    PermittedAnalysis,
)

RULE_SET_VERSION = "metabolite-assay-harmonization-1.0.0"
SCHEMA_VERSION = "1.0.0"

APPROVED_TRANSFORM_REGISTRY = {
    "convert_compatible_concentration_unit",
    "use_unimputed_source_values",
    "preserve_missing_reason_codes",
    "censor_below_common_loq",
    "within_study_batch_processing_only",
    "apply_validated_method_bridge",
}

DEFAULT_POLICY: dict[str, Any] = {
    "maximum_missing_fraction": 0.20,
    "hard_missing_fraction_exclusion": 0.50,
    "maximum_targeted_qc_cv_percent": 20.0,
    "maximum_other_qc_cv_percent": 30.0,
    "require_msi_level_1_for_value_pooling": True,
    "require_exact_structure_for_value_pooling": True,
    "require_linear_absolute_concentrations_for_value_pooling": True,
    "allow_cross_platform_pooling_only_with_validated_bridge": True,
    "never_jointly_batch_correct_across_studies": True,
    "below_limit_rule": "preserve censoring and use the highest compatible LOQ",
    "relative_data_rule": "study-specific effects only; never pool raw values",
}

# Unit factors convert to a dimensional base (mol/L or g/L).  Direct conversion
# is allowed only within a family.  Molar-to-mass conversion remains review-only
# even when a molecular weight is supplied because salt/hydrate form matters.
UNIT_REGISTRY: dict[str, tuple[str, float, str]] = {
    "mol/l": ("molar_concentration", 1.0, "umol/L"),
    "mmol/l": ("molar_concentration", 1e-3, "umol/L"),
    "umol/l": ("molar_concentration", 1e-6, "umol/L"),
    "nmol/l": ("molar_concentration", 1e-9, "umol/L"),
    "pmol/l": ("molar_concentration", 1e-12, "umol/L"),
    "g/l": ("mass_concentration", 1.0, "mg/L"),
    "mg/l": ("mass_concentration", 1e-3, "mg/L"),
    "ug/l": ("mass_concentration", 1e-6, "mg/L"),
    "ng/l": ("mass_concentration", 1e-9, "mg/L"),
    "mg/dl": ("mass_concentration", 1e-2, "mg/L"),
    "ug/ml": ("mass_concentration", 1e-3, "mg/L"),
    "ng/ml": ("mass_concentration", 1e-6, "mg/L"),
}

_MISSING_TEXT = {"", "unknown", "not_reported", "not_available", "none"}
_HARMFUL_IMPUTATION = {
    "half_lod",
    "half_loq",
    "half_limit",
    "zero",
    "minimum",
    "minimum_value",
    "knn",
    "random_forest",
}
_ACCEPTED_STATUS = str(HarmonizationStatus.ACCEPTED.value)
_REVIEW_STATUS = str(HarmonizationStatus.REQUIRES_HUMAN_REVIEW.value)
_NONCOMBINABLE_STATUS = str(HarmonizationStatus.NON_COMBINABLE.value)


@dataclass
class _Assessment:
    status: str
    confidence: float
    evidence: list[DecisionEvidence] = field(default_factory=list)
    transforms: list[HarmonizationTransform] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    review_questions: list[str] = field(default_factory=list)
    canonical_identity: str = "not_established"
    common_unit: str = "not_applicable"


def _text(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    return _text(value).lower() in _MISSING_TEXT


def _normalized_unit(value: str) -> str:
    normalized = _text(value).lower().replace("μ", "u").replace("µ", "u")
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("per", "/")
    normalized = normalized.replace("litre", "l").replace("liter", "l")
    return normalized


def _normalized_identifier(scheme: str, value: str) -> tuple[str, str]:
    normalized_scheme = re.sub(r"[^a-z0-9]+", "_", _text(scheme).lower()).strip("_")
    aliases = {
        "inchi_key": "inchikey",
        "inchi_key_27": "inchikey",
        "pubchem": "pubchem_cid",
        "chebi_id": "chebi",
        "hmdb_id": "hmdb",
        "lipid_maps": "lipidmaps",
    }
    normalized_scheme = aliases.get(normalized_scheme, normalized_scheme)
    normalized_value = re.sub(r"\s+", "", _text(value))
    if normalized_scheme in {"inchikey", "hmdb", "chebi", "lipidmaps", "refmet"}:
        normalized_value = normalized_value.upper()
    if normalized_scheme == "chebi" and normalized_value.isdigit():
        normalized_value = f"CHEBI:{normalized_value}"
    return normalized_scheme, normalized_value


def _digest(value: Any) -> str:
    payload = json.dumps(to_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean_number(value: float) -> float:
    """Remove binary floating-point noise from serialized conversion factors."""

    return float(f"{value:.12g}")


def _evidence(
    code: str,
    conclusion: str,
    detail: str,
    *refs: str,
) -> DecisionEvidence:
    return DecisionEvidence(
        code=code,
        conclusion=conclusion,
        detail=detail,
        provenance_refs=sorted({ref for ref in refs if ref}),
    )


def _identifier_index(record: MetaboliteAssayRecord) -> dict[str, dict[str, list[Any]]]:
    index: dict[str, dict[str, list[Any]]] = {}
    for identifier in record.identity.standard_identifiers:
        scheme, value = _normalized_identifier(identifier.scheme, identifier.value)
        index.setdefault(scheme, {}).setdefault(value, []).append(identifier)
    return index


def _identity_references(record: MetaboliteAssayRecord) -> set[str]:
    refs = {item.provenance_ref for item in record.identity.standard_identifiers}
    refs.update(item.provenance_ref for item in record.identity.evidence)
    return refs


def _has_authentic_standard(record: MetaboliteAssayRecord) -> bool:
    return any(
        _text(item.evidence_type) in {"authentic_standard", "orthogonal_standard"}
        for item in record.identity.evidence
    )


def _assess_identity(
    left: MetaboliteAssayRecord,
    right: MetaboliteAssayRecord,
) -> _Assessment:
    evidence: list[DecisionEvidence] = []
    blockers: list[str] = []
    review_questions: list[str] = []

    if (
        left.identity.reported_name.strip().casefold()
        == right.identity.reported_name.strip().casefold()
    ):
        evidence.append(
            _evidence(
                "reported_name_not_identity_evidence",
                "neutral",
                "Reported names match, but names are not used as chemical identity evidence.",
            )
        )

    for record in (left, right):
        declared = set(record.provenance.evidence_locators)
        missing_refs = sorted(_identity_references(record) - declared)
        if missing_refs:
            blockers.append(f"{record.feature_id}:unresolved_identity_provenance")
            review_questions.append(
                f"Resolve provenance references for {record.feature_id}: {', '.join(missing_refs)}."
            )
            evidence.append(
                _evidence(
                    "identity_provenance_unresolved",
                    "review",
                    f"{record.feature_id} has identity evidence without a resolvable "
                    "source locator.",
                    *missing_refs,
                )
            )

    left_index = _identifier_index(left)
    right_index = _identifier_index(right)
    left_inchikeys = set(left_index.get("inchikey", {}))
    right_inchikeys = set(right_index.get("inchikey", {}))

    if left_inchikeys and right_inchikeys and not (left_inchikeys & right_inchikeys):
        left_connectivity = {value.split("-")[0] for value in left_inchikeys}
        right_connectivity = {value.split("-")[0] for value in right_inchikeys}
        if left_connectivity & right_connectivity:
            detail = (
                "InChIKeys share a connectivity block but differ in remaining layers; "
                "stereoisomer/protonation ambiguity cannot be collapsed."
            )
            code = "inchikey_layer_conflict"
        else:
            detail = "Exact InChIKeys conflict, indicating different chemical structures."
            code = "inchikey_structure_conflict"
        return _Assessment(
            status=_NONCOMBINABLE_STATUS,
            confidence=0.05,
            evidence=evidence + [_evidence(code, "incompatible", detail)],
            blockers=blockers + [code],
            review_questions=review_questions,
        )

    shared: list[tuple[str, str, Any, Any]] = []
    for scheme in sorted(set(left_index) & set(right_index)):
        for value in sorted(set(left_index[scheme]) & set(right_index[scheme])):
            for left_identifier in left_index[scheme][value]:
                for right_identifier in right_index[scheme][value]:
                    shared.append((scheme, value, left_identifier, right_identifier))

    if not shared:
        evidence.append(
            _evidence(
                "no_shared_standard_identifier",
                "review",
                "No shared standard chemical identifier was found; a name match cannot substitute.",
            )
        )
        return _Assessment(
            status=_REVIEW_STATUS,
            confidence=0.20,
            evidence=evidence,
            blockers=blockers + ["identity_not_machine_resolved"],
            review_questions=review_questions
            + ["Curate a standard identifier and document isomer/stereochemistry resolution."],
        )

    resolution_rank = {
        "exact_structure": 5,
        "stereochemistry_unresolved": 4,
        "positional_isomer_unresolved": 3,
        "lipid_species": 2,
        "chemical_class": 1,
        "feature_only": 0,
    }
    scheme_rank = {
        "inchikey": 7,
        "chebi": 6,
        "hmdb": 5,
        "pubchem_cid": 4,
        "lipidmaps": 3,
        "kegg": 2,
        "refmet": 1,
    }
    strongest = max(
        shared,
        key=lambda item: (
            min(
                resolution_rank.get(_text(item[2].resolution), 0),
                resolution_rank.get(_text(item[3].resolution), 0),
            ),
            scheme_rank.get(item[0], 0),
        ),
    )
    scheme, value, left_identifier, right_identifier = strongest
    canonical_identity = f"{scheme}:{value}"
    refs = (left_identifier.provenance_ref, right_identifier.provenance_ref)
    exact_resolution = all(
        _text(value) == "exact_structure"
        for value in (
            left_identifier.resolution,
            right_identifier.resolution,
            left.identity.resolution,
            right.identity.resolution,
        )
    )
    msi_level_1 = all(
        _text(record.identity.identification_level) == "msi_level_1"
        for record in (left, right)
    )
    authentic_standard = all(_has_authentic_standard(record) for record in (left, right))

    evidence.append(
        _evidence(
            "shared_standard_identifier",
            "compatible" if exact_resolution else "review",
            f"Both records declare {canonical_identity} at "
            f"{'exact' if exact_resolution else 'incomplete'} structural resolution.",
            *refs,
        )
    )

    left_adduct = _text(left.identity.adduct)
    right_adduct = _text(right.identity.adduct)
    if left_adduct != right_adduct:
        absolute = all(
            _text(record.quantitative.quantitation_type) == "absolute_concentration"
            for record in (left, right)
        )
        evidence.append(
            _evidence(
                "analytical_adducts_differ",
                "compatible" if absolute and msi_level_1 else "review",
                (
                    f"Analytical ions differ ({left_adduct} versus {right_adduct}). "
                    + (
                        "This does not redefine an MSI level 1 calibrated neutral analyte."
                        if absolute and msi_level_1
                        else "Feature intensities from different ions are not interchangeable."
                    )
                ),
            )
        )

    # Conflicts in another exact identifier system override a shared accession.
    conflicts: list[str] = []
    for common_scheme in sorted(set(left_index) & set(right_index)):
        left_values = set(left_index[common_scheme])
        right_values = set(right_index[common_scheme])
        if left_values and right_values and not (left_values & right_values):
            conflicts.append(common_scheme)
    if conflicts:
        evidence.append(
            _evidence(
                "cross_identifier_conflict",
                "review",
                "Identifier systems disagree across records: " + ", ".join(conflicts) + ".",
            )
        )
        blockers.append("cross_identifier_conflict")
        review_questions.append("Resolve conflicting identifier accessions before harmonization.")

    if not exact_resolution:
        ambiguity = sorted(
            {
                _text(left.identity.resolution),
                _text(right.identity.resolution),
                _text(left_identifier.resolution),
                _text(right_identifier.resolution),
            }
        )
        evidence.append(
            _evidence(
                "isomer_resolution_incomplete",
                "review",
                "Identity resolution is insufficient for pooling: " + ", ".join(ambiguity) + ".",
                *refs,
            )
        )
        blockers.append("isomer_or_stereochemistry_unresolved")
        review_questions.append("Confirm exact isomer/stereochemistry or retain separate analytes.")

    if not msi_level_1 or not authentic_standard:
        evidence.append(
            _evidence(
                "msi_level_gate_not_met",
                "review",
                "Automatic identity acceptance requires MSI level 1 with linked authentic or "
                "orthogonal standard evidence for both records.",
            )
        )
        blockers.append("msi_level_1_evidence_required")
        review_questions.append("Confirm MSI level 1 identification evidence for both assays.")

    if blockers:
        return _Assessment(
            status=_REVIEW_STATUS,
            confidence=0.72 if exact_resolution else 0.55,
            evidence=evidence,
            blockers=sorted(set(blockers)),
            review_questions=sorted(set(review_questions)),
            canonical_identity=canonical_identity,
        )

    return _Assessment(
        status=_ACCEPTED_STATUS,
        confidence=0.98,
        evidence=evidence
        + [
            _evidence(
                "msi_level_1_exact_identity",
                "compatible",
                "Exact identity passed the MSI level 1 evidence gate.",
                *refs,
            )
        ],
        canonical_identity=canonical_identity,
    )


def _qc_threshold(record: MetaboliteAssayRecord, policy: dict[str, Any]) -> float:
    if _text(record.assay.platform_family) == "lc_ms_targeted":
        return float(policy["maximum_targeted_qc_cv_percent"])
    return float(policy["maximum_other_qc_cv_percent"])


def _assess_qa_qc(
    left: MetaboliteAssayRecord,
    right: MetaboliteAssayRecord,
    policy: dict[str, Any],
) -> _Assessment:
    evidence: list[DecisionEvidence] = []
    transforms: list[HarmonizationTransform] = []
    blockers: list[str] = []
    review_questions: list[str] = []
    hard_failure = False

    for record in (left, right):
        batch = record.assay.batch
        prefix = record.feature_id
        threshold = _qc_threshold(record, policy)

        if batch.qc_cv_percent is None:
            blockers.append(f"{prefix}:qc_precision_not_reported")
            review_questions.append(f"Document feature-level pooled-QC CV for {prefix}.")
        elif float(batch.qc_cv_percent) > threshold:
            hard_failure = True
            blockers.append(f"{prefix}:qc_cv_exceeds_threshold")
            evidence.append(
                _evidence(
                    "qc_cv_exceeds_threshold",
                    "incompatible",
                    f"{prefix} QC CV is {batch.qc_cv_percent}% (threshold {threshold}%).",
                )
            )
        else:
            evidence.append(
                _evidence(
                    "qc_precision_acceptable",
                    "compatible",
                    f"{prefix} QC CV is {batch.qc_cv_percent}% (threshold {threshold}%).",
                )
            )

        if _is_missing(batch.run_order_variable) or batch.run_order_randomized is None:
            blockers.append(f"{prefix}:run_order_not_documented")
        if not bool(batch.pooled_qc_present) or _is_missing(batch.pooled_qc_frequency):
            blockers.append(f"{prefix}:pooled_qc_schedule_missing")
        if not bool(batch.drift_evaluated):
            blockers.append(f"{prefix}:analytical_drift_not_evaluated")
        elif _is_missing(batch.drift_correction_method):
            blockers.append(f"{prefix}:drift_evaluation_method_missing")

        if _text(batch.correction_scope) == "cross_study":
            hard_failure = True
            blockers.append(f"{prefix}:cross_study_batch_correction")
            evidence.append(
                _evidence(
                    "cross_study_batch_correction_prohibited",
                    "incompatible",
                    "Joint cross-study batch correction can remove true "
                    "study/platform effects.",
                )
            )

        if int(batch.batch_count) > 1:
            if _is_missing(batch.batch_id_variable):
                blockers.append(f"{prefix}:batch_identifier_missing")
            if _text(batch.correction_scope) != "within_study":
                blockers.append(f"{prefix}:within_study_batch_processing_required")
            else:
                transforms.append(
                    HarmonizationTransform(
                        order=0,
                        registry_key="within_study_batch_processing_only",
                        applies_to=[prefix],
                        parameters={
                            "batch_variable": batch.batch_id_variable,
                            "run_order_variable": batch.run_order_variable,
                            "drift_method": batch.drift_correction_method,
                            "batch_method": batch.batch_correction_method,
                        },
                        rationale=(
                            "Correct analytical drift/batch within each study before combination."
                        ),
                    )
                )

        if not batch.blank_types or not bool(batch.blank_acceptance_documented):
            blockers.append(f"{prefix}:blank_qc_not_documented")
        if _is_missing(batch.reference_material):
            blockers.append(f"{prefix}:reference_material_not_documented")

        if _text(record.assay.platform_family) in {
            "lc_ms_targeted",
            "lc_ms_untargeted",
            "gc_ms",
            "direct_infusion_ms",
            "commercial_kit",
        } and _is_missing(record.quantitative.internal_standard):
            blockers.append(f"{prefix}:internal_standard_not_documented")

    if hard_failure:
        status = _NONCOMBINABLE_STATUS
        confidence = 0.20
    elif blockers:
        status = _REVIEW_STATUS
        confidence = 0.65
        evidence.append(
            _evidence(
                "mqacc_qaqc_metadata_incomplete",
                "review",
                "One or more mQACC-style QA/QC fields are absent or inadequate.",
            )
        )
        review_questions.append(
            "Resolve batch/run-order, pooled QC, drift, blanks, internal-standard, and "
            "reference-material documentation gaps."
        )
    else:
        status = _ACCEPTED_STATUS
        confidence = 0.95
        evidence.append(
            _evidence(
                "mqacc_qaqc_gate_passed",
                "compatible",
                "QC precision, batches/run order, drift, blanks, internal/reference standards "
                "are sufficiently documented for deterministic planning.",
            )
        )

    return _Assessment(
        status=status,
        confidence=confidence,
        evidence=evidence,
        transforms=transforms,
        blockers=sorted(set(blockers)),
        review_questions=sorted(set(review_questions)),
    )


def _unit_info(unit: str) -> tuple[str, float, str] | None:
    return UNIT_REGISTRY.get(_normalized_unit(unit))


def _unit_multiplier(source_unit: str, target_unit: str) -> float:
    source = _unit_info(source_unit)
    target = _unit_info(target_unit)
    if source is None or target is None or source[0] != target[0]:
        raise ValueError(f"Units are not directly compatible: {source_unit!r}, {target_unit!r}")
    return _clean_number(source[1] / target[1])


def _assess_nonabsolute_data_integrity(
    left: MetaboliteAssayRecord,
    right: MetaboliteAssayRecord,
    policy: dict[str, Any],
) -> tuple[list[DecisionEvidence], list[str], list[str]]:
    """Check missingness integrity even when values cannot be directly pooled."""

    evidence: list[DecisionEvidence] = []
    blockers: list[str] = []
    review_questions: list[str] = []
    for record in (left, right):
        missingness = record.quantitative.missingness
        prefix = record.feature_id
        fraction = float(missingness.feature_missing_fraction)
        if fraction > float(policy["hard_missing_fraction_exclusion"]):
            blockers.append(f"{prefix}:missingness_exceeds_hard_limit")
        elif fraction > float(policy["maximum_missing_fraction"]):
            blockers.append(f"{prefix}:missingness_requires_sensitivity_analysis")
        if fraction > 0 and not missingness.encoded_missing_values:
            blockers.append(f"{prefix}:missing_value_codes_not_documented")
        if fraction > 0 and _is_missing(missingness.missing_reason_variable):
            blockers.append(f"{prefix}:missing_reason_not_preserved")
        if not bool(missingness.biological_zero_distinguished):
            blockers.append(f"{prefix}:biological_zero_not_distinguished")
        imputation = _text(missingness.imputation_method).lower().replace(" ", "_")
        if imputation not in _MISSING_TEXT and imputation not in {"not_applied", "no_imputation"}:
            if not bool(missingness.unimputed_values_available):
                blockers.append(f"{prefix}:irreversible_imputation")
            else:
                review_questions.append(
                    f"Use the unimputed {prefix} values when fitting its study-specific model."
                )
    evidence.append(
        _evidence(
            "nonabsolute_missingness_assessed",
            "review" if blockers else "compatible",
            "Missingness is assessed within study; assay-specific LODs and arbitrary intensity "
            "scales are not treated as a common quantifiable range.",
        )
    )
    return evidence, sorted(set(blockers)), sorted(set(review_questions))


def _assess_missingness_and_limits(
    left: MetaboliteAssayRecord,
    right: MetaboliteAssayRecord,
    common_unit: str,
    policy: dict[str, Any],
) -> _Assessment:
    evidence: list[DecisionEvidence] = []
    transforms: list[HarmonizationTransform] = []
    blockers: list[str] = []
    review_questions: list[str] = []
    hard_failure = False
    common_loqs: list[float] = []

    for record in (left, right):
        missingness = record.quantitative.missingness
        limits = record.quantitative.limits
        fraction = float(missingness.feature_missing_fraction)
        prefix = record.feature_id

        if fraction > float(policy["hard_missing_fraction_exclusion"]):
            hard_failure = True
            blockers.append(f"{prefix}:missingness_exceeds_hard_limit")
        elif fraction > float(policy["maximum_missing_fraction"]):
            blockers.append(f"{prefix}:missingness_requires_sensitivity_analysis")
            review_questions.append(
                f"Review missingness ({fraction:.1%}) and prespecify sensitivity "
                f"analyses for {prefix}."
            )

        if fraction > 0 and not missingness.encoded_missing_values:
            blockers.append(f"{prefix}:missing_value_codes_not_documented")
        if fraction > 0 and _is_missing(missingness.missing_reason_variable):
            blockers.append(f"{prefix}:missing_reason_not_preserved")
        if not bool(missingness.biological_zero_distinguished):
            blockers.append(f"{prefix}:biological_zero_not_distinguished")

        imputation = _text(missingness.imputation_method).lower().replace(" ", "_")
        if imputation not in _MISSING_TEXT and imputation not in {"not_applied", "no_imputation"}:
            if not bool(missingness.unimputed_values_available):
                hard_failure = True
                blockers.append(f"{prefix}:irreversible_imputation")
            else:
                transforms.append(
                    HarmonizationTransform(
                        order=0,
                        registry_key="use_unimputed_source_values",
                        applies_to=[prefix],
                        parameters={"discarded_imputation_method": imputation},
                        rationale="Harmonization must start from unimputed values.",
                    )
                )

        censoring_policy = _text(limits.censoring_policy)
        if censoring_policy in {
            "half_limit_imputed",
            "zero_imputed",
            "minimum_value_imputed",
        } and not bool(missingness.unimputed_values_available):
            hard_failure = True
            blockers.append(f"{prefix}:irreversible_below_limit_imputation")
        if censoring_policy == "none_expected":
            blockers.append(f"{prefix}:absolute_concentration_censoring_not_defined")
        if censoring_policy == "unknown":
            blockers.append(f"{prefix}:below_limit_policy_unknown")
        if not bool(limits.raw_censoring_flags_available):
            blockers.append(f"{prefix}:below_limit_flags_unavailable")
        if _is_missing(limits.below_limit_code):
            blockers.append(f"{prefix}:below_limit_code_missing")

        if limits.loq is None:
            blockers.append(f"{prefix}:loq_not_reported")
        else:
            try:
                common_loqs.append(
                    _clean_number(float(limits.loq) * _unit_multiplier(limits.unit, common_unit))
                )
            except ValueError:
                hard_failure = True
                blockers.append(f"{prefix}:loq_unit_incompatible")

        transforms.append(
            HarmonizationTransform(
                order=0,
                registry_key="preserve_missing_reason_codes",
                applies_to=[prefix],
                parameters={
                    "missing_codes": sorted(missingness.encoded_missing_values),
                    "missing_reason_variable": missingness.missing_reason_variable,
                    "below_limit_code": limits.below_limit_code,
                },
                rationale="Retain missing, below-limit, and biological-zero semantics separately.",
            )
        )

    if len(common_loqs) == 2 and not hard_failure:
        common_loq = _clean_number(max(common_loqs))
        transforms.append(
            HarmonizationTransform(
                order=0,
                registry_key="censor_below_common_loq",
                applies_to=sorted([left.feature_id, right.feature_id]),
                parameters={"common_loq": common_loq, "unit": common_unit},
                rationale="Use the more conservative compatible LOQ without numeric substitution.",
            )
        )
        evidence.append(
            _evidence(
                "common_quantifiable_range_defined",
                "compatible",
                f"Common LOQ is {common_loq:g} {common_unit}; values below remain left-censored.",
            )
        )

    if hard_failure:
        status = _NONCOMBINABLE_STATUS
        confidence = 0.15
    elif blockers:
        status = _REVIEW_STATUS
        confidence = 0.60
        evidence.append(
            _evidence(
                "lod_missingness_gate_incomplete",
                "review",
                "LOD/LOQ, censoring, or missing-reason metadata prevent automatic pooling.",
            )
        )
        review_questions.append(
            "Recover unimputed values and explicit missing/below-limit reason codes before pooling."
        )
    else:
        status = _ACCEPTED_STATUS
        confidence = 0.94
        evidence.append(
            _evidence(
                "lod_missingness_gate_passed",
                "compatible",
                "Missingness and left-censoring can be represented without "
                "zero/half-limit imputation.",
            )
        )

    return _Assessment(
        status=status,
        confidence=confidence,
        evidence=evidence,
        transforms=transforms,
        blockers=sorted(set(blockers)),
        review_questions=sorted(set(review_questions)),
        common_unit=common_unit,
    )


def _assess_quantitative(
    left: MetaboliteAssayRecord,
    right: MetaboliteAssayRecord,
    policy: dict[str, Any],
) -> _Assessment:
    evidence: list[DecisionEvidence] = []
    transforms: list[HarmonizationTransform] = []
    blockers: list[str] = []
    review_questions: list[str] = []
    left_type = _text(left.quantitative.quantitation_type)
    right_type = _text(right.quantitative.quantitation_type)

    if left_type != "absolute_concentration" or right_type != "absolute_concentration":
        if left_type != right_type:
            code = "quantitation_type_incompatible"
            detail = f"Quantitation types differ ({left_type} versus {right_type})."
        else:
            code = "non_absolute_values_not_poolable"
            detail = (
                f"{left_type} values are assay-specific; direct raw-value pooling is prohibited."
            )
        integrity_evidence, integrity_blockers, integrity_questions = (
            _assess_nonabsolute_data_integrity(left, right, policy)
        )
        return _Assessment(
            status=_NONCOMBINABLE_STATUS,
            confidence=0.10,
            evidence=[_evidence(code, "incompatible", detail)] + integrity_evidence,
            blockers=sorted(set([code] + integrity_blockers)),
            review_questions=[
                "Use study-specific models and meta-analyze effects after checking "
                "platform heterogeneity."
            ]
            + integrity_questions,
        )

    if any(_text(record.quantitative.scale) != "linear" for record in (left, right)):
        return _Assessment(
            status=_REVIEW_STATUS,
            confidence=0.45,
            evidence=[
                _evidence(
                    "nonlinear_concentration_scale",
                    "review",
                    "Absolute concentrations are not both on a documented linear scale; "
                    "offsets and back-transformation cannot be inferred.",
                )
            ],
            blockers=["nonlinear_or_unknown_scale"],
            review_questions=["Document the exact transform and offset, then regenerate the plan."],
        )

    left_unit = _unit_info(left.quantitative.unit)
    right_unit = _unit_info(right.quantitative.unit)
    if left_unit is None or right_unit is None:
        return _Assessment(
            status=_REVIEW_STATUS,
            confidence=0.40,
            evidence=[
                _evidence(
                    "unit_not_in_registry",
                    "review",
                    "At least one concentration unit is not in the approved "
                    "deterministic registry.",
                )
            ],
            blockers=["unit_not_in_registry"],
            review_questions=["Curate dimensional units and approve a conversion rule."],
        )
    if left_unit[0] != right_unit[0]:
        return _Assessment(
            status=_REVIEW_STATUS,
            confidence=0.35,
            evidence=[
                _evidence(
                    "mass_molar_conversion_not_automatic",
                    "review",
                    "Mass and molar concentrations are not automatically interconverted; molecular "
                    "weight, salt/hydrate form, and identity require expert approval.",
                )
            ],
            blockers=["concentration_dimension_mismatch"],
            review_questions=[
                "Confirm analyte form and molecular weight, then register an approved conversion."
            ],
        )

    common_unit = left_unit[2]
    for record in (left, right):
        multiplier = _unit_multiplier(record.quantitative.unit, common_unit)
        transforms.append(
            HarmonizationTransform(
                order=0,
                registry_key="convert_compatible_concentration_unit",
                applies_to=[record.feature_id],
                parameters={
                    "source_unit": record.quantitative.unit,
                    "target_unit": common_unit,
                    "multiplier": multiplier,
                },
                rationale="Convert only within the same concentration dimension.",
            )
        )

    if _text(left.assay.sample_matrix).casefold() != _text(right.assay.sample_matrix).casefold():
        return _Assessment(
            status=_NONCOMBINABLE_STATUS,
            confidence=0.10,
            evidence=[
                _evidence(
                    "biospecimen_matrix_incompatible",
                    "incompatible",
                    f"Matrices differ ({left.assay.sample_matrix} versus "
                    f"{right.assay.sample_matrix}).",
                )
            ],
            transforms=transforms,
            blockers=["biospecimen_matrix_incompatible"],
            common_unit=common_unit,
        )

    for record in (left, right):
        if _is_missing(record.quantitative.calibration_model) or _is_missing(
            record.quantitative.calibration_traceability
        ):
            blockers.append(f"{record.feature_id}:calibration_traceability_missing")

    if (
        _text(left.quantitative.calibration_model)
        != _text(right.quantitative.calibration_model)
    ):
        blockers.append("calibration_models_differ")
    if (
        _text(left.quantitative.calibration_traceability)
        != _text(right.quantitative.calibration_traceability)
    ):
        blockers.append("calibration_traceability_differs")
    if _text(left.quantitative.internal_standard) != _text(right.quantitative.internal_standard):
        blockers.append("internal_standards_differ")
    if _text(left.assay.batch.reference_material) != _text(right.assay.batch.reference_material):
        blockers.append("reference_materials_differ")

    same_platform_family = _text(left.assay.platform_family) == _text(
        right.assay.platform_family
    )
    same_method = (
        _text(left.assay.method_id) == _text(right.assay.method_id)
        and _text(left.assay.assay_version) == _text(right.assay.assay_version)
        and same_platform_family
    )
    common_bridges = sorted(
        set(left.assay.validated_bridge_ids) & set(right.assay.validated_bridge_ids)
    )
    if not same_method:
        bridge_provenance_resolved = common_bridges and all(
            common_bridges[0] in record.provenance.evidence_locators for record in (left, right)
        )
        if common_bridges and bridge_provenance_resolved:
            transforms.append(
                HarmonizationTransform(
                    order=0,
                    registry_key="apply_validated_method_bridge",
                    applies_to=sorted([left.feature_id, right.feature_id]),
                    parameters={"bridge_id": common_bridges[0]},
                    rationale="Apply a prevalidated method-comparison bridge before pooling.",
                )
            )
            evidence.append(
                _evidence(
                    "validated_cross_method_bridge",
                    "compatible",
                    f"Methods share approved bridge {common_bridges[0]}.",
                )
            )
        else:
            blockers.append("unbridged_assay_methods")
            if common_bridges and not bridge_provenance_resolved:
                blockers.append("method_bridge_provenance_unresolved")
            review_questions.append(
                "Provide a matrix-matched method-comparison/commutability bridge or "
                "keep studies separate."
            )
            evidence.append(
                _evidence(
                    "cross_platform_heterogeneity_unbridged",
                    "review",
                    "Assay methods/platforms differ without a validated bridge; "
                    "direct pooling is blocked."
                    if not same_platform_family
                    else (
                        "Assay methods differ without a validated bridge; "
                        "direct pooling is blocked."
                    ),
                )
            )

    limits = _assess_missingness_and_limits(left, right, common_unit, policy)
    evidence.extend(limits.evidence)
    transforms.extend(limits.transforms)
    blockers.extend(limits.blockers)
    review_questions.extend(limits.review_questions)

    if limits.status == _NONCOMBINABLE_STATUS:
        status = _NONCOMBINABLE_STATUS
        confidence = min(0.20, limits.confidence)
    elif blockers:
        status = _REVIEW_STATUS
        confidence = min(0.70, limits.confidence)
    else:
        status = _ACCEPTED_STATUS
        confidence = min(0.96, limits.confidence)
        evidence.append(
            _evidence(
                "absolute_scale_unit_gate_passed",
                "compatible",
                f"Linear absolute concentrations can be expressed in {common_unit}.",
            )
        )

    return _Assessment(
        status=status,
        confidence=confidence,
        evidence=evidence,
        transforms=transforms,
        blockers=sorted(set(blockers)),
        review_questions=sorted(set(review_questions)),
        common_unit=common_unit,
    )


def _combined_status(*statuses: str) -> str:
    if _NONCOMBINABLE_STATUS in statuses:
        return _NONCOMBINABLE_STATUS
    if _REVIEW_STATUS in statuses:
        return _REVIEW_STATUS
    return _ACCEPTED_STATUS


def _heterogeneity_plan(
    permitted_analysis: str,
) -> HeterogeneityPlan:
    if permitted_analysis == PermittedAnalysis.POOLED_INDIVIDUAL_VALUES.value:
        level = "pooled_values_with_study_and_platform_sensitivity_analysis"
    elif permitted_analysis == PermittedAnalysis.STUDY_SPECIFIC_EFFECTS_META_ANALYSIS.value:
        level = "study_specific_effects_random_effects_meta_analysis"
    else:
        level = "no_cross_study_combination_until_blockers_are_resolved"
    return HeterogeneityPlan(
        analysis_level=level,
        stratify_by=["study_id", "platform_family", "assay_id", "sample_matrix"],
        required_diagnostics=[
            "Cochran_Q",
            "I2",
            "tau2",
            "platform_moderator_meta_regression",
            "leave_one_study_out",
            "leave_one_platform_out",
        ],
        interpretation_rule=(
            "Report direction and heterogeneity, retain platform/study strata, and do not convert "
            "a heterogeneous or scale-incompatible result into a pooled concentration."
        ),
    )


def evaluate_assay_pair(
    left: MetaboliteAssayRecord,
    right: MetaboliteAssayRecord,
    *,
    policy: dict[str, Any] | None = None,
) -> AssayHarmonizationDecision:
    """Evaluate a candidate pair without name-based identity inference."""

    if left.feature_id == right.feature_id:
        raise ValueError("A feature cannot be harmonized with itself.")
    policy = {**DEFAULT_POLICY, **(policy or {})}

    # Pair orientation is stable so decisions are reproducible when inputs are reversed.
    if right.feature_id < left.feature_id:
        left, right = right, left

    identity = _assess_identity(left, right)
    quantitative = _assess_quantitative(left, right, policy)
    qa_qc = _assess_qa_qc(left, right, policy)
    status = _combined_status(identity.status, quantitative.status, qa_qc.status)
    raw_values_combinable = status == _ACCEPTED_STATUS

    component_blockers = identity.blockers + quantitative.blockers + qa_qc.blockers
    effect_analysis_disqualifiers = (
        "irreversible",
        "cross_study_batch_correction",
        "qc_cv_exceeds_threshold",
        "missingness_exceeds_hard_limit",
    )
    effects_safe = not any(
        marker in blocker
        for blocker in component_blockers
        for marker in effect_analysis_disqualifiers
    )
    if raw_values_combinable:
        permitted_analysis = PermittedAnalysis.POOLED_INDIVIDUAL_VALUES.value
    elif identity.status == _ACCEPTED_STATUS and effects_safe and status in {
        _NONCOMBINABLE_STATUS,
        _REVIEW_STATUS,
    }:
        permitted_analysis = PermittedAnalysis.STUDY_SPECIFIC_EFFECTS_META_ANALYSIS.value
    elif status == _REVIEW_STATUS:
        permitted_analysis = PermittedAnalysis.NONE_PENDING_REVIEW.value
    else:
        permitted_analysis = PermittedAnalysis.NONE.value

    confidence = round(min(identity.confidence, quantitative.confidence, qa_qc.confidence), 2)
    if status == _REVIEW_STATUS:
        confidence = min(confidence, 0.79)
    elif status == _NONCOMBINABLE_STATUS:
        confidence = min(confidence, 0.39)
    else:
        confidence = max(confidence, 0.90)

    transforms = identity.transforms + quantitative.transforms + qa_qc.transforms
    transforms = sorted(
        transforms,
        key=lambda item: (
            item.registry_key,
            tuple(item.applies_to),
            json.dumps(item.parameters, sort_keys=True),
        ),
    )
    for index, transform in enumerate(transforms, start=1):
        transform.order = index

    unapproved = sorted(
        {
            item.registry_key
            for item in transforms
            if item.registry_key not in APPROVED_TRANSFORM_REGISTRY
        }
    )
    if unapproved:
        status = _REVIEW_STATUS
        raw_values_combinable = False
        permitted_analysis = PermittedAnalysis.NONE_PENDING_REVIEW.value

    blockers = sorted(set(component_blockers))
    review_questions = sorted(
        set(identity.review_questions + quantitative.review_questions + qa_qc.review_questions)
    )
    if unapproved:
        blockers.append("unapproved_transform")
        review_questions.append("Approve or remove transforms: " + ", ".join(unapproved) + ".")

    combined_evidence = identity.evidence + quantitative.evidence + qa_qc.evidence
    if status != _ACCEPTED_STATUS and transforms:
        combined_evidence.append(
            _evidence(
                "transforms_withheld_by_review_gate",
                "blocked",
                "Candidate transform steps are withheld because this pair is not accepted.",
            )
        )
        transforms = []

    pair_payload = sorted(
        [to_plain(left), to_plain(right)], key=lambda item: str(item["feature_id"])
    )
    provenance = DecisionProvenance(
        source_feature_ids=[left.feature_id, right.feature_id],
        source_artifacts=sorted(
            {left.provenance.source_artifact, right.provenance.source_artifact}
        ),
        source_sha256=sorted({left.provenance.source_sha256, right.provenance.source_sha256}),
        rule_set_version=RULE_SET_VERSION,
        pair_input_digest=_digest(pair_payload),
    )

    return AssayHarmonizationDecision(
        left_feature_id=left.feature_id,
        right_feature_id=right.feature_id,
        status=status,
        identity_status=identity.status,
        quantitative_status=quantitative.status,
        qa_qc_status=qa_qc.status,
        confidence=confidence,
        raw_values_combinable=raw_values_combinable,
        permitted_analysis=permitted_analysis,
        canonical_identity=identity.canonical_identity,
        common_unit=quantitative.common_unit,
        evidence=sorted(combined_evidence, key=lambda x: x.code),
        transforms=transforms,
        blockers=blockers,
        review_questions=review_questions,
        heterogeneity_plan=_heterogeneity_plan(permitted_analysis),
        provenance=provenance,
    )


def build_assay_harmonization_plan(
    records: Iterable[MetaboliteAssayRecord],
    candidate_pairs: Sequence[Sequence[str]] | None = None,
    *,
    policy: dict[str, Any] | None = None,
    out_path: str | Path | None = None,
) -> AssayHarmonizationPlan:
    """Build a stable pairwise plan from typed assay records.

    When ``candidate_pairs`` is omitted all pairs are evaluated.  In production,
    callers should supply chemically generated candidates rather than using names.
    """

    merged_policy = {**DEFAULT_POLICY, **(policy or {})}
    records_by_id: dict[str, MetaboliteAssayRecord] = {}
    for record in records:
        if record.feature_id in records_by_id:
            raise ValueError(f"Duplicate feature_id: {record.feature_id}")
        records_by_id[record.feature_id] = record
    ordered_records = [records_by_id[key] for key in sorted(records_by_id)]

    if candidate_pairs is None:
        pairs = list(combinations(sorted(records_by_id), 2))
    else:
        normalized_pairs: set[tuple[str, str]] = set()
        for pair in candidate_pairs:
            if len(pair) != 2:
                raise ValueError(f"Candidate pair must contain two feature IDs: {pair!r}")
            left_id, right_id = sorted((_text(pair[0]), _text(pair[1])))
            if left_id == right_id:
                raise ValueError(f"Candidate pair contains the same feature twice: {left_id}")
            missing = [item for item in (left_id, right_id) if item not in records_by_id]
            if missing:
                raise ValueError("Unknown candidate feature_id(s): " + ", ".join(missing))
            normalized_pairs.add((left_id, right_id))
        pairs = sorted(normalized_pairs)

    decisions = [
        evaluate_assay_pair(records_by_id[left_id], records_by_id[right_id], policy=merged_policy)
        for left_id, right_id in pairs
    ]
    decisions.sort(key=lambda item: (item.left_feature_id, item.right_feature_id))
    statuses = [_text(item.status) for item in decisions]
    summary = {
        "record_count": len(ordered_records),
        "candidate_pair_count": len(decisions),
        "accepted_count": statuses.count(_ACCEPTED_STATUS),
        "requires_human_review_count": statuses.count(_REVIEW_STATUS),
        "non_combinable_count": statuses.count(_NONCOMBINABLE_STATUS),
    }

    plan = AssayHarmonizationPlan(
        schema_version=SCHEMA_VERSION,
        rule_set_version=RULE_SET_VERSION,
        input_digest=_digest([to_plain(item) for item in ordered_records]),
        policy=merged_policy,
        summary=summary,
        decisions=decisions,
        approved_transform_registry=sorted(APPROVED_TRANSFORM_REGISTRY),
        validation_checks=[
            "No reported-name-only match is accepted as chemical identity.",
            "Only MSI level 1 exact identities with linked evidence may pool values.",
            "No incompatible quantitative representation or scale pools raw values.",
            "All accepted transforms are present in the approved transform registry.",
            "Batch/drift processing is performed within study, never jointly across studies.",
            "Below-limit observations remain censored and distinct from biological zero.",
            "Every identity assertion and decision retains source provenance.",
        ],
        failure_conditions=[
            "Duplicate or unknown feature identifier.",
            "Conflicting exact chemical identifiers.",
            "Unresolved isomer, stereochemistry, or identity provenance.",
            "Unapproved unit or transform.",
            "Irreversible zero/half-limit imputation or missing censoring flags.",
            "Cross-study batch correction or feature QC CV above policy threshold.",
            "Unbridged assay/platform method for individual-value pooling.",
        ],
    )
    if out_path is not None:
        write_json(out_path, plan)
    return plan


def load_assay_harmonization_fixture(
    path: str | Path,
) -> tuple[list[MetaboliteAssayRecord], list[list[str]]]:
    """Load a local JSON fixture containing records and explicit candidate pairs."""

    payload = read_json(path)
    records = [MetaboliteAssayRecord.model_validate(item) for item in payload["records"]]
    candidate_pairs = [list(pair) for pair in payload.get("candidate_pairs", [])]
    return records, candidate_pairs


def write_assay_harmonization_artifacts(
    fixture_path: str | Path,
    project_root: str | Path,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Materialize all review-gated artifacts promised by the assay workflow.

    Outputs are deterministic: no wall-clock time, random state, or environment
    path is embedded in their content.  Only accepted decisions contain executable
    transforms; review and non-combinable ledgers retain evidence and provenance.
    """

    records, pairs = load_assay_harmonization_fixture(fixture_path)
    plan = build_assay_harmonization_plan(records, pairs, policy=policy)
    root = Path(project_root)
    paths = {
        "plan": root / "reports/aim2_assay_harmonization_plan.json",
        "accepted": root / "data/harmonized/approved_assay_harmonization.json",
        "review": root / "data/review/assay_harmonization_review_queue.json",
        "non_combinable": root / "data/review/non_combinable_assay_pairs.json",
        "audit": root / "data/harmonized/assay_harmonization_audit.json",
    }

    plain_decisions = [to_plain(item) for item in plan.decisions]
    accepted = [item for item in plain_decisions if item["status"] == _ACCEPTED_STATUS]
    review = [item for item in plain_decisions if item["status"] == _REVIEW_STATUS]
    non_combinable = [
        item for item in plain_decisions if item["status"] == _NONCOMBINABLE_STATUS
    ]
    accepted_payload = {
        "schema_version": SCHEMA_VERSION,
        "rule_set_version": RULE_SET_VERSION,
        "input_digest": plan.input_digest,
        "decisions": accepted,
    }
    review_payload = {
        "schema_version": SCHEMA_VERSION,
        "rule_set_version": RULE_SET_VERSION,
        "input_digest": plan.input_digest,
        "decisions": review,
    }
    non_combinable_payload = {
        "schema_version": SCHEMA_VERSION,
        "rule_set_version": RULE_SET_VERSION,
        "input_digest": plan.input_digest,
        "decisions": non_combinable,
    }
    source_provenance = [
        {
            "feature_id": record.feature_id,
            "provenance": to_plain(record.provenance),
        }
        for record in sorted(records, key=lambda item: item.feature_id)
    ]
    audit_payload = {
        "schema_version": SCHEMA_VERSION,
        "rule_set_version": RULE_SET_VERSION,
        "input_digest": plan.input_digest,
        "fixture_content_digest": _digest(read_json(fixture_path)),
        "summary": to_plain(plan.summary),
        "source_provenance": source_provenance,
        "artifact_payload_digests": {
            "plan": _digest(plan),
            "accepted": _digest(accepted_payload),
            "review": _digest(review_payload),
            "non_combinable": _digest(non_combinable_payload),
        },
        "validation_checks": to_plain(plan.validation_checks),
        "failure_conditions": to_plain(plan.failure_conditions),
    }

    write_json(paths["plan"], plan)
    write_json(paths["accepted"], accepted_payload)
    write_json(paths["review"], review_payload)
    write_json(paths["non_combinable"], non_combinable_payload)
    write_json(paths["audit"], audit_payload)
    return paths

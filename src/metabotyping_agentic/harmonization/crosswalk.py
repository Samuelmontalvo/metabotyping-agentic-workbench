"""Deterministic variable crosswalk heuristics with review gates."""

from __future__ import annotations

import re
from pathlib import Path

from ..extraction.variable_inventory import load_variable_cards
from ..io import to_plain, write_csv_rows, write_json
from ..models import ReviewStatus, VariableCard, VariableMapping

SYNONYMS: dict[str, list[str]] = {
    "vo2max": ["vo2max", "vo2_max", "vo2peak", "peak_vo2", "cardiorespiratory_fitness"],
    "steps_per_day": ["steps", "daily_steps", "mean_steps", "steps_per_day"],
    "mvpa_minutes": ["mvpa", "mvpa_min", "moderate_vigorous_physical_activity"],
    "age": ["age", "participant_age"],
    "sex": ["sex", "biological_sex", "gender"],
    "bmi": ["bmi", "body_mass_index"],
    "fasting_glucose": ["fasting_glucose", "glucose_fasting"],
    "insulin": ["insulin", "fasting_insulin"],
    "lean_mass": ["lean_mass", "total_lean_mass", "dxa_lean_mass"],
    "fat_mass": ["fat_mass", "total_fat_mass", "dxa_fat_mass"],
}

COMMON_UNITS = {
    "vo2max": "mL/kg/min",
    "steps_per_day": "steps/day",
    "mvpa_minutes": "min/day",
    "age": "years",
    "sex": "category",
    "bmi": "kg/m^2",
    "fasting_glucose": "mg/dL",
    "insulin": "uIU/mL",
    "lean_mass": "kg",
    "fat_mass": "kg",
}

EXPECTED_MODALITY = {
    "vo2max": {"cpet", "exercise"},
    "steps_per_day": {"actigraphy", "physical_activity"},
    "mvpa_minutes": {"actigraphy", "physical_activity"},
    "age": {"demographics", "clinical"},
    "sex": {"demographics", "clinical"},
    "bmi": {"body_composition", "clinical"},
    "fasting_glucose": {"metabolomics", "clinical"},
    "insulin": {"metabolomics", "clinical"},
    "lean_mass": {"body_composition"},
    "fat_mass": {"body_composition"},
}


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("vo₂", "vo2")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def common_variable_for(card: VariableCard) -> tuple[str, str]:
    haystack = {normalize_name(card.source_variable), normalize_name(card.label)}
    for common, synonyms in SYNONYMS.items():
        normalized_synonyms = {normalize_name(item) for item in synonyms}
        if haystack & normalized_synonyms:
            return common, "name_or_label_synonym"
    for common, synonyms in SYNONYMS.items():
        normalized_synonyms = [normalize_name(item) for item in synonyms]
        if any(synonym in item or item in synonym for item in haystack for synonym in normalized_synonyms):
            return common, "partial_name_similarity"
    return "not_mapped", "no_supported_synonym"


def choose_transform(source_unit: str, common_unit: str) -> tuple[str, bool]:
    source = source_unit.strip().lower()
    target = common_unit.strip().lower()
    if source in {"", "unknown", "not_reported"} or target in {"", "unknown"}:
        return "not_available", False
    if source == target.lower():
        return "identity", True
    glucose_pairs = {("mmol/l", "mg/dl"), ("mmol/l", "mg/dl")}
    if (source, target) in glucose_pairs:
        return "multiply_by_18.0182", True
    return "unit_conversion_requires_review", False


def score_mapping(card: VariableCard) -> VariableMapping:
    common, evidence_kind = common_variable_for(card)
    source_modality = str(card.modality.value if hasattr(card.modality, "value") else card.modality)
    source_unit = card.unit or "unknown"
    source_timing = card.timing or "unknown"

    if common == "not_mapped":
        return VariableMapping(
            source_study=card.study_id,
            source_variable=card.source_variable,
            source_label=card.label,
            source_unit=source_unit,
            source_timing=source_timing,
            source_modality=source_modality,
            proposed_common_variable="not_mapped",
            proposed_common_unit="not_available",
            transform="not_available",
            confidence=0.20,
            evidence="No supported scientific synonym or mapping rule matched.",
            review_status=ReviewStatus.REJECTED,
        )

    common_unit = COMMON_UNITS[common]
    transform, unit_ok = choose_transform(source_unit, common_unit)
    modality_ok = source_modality in EXPECTED_MODALITY.get(common, {source_modality})
    timing_ok = source_timing.lower() not in {"", "unknown", "not_reported"}
    exact_name = normalize_name(card.source_variable) == common

    confidence = 0.50
    evidence = [f"Matched {common} via {evidence_kind}."]
    if exact_name:
        confidence += 0.20
        evidence.append("Source variable exactly matches common variable.")
    else:
        confidence += 0.12
        evidence.append("Source variable is a synonym or related label.")
    if unit_ok:
        confidence += 0.12
        evidence.append("Unit is compatible.")
    else:
        confidence -= 0.12
        evidence.append("Unit is missing or requires review.")
    if modality_ok:
        confidence += 0.10
        evidence.append("Modality is compatible.")
    else:
        confidence -= 0.22
        evidence.append("Modality is incompatible with the proposed common variable.")
    if timing_ok:
        confidence += 0.04
        evidence.append("Timing is reported.")
    else:
        confidence -= 0.08
        evidence.append("Timing is missing.")

    if common == "vo2max" and normalize_name(card.source_variable) in {"vo2peak", "peak_vo2"}:
        confidence = min(confidence, 0.78)
        evidence.append("VO2peak and VO2max are not accepted as equivalent without protocol evidence.")

    confidence = max(0.0, min(round(confidence, 2), 0.99))
    if not modality_ok:
        status = ReviewStatus.REJECTED
    elif confidence >= 0.90 and unit_ok and timing_ok and common != "vo2max":
        status = ReviewStatus.ACCEPTED
    elif confidence >= 0.90 and unit_ok and timing_ok and normalize_name(card.source_variable) == "vo2max":
        status = ReviewStatus.ACCEPTED
    elif confidence >= 0.40:
        status = ReviewStatus.REQUIRES_HUMAN_REVIEW
    else:
        status = ReviewStatus.REJECTED

    return VariableMapping(
        source_study=card.study_id,
        source_variable=card.source_variable,
        source_label=card.label,
        source_unit=source_unit,
        source_timing=source_timing,
        source_modality=source_modality,
        proposed_common_variable=common,
        proposed_common_unit=common_unit,
        transform=transform,
        confidence=confidence,
        evidence=" ".join(evidence),
        review_status=status,
    )


def build_crosswalk(variables_path: str | Path, out_dir: str | Path) -> list[VariableMapping]:
    cards = load_variable_cards(variables_path)
    mappings = [score_mapping(card) for card in cards]
    rows = [to_plain(mapping) for mapping in mappings]
    fieldnames = [
        "source_study",
        "source_variable",
        "source_label",
        "source_unit",
        "source_timing",
        "source_modality",
        "proposed_common_variable",
        "proposed_common_unit",
        "transform",
        "confidence",
        "evidence",
        "review_status",
    ]
    out_dir = Path(out_dir)
    write_csv_rows(out_dir / "crosswalk.csv", rows, fieldnames=fieldnames)
    write_json(out_dir / "crosswalk.json", rows)
    return mappings


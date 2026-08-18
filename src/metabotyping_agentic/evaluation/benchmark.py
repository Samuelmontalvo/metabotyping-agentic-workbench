"""Benchmark predicted outputs against synthetic expert fixtures."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .. import __version__
from ..io import read_json, to_plain, write_csv_rows, write_json
from ..models import (
    BenchmarkArtifactDigest,
    BenchmarkCaseResult,
    BenchmarkManifest,
    BenchmarkResult,
)
from ..schemas import project_schema_path, validate_or_raise

MANIFEST_VERSION = "1.0.0"
RULE_SET_VERSION = "0.2.0"
QUALITY_SCORE_TOLERANCE = Decimal("0.15")
CONFIDENCE_LEVEL = 0.95
WILSON_Z_95 = 1.959963984540054
VALID_REVIEW_STATUSES = {"accepted", "rejected", "requires_human_review"}
MISSING_MAPPING = "not_mapped"
CASE_OUTCOME_PRECEDENCE = [
    "missing_prediction",
    "unexpected_prediction",
    "common_variable_mismatch",
    "review_status_mismatch",
    "quality_score_outside_tolerance",
    "unsafe_auto_accept",
]

METRIC_NAMES = [
    "candidate_precision",
    "candidate_recall",
    "candidate_f1",
    "auto_accept_precision",
    "auto_accept_recall",
    "unsafe_auto_accept_rate",
    "review_capture_rate",
    "review_status_accuracy",
    "quality_score_agreement_within_0.15",
]

RESULT_FIELDNAMES = ["metric_name", "value", "details"]
CASE_FIELDNAMES = [
    "case_type",
    "source_study",
    "source_variable",
    "common_variable",
    "outcome",
    "reason_codes",
    "gold",
    "predicted",
    "absolute_difference",
    "within_tolerance",
]
DISAGREEMENT_FIELDNAMES = [
    "case_type",
    "source_study",
    "source_variable",
    "common_variable",
    "outcome",
    "reason_codes",
    "gold_common_variable",
    "predicted_common_variable",
    "gold_review_status",
    "predicted_review_status",
    "gold_overall_score",
    "predicted_overall_score",
    "absolute_difference",
    "within_tolerance",
]


class BenchmarkInputError(ValueError):
    """Raised before output when a benchmark input violates its contract."""


@dataclass(frozen=True)
class _BenchmarkRunBundle:
    """One internally consistent benchmark run passed to writers and renderer."""

    results: list[BenchmarkResult]
    result_rows: list[dict[str, Any]]
    cases: list[BenchmarkCaseResult]
    case_rows: list[dict[str, Any]]
    disagreement_rows: list[dict[str, Any]]
    input_artifacts: list[BenchmarkArtifactDigest]
    manifest_metadata: dict[str, Any]


def _require_input_files(
    predicted_dir: Path,
    gold_dir: Path,
) -> tuple[dict[str, Path], bool]:
    mapping_paths = {
        "predicted_crosswalk": predicted_dir / "crosswalk.csv",
        "gold_variable_mappings": gold_dir / "expert_variable_mappings.csv",
    }
    quality_paths = {
        "predicted_quality_scores": predicted_dir / "quality_scores.json",
        "gold_quality_scores": gold_dir / "expert_quality_scores.csv",
    }
    missing = [str(path) for path in mapping_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Benchmark requires both mapping inputs; missing: " + ", ".join(missing)
        )

    quality_presence = {
        role: path.is_file() for role, path in quality_paths.items()
    }
    if len(set(quality_presence.values())) != 1:
        missing_quality = [
            str(quality_paths[role])
            for role, present in quality_presence.items()
            if not present
        ]
        raise FileNotFoundError(
            "Benchmark quality inputs must be provided together; asymmetric input is "
            "missing: "
            + ", ".join(missing_quality)
        )
    if not all(quality_presence.values()):
        return {**mapping_paths, **quality_paths}, False
    return {**mapping_paths, **quality_paths}, True


def _read_csv_strict(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise BenchmarkInputError(f"{path.name}: CSV header is missing")
        blank_positions = [
            str(index)
            for index, name in enumerate(fieldnames, start=1)
            if not name.strip()
        ]
        if blank_positions:
            raise BenchmarkInputError(
                f"{path.name}: CSV header has blank column name(s) at position "
                + ", ".join(blank_positions)
            )
        whitespace_names = [name for name in fieldnames if name != name.strip()]
        if whitespace_names:
            raise BenchmarkInputError(
                f"{path.name}: CSV header column names may not contain surrounding "
                "whitespace"
            )
        if len(fieldnames) != len(set(fieldnames)):
            raise BenchmarkInputError(
                f"{path.name}: duplicate CSV column names are not allowed"
            )
        rows = list(reader)

    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise BenchmarkInputError(
                f"{path.name}: row {row_number} has more values than the header"
            )
    return fieldnames, rows


def _required_text(row: dict[str, Any], column: str, path: Path, row_number: int) -> str:
    value = row.get(column)
    if value is None or not str(value).strip():
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} is missing required field {column!r}"
        )
    return str(value).strip()


def _study_alias(
    row: dict[str, Any],
    fieldnames: list[str],
    path: Path,
    row_number: int,
) -> str:
    source_study = str(row.get("source_study") or "").strip()
    study_id = str(row.get("study_id") or "").strip()
    if not ({"source_study", "study_id"} & set(fieldnames)):
        raise BenchmarkInputError(
            f"{path.name}: header must contain source_study or its supported alias study_id"
        )
    if source_study and study_id and source_study != study_id:
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} has conflicting source_study and study_id values"
        )
    value = source_study or study_id
    if not value:
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} is missing source_study/study_id"
        )
    return value


def _common_variable_alias(
    row: dict[str, Any],
    fieldnames: list[str],
    preferred_column: str,
    path: Path,
    row_number: int,
) -> str:
    alias_column = (
        "common_variable"
        if preferred_column == "proposed_common_variable"
        else "proposed_common_variable"
    )
    if not ({preferred_column, alias_column} & set(fieldnames)):
        raise BenchmarkInputError(
            f"{path.name}: missing required common-variable column "
            f"{preferred_column}/{alias_column}"
        )
    preferred = str(row.get(preferred_column) or "").strip()
    alias = str(row.get(alias_column) or "").strip()
    if preferred and alias and preferred != alias:
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} has conflicting {preferred_column} "
            f"and {alias_column} values"
        )
    value = preferred or alias
    if not value:
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} is missing "
            f"{preferred_column}/{alias_column}"
        )
    return value


def _read_mapping_rows(
    path: Path,
    *,
    common_variable_column: str,
) -> tuple[list[dict[str, str]], list[str]]:
    fieldnames, raw_rows = _read_csv_strict(path)
    required_columns = {
        "source_variable",
        "review_status",
    }
    missing_columns = sorted(required_columns - set(fieldnames))
    if missing_columns:
        raise BenchmarkInputError(
            f"{path.name}: missing required columns: {', '.join(missing_columns)}"
        )
    if not ({"source_study", "study_id"} & set(fieldnames)):
        raise BenchmarkInputError(
            f"{path.name}: missing required study column source_study/study_id"
        )
    common_alias = (
        "common_variable"
        if common_variable_column == "proposed_common_variable"
        else "proposed_common_variable"
    )
    if not ({common_variable_column, common_alias} & set(fieldnames)):
        raise BenchmarkInputError(
            f"{path.name}: missing required common-variable column "
            f"{common_variable_column}/{common_alias}"
        )

    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str], int] = {}
    for row_number, row in enumerate(raw_rows, start=2):
        source_study = _study_alias(row, fieldnames, path, row_number)
        source_variable = _required_text(row, "source_variable", path, row_number)
        common_variable = _common_variable_alias(
            row,
            fieldnames,
            common_variable_column,
            path,
            row_number,
        )
        review_status = _required_text(row, "review_status", path, row_number)
        if review_status not in VALID_REVIEW_STATUSES:
            allowed = ", ".join(sorted(VALID_REVIEW_STATUSES))
            raise BenchmarkInputError(
                f"{path.name}: row {row_number} has invalid review_status "
                f"{review_status!r}; expected one of {allowed}"
            )
        if review_status != "rejected" and common_variable == MISSING_MAPPING:
            raise BenchmarkInputError(
                f"{path.name}: row {row_number} has review_status {review_status!r} "
                f"but common variable is {MISSING_MAPPING!r}"
            )

        entity_key = (source_study, source_variable)
        if entity_key in seen:
            first_row = seen[entity_key]
            raise BenchmarkInputError(
                f"{path.name}: duplicate mapping entity {entity_key!r} "
                f"at rows {first_row} and {row_number}"
            )
        seen[entity_key] = row_number
        rows.append(
            {
                "source_study": source_study,
                "source_variable": source_variable,
                "common_variable": common_variable,
                "review_status": review_status,
            }
        )
    return rows, fieldnames


def _decimal_score(value: Any, path: Path, row_number: int | str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} overall_score must be a finite decimal"
        )
    try:
        score = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} overall_score must be a finite decimal"
        ) from None
    if not score.is_finite():
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} overall_score must be a finite decimal"
        )
    if score < Decimal("0") or score > Decimal("1"):
        raise BenchmarkInputError(
            f"{path.name}: row {row_number} overall_score must be between 0 and 1"
        )
    return score


def _read_predicted_quality(path: Path) -> tuple[dict[str, Decimal], list[str]]:
    try:
        value = read_json(path)
    except ValueError as exc:
        raise BenchmarkInputError(f"{path.name}: invalid JSON: {exc}") from exc
    if not isinstance(value, list):
        raise BenchmarkInputError(
            f"{path.name}: expected a JSON array of quality-score rows"
        )

    scores: dict[str, Decimal] = {}
    seen_rows: dict[str, int] = {}
    columns: set[str] = set()
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            raise BenchmarkInputError(f"{path.name}: row {index} must be a JSON object")
        columns.update(str(column) for column in row)
        raw_study_id = row.get("study_id")
        if not isinstance(raw_study_id, str) or not raw_study_id.strip():
            raise BenchmarkInputError(
                f"{path.name}: row {index} study_id must be a nonempty string"
            )
        study_id = raw_study_id.strip()
        if "overall_score" not in row:
            raise BenchmarkInputError(
                f"{path.name}: row {index} is missing required field 'overall_score'"
            )
        if study_id in scores:
            raise BenchmarkInputError(
                f"{path.name}: duplicate quality-score study_id {study_id!r} "
                f"at rows {seen_rows[study_id]} and {index}"
            )
        seen_rows[study_id] = index
        scores[study_id] = _decimal_score(row["overall_score"], path, index)
    return scores, sorted(columns)


def _read_gold_quality(path: Path) -> tuple[dict[str, Decimal], list[str]]:
    fieldnames, rows = _read_csv_strict(path)
    required_columns = {"study_id", "overall_score"}
    missing_columns = sorted(required_columns - set(fieldnames))
    if missing_columns:
        raise BenchmarkInputError(
            f"{path.name}: missing required columns: {', '.join(missing_columns)}"
        )

    scores: dict[str, Decimal] = {}
    seen_rows: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        study_id = _required_text(row, "study_id", path, row_number)
        score_text = _required_text(row, "overall_score", path, row_number)
        if study_id in scores:
            raise BenchmarkInputError(
                f"{path.name}: duplicate quality-score study_id {study_id!r} "
                f"at rows {seen_rows[study_id]} and {row_number}"
            )
        seen_rows[study_id] = row_number
        scores[study_id] = _decimal_score(score_text, path, row_number)
    return scores, fieldnames


def _mapping_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row["source_study"],
        row["source_variable"],
        row["common_variable"],
        row["review_status"],
    )


def _entity_key(row: dict[str, str]) -> tuple[str, str]:
    return row["source_study"], row["source_variable"]


def _is_mapped(row: dict[str, str]) -> bool:
    return row["common_variable"] != MISSING_MAPPING


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def _wilson_95_interval(numerator: int, denominator: int) -> dict[str, float] | None:
    if denominator == 0:
        return None
    proportion = numerator / denominator
    z_squared = WILSON_Z_95**2
    scale = 1 + z_squared / denominator
    center = (proportion + z_squared / (2 * denominator)) / scale
    half_width = (
        WILSON_Z_95
        * math.sqrt(
            proportion * (1 - proportion) / denominator
            + z_squared / (4 * denominator**2)
        )
        / scale
    )
    return {
        "lower": round(max(0.0, center - half_width), 6),
        "upper": round(min(1.0, center + half_width), 6),
    }


def _proportion_result(
    metric_name: str,
    numerator: int,
    denominator: int,
    definition: str,
    *,
    legacy_details: dict[str, Any] | None = None,
) -> BenchmarkResult:
    value = _ratio(numerator, denominator)
    details: dict[str, Any] = {
        "numerator": numerator,
        "denominator": denominator if denominator else None,
        "definition": definition,
        "applicability": "applicable" if value is not None else "not_applicable",
        "undefined_reason": None if value is not None else "zero_denominator",
        "wilson_95_interval": _wilson_95_interval(numerator, denominator),
    }
    details.update(legacy_details or {})
    return BenchmarkResult(metric_name=metric_name, value=_rounded(value), details=details)


def _mapping_case_results(
    predicted_rows: list[dict[str, str]],
    gold_rows: list[dict[str, str]],
) -> list[BenchmarkCaseResult]:
    predicted_by_entity = {_entity_key(row): row for row in predicted_rows}
    gold_by_entity = {_entity_key(row): row for row in gold_rows}
    entity_keys = sorted(set(predicted_by_entity) | set(gold_by_entity))
    cases: list[BenchmarkCaseResult] = []

    for source_study, source_variable in entity_keys:
        entity_key = (source_study, source_variable)
        predicted = predicted_by_entity.get(entity_key)
        gold = gold_by_entity.get(entity_key)
        reason_codes: list[str] = []

        if predicted is None:
            reason_codes.append("missing_prediction")
        elif gold is None:
            reason_codes.append("unexpected_prediction")
        else:
            if predicted["common_variable"] != gold["common_variable"]:
                reason_codes.append("common_variable_mismatch")
            if predicted["review_status"] != gold["review_status"]:
                reason_codes.append("review_status_mismatch")

        predicted_is_auto_accept = (
            predicted is not None
            and predicted["review_status"] == "accepted"
            and _is_mapped(predicted)
        )
        gold_confirms_auto_accept = (
            gold is not None
            and gold["review_status"] == "accepted"
            and predicted is not None
            and predicted["common_variable"] == gold["common_variable"]
        )
        if predicted_is_auto_accept and not gold_confirms_auto_accept:
            reason_codes.append("unsafe_auto_accept")

        common_variable = (
            gold["common_variable"]
            if gold is not None
            else predicted["common_variable"] if predicted is not None else None
        )
        ordered_reason_codes = [
            code for code in CASE_OUTCOME_PRECEDENCE if code in reason_codes
        ]
        cases.append(
            BenchmarkCaseResult(
                case_type="mapping",
                source_study=source_study,
                source_variable=source_variable,
                common_variable=common_variable,
                outcome=(
                    ordered_reason_codes[0]
                    if ordered_reason_codes
                    else "correct"
                ),
                reason_codes=ordered_reason_codes,
                gold=(
                    {
                        "common_variable": gold["common_variable"],
                        "review_status": gold["review_status"],
                    }
                    if gold is not None
                    else None
                ),
                predicted=(
                    {
                        "common_variable": predicted["common_variable"],
                        "review_status": predicted["review_status"],
                    }
                    if predicted is not None
                    else None
                ),
            )
        )
    return cases


def _quality_case_results(
    predicted_scores: dict[str, Decimal],
    gold_scores: dict[str, Decimal],
) -> list[BenchmarkCaseResult]:
    cases: list[BenchmarkCaseResult] = []
    for study_id in sorted(set(predicted_scores) | set(gold_scores)):
        predicted = predicted_scores.get(study_id)
        gold = gold_scores.get(study_id)
        reason_codes: list[str] = []
        absolute_difference: Decimal | None = None
        within_tolerance: bool | None = None

        if predicted is None:
            reason_codes.append("missing_prediction")
        elif gold is None:
            reason_codes.append("unexpected_prediction")
        else:
            absolute_difference = abs(predicted - gold)
            within_tolerance = absolute_difference <= QUALITY_SCORE_TOLERANCE
            if not within_tolerance:
                reason_codes.append("quality_score_outside_tolerance")

        ordered_reason_codes = [
            code for code in CASE_OUTCOME_PRECEDENCE if code in reason_codes
        ]
        cases.append(
            BenchmarkCaseResult(
                case_type="quality",
                source_study=study_id,
                outcome=(
                    ordered_reason_codes[0]
                    if ordered_reason_codes
                    else "correct"
                ),
                reason_codes=ordered_reason_codes,
                gold=(
                    {"overall_score": float(gold)}
                    if gold is not None
                    else None
                ),
                predicted=(
                    {"overall_score": float(predicted)}
                    if predicted is not None
                    else None
                ),
                absolute_difference=(
                    float(absolute_difference)
                    if absolute_difference is not None
                    else None
                ),
                within_tolerance=within_tolerance,
            )
        )
    return cases


def _disagreement_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        if case["outcome"] == "correct":
            continue
        gold = case.get("gold") or {}
        predicted = case.get("predicted") or {}
        rows.append(
            {
                "case_type": case["case_type"],
                "source_study": case["source_study"],
                "source_variable": case.get("source_variable") or "",
                "common_variable": case.get("common_variable") or "",
                "outcome": case["outcome"],
                "reason_codes": ";".join(case.get("reason_codes", [])),
                "gold_common_variable": gold.get("common_variable", ""),
                "predicted_common_variable": predicted.get("common_variable", ""),
                "gold_review_status": gold.get("review_status", ""),
                "predicted_review_status": predicted.get("review_status", ""),
                "gold_overall_score": gold.get("overall_score", ""),
                "predicted_overall_score": predicted.get("overall_score", ""),
                "absolute_difference": (
                    case["absolute_difference"]
                    if case.get("absolute_difference") is not None
                    else ""
                ),
                "within_tolerance": (
                    case["within_tolerance"]
                    if case.get("within_tolerance") is not None
                    else ""
                ),
            }
        )
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_digest(
    role: str,
    path: Path,
    *,
    state: str,
    row_count: int | None,
    columns: list[str],
) -> BenchmarkArtifactDigest:
    return BenchmarkArtifactDigest(
        role=role,
        path=Path(path.name).as_posix(),
        state=state,
        row_count=row_count,
        columns=columns,
        sha256=_sha256(path) if state == "present" else None,
    )


def _compute_metrics(
    predicted_rows: list[dict[str, str]],
    gold_rows: list[dict[str, str]],
    predicted_quality: dict[str, Decimal],
    gold_quality: dict[str, Decimal],
    *,
    quality_inputs_present: bool,
) -> list[BenchmarkResult]:
    predicted_candidate = {
        _mapping_key(row)
        for row in predicted_rows
        if row["review_status"] in {"accepted", "requires_human_review"}
        and _is_mapped(row)
    }
    gold_candidate = {
        _mapping_key(row)
        for row in gold_rows
        if row["review_status"] != "rejected" and _is_mapped(row)
    }
    candidate_true_positive = len(predicted_candidate & gold_candidate)
    candidate_false_positive = len(predicted_candidate - gold_candidate)
    candidate_false_negative = len(gold_candidate - predicted_candidate)
    candidate_f1_numerator = 2 * candidate_true_positive
    candidate_f1_denominator = (
        candidate_f1_numerator
        + candidate_false_positive
        + candidate_false_negative
    )
    candidate_f1 = _ratio(candidate_f1_numerator, candidate_f1_denominator)
    f1_undefined_reason = None if candidate_f1 is not None else "zero_denominator"

    predicted_accepted = {
        _mapping_key(row)
        for row in predicted_rows
        if row["review_status"] == "accepted" and _is_mapped(row)
    }
    gold_accepted = {
        _mapping_key(row)
        for row in gold_rows
        if row["review_status"] == "accepted" and _is_mapped(row)
    }
    accepted_true_positive = len(predicted_accepted & gold_accepted)
    unsafe_auto_accepts = len(predicted_accepted - gold_accepted)

    predicted_review = {
        _mapping_key(row)
        for row in predicted_rows
        if row["review_status"] == "requires_human_review" and _is_mapped(row)
    }
    gold_review = {
        _mapping_key(row)
        for row in gold_rows
        if row["review_status"] == "requires_human_review" and _is_mapped(row)
    }
    review_captured = len(predicted_review & gold_review)

    predicted_by_entity = {_entity_key(row): row for row in predicted_rows}
    gold_by_entity = {_entity_key(row): row for row in gold_rows}
    status_correct = sum(
        1
        for entity_key, gold_row in gold_by_entity.items()
        if entity_key in predicted_by_entity
        and predicted_by_entity[entity_key]["review_status"]
        == gold_row["review_status"]
        and predicted_by_entity[entity_key]["common_variable"]
        == gold_row["common_variable"]
    )

    quality_hits = sum(
        1
        for study_id, gold_score in gold_quality.items()
        if study_id in predicted_quality
        and abs(predicted_quality[study_id] - gold_score) <= QUALITY_SCORE_TOLERANCE
    )
    quality_matched = len(set(predicted_quality) & set(gold_quality))

    f1_details: dict[str, Any] = {
        "numerator": candidate_f1_numerator,
        "denominator": (
            candidate_f1_denominator if candidate_f1_denominator else None
        ),
        "definition": (
            "Two times the exact candidate true positives, divided by two times "
            "true positives plus candidate false positives and false negatives. "
            "This F1 score is derived and does not receive a Wilson interval."
        ),
        "applicability": (
            "applicable" if candidate_f1 is not None else "not_applicable"
        ),
        "undefined_reason": f1_undefined_reason,
        "wilson_95_interval": None,
        "precision_denominator": len(predicted_candidate),
        "recall_denominator": len(gold_candidate),
        "true_positive": candidate_true_positive,
        "false_positive": candidate_false_positive,
        "false_negative": candidate_false_negative,
    }

    quality_result = _proportion_result(
        "quality_score_agreement_within_0.15",
        quality_hits,
        len(gold_quality),
        (
            "Gold quality-score studies with a prediction within an inclusive "
            "Decimal tolerance of 0.15, divided by all gold quality-score studies; "
            "missing predictions are failures."
        ),
        legacy_details={
            "within_tolerance": quality_hits,
            "compared": len(gold_quality),
            "matched_predictions": quality_matched,
            "tolerance": 0.15,
            "tolerance_decimal": str(QUALITY_SCORE_TOLERANCE),
            "quality_inputs_present": quality_inputs_present,
        },
    )
    if not quality_inputs_present:
        quality_result.details["undefined_reason"] = "quality_inputs_not_provided"

    return [
        _proportion_result(
            "candidate_precision",
            candidate_true_positive,
            len(predicted_candidate),
            (
                "Exact predicted study, source-variable, common-variable, and "
                "review-status candidate tuples confirmed by a non-rejected expert "
                "tuple, divided by all predicted accepted or review-required mapped "
                "candidates."
            ),
            legacy_details={
                "true_positive": candidate_true_positive,
                "predicted_candidate": len(predicted_candidate),
            },
        ),
        _proportion_result(
            "candidate_recall",
            candidate_true_positive,
            len(gold_candidate),
            (
                "Exact predicted study, source-variable, common-variable, and "
                "review-status candidate tuples confirmed by a non-rejected expert "
                "tuple, divided by all non-rejected mapped expert candidates."
            ),
            legacy_details={
                "true_positive": candidate_true_positive,
                "gold_candidate": len(gold_candidate),
            },
        ),
        BenchmarkResult(
            metric_name="candidate_f1",
            value=_rounded(candidate_f1),
            details=f1_details,
        ),
        _proportion_result(
            "auto_accept_precision",
            accepted_true_positive,
            len(predicted_accepted),
            (
                "Exact predicted automatic accepts that experts also marked accepted, "
                "divided by all predicted mapped automatic accepts."
            ),
            legacy_details={
                "safe_auto_accepts": accepted_true_positive,
                "predicted_auto_accepts": len(predicted_accepted),
            },
        ),
        _proportion_result(
            "auto_accept_recall",
            accepted_true_positive,
            len(gold_accepted),
            (
                "Exact predicted automatic accepts that experts also marked accepted, "
                "divided by all mapped expert accepts."
            ),
            legacy_details={
                "safe_auto_accepts": accepted_true_positive,
                "gold_accepted": len(gold_accepted),
            },
        ),
        _proportion_result(
            "unsafe_auto_accept_rate",
            unsafe_auto_accepts,
            len(predicted_accepted),
            (
                "Predicted mapped automatic accepts not confirmed as the same accepted "
                "expert mapping, divided by all predicted mapped automatic accepts."
            ),
            legacy_details={
                "unsafe_auto_accepts": unsafe_auto_accepts,
                "predicted_auto_accepts": len(predicted_accepted),
                "release_target": 0.0,
            },
        ),
        _proportion_result(
            "review_capture_rate",
            review_captured,
            len(gold_review),
            (
                "Exact expert review-required mappings routed to review by the "
                "prediction, divided by all mapped expert review-required cases."
            ),
            legacy_details={
                "correctly_routed_to_review": review_captured,
                "gold_review_required": len(gold_review),
            },
        ),
        _proportion_result(
            "review_status_accuracy",
            status_correct,
            len(gold_by_entity),
            (
                "Gold mapping entities with both the exact expert common variable and "
                "exact expert review status, divided by all gold mapping entities; "
                "missing predictions are incorrect and extras are reported separately."
            ),
            legacy_details={"correct": status_correct, "compared": len(gold_by_entity)},
        ),
        quality_result,
    ]


def benchmark(
    predicted_dir: str | Path,
    gold_dir: str | Path,
    out_dir: str | Path,
) -> list[BenchmarkResult]:
    """Run a strict, deterministic benchmark and write its review artifacts.

    All source artifacts are validated before any output is written. The function
    deliberately returns only the stable list of nine aggregate metrics; case-level
    evidence, disagreements, provenance, and the report are written under ``out_dir``.
    """

    predicted_dir = Path(predicted_dir)
    gold_dir = Path(gold_dir)
    out_dir = Path(out_dir)
    input_paths, quality_inputs_present = _require_input_files(
        predicted_dir, gold_dir
    )

    predicted_crosswalk_path = input_paths["predicted_crosswalk"]
    gold_mappings_path = input_paths["gold_variable_mappings"]
    predicted_rows, predicted_mapping_columns = _read_mapping_rows(
        predicted_crosswalk_path,
        common_variable_column="proposed_common_variable",
    )
    gold_rows, gold_mapping_columns = _read_mapping_rows(
        gold_mappings_path,
        common_variable_column="common_variable",
    )
    predicted_quality_path = input_paths["predicted_quality_scores"]
    gold_quality_path = input_paths["gold_quality_scores"]
    if quality_inputs_present:
        predicted_quality, predicted_quality_columns = _read_predicted_quality(
            predicted_quality_path
        )
        gold_quality, gold_quality_columns = _read_gold_quality(gold_quality_path)
    else:
        predicted_quality = {}
        gold_quality = {}
        predicted_quality_columns = []
        gold_quality_columns = []

    results = _compute_metrics(
        predicted_rows,
        gold_rows,
        predicted_quality,
        gold_quality,
        quality_inputs_present=quality_inputs_present,
    )
    mapping_cases = _mapping_case_results(predicted_rows, gold_rows)
    quality_cases = _quality_case_results(predicted_quality, gold_quality)
    cases = mapping_cases + quality_cases
    result_rows = [to_plain(result) for result in results]
    case_rows = [to_plain(case) for case in cases]
    disagreements = _disagreement_rows(case_rows)
    input_artifacts = [
        _artifact_digest(
            "predicted_crosswalk",
            predicted_crosswalk_path,
            state="present",
            row_count=len(predicted_rows),
            columns=predicted_mapping_columns,
        ),
        _artifact_digest(
            "predicted_quality_scores",
            predicted_quality_path,
            state="present" if quality_inputs_present else "not_provided",
            row_count=len(predicted_quality) if quality_inputs_present else None,
            columns=predicted_quality_columns,
        ),
        _artifact_digest(
            "gold_variable_mappings",
            gold_mappings_path,
            state="present",
            row_count=len(gold_rows),
            columns=gold_mapping_columns,
        ),
        _artifact_digest(
            "gold_quality_scores",
            gold_quality_path,
            state="present" if quality_inputs_present else "not_provided",
            row_count=len(gold_quality) if quality_inputs_present else None,
            columns=gold_quality_columns,
        ),
    ]
    run_bundle = _BenchmarkRunBundle(
        results=results,
        result_rows=result_rows,
        cases=cases,
        case_rows=case_rows,
        disagreement_rows=disagreements,
        input_artifacts=input_artifacts,
        manifest_metadata={
            "manifest_version": MANIFEST_VERSION,
            "benchmark_rule_set_version": RULE_SET_VERSION,
            "software_version": __version__,
            "quality_score_tolerance": str(QUALITY_SCORE_TOLERANCE),
        },
    )

    result_schema = project_schema_path("benchmark_result.schema.json")
    case_schema = project_schema_path("benchmark_case_result.schema.json")
    for row in run_bundle.result_rows:
        validate_or_raise(
            row,
            result_schema,
            label=f"benchmark metric {row['metric_name']}",
        )
    for row in run_bundle.case_rows:
        validate_or_raise(
            row,
            case_schema,
            label=(
                f"benchmark {row['case_type']} case "
                f"{row['source_study']}:{row.get('source_variable') or ''}"
            ),
        )

    results_path = out_dir / "benchmark_results.json"
    cases_path = out_dir / "benchmark_case_results.json"
    disagreements_path = out_dir / "benchmark_disagreements.csv"
    report_path = out_dir / "benchmark_report.md"
    manifest_path = out_dir / "benchmark_manifest.json"

    write_json(results_path, run_bundle.result_rows)
    write_json(cases_path, run_bundle.case_rows)
    write_csv_rows(
        disagreements_path,
        run_bundle.disagreement_rows,
        fieldnames=DISAGREEMENT_FIELDNAMES,
    )

    # Import lazily so the renderer can continue importing BenchmarkResult without
    # creating an import cycle. It receives the same immutable run bundle used by
    # the artifact writers and never reads a manifest that has not yet been written.
    from ..reports.render import render_benchmark_report

    render_benchmark_report(run_bundle.results, out_dir, run_bundle=run_bundle)

    outputs = [
        _artifact_digest(
            "benchmark_results",
            results_path,
            state="present",
            row_count=len(run_bundle.result_rows),
            columns=RESULT_FIELDNAMES,
        ),
        _artifact_digest(
            "benchmark_case_results",
            cases_path,
            state="present",
            row_count=len(run_bundle.case_rows),
            columns=CASE_FIELDNAMES,
        ),
        _artifact_digest(
            "benchmark_disagreements",
            disagreements_path,
            state="present",
            row_count=len(run_bundle.disagreement_rows),
            columns=DISAGREEMENT_FIELDNAMES,
        ),
        _artifact_digest(
            "benchmark_report",
            report_path,
            state="present",
            row_count=None,
            columns=[],
        ),
    ]
    manifest = BenchmarkManifest(
        manifest_version=MANIFEST_VERSION,
        rule_set_version=RULE_SET_VERSION,
        benchmark_rule_set_version=RULE_SET_VERSION,
        software_version=__version__,
        parameters={
            "quality_score_tolerance": str(QUALITY_SCORE_TOLERANCE),
            "quality_score_tolerance_comparison": "inclusive",
            "confidence_level": CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score",
            "mapping_entity_key": ["source_study", "source_variable"],
            "quality_metric_denominator": "all_gold_studies",
            "quality_inputs_present": quality_inputs_present,
            "case_outcome_precedence": CASE_OUTCOME_PRECEDENCE,
        },
        metric_names=METRIC_NAMES,
        case_counts={
            "total": len(cases),
            "mapping": len(mapping_cases),
            "quality": len(quality_cases),
            "correct": len(cases) - len(disagreements),
            "agreements": len(cases) - len(disagreements),
            "disagreements": len(disagreements),
        },
        inputs=run_bundle.input_artifacts,
        outputs=outputs,
        human_readable_output="benchmark_report.md",
    )
    manifest_row = to_plain(manifest)
    validate_or_raise(
        manifest_row,
        project_schema_path("benchmark_manifest.schema.json"),
        label="benchmark manifest",
    )
    write_json(manifest_path, manifest_row)
    return run_bundle.results

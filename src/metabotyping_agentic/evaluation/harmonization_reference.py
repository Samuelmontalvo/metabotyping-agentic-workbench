"""Compare an agent crosswalk with an independent curator reference.

The comparison is deliberately conservative: headline metrics are available only
when the two inputs contain exactly the same ``(source_study, source_variable)``
universe.  Missing or incomplete reference material is represented as a blocked
artifact rather than silently converted into a partial accuracy estimate.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io import write_csv_rows, write_json, write_text
from ..schemas import project_schema_path, validate_or_raise

COMPARATOR_VERSION = "1.0.0"
MANIFEST_VERSION = "1.0.0"
VALID_REVIEW_STATUSES = (
    "accepted",
    "rejected",
    "requires_human_review",
)
ENTITY_KEY_FIELDS = ("source_study", "source_variable")

COMPARISON_FILENAME = "harmonization_reference_comparison.json"
REPORT_FILENAME = "harmonization_reference_report.md"
MANIFEST_FILENAME = "harmonization_reference_manifest.json"
DISAGREEMENT_FILENAME = "harmonization_reference_disagreements.csv"

DISAGREEMENT_FIELDNAMES = [
    "source_study",
    "source_variable",
    "reference_common_variable",
    "predicted_common_variable",
    "reference_review_status",
    "predicted_review_status",
    "reason_codes",
]


class HarmonizationReferenceInputError(ValueError):
    """Raised before writing when an input violates the comparison contract."""


@dataclass(frozen=True)
class _MappingTable:
    rows: tuple[dict[str, str], ...]
    columns: tuple[str, ...]

    @property
    def by_entity(self) -> dict[tuple[str, str], dict[str, str]]:
        return {
            (row["source_study"], row["source_variable"]): row
            for row in self.rows
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _declared_relative_path(path: Path, declared_path: str | Path | None) -> str:
    candidate = Path(declared_path) if declared_path is not None else Path(path.name)
    if not str(candidate).strip():
        raise HarmonizationReferenceInputError("declared input paths may not be empty")
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HarmonizationReferenceInputError(
            f"declared input path must be repository-relative: {candidate}"
        )
    return candidate.as_posix()


def _read_csv_strict(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            if not fieldnames:
                raise HarmonizationReferenceInputError(
                    f"{path.name}: CSV header is missing"
                )
            if any(not name.strip() for name in fieldnames):
                raise HarmonizationReferenceInputError(
                    f"{path.name}: CSV header contains a blank column name"
                )
            if any(name != name.strip() for name in fieldnames):
                raise HarmonizationReferenceInputError(
                    f"{path.name}: CSV column names may not have surrounding whitespace"
                )
            if len(fieldnames) != len(set(fieldnames)):
                raise HarmonizationReferenceInputError(
                    f"{path.name}: duplicate CSV column names are not allowed"
                )
            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise HarmonizationReferenceInputError(
            f"{path.name}: CSV must be UTF-8 encoded"
        ) from exc

    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise HarmonizationReferenceInputError(
                f"{path.name}: row {row_number} has more values than the header"
            )
    return fieldnames, rows


def _required_text(
    row: dict[str, str], column: str, path: Path, row_number: int
) -> str:
    value = str(row.get(column) or "").strip()
    if not value:
        raise HarmonizationReferenceInputError(
            f"{path.name}: row {row_number} is missing required field {column!r}"
        )
    return value


def _aliased_text(
    row: dict[str, str],
    fieldnames: list[str],
    primary: str,
    alias: str,
    path: Path,
    row_number: int,
) -> str:
    available = {primary, alias} & set(fieldnames)
    if not available:
        raise HarmonizationReferenceInputError(
            f"{path.name}: header must contain {primary!r} or {alias!r}"
        )
    primary_value = str(row.get(primary) or "").strip()
    alias_value = str(row.get(alias) or "").strip()
    if primary_value and alias_value and primary_value != alias_value:
        raise HarmonizationReferenceInputError(
            f"{path.name}: row {row_number} has conflicting {primary} and {alias} values"
        )
    value = primary_value or alias_value
    if not value:
        raise HarmonizationReferenceInputError(
            f"{path.name}: row {row_number} is missing {primary}/{alias}"
        )
    return value


def _read_mapping_table(path: Path, *, role: str) -> _MappingTable:
    fieldnames, raw_rows = _read_csv_strict(path)
    missing_columns = sorted(
        {"source_variable", "review_status"} - set(fieldnames)
    )
    if missing_columns:
        raise HarmonizationReferenceInputError(
            f"{path.name}: missing required columns: {', '.join(missing_columns)}"
        )
    if not ({"source_study", "study_id"} & set(fieldnames)):
        raise HarmonizationReferenceInputError(
            f"{path.name}: missing required study column source_study/study_id"
        )
    if role == "reference" and "common_variable" not in fieldnames:
        raise HarmonizationReferenceInputError(
            f"{path.name}: independent reference must contain common_variable"
        )
    if role == "predicted" and not (
        {"common_variable", "proposed_common_variable"} & set(fieldnames)
    ):
        raise HarmonizationReferenceInputError(
            f"{path.name}: missing required common-variable column "
            "common_variable/proposed_common_variable"
        )

    normalized: list[dict[str, str]] = []
    seen: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
    for row_number, row in enumerate(raw_rows, start=2):
        source_study = _aliased_text(
            row,
            fieldnames,
            "source_study",
            "study_id",
            path,
            row_number,
        )
        source_variable = _required_text(
            row, "source_variable", path, row_number
        )
        if role == "predicted":
            common_variable = _aliased_text(
                row,
                fieldnames,
                "common_variable",
                "proposed_common_variable",
                path,
                row_number,
            )
        else:
            common_variable = _required_text(
                row, "common_variable", path, row_number
            )
        review_status = _required_text(row, "review_status", path, row_number)
        if review_status not in VALID_REVIEW_STATUSES:
            raise HarmonizationReferenceInputError(
                f"{path.name}: row {row_number} has invalid review_status "
                f"{review_status!r}; expected one of "
                + ", ".join(VALID_REVIEW_STATUSES)
            )

        normalized_row = {
            "source_study": source_study,
            "source_variable": source_variable,
            "common_variable": common_variable,
            "review_status": review_status,
        }
        entity = (source_study, source_variable)
        if entity in seen:
            first_row_number, first_row = seen[entity]
            duplicate_kind = (
                "duplicate"
                if first_row == normalized_row
                else "conflicting duplicate"
            )
            raise HarmonizationReferenceInputError(
                f"{path.name}: {duplicate_kind} entity key {entity!r} "
                f"at rows {first_row_number} and {row_number}"
            )
        seen[entity] = (row_number, normalized_row)
        normalized.append(normalized_row)

    return _MappingTable(rows=tuple(normalized), columns=tuple(fieldnames))


def _input_record(
    *,
    role: str,
    declared_path: str,
    path: Path,
    state: str,
    table: _MappingTable | None,
) -> dict[str, Any]:
    return {
        "role": role,
        "declared_path": declared_path,
        "state": state,
        "sha256": _sha256(path) if state == "present" else None,
        "row_count": len(table.rows) if table is not None else None,
        "columns": list(table.columns) if table is not None else [],
    }


def _entity_objects(entities: set[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"source_study": source_study, "source_variable": source_variable}
        for source_study, source_variable in sorted(entities)
    ]


def _proportion_metric(
    numerator: int,
    denominator: int,
    denominator_label: str,
    definition: str,
) -> dict[str, Any]:
    return {
        "value": (
            round(numerator / denominator, 6) if denominator else None
        ),
        "numerator": numerator,
        "denominator": denominator,
        "denominator_label": denominator_label,
        "unit": "proportion",
        "undefined_reason": None if denominator else "zero_denominator",
        "definition": definition,
    }


def _count_metric(value: int, definition: str) -> dict[str, Any]:
    return {
        "value": value,
        "numerator": value,
        "denominator": None,
        "denominator_label": None,
        "unit": "count",
        "undefined_reason": None,
        "definition": definition,
    }


def _compute_metrics(
    predicted: dict[tuple[str, str], dict[str, str]],
    reference: dict[tuple[str, str], dict[str, str]],
) -> dict[str, dict[str, Any]]:
    entities = sorted(reference)
    mapping_matches = sum(
        predicted[key]["common_variable"] == reference[key]["common_variable"]
        for key in entities
    )
    status_matches = sum(
        predicted[key]["review_status"] == reference[key]["review_status"]
        for key in entities
    )
    predicted_accepted = [
        key for key in entities if predicted[key]["review_status"] == "accepted"
    ]
    reference_accepted = [
        key for key in entities if reference[key]["review_status"] == "accepted"
    ]
    safe_accepted = [
        key
        for key in predicted_accepted
        if reference[key]["review_status"] == "accepted"
        and predicted[key]["common_variable"]
        == reference[key]["common_variable"]
    ]
    unsafe_accepted_count = len(predicted_accepted) - len(safe_accepted)
    reference_review_required = [
        key
        for key in entities
        if reference[key]["review_status"] == "requires_human_review"
    ]
    captured_review_required = sum(
        predicted[key]["review_status"] == "requires_human_review"
        and predicted[key]["common_variable"]
        == reference[key]["common_variable"]
        for key in reference_review_required
    )

    return {
        "exact_mapping_agreement": _proportion_metric(
            mapping_matches,
            len(entities),
            "all_reference_entities",
            "Rows with the exact same common_variable, divided by all entities "
            "in the exact shared reference universe.",
        ),
        "review_status_accuracy": _proportion_metric(
            status_matches,
            len(entities),
            "all_reference_entities",
            "Rows with the exact same review_status, divided by all entities in "
            "the exact shared reference universe.",
        ),
        "accepted_mapping_precision": _proportion_metric(
            len(safe_accepted),
            len(predicted_accepted),
            "predicted_accepted_entities",
            "Predicted accepted rows confirmed as the exact accepted reference "
            "mapping, divided by all predicted accepted rows.",
        ),
        "accepted_mapping_recall": _proportion_metric(
            len(safe_accepted),
            len(reference_accepted),
            "reference_accepted_entities",
            "Exact accepted reference mappings recovered as accepted, divided by "
            "all reference accepted rows.",
        ),
        "unsafe_auto_accept_count": _count_metric(
            unsafe_accepted_count,
            "Number of predicted accepted rows not confirmed as the exact accepted "
            "reference mapping.",
        ),
        "unsafe_auto_accept_rate": _proportion_metric(
            unsafe_accepted_count,
            len(predicted_accepted),
            "predicted_accepted_entities",
            "Predicted accepted rows not confirmed as the exact accepted reference "
            "mapping, divided by all predicted accepted rows.",
        ),
        "review_required_capture": _proportion_metric(
            captured_review_required,
            len(reference_review_required),
            "reference_review_required_entities",
            "Exact reference mappings requiring human review that were mapped "
            "identically and routed to human review, divided by all reference "
            "review-required rows.",
        ),
    }


def _disagreements(
    predicted: dict[tuple[str, str], dict[str, str]],
    reference: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_study, source_variable in sorted(reference):
        key = (source_study, source_variable)
        predicted_row = predicted[key]
        reference_row = reference[key]
        reason_codes: list[str] = []
        mapping_matches = (
            predicted_row["common_variable"] == reference_row["common_variable"]
        )
        status_matches = (
            predicted_row["review_status"] == reference_row["review_status"]
        )
        if not mapping_matches:
            reason_codes.append("common_variable_mismatch")
        if not status_matches:
            reason_codes.append("review_status_mismatch")
        if predicted_row["review_status"] == "accepted" and not (
            mapping_matches and reference_row["review_status"] == "accepted"
        ):
            reason_codes.append("unsafe_auto_accept")
        if not reason_codes:
            continue
        rows.append(
            {
                "source_study": source_study,
                "source_variable": source_variable,
                "reference_common_variable": reference_row["common_variable"],
                "predicted_common_variable": predicted_row["common_variable"],
                "reference_review_status": reference_row["review_status"],
                "predicted_review_status": predicted_row["review_status"],
                "reason_codes": ";".join(reason_codes),
            }
        )
    return rows


def _comparison_payload(
    *,
    status: str,
    inputs: list[dict[str, Any]],
    predicted_count: int,
    reference_count: int | None,
    missing_from_prediction: set[tuple[str, str]] | None = None,
    extra_in_prediction: set[tuple[str, str]] | None = None,
    metrics: dict[str, dict[str, Any]] | None = None,
    disagreement_count: int | None = None,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    missing = missing_from_prediction or set()
    extra = extra_in_prediction or set()
    exact_match = (
        None
        if reference_count is None
        else not missing and not extra and reference_count > 0
    )
    return {
        "artifact_type": "harmonization_reference_comparison",
        "comparator_version": COMPARATOR_VERSION,
        "status": status,
        "headline_metrics_available": status == "complete",
        "blocked_reason": blocked_reason,
        "inputs": inputs,
        "dataset_universe": {
            "entity_key": list(ENTITY_KEY_FIELDS),
            "predicted_count": predicted_count,
            "reference_count": reference_count,
            "exact_match": exact_match,
            "missing_from_prediction": _entity_objects(missing),
            "extra_in_prediction": _entity_objects(extra),
        },
        "metrics": metrics,
        "disagreement_count": disagreement_count,
        "disagreement_artifact": (
            DISAGREEMENT_FILENAME if status == "complete" else None
        ),
        "interpretation": (
            "Comparison with an independent curator reference; this artifact does "
            "not by itself establish a gold standard or authorize harmonization."
        ),
    }


def _format_metric(value: Any, unit: str) -> str:
    if value is None:
        return "not defined"
    if unit == "count":
        return str(value)
    return f"{value:.3f}"


def _render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Independent Curator Harmonization Comparison",
        "",
        f"**Status:** `{payload['status']}`",
        "",
    ]
    if payload["status"] != "complete":
        lines.extend(
            [
                "Headline performance metrics were not computed.",
                "",
                f"**Blocked reason:** {payload['blocked_reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Declared inputs",
            "",
            "| Role | Declared path | State | Rows | SHA-256 |",
            "|---|---|---:|---:|---|",
        ]
    )
    for item in payload["inputs"]:
        rows = "not available" if item["row_count"] is None else item["row_count"]
        digest = item["sha256"] or "not available"
        lines.append(
            f"| {item['role']} | `{item['declared_path']}` | {item['state']} | "
            f"{rows} | `{digest}` |"
        )

    universe = payload["dataset_universe"]
    lines.extend(
        [
            "",
            "## Dataset universe gate",
            "",
            f"- Entity key: `{', '.join(universe['entity_key'])}`",
            f"- Predicted entities: {universe['predicted_count']}",
            "- Reference entities: "
            + (
                "not available"
                if universe["reference_count"] is None
                else str(universe["reference_count"])
            ),
            "- Exact universe match: "
            + (
                "not assessable"
                if universe["exact_match"] is None
                else str(universe["exact_match"]).lower()
            ),
        ]
    )
    if universe["missing_from_prediction"]:
        lines.extend(["", "Reference-only entity keys:", ""])
        for item in universe["missing_from_prediction"]:
            lines.append(
                f"- `{item['source_study']} / {item['source_variable']}`"
            )
    if universe["extra_in_prediction"]:
        lines.extend(["", "Prediction-only entity keys:", ""])
        for item in universe["extra_in_prediction"]:
            lines.append(
                f"- `{item['source_study']} / {item['source_variable']}`"
            )

    if payload["status"] == "complete":
        lines.extend(
            [
                "",
                "## Headline metrics",
                "",
                "| Metric | Value | Numerator | Denominator | Denominator definition |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for name, metric in payload["metrics"].items():
            denominator = (
                "not applicable"
                if metric["denominator"] is None
                else str(metric["denominator"])
            )
            denominator_label = metric["denominator_label"] or "not applicable"
            lines.append(
                f"| {name} | {_format_metric(metric['value'], metric['unit'])} | "
                f"{metric['numerator']} | {denominator} | {denominator_label} |"
            )
        lines.extend(
            [
                "",
                f"Disagreements: {payload['disagreement_count']} (see "
                f"`{DISAGREEMENT_FILENAME}`).",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_digest(role: str, path: Path) -> dict[str, str]:
    return {
        "role": role,
        "path": path.name,
        "sha256": _sha256(path),
    }


def _write_artifacts(
    output_dir: Path,
    payload: dict[str, Any],
    disagreements: list[dict[str, str]] | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = output_dir / COMPARISON_FILENAME
    report_path = output_dir / REPORT_FILENAME
    disagreement_path = output_dir / DISAGREEMENT_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME

    write_json(comparison_path, payload)
    write_text(report_path, _render_report(payload))
    if disagreements is not None:
        write_csv_rows(
            disagreement_path,
            disagreements,
            fieldnames=DISAGREEMENT_FIELDNAMES,
        )
    else:
        disagreement_path.unlink(missing_ok=True)

    output_digests = [
        _artifact_digest("comparison_json", comparison_path),
        _artifact_digest("comparison_report", report_path),
    ]
    if disagreements is not None:
        output_digests.append(
            _artifact_digest("comparison_disagreements", disagreement_path)
        )
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "comparator_version": COMPARATOR_VERSION,
        "status": payload["status"],
        "entity_key": list(ENTITY_KEY_FIELDS),
        "valid_review_statuses": list(VALID_REVIEW_STATUSES),
        "exact_universe_required_for_headline_metrics": True,
        "inputs": payload["inputs"],
        "outputs": output_digests,
        "human_readable_output": REPORT_FILENAME,
    }
    write_json(manifest_path, manifest)


def compare_harmonization_reference(
    predicted_csv: str | Path,
    reference_csv: str | Path,
    output_dir: str | Path,
    *,
    predicted_declared_path: str | Path | None = None,
    reference_declared_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare crosswalks, writing deterministic artifacts for valid run states.

    Missing and empty curator references are valid *blocked* run states.  Malformed
    CSVs, invalid statuses, and duplicate/conflicting entity keys raise
    :class:`HarmonizationReferenceInputError` before the output directory is
    created or changed.
    """

    predicted_path = Path(predicted_csv)
    reference_path = Path(reference_csv)
    output_path = Path(output_dir)
    predicted_declared = _declared_relative_path(
        predicted_path, predicted_declared_path
    )
    reference_declared = _declared_relative_path(
        reference_path, reference_declared_path
    )

    if not predicted_path.is_file():
        raise FileNotFoundError(f"predicted crosswalk not found: {predicted_path}")
    predicted_table = _read_mapping_table(predicted_path, role="predicted")
    predicted_input = _input_record(
        role="predicted_crosswalk",
        declared_path=predicted_declared,
        path=predicted_path,
        state="present",
        table=predicted_table,
    )

    if not reference_path.exists():
        reference_input = _input_record(
            role="independent_curator_reference",
            declared_path=reference_declared,
            path=reference_path,
            state="missing",
            table=None,
        )
        payload = _comparison_payload(
            status="blocked_missing_reference",
            inputs=[predicted_input, reference_input],
            predicted_count=len(predicted_table.rows),
            reference_count=None,
            blocked_reason=(
                "The declared independent curator reference CSV is missing. No "
                "accuracy or safety metric can be estimated."
            ),
        )
        validate_or_raise(
            payload,
            project_schema_path("harmonization_reference_comparison.schema.json"),
            label="harmonization reference comparison",
        )
        _write_artifacts(output_path, payload, None)
        return payload
    if not reference_path.is_file():
        raise HarmonizationReferenceInputError(
            f"reference input is not a regular file: {reference_path}"
        )

    reference_table = (
        _MappingTable(rows=(), columns=())
        if reference_path.stat().st_size == 0
        else _read_mapping_table(reference_path, role="reference")
    )
    reference_input = _input_record(
        role="independent_curator_reference",
        declared_path=reference_declared,
        path=reference_path,
        state="present",
        table=reference_table,
    )
    inputs = [predicted_input, reference_input]
    if not reference_table.rows:
        payload = _comparison_payload(
            status="blocked_empty_reference",
            inputs=inputs,
            predicted_count=len(predicted_table.rows),
            reference_count=0,
            blocked_reason=(
                "The independent curator reference contains a valid header but no "
                "rows. No headline metrics were computed."
            ),
        )
        validate_or_raise(
            payload,
            project_schema_path("harmonization_reference_comparison.schema.json"),
            label="harmonization reference comparison",
        )
        _write_artifacts(output_path, payload, None)
        return payload

    predicted_by_entity = predicted_table.by_entity
    reference_by_entity = reference_table.by_entity
    predicted_entities = set(predicted_by_entity)
    reference_entities = set(reference_by_entity)
    missing_from_prediction = reference_entities - predicted_entities
    extra_in_prediction = predicted_entities - reference_entities
    if missing_from_prediction or extra_in_prediction:
        payload = _comparison_payload(
            status="blocked_dataset_universe_mismatch",
            inputs=inputs,
            predicted_count=len(predicted_entities),
            reference_count=len(reference_entities),
            missing_from_prediction=missing_from_prediction,
            extra_in_prediction=extra_in_prediction,
            blocked_reason=(
                "Predicted and independent-reference entity keys do not define the "
                "same evaluation universe. Partial-universe accuracy is withheld."
            ),
        )
        validate_or_raise(
            payload,
            project_schema_path("harmonization_reference_comparison.schema.json"),
            label="harmonization reference comparison",
        )
        _write_artifacts(output_path, payload, None)
        return payload

    metrics = _compute_metrics(predicted_by_entity, reference_by_entity)
    disagreements = _disagreements(predicted_by_entity, reference_by_entity)
    payload = _comparison_payload(
        status="complete",
        inputs=inputs,
        predicted_count=len(predicted_entities),
        reference_count=len(reference_entities),
        metrics=metrics,
        disagreement_count=len(disagreements),
    )
    validate_or_raise(
        payload,
        project_schema_path("harmonization_reference_comparison.schema.json"),
        label="harmonization reference comparison",
    )
    _write_artifacts(output_path, payload, disagreements)
    return payload


# A descriptive alias for callers that treat the comparison as a pipeline step.
run_harmonization_reference_comparison = compare_harmonization_reference

"""Deterministic, offline evaluation of a synthetic statin-exposure classifier.

This module intentionally implements a small closed-form model.  It is an
evaluation fixture for the workbench's reproducibility and generalization
plumbing, not a clinically validated medication detector.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import __version__
from ..schemas import project_schema_path, validate_or_raise

CLASSIFIER_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
ALGORITHM = "closed_form_diagonal_lda"
VARIANCE_FLOOR = 1e-12
OUTPUT_FILENAMES = (
    "model.json",
    "predictions.csv",
    "metrics.json",
    "model_card.md",
    "run_manifest.json",
)
PREDICTION_FIELDNAMES = (
    "sample_id",
    "cohort_id",
    "observed_statin_exposure",
    "decision_status",
    "predicted_statin_exposure",
    "statin_probability",
    "log_odds",
    "feature_count_used",
    "feature_count_expected",
    "feature_coverage",
    "features_used",
    "abstention_reason",
)


class MedicationClassifierInputError(ValueError):
    """Raised before any output is written when an input contract is violated."""


@dataclass(frozen=True)
class FeatureCatalog:
    """Validated feature-catalog values needed by the deterministic model."""

    catalog_id: str
    target_column: str
    sample_id_column: str
    cohort_id_column: str
    negative_label: str
    positive_label: str
    feature_names: tuple[str, ...]
    minimum_feature_count: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class DatasetRow:
    """One validated row; missing test features remain missing rather than zero-filled."""

    sample_id: str
    cohort_id: str
    label: str
    features: dict[str, float | None]


@dataclass(frozen=True)
class Dataset:
    """A validated labeled split."""

    role: str
    path: Path
    fieldnames: tuple[str, ...]
    rows: tuple[DatasetRow, ...]
    sha256: str


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 of a file without normalizing its bytes."""

    return _sha256_bytes(Path(path).read_bytes())


def _json_bytes(value: dict[str, Any]) -> bytes:
    text = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(
        handle,
        fieldnames=list(PREDICTION_FIELDNAMES),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise MedicationClassifierInputError(
                f"JSON object contains duplicate key {key!r}"
            )
        value[key] = item
    return value


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except MedicationClassifierInputError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MedicationClassifierInputError(f"Invalid {label} JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise MedicationClassifierInputError(f"{label} must be a JSON object")
    return value


def _validate_input_schema(
    value: dict[str, Any], schema_name: str, label: str
) -> None:
    try:
        validate_or_raise(value, project_schema_path(schema_name), label=label)
    except (ValueError, FileNotFoundError) as exc:
        raise MedicationClassifierInputError(str(exc)) from exc


def _load_feature_catalog(path: Path) -> FeatureCatalog:
    raw = _read_json_object(path, "feature catalog")
    _validate_input_schema(
        raw,
        "medication_classifier_feature_catalog.schema.json",
        "medication classifier feature catalog",
    )

    feature_names = tuple(item["name"] for item in raw["features"])
    if len(feature_names) != len(set(feature_names)):
        raise MedicationClassifierInputError("Feature names must be unique")

    id_columns = tuple(raw["id_columns"])
    reserved = {*id_columns, raw["target_column"]}
    overlap = sorted(set(feature_names) & reserved)
    if overlap:
        raise MedicationClassifierInputError(
            "Feature allowlist overlaps reserved columns: " + ", ".join(overlap)
        )

    minimum_feature_count = raw["minimum_feature_count"]
    if minimum_feature_count > len(feature_names):
        raise MedicationClassifierInputError(
            "minimum_feature_count exceeds the declared feature count"
        )

    return FeatureCatalog(
        catalog_id=raw["catalog_id"],
        target_column=raw["target_column"],
        sample_id_column=id_columns[0],
        cohort_id_column=id_columns[1],
        negative_label=raw["negative_label"],
        positive_label=raw["positive_label"],
        feature_names=feature_names,
        minimum_feature_count=minimum_feature_count,
        raw=raw,
    )


def _read_csv_strict(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing CSV input: {path}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            if not fieldnames:
                raise MedicationClassifierInputError(
                    f"{path.name}: CSV header is missing"
                )
            if any(not name.strip() for name in fieldnames):
                raise MedicationClassifierInputError(
                    f"{path.name}: blank CSV column names are not allowed"
                )
            if any(name != name.strip() for name in fieldnames):
                raise MedicationClassifierInputError(
                    f"{path.name}: CSV column names may not have surrounding whitespace"
                )
            if len(fieldnames) != len(set(fieldnames)):
                raise MedicationClassifierInputError(
                    f"{path.name}: duplicate CSV column names are not allowed"
                )
            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise MedicationClassifierInputError(
            f"{path.name}: CSV must be UTF-8 text"
        ) from exc

    if not rows:
        raise MedicationClassifierInputError(f"{path.name}: CSV contains no samples")
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise MedicationClassifierInputError(
                f"{path.name}: row {row_number} has more values than the header"
            )
    return fieldnames, rows


def _parse_finite_feature(
    raw_value: str | None,
    *,
    path: Path,
    row_number: int,
    feature_name: str,
    missing_allowed: bool,
) -> float | None:
    text = "" if raw_value is None else str(raw_value).strip()
    if not text:
        if missing_allowed:
            return None
        raise MedicationClassifierInputError(
            f"{path.name}: row {row_number} is missing training feature "
            f"{feature_name!r}"
        )
    try:
        value = float(text)
    except ValueError as exc:
        raise MedicationClassifierInputError(
            f"{path.name}: row {row_number} feature {feature_name!r} is not numeric"
        ) from exc
    if not math.isfinite(value):
        raise MedicationClassifierInputError(
            f"{path.name}: row {row_number} feature {feature_name!r} is not finite"
        )
    return value


def _load_dataset(path: Path, catalog: FeatureCatalog, role: str) -> Dataset:
    fieldnames, raw_rows = _read_csv_strict(path)
    required_columns = {
        catalog.sample_id_column,
        catalog.cohort_id_column,
        catalog.target_column,
    }
    missing_required = sorted(required_columns - set(fieldnames))
    if missing_required:
        raise MedicationClassifierInputError(
            f"{path.name}: missing required columns: {', '.join(missing_required)}"
        )

    if role == "train":
        missing_features = sorted(set(catalog.feature_names) - set(fieldnames))
        if missing_features:
            raise MedicationClassifierInputError(
                f"{path.name}: training data are missing allowlisted features: "
                + ", ".join(missing_features)
            )

    allowed_labels = {catalog.negative_label, catalog.positive_label}
    rows: list[DatasetRow] = []
    seen_sample_ids: set[str] = set()
    for row_number, raw_row in enumerate(raw_rows, start=2):
        sample_id = str(raw_row.get(catalog.sample_id_column) or "").strip()
        cohort_id = str(raw_row.get(catalog.cohort_id_column) or "").strip()
        label = str(raw_row.get(catalog.target_column) or "").strip()
        if not sample_id:
            raise MedicationClassifierInputError(
                f"{path.name}: row {row_number} has no sample identifier"
            )
        if sample_id in seen_sample_ids:
            raise MedicationClassifierInputError(
                f"{path.name}: duplicate sample identifier {sample_id!r}"
            )
        seen_sample_ids.add(sample_id)
        if not cohort_id:
            raise MedicationClassifierInputError(
                f"{path.name}: row {row_number} has no cohort identifier"
            )
        if label not in allowed_labels:
            raise MedicationClassifierInputError(
                f"{path.name}: row {row_number} label {label!r} is not one of "
                f"{sorted(allowed_labels)!r}"
            )

        features = {
            feature_name: _parse_finite_feature(
                raw_row.get(feature_name),
                path=path,
                row_number=row_number,
                feature_name=feature_name,
                missing_allowed=role == "test",
            )
            for feature_name in catalog.feature_names
        }
        rows.append(
            DatasetRow(
                sample_id=sample_id,
                cohort_id=cohort_id,
                label=label,
                features=features,
            )
        )

    labels_present = {row.label for row in rows}
    if role == "train" and labels_present != allowed_labels:
        raise MedicationClassifierInputError(
            f"{path.name}: training data must contain both binary labels"
        )
    if role == "train":
        class_counts = {
            label: sum(row.label == label for row in rows) for label in allowed_labels
        }
        if min(class_counts.values()) < 2:
            raise MedicationClassifierInputError(
                f"{path.name}: diagonal LDA requires at least two training samples "
                "in each class"
            )

    return Dataset(
        role=role,
        path=path,
        fieldnames=fieldnames,
        rows=tuple(rows),
        sha256=sha256_file(path),
    )


def _dataset_summary(dataset: Dataset, catalog: FeatureCatalog) -> dict[str, Any]:
    return {
        "sample_count": len(dataset.rows),
        "cohort_ids": sorted({row.cohort_id for row in dataset.rows}),
        "class_counts": {
            catalog.negative_label: sum(
                row.label == catalog.negative_label for row in dataset.rows
            ),
            catalog.positive_label: sum(
                row.label == catalog.positive_label for row in dataset.rows
            ),
        },
    }


def _verify_manifest_artifact(
    manifest: dict[str, Any],
    role: str,
    path: Path,
    digest: str,
) -> None:
    declared = manifest["artifacts"][role]
    if declared["path"] != path.name:
        raise MedicationClassifierInputError(
            f"Split manifest {role} path {declared['path']!r} does not match "
            f"provided file {path.name!r}"
        )
    if declared["sha256"] != digest:
        raise MedicationClassifierInputError(
            f"SHA-256 mismatch for {role}: expected {declared['sha256']}, got {digest}"
        )


def _validate_split_contract(
    manifest: dict[str, Any],
    manifest_path: Path,
    feature_catalog_path: Path,
    feature_catalog_sha256: str,
    train: Dataset,
    test: Dataset,
    catalog: FeatureCatalog,
) -> None:
    if manifest["target_column"] != catalog.target_column:
        raise MedicationClassifierInputError(
            "Split manifest and feature catalog disagree on target_column"
        )
    _verify_manifest_artifact(
        manifest,
        "feature_catalog",
        feature_catalog_path,
        feature_catalog_sha256,
    )
    _verify_manifest_artifact(manifest, "train", train.path, train.sha256)
    _verify_manifest_artifact(manifest, "test", test.path, test.sha256)

    for role, dataset in (("train", train), ("test", test)):
        expected = manifest["artifacts"][role]
        observed = _dataset_summary(dataset, catalog)
        for key in ("sample_count", "cohort_ids", "class_counts"):
            if expected[key] != observed[key]:
                raise MedicationClassifierInputError(
                    f"Split manifest {role} {key} does not match {dataset.path.name}"
                )

    train_samples = {row.sample_id for row in train.rows}
    test_samples = {row.sample_id for row in test.rows}
    sample_overlap = sorted(train_samples & test_samples)
    if sample_overlap:
        raise MedicationClassifierInputError(
            "Train/test sample identifiers overlap: " + ", ".join(sample_overlap[:5])
        )

    train_vectors = {
        tuple(row.features[name] for name in catalog.feature_names)
        for row in train.rows
    }
    test_vectors = {
        tuple(row.features[name] for name in catalog.feature_names)
        for row in test.rows
    }
    if train_vectors & test_vectors:
        raise MedicationClassifierInputError(
            "Train/test declared feature vectors overlap despite disjoint identifiers"
        )

    train_cohorts = {row.cohort_id for row in train.rows}
    test_cohorts = {row.cohort_id for row in test.rows}
    if len(train_cohorts) < 2:
        raise MedicationClassifierInputError(
            "Cold training data must contain at least two synthetic cohorts"
        )
    cohort_overlap = sorted(train_cohorts & test_cohorts)
    if cohort_overlap:
        raise MedicationClassifierInputError(
            "Train/test cohort identifiers overlap: " + ", ".join(cohort_overlap)
        )

    constraints = manifest["constraints"]
    required_true = (
        "sample_id_disjoint",
        "cohort_id_disjoint",
        "declared_feature_vectors_disjoint",
        "test_labels_excluded_from_model_fitting",
        "test_labels_excluded_from_scoring",
    )
    false_declarations = [name for name in required_true if constraints[name] is not True]
    if false_declarations:
        raise MedicationClassifierInputError(
            f"{manifest_path.name}: required split constraints are not asserted"
        )


def _validate_no_exact_label_copy_features(
    train: Dataset, catalog: FeatureCatalog
) -> None:
    leaked: list[str] = []
    for feature_name in catalog.feature_names:
        negative_values = {
            row.features[feature_name]
            for row in train.rows
            if row.label == catalog.negative_label
        }
        positive_values = {
            row.features[feature_name]
            for row in train.rows
            if row.label == catalog.positive_label
        }
        if (
            len(negative_values) == 1
            and len(positive_values) == 1
            and negative_values != positive_values
        ):
            leaked.append(feature_name)
    if leaked:
        raise MedicationClassifierInputError(
            "Allowlisted training features exactly encode the binary target: "
            + ", ".join(leaked)
        )


def _rounded(value: float, digits: int = 12) -> float:
    if not math.isfinite(value):
        raise MedicationClassifierInputError(
            "Model computation produced a non-finite numeric value"
        )
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def _fit_model(
    train: Dataset,
    catalog: FeatureCatalog,
    *,
    feature_catalog_sha256: str,
    split_id: str,
) -> dict[str, Any]:
    class_rows = {
        catalog.negative_label: [
            row for row in train.rows if row.label == catalog.negative_label
        ],
        catalog.positive_label: [
            row for row in train.rows if row.label == catalog.positive_label
        ],
    }
    sample_count = len(train.rows)
    means: dict[str, dict[str, float]] = {
        catalog.negative_label: {},
        catalog.positive_label: {},
    }
    centers: dict[str, float] = {}
    scales: dict[str, float] = {}

    for feature_name in catalog.feature_names:
        values = [row.features[feature_name] for row in train.rows]
        # Training validation guarantees that these values are finite floats.
        finite_values = [float(value) for value in values if value is not None]
        try:
            centers[feature_name] = math.fsum(finite_values) / sample_count
            for label, rows in class_rows.items():
                label_values = [float(row.features[feature_name]) for row in rows]
                means[label][feature_name] = math.fsum(label_values) / len(
                    label_values
                )

            within_class_ss = math.fsum(
                (
                    float(row.features[feature_name])
                    - means[row.label][feature_name]
                )
                ** 2
                for row in train.rows
            )
            pooled_variance = within_class_ss / (sample_count - 2)
            scales[feature_name] = math.sqrt(
                max(pooled_variance, VARIANCE_FLOOR)
            )
        except (OverflowError, ValueError) as exc:
            raise MedicationClassifierInputError(
                f"Non-finite training computation for feature {feature_name!r}"
            ) from exc
        computed = [
            centers[feature_name],
            scales[feature_name],
            *(means[label][feature_name] for label in class_rows),
        ]
        if not all(math.isfinite(value) for value in computed):
            raise MedicationClassifierInputError(
                f"Non-finite training computation for feature {feature_name!r}"
            )

    standardized_centroids = {
        label: {
            feature_name: _rounded(
                (means[label][feature_name] - centers[feature_name])
                / scales[feature_name]
            )
            for feature_name in catalog.feature_names
        }
        for label in (catalog.negative_label, catalog.positive_label)
    }
    coefficients = {
        feature_name: _rounded(
            standardized_centroids[catalog.positive_label][feature_name]
            - standardized_centroids[catalog.negative_label][feature_name]
        )
        for feature_name in catalog.feature_names
    }
    prior_negative = len(class_rows[catalog.negative_label]) / sample_count
    prior_positive = len(class_rows[catalog.positive_label]) / sample_count
    intercept = math.log(prior_positive / prior_negative) - 0.5 * sum(
        standardized_centroids[catalog.positive_label][feature_name] ** 2
        - standardized_centroids[catalog.negative_label][feature_name] ** 2
        for feature_name in catalog.feature_names
    )

    train_summary = _dataset_summary(train, catalog)
    model = {
        "schema_version": SCHEMA_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "model_type": ALGORITHM,
        "target_column": catalog.target_column,
        "negative_label": catalog.negative_label,
        "positive_label": catalog.positive_label,
        "decision_threshold": 0.5,
        "feature_allowlist": list(catalog.feature_names),
        "minimum_feature_count": catalog.minimum_feature_count,
        "training_provenance": {
            "split_id": split_id,
            "train_sha256": train.sha256,
            "feature_catalog_sha256": feature_catalog_sha256,
            **train_summary,
        },
        "preprocessing": {
            "fit_scope": "training_data_only",
            "missing_value_policy": "never_zero_fill; abstain_below_minimum_coverage",
            "center": {
                name: _rounded(centers[name]) for name in catalog.feature_names
            },
            "scale": {
                name: _rounded(scales[name]) for name in catalog.feature_names
            },
            "variance_floor": VARIANCE_FLOOR,
        },
        "parameters": {
            "class_priors": {
                catalog.negative_label: _rounded(prior_negative),
                catalog.positive_label: _rounded(prior_positive),
            },
            "standardized_centroids": standardized_centroids,
            "coefficients": coefficients,
            "intercept": _rounded(intercept),
        },
        "validation_status": "synthetic_only_not_clinically_validated",
        "clinically_validated": False,
    }
    return model


def _logistic(log_odds: float) -> float:
    if log_odds >= 0:
        return 1.0 / (1.0 + math.exp(-log_odds))
    exp_value = math.exp(log_odds)
    return exp_value / (1.0 + exp_value)


def _validate_model_feature_keys(
    model: dict[str, Any], catalog: FeatureCatalog
) -> None:
    expected = set(catalog.feature_names)
    mappings = {
        "preprocessing.center": model["preprocessing"]["center"],
        "preprocessing.scale": model["preprocessing"]["scale"],
        "parameters.coefficients": model["parameters"]["coefficients"],
        "parameters.standardized_centroids.negative": model["parameters"][
            "standardized_centroids"
        ][catalog.negative_label],
        "parameters.standardized_centroids.positive": model["parameters"][
            "standardized_centroids"
        ][catalog.positive_label],
    }
    for label, mapping in mappings.items():
        if set(mapping) != expected:
            raise RuntimeError(
                f"internal error: {label} keys differ from feature allowlist"
            )


def _format_float_roundtrip(value: float) -> str:
    if not math.isfinite(value):
        raise RuntimeError("internal error: cannot serialize a non-finite score")
    return "0" if value == 0 else format(value, ".17g")


def _score_test_rows(
    test: Dataset,
    model: dict[str, Any],
    catalog: FeatureCatalog,
) -> list[dict[str, Any]]:
    center = model["preprocessing"]["center"]
    scale = model["preprocessing"]["scale"]
    centroids = model["parameters"]["standardized_centroids"]
    priors = model["parameters"]["class_priors"]
    expected_count = len(catalog.feature_names)
    predictions: list[dict[str, Any]] = []

    for row in test.rows:
        available = [
            feature_name
            for feature_name in catalog.feature_names
            if row.features[feature_name] is not None
        ]
        used_count = len(available)
        coverage = used_count / expected_count
        base = {
            "sample_id": row.sample_id,
            "cohort_id": row.cohort_id,
            "observed_statin_exposure": row.label,
            "feature_count_used": used_count,
            "feature_count_expected": expected_count,
            "feature_coverage": f"{coverage:.6f}",
            "features_used": ";".join(available),
        }
        if used_count < catalog.minimum_feature_count:
            predictions.append(
                {
                    **base,
                    "decision_status": "abstained",
                    "predicted_statin_exposure": "",
                    "statin_probability": "",
                    "log_odds": "",
                    "abstention_reason": "insufficient_feature_coverage",
                }
            )
            continue

        log_odds = math.log(
            priors[catalog.positive_label] / priors[catalog.negative_label]
        )
        numerically_stable = math.isfinite(log_odds)
        for feature_name in available:
            try:
                z_value = (
                    float(row.features[feature_name]) - center[feature_name]
                ) / scale[feature_name]
                negative_centroid = centroids[catalog.negative_label][feature_name]
                positive_centroid = centroids[catalog.positive_label][feature_name]
                linear_term = z_value * (positive_centroid - negative_centroid)
                quadratic_term = 0.5 * (
                    positive_centroid**2 - negative_centroid**2
                )
                updated_log_odds = log_odds + linear_term - quadratic_term
            except (OverflowError, ValueError):
                numerically_stable = False
                break
            if not all(
                math.isfinite(value)
                for value in (
                    z_value,
                    linear_term,
                    quadratic_term,
                    updated_log_odds,
                )
            ):
                numerically_stable = False
                break
            log_odds = updated_log_odds

        if not numerically_stable:
            predictions.append(
                {
                    **base,
                    "decision_status": "abstained",
                    "predicted_statin_exposure": "",
                    "statin_probability": "",
                    "log_odds": "",
                    "abstention_reason": "numerical_instability",
                }
            )
            continue

        probability = _logistic(log_odds)
        if not math.isfinite(probability):
            predictions.append(
                {
                    **base,
                    "decision_status": "abstained",
                    "predicted_statin_exposure": "",
                    "statin_probability": "",
                    "log_odds": "",
                    "abstention_reason": "numerical_instability",
                }
            )
            continue
        reported_probability = float(_format_float_roundtrip(probability))
        predicted_label = (
            catalog.positive_label
            if reported_probability >= model["decision_threshold"]
            else catalog.negative_label
        )
        predictions.append(
            {
                **base,
                "decision_status": "scored",
                "predicted_statin_exposure": predicted_label,
                "statin_probability": _format_float_roundtrip(probability),
                "log_odds": _format_float_roundtrip(log_odds),
                "abstention_reason": "",
            }
        )
    return predictions


def _validate_predictions(
    predictions: list[dict[str, Any]], catalog: FeatureCatalog
) -> None:
    """Fail closed if an internal score row violates the output contract."""

    for row in predictions:
        features_used = [
            name for name in str(row["features_used"]).split(";") if name
        ]
        if len(features_used) != row["feature_count_used"]:
            raise RuntimeError("internal error: feature count does not match names")
        if not set(features_used).issubset(catalog.feature_names):
            raise RuntimeError("internal error: prediction used an undeclared feature")
        expected_coverage = row["feature_count_used"] / row["feature_count_expected"]
        if not math.isclose(
            float(row["feature_coverage"]),
            expected_coverage,
            rel_tol=0.0,
            abs_tol=5e-7,
        ):
            raise RuntimeError("internal error: inconsistent feature coverage")
        status = row["decision_status"]
        if status == "scored":
            probability = float(row["statin_probability"])
            log_odds = float(row["log_odds"])
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise RuntimeError("internal error: invalid statin probability")
            if not math.isfinite(log_odds):
                raise RuntimeError("internal error: non-finite classifier log odds")
            if row["predicted_statin_exposure"] not in {
                catalog.negative_label,
                catalog.positive_label,
            }:
                raise RuntimeError("internal error: invalid predicted class")
            expected_label = (
                catalog.positive_label
                if probability >= 0.5
                else catalog.negative_label
            )
            if row["predicted_statin_exposure"] != expected_label:
                raise RuntimeError("internal error: score and predicted class disagree")
            if not math.isclose(
                probability,
                _logistic(log_odds),
                rel_tol=1e-15,
                abs_tol=0.0,
            ):
                raise RuntimeError("internal error: probability and log odds disagree")
            if row["abstention_reason"]:
                raise RuntimeError("internal error: scored row has abstention reason")
        elif status == "abstained":
            if any(
                row[field]
                for field in (
                    "predicted_statin_exposure",
                    "statin_probability",
                    "log_odds",
                )
            ):
                raise RuntimeError("internal error: abstained row contains a score")
            if row["abstention_reason"] not in {
                "insufficient_feature_coverage",
                "numerical_instability",
            }:
                raise RuntimeError("internal error: invalid abstention reason")
        else:
            raise RuntimeError("internal error: invalid classifier decision status")


def _rate(
    numerator: int,
    denominator: int,
    denominator_definition: str,
) -> dict[str, Any]:
    return {
        "value": _rounded(numerator / denominator, 6) if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
        "denominator_definition": denominator_definition,
        "undefined_reason": None if denominator else "denominator_is_zero",
    }


def _auroc(
    scored: list[dict[str, Any]], catalog: FeatureCatalog
) -> dict[str, Any]:
    positives = [
        float(row["log_odds"])
        for row in scored
        if row["observed_statin_exposure"] == catalog.positive_label
    ]
    negatives = [
        float(row["log_odds"])
        for row in scored
        if row["observed_statin_exposure"] == catalog.negative_label
    ]
    if not all(math.isfinite(value) for value in [*positives, *negatives]):
        raise RuntimeError("internal error: AUROC received a non-finite score")
    pair_denominator = len(positives) * len(negatives)
    concordant = 0
    ties = 0
    for positive_score in positives:
        for negative_score in negatives:
            if positive_score > negative_score:
                concordant += 1
            elif positive_score == negative_score:
                ties += 1
    value = (
        _rounded((concordant + 0.5 * ties) / pair_denominator, 6)
        if pair_denominator
        else None
    )
    return {
        "value": value,
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "pair_denominator": pair_denominator,
        "concordant_pairs": concordant,
        "tied_pairs": ties,
        "ranking_score": "log_odds",
        "tie_handling": "half_credit",
        "undefined_reason": None if pair_denominator else "both_classes_required",
    }


def _build_metrics(
    predictions: list[dict[str, Any]],
    train: Dataset,
    catalog: FeatureCatalog,
) -> dict[str, Any]:
    scored = [row for row in predictions if row["decision_status"] == "scored"]
    positive = catalog.positive_label
    negative = catalog.negative_label
    tp = sum(
        row["observed_statin_exposure"] == positive
        and row["predicted_statin_exposure"] == positive
        for row in scored
    )
    fn = sum(
        row["observed_statin_exposure"] == positive
        and row["predicted_statin_exposure"] == negative
        for row in scored
    )
    tn = sum(
        row["observed_statin_exposure"] == negative
        and row["predicted_statin_exposure"] == negative
        for row in scored
    )
    fp = sum(
        row["observed_statin_exposure"] == negative
        and row["predicted_statin_exposure"] == positive
        for row in scored
    )
    actual_positive = tp + fn
    actual_negative = tn + fp
    sensitivity = _rate(tp, actual_positive, "scored_observed_positive")
    specificity = _rate(tn, actual_negative, "scored_observed_negative")
    precision = _rate(tp, tp + fp, "scored_predicted_positive")
    f1_score = _rate(
        2 * tp,
        2 * tp + fp + fn,
        "two_tp_plus_fp_plus_fn",
    )
    balanced_accuracy_value = (
        _rounded((sensitivity["value"] + specificity["value"]) / 2, 6)
        if sensitivity["value"] is not None and specificity["value"] is not None
        else None
    )

    train_counts = _dataset_summary(train, catalog)["class_counts"]
    baseline_label = (
        positive if train_counts[positive] > train_counts[negative] else negative
    )
    baseline_correct = sum(
        row["observed_statin_exposure"] == baseline_label for row in scored
    )
    scored_count = len(scored)
    abstained = [
        row for row in predictions if row["decision_status"] == "abstained"
    ]
    abstained_by_class = {
        negative: sum(
            row["observed_statin_exposure"] == negative for row in abstained
        ),
        positive: sum(
            row["observed_statin_exposure"] == positive for row in abstained
        ),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "evaluation_status": "synthetic_only_not_clinically_validated",
        "synthetic_data": True,
        "clinically_validated": False,
        "target_column": catalog.target_column,
        "sample_counts": {
            "test_total": len(predictions),
            "scored": scored_count,
            "abstained": len(predictions) - scored_count,
            "abstained_by_observed_class": abstained_by_class,
        },
        "confusion_matrix": {
            "true_positive": {
                "count": tp,
                "denominator": actual_positive,
                "denominator_definition": "scored_observed_positive",
            },
            "false_negative": {
                "count": fn,
                "denominator": actual_positive,
                "denominator_definition": "scored_observed_positive",
            },
            "true_negative": {
                "count": tn,
                "denominator": actual_negative,
                "denominator_definition": "scored_observed_negative",
            },
            "false_positive": {
                "count": fp,
                "denominator": actual_negative,
                "denominator_definition": "scored_observed_negative",
            },
        },
        "metrics": {
            "accuracy": _rate(tp + tn, scored_count, "all_scored_test_samples"),
            "sensitivity": sensitivity,
            "positive_recall": sensitivity,
            "specificity": specificity,
            "positive_precision": precision,
            "f1_score": f1_score,
            "scored_coverage": _rate(
                scored_count,
                len(predictions),
                "all_test_samples",
            ),
            "abstention_rate": _rate(
                len(predictions) - scored_count,
                len(predictions),
                "all_test_samples",
            ),
            "balanced_accuracy": {
                "value": balanced_accuracy_value,
                "component_count": 2 if balanced_accuracy_value is not None else 0,
                "components": ["sensitivity", "specificity"],
                "undefined_reason": (
                    None
                    if balanced_accuracy_value is not None
                    else "both_class_conditional_rates_required"
                ),
            },
            "auroc": _auroc(scored, catalog),
        },
        "baseline": {
            "method": "training_majority_class; ties_choose_negative_label",
            "predicted_label": baseline_label,
            **_rate(
                baseline_correct,
                scored_count,
                "all_scored_test_samples",
            ),
        },
        "limitations": [
            "All records and labels are synthetic.",
            "Performance does not establish medication exposure in humans.",
            "The model has not been clinically validated or calibrated.",
            "Test labels are used only after scoring to compute evaluation metrics.",
        ],
    }


def _format_metric(value: float | None) -> str:
    return "undefined" if value is None else f"{value:.3f}"


def _build_model_card(
    model: dict[str, Any],
    metrics: dict[str, Any],
    train: Dataset,
    test: Dataset,
    catalog: FeatureCatalog,
) -> str:
    confusion = metrics["confusion_matrix"]
    metric_values = metrics["metrics"]
    return "\n".join(
        [
            "# Synthetic statin-exposure classifier model card",
            "",
            "## Status",
            "",
            "Synthetic-only evaluation artifact. This model is not clinically validated,",
            "must not be used to infer medication exposure in a person, and does not establish",
            "that any listed signal is a clinical biomarker of statin use.",
            "",
            "## Intended use",
            "",
            "The classifier exercises deterministic, offline training, cold-cohort testing,",
            "artifact provenance, and safe feature-coverage handling in the workbench.",
            "",
            "## Model",
            "",
            f"- Algorithm: `{model['model_type']}` (closed-form standardized centroids)",
            f"- Target: `{catalog.target_column}` (`{catalog.positive_label}` is positive)",
            f"- Declared feature allowlist: {len(catalog.feature_names)} features",
            f"- Minimum scoring coverage: {catalog.minimum_feature_count} of "
            f"{len(catalog.feature_names)} features",
            "- Preprocessing fit scope: training data only",
            "- Missing-feature policy: never zero-fill; abstain below minimum coverage",
            "",
            "## Cold split and provenance",
            "",
            f"- Train: `{train.path.name}`; SHA-256 `{train.sha256}`; "
            f"{len(train.rows)} samples; cohorts "
            f"{', '.join(_dataset_summary(train, catalog)['cohort_ids'])}",
            f"- Test: `{test.path.name}`; SHA-256 `{test.sha256}`; "
            f"{len(test.rows)} samples; cohorts "
            f"{', '.join(_dataset_summary(test, catalog)['cohort_ids'])}",
            "- Training/test sample identifiers, cohort identifiers, and declared feature vectors "
            "were verified disjoint.",
            "- Allowlisted features that exactly encode the binary target are rejected.",
            "- Test labels were excluded from preprocessing, fitting, and score generation.",
            "",
            "## Synthetic evaluation",
            "",
            "| Quantity | Result | Explicit denominator |",
            "|---|---:|---|",
            f"| True positive | {confusion['true_positive']['count']} | "
            f"{confusion['true_positive']['denominator']} scored observed-positive |",
            f"| False negative | {confusion['false_negative']['count']} | "
            f"{confusion['false_negative']['denominator']} scored observed-positive |",
            f"| True negative | {confusion['true_negative']['count']} | "
            f"{confusion['true_negative']['denominator']} scored observed-negative |",
            f"| False positive | {confusion['false_positive']['count']} | "
            f"{confusion['false_positive']['denominator']} scored observed-negative |",
            f"| Balanced accuracy | "
            f"{_format_metric(metric_values['balanced_accuracy']['value'])} | "
            "mean of sensitivity and specificity |",
            f"| Positive precision | "
            f"{_format_metric(metric_values['positive_precision']['value'])} | "
            f"{metric_values['positive_precision']['denominator']} scored predicted-positive |",
            f"| Positive recall | "
            f"{_format_metric(metric_values['positive_recall']['value'])} | "
            f"{metric_values['positive_recall']['denominator']} scored observed-positive |",
            f"| F1 score | {_format_metric(metric_values['f1_score']['value'])} | "
            f"2TP+FP+FN = {metric_values['f1_score']['denominator']} |",
            f"| AUROC | {_format_metric(metric_values['auroc']['value'])} | "
            f"{metric_values['auroc']['pair_denominator']} positive-negative score pairs |",
            f"| Scored coverage | "
            f"{_format_metric(metric_values['scored_coverage']['value'])} | "
            f"{metric_values['scored_coverage']['denominator']} total test samples |",
            f"| Abstention rate | "
            f"{_format_metric(metric_values['abstention_rate']['value'])} | "
            f"{metric_values['abstention_rate']['denominator']} total test samples |",
            f"| Training-majority baseline accuracy | "
            f"{_format_metric(metrics['baseline']['value'])} | "
            f"{metrics['baseline']['denominator']} scored test samples |",
            "",
            f"Scored: {metrics['sample_counts']['scored']}; "
            f"abstained: {metrics['sample_counts']['abstained']}; "
            f"total: {metrics['sample_counts']['test_total']}.",
            "",
            "## Limitations",
            "",
            "- The cohort effects, exposure effects, and noise are generated by fixed formulas.",
            "- The small synthetic split cannot estimate real-world discrimination, calibration,",
            "  confounding, batch effects, adherence, dose, or medication combinations.",
            "- External human-cohort replication and expert review are required before any clinical",
            "  interpretation can be considered.",
            "",
        ]
    )


def _artifact_record(role: str, filename: str, payload: bytes) -> dict[str, Any]:
    return {
        "role": role,
        "path": filename,
        "sha256": _sha256_bytes(payload),
        "byte_count": len(payload),
    }


def _build_run_manifest(
    *,
    split_manifest_path: Path,
    split_manifest_sha256: str,
    split_id: str,
    feature_catalog_path: Path,
    feature_catalog_sha256: str,
    train: Dataset,
    test: Dataset,
    payloads: dict[str, bytes],
) -> dict[str, Any]:
    identity_material = "|".join(
        [
            CLASSIFIER_VERSION,
            split_id,
            train.sha256,
            test.sha256,
            feature_catalog_sha256,
            split_manifest_sha256,
        ]
    ).encode("utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": "synthetic-statin-" + _sha256_bytes(identity_material)[:16],
        "classifier_version": CLASSIFIER_VERSION,
        "software_version": __version__,
        "algorithm": ALGORITHM,
        "split_id": split_id,
        "validation_status": "synthetic_only_not_clinically_validated",
        "clinically_validated": False,
        "inputs": [
            {
                "role": "feature_catalog",
                "path": feature_catalog_path.name,
                "sha256": feature_catalog_sha256,
                "byte_count": feature_catalog_path.stat().st_size,
            },
            {
                "role": "split_manifest",
                "path": split_manifest_path.name,
                "sha256": split_manifest_sha256,
                "byte_count": split_manifest_path.stat().st_size,
            },
            {
                "role": "train",
                "path": train.path.name,
                "sha256": train.sha256,
                "byte_count": train.path.stat().st_size,
            },
            {
                "role": "test",
                "path": test.path.name,
                "sha256": test.sha256,
                "byte_count": test.path.stat().st_size,
            },
        ],
        "outputs": [
            _artifact_record("model", "model.json", payloads["model.json"]),
            _artifact_record(
                "predictions", "predictions.csv", payloads["predictions.csv"]
            ),
            _artifact_record("metrics", "metrics.json", payloads["metrics.json"]),
            _artifact_record(
                "model_card", "model_card.md", payloads["model_card.md"]
            ),
        ],
        "guards": {
            "input_hashes_verified": True,
            "sample_id_disjoint_verified": True,
            "cohort_id_disjoint_verified": True,
            "declared_feature_vectors_disjoint_verified": True,
            "binary_labels_verified": True,
            "finite_declared_features_verified": True,
            "exact_target_copy_features_rejected": True,
            "feature_allowlist_enforced": True,
            "model_feature_key_sets_verified": True,
            "train_only_preprocessing": True,
            "missing_features_zero_filled": False,
            "test_labels_used_for_model_fitting": False,
            "test_labels_used_for_scoring": False,
            "test_labels_used_for_metrics_only": True,
        },
        "human_readable_output": "model_card.md",
    }


def _write_payloads(out_dir: Path, payloads: dict[str, bytes]) -> None:
    if out_dir.exists() or out_dir.is_symlink():
        raise MedicationClassifierInputError(
            f"Output path already exists; choose a new destination: {out_dir}"
        )
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=".medication-classifier-", dir=out_dir.parent)
    )
    try:
        for filename in OUTPUT_FILENAMES:
            (stage / filename).write_bytes(payloads[filename])
        os.replace(stage, out_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def run_medication_classifier(
    train_csv: str | Path,
    test_csv: str | Path,
    feature_catalog_json: str | Path,
    split_manifest_json: str | Path,
    out_dir: str | Path,
) -> dict[str, Path]:
    """Fit, cold-test, and materialize the synthetic statin classifier.

    All input parsing, hash checks, split checks, fitting, scoring, metric
    construction, and schema checks complete before the output directory is
    touched.  The returned mapping contains the five deterministic artifacts.
    """

    train_path = Path(train_csv)
    test_path = Path(test_csv)
    feature_catalog_path = Path(feature_catalog_json)
    split_manifest_path = Path(split_manifest_json)
    destination = Path(out_dir)

    catalog = _load_feature_catalog(feature_catalog_path)
    feature_catalog_sha256 = sha256_file(feature_catalog_path)
    split_manifest = _read_json_object(split_manifest_path, "split manifest")
    _validate_input_schema(
        split_manifest,
        "medication_classifier_split_manifest.schema.json",
        "medication classifier split manifest",
    )
    train = _load_dataset(train_path, catalog, "train")
    test = _load_dataset(test_path, catalog, "test")
    _validate_no_exact_label_copy_features(train, catalog)
    _validate_split_contract(
        split_manifest,
        split_manifest_path,
        feature_catalog_path,
        feature_catalog_sha256,
        train,
        test,
        catalog,
    )

    model = _fit_model(
        train,
        catalog,
        feature_catalog_sha256=feature_catalog_sha256,
        split_id=split_manifest["split_id"],
    )
    _validate_model_feature_keys(model, catalog)
    predictions = _score_test_rows(test, model, catalog)
    _validate_predictions(predictions, catalog)
    metrics = _build_metrics(predictions, train, catalog)
    model_card = _build_model_card(model, metrics, train, test, catalog)

    validate_or_raise(
        model,
        project_schema_path("medication_classifier_model.schema.json"),
        label="medication classifier model",
    )
    validate_or_raise(
        metrics,
        project_schema_path("medication_classifier_metrics.schema.json"),
        label="medication classifier metrics",
    )

    payloads = {
        "model.json": _json_bytes(model),
        "predictions.csv": _csv_bytes(predictions),
        "metrics.json": _json_bytes(metrics),
        "model_card.md": model_card.encode("utf-8"),
    }
    run_manifest = _build_run_manifest(
        split_manifest_path=split_manifest_path,
        split_manifest_sha256=sha256_file(split_manifest_path),
        split_id=split_manifest["split_id"],
        feature_catalog_path=feature_catalog_path,
        feature_catalog_sha256=feature_catalog_sha256,
        train=train,
        test=test,
        payloads=payloads,
    )
    validate_or_raise(
        run_manifest,
        project_schema_path("medication_classifier_run_manifest.schema.json"),
        label="medication classifier run manifest",
    )
    payloads["run_manifest.json"] = _json_bytes(run_manifest)

    _write_payloads(destination, payloads)
    return {filename: destination / filename for filename in OUTPUT_FILENAMES}


def run_cold_synthetic_evaluation(
    data_dir: str | Path, out_dir: str | Path
) -> dict[str, Path]:
    """Run the classifier using the standard four files in a cold-data directory."""

    root = Path(data_dir)
    return run_medication_classifier(
        root / "train.csv",
        root / "test.csv",
        root / "feature_catalog.json",
        root / "split_manifest.json",
        out_dir,
    )

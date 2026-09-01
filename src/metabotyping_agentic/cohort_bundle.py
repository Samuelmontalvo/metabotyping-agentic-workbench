"""Run the offline curation pipeline against an explicit cohort bundle.

The pilot intentionally uses built-in synthetic fixtures.  This module is the
portable boundary for an unseen cohort: every input is declared and hashed in a
bundle manifest, publication evidence is mandatory for every repository study,
and no path can fall back to the pilot fixtures.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .evaluation.motrpac_alignment import align_motrpac
from .evaluation.quality_scoring import score_quality
from .extraction.metadata_cards import extract_metadata_cards
from .extraction.variable_inventory import extract_variable_inventory
from .harmonization.crosswalk import build_crosswalk
from .io import ensure_dir, to_plain, write_json, write_text
from .schemas import project_schema_path, validate_or_raise

BUNDLE_SCHEMA_VERSION = "1.0"
REQUIRED_FILE_ROLES = (
    "publications",
    "repository_records",
    "variable_dictionary",
)
PUBLICATION_BOOLEAN_COLUMNS = (
    "human",
    "exercise",
    "actigraphy",
    "metabolomics",
    "genetics",
    "cpet",
    "body_composition",
    "diet",
)
REPOSITORY_BOOLEAN_COLUMNS = (
    "has_metadata",
    "has_codebook",
    "has_data_files",
)


class CohortBundleError(ValueError):
    """Raised before output when a cohort bundle violates its contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_input_path(bundle_dir: Path, declared_path: str) -> Path:
    relative = Path(str(declared_path))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise CohortBundleError(
            f"Bundle input paths must be nonempty paths beneath the bundle: {declared_path!r}"
        )
    candidate = bundle_dir / relative
    if not candidate.is_file():
        raise CohortBundleError(f"Declared bundle input does not exist: {declared_path}")
    path = candidate.resolve(strict=True)
    try:
        path.relative_to(bundle_dir)
    except ValueError as exc:
        raise CohortBundleError(
            f"Declared bundle input escapes the bundle through a symlink: {declared_path}"
        ) from exc
    return path


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CohortBundleError(f"Bundle manifest contains duplicate key {key!r}")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str) -> None:
    raise CohortBundleError(
        f"Bundle manifest contains non-standard JSON constant {value!r}"
    )


def _read_manifest_strict(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except CohortBundleError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CohortBundleError(f"Bundle manifest is not valid JSON: {exc}") from exc


def _read_csv_strict(
    path: Path,
    *,
    required_columns: set[str],
    role: str,
) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        raise CohortBundleError(f"{role}: CSV header is missing")
    if len(fieldnames) != len(set(fieldnames)) or any(not name.strip() for name in fieldnames):
        raise CohortBundleError(f"{role}: CSV column names must be unique and nonempty")
    missing = sorted(required_columns - set(fieldnames))
    if missing:
        raise CohortBundleError(f"{role}: missing required columns: {', '.join(missing)}")
    if not rows:
        raise CohortBundleError(f"{role}: at least one data row is required")
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise CohortBundleError(f"{role}: row {row_number} has more values than the header")
        if not str(row.get("study_id") or "").strip():
            raise CohortBundleError(f"{role}: row {row_number} has no study_id")
    return fieldnames, rows


def _unique_keys(
    rows: list[dict[str, str]],
    columns: tuple[str, ...],
    *,
    role: str,
) -> None:
    seen: dict[tuple[str, ...], int] = {}
    for row_number, row in enumerate(rows, start=2):
        key = tuple(str(row.get(column) or "").strip() for column in columns)
        if not all(key):
            raise CohortBundleError(
                f"{role}: row {row_number} has a blank key field in {', '.join(columns)}"
            )
        if key in seen:
            raise CohortBundleError(
                f"{role}: duplicate key {key!r} at rows {seen[key]} and {row_number}"
            )
        seen[key] = row_number


def _validate_boolean_columns(
    rows: list[dict[str, str]], columns: tuple[str, ...], *, role: str
) -> None:
    """Require explicit booleans so unknown evidence is never collapsed to false."""

    for row_number, row in enumerate(rows, start=2):
        for column in columns:
            if column not in row:
                continue
            value = str(row.get(column) or "").strip().lower()
            if value not in {"true", "false"}:
                raise CohortBundleError(
                    f"{role}: row {row_number} column {column!r} must be "
                    "explicitly true or false"
                )


def _validate_study_card_filename_universe(study_ids: set[str]) -> None:
    """Reject IDs that would overwrite one another on common filesystems."""

    filenames: dict[str, str] = {}
    for study_id in sorted(study_ids):
        token = re.sub(
            r"[^A-Za-z0-9._-]+", "-", str(study_id).strip()
        ).strip("-._")
        filename = f"study_{token or 'unknown'}.json"
        collision_key = filename.casefold()
        if collision_key in filenames:
            raise CohortBundleError(
                "Study identifiers map to the same metadata-card filename: "
                f"{filenames[collision_key]!r} and {study_id!r}"
            )
        filenames[collision_key] = study_id


def _validate_bundle(bundle_dir: Path) -> dict[str, Any]:
    try:
        bundle_dir = bundle_dir.resolve(strict=True)
    except OSError as exc:
        raise CohortBundleError(f"Bundle directory does not exist: {bundle_dir}") from exc
    declared_manifest_path = bundle_dir / "manifest.json"
    if not declared_manifest_path.is_file():
        raise CohortBundleError(
            f"Bundle manifest does not exist: {declared_manifest_path}"
        )
    manifest_path = declared_manifest_path.resolve(strict=True)
    try:
        manifest_path.relative_to(bundle_dir)
    except ValueError as exc:
        raise CohortBundleError("Bundle manifest escapes the bundle through a symlink") from exc
    manifest = _read_manifest_strict(manifest_path)
    if not isinstance(manifest, dict):
        raise CohortBundleError("Bundle manifest must be a JSON object")
    validate_or_raise(
        manifest,
        project_schema_path("cohort_bundle.schema.json"),
        label="cohort bundle manifest",
    )
    if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise CohortBundleError(
            f"Unsupported cohort bundle schema_version: {manifest.get('schema_version')!r}"
        )

    files = manifest.get("files") or {}
    if set(files) != set(REQUIRED_FILE_ROLES):
        raise CohortBundleError(
            "Bundle files must declare exactly: " + ", ".join(REQUIRED_FILE_ROLES)
        )

    paths: dict[str, Path] = {}
    artifacts: list[dict[str, Any]] = [
        {
            "role": "bundle_manifest",
            "path": "manifest.json",
            "sha256": _sha256(manifest_path),
        }
    ]
    for role in REQUIRED_FILE_ROLES:
        entry = files[role]
        declared_path = str(entry["path"])
        path = _safe_input_path(bundle_dir, declared_path)
        observed_digest = _sha256(path)
        if observed_digest != entry["sha256"]:
            raise CohortBundleError(
                f"{role}: SHA-256 mismatch for {declared_path}; "
                f"expected {entry['sha256']}, observed {observed_digest}"
            )
        paths[role] = path
        artifacts.append(
            {
                "role": role,
                "path": declared_path,
                "sha256": observed_digest,
                "row_count": int(entry["row_count"]),
            }
        )

    _, publication_rows = _read_csv_strict(
        paths["publications"],
        required_columns={"study_id", "title", *PUBLICATION_BOOLEAN_COLUMNS},
        role="publications",
    )
    _, repository_rows = _read_csv_strict(
        paths["repository_records"],
        required_columns={
            "study_id",
            "repository",
            "accession",
            *REPOSITORY_BOOLEAN_COLUMNS,
        },
        role="repository_records",
    )
    _, variable_rows = _read_csv_strict(
        paths["variable_dictionary"],
        required_columns={"study_id", "source_variable", "label", "unit", "timing"},
        role="variable_dictionary",
    )
    _validate_boolean_columns(
        publication_rows,
        PUBLICATION_BOOLEAN_COLUMNS,
        role="publications",
    )
    _validate_boolean_columns(
        repository_rows,
        REPOSITORY_BOOLEAN_COLUMNS,
        role="repository_records",
    )
    _unique_keys(publication_rows, ("study_id",), role="publications")
    _unique_keys(
        repository_rows,
        ("study_id", "repository", "accession"),
        role="repository_records",
    )
    _unique_keys(
        variable_rows,
        ("study_id", "source_variable"),
        role="variable_dictionary",
    )

    observed_counts = {
        "publications": len(publication_rows),
        "repository_records": len(repository_rows),
        "variable_dictionary": len(variable_rows),
    }
    for artifact in artifacts:
        if artifact["role"] == "bundle_manifest":
            continue
        if artifact["row_count"] != observed_counts[artifact["role"]]:
            raise CohortBundleError(
                f"{artifact['role']}: manifest row_count {artifact['row_count']} "
                f"does not match observed {observed_counts[artifact['role']]}"
            )

    publication_ids = {row["study_id"].strip() for row in publication_rows}
    repository_ids = {row["study_id"].strip() for row in repository_rows}
    variable_ids = {row["study_id"].strip() for row in variable_rows}
    expected_ids = set(manifest["study_ids"])
    _validate_study_card_filename_universe(expected_ids)
    if publication_ids != expected_ids or repository_ids != expected_ids:
        raise CohortBundleError(
            "Manifest, publication, and repository study universes must match exactly"
        )
    unknown_variable_ids = sorted(variable_ids - expected_ids)
    missing_variable_ids = sorted(expected_ids - variable_ids)
    if unknown_variable_ids or missing_variable_ids:
        raise CohortBundleError(
            "Every declared study must have variables and no variable may reference an "
            "undeclared study"
        )

    return {
        "manifest": manifest,
        "paths": paths,
        "input_artifacts": artifacts,
        "counts": observed_counts,
    }


def _output_artifact(path: Path, out_dir: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(out_dir).as_posix(),
        "sha256": _sha256(path),
    }


def _render_report(result: dict[str, Any]) -> str:
    gates = result["evidence_gates"]
    interpretation = (
        "Synthetic holdout performance cannot substitute for an independently "
        "curated real cohort."
        if result["synthetic_data"]
        else "A declared real-cohort intake establishes interface compatibility only; "
        "subject provenance and scientific validity still require external adjudication."
    )
    lines = [
        "# Unseen Cohort Intake Evaluation",
        "",
        f"- Bundle: `{result['bundle_id']}`",
        f"- Status: **{result['status']}**",
        f"- Synthetic data: `{str(result['synthetic_data']).lower()}`",
        f"- Studies: {', '.join(result['study_ids'])}",
        "",
        "## Evidence gates",
        "",
        f"- Declared-input hashes verified: {gates['input_hashes_verified']}.",
        f"- Publication/repository universes match: {gates['study_universe_match']}.",
        f"- Built-in fixture fallback used: {gates['builtin_fixture_fallback_used']}.",
        f"- Human-participant evidence unknown: {gates['unknown_human_evidence_count']} study/studies.",
        f"- Crosswalk rows requiring review: {gates['crosswalk_review_required_count']}.",
        "",
        "## Interpretation",
        "",
        (
            "This run demonstrates that the deterministic workflow accepts a new, "
            "manifested cohort bundle without borrowing the pilot's fixtures."
        ),
        f"It does not establish external scientific validity. {interpretation}",
        "",
    ]
    return "\n".join(lines)


def run_cohort_bundle(bundle_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Validate and run one explicit cohort bundle without hidden inputs.

    The destination must be new.  Building in a fresh staging directory and
    atomically publishing it prevents stale cards from an earlier run being
    mistaken for current outputs and prevents a failed run from leaving a
    partial evidence packet.
    """

    bundle_dir = Path(bundle_dir)
    out_dir = Path(out_dir)
    if out_dir.exists() or out_dir.is_symlink():
        raise CohortBundleError(
            f"Output path already exists; choose a new destination: {out_dir}"
        )
    validated = _validate_bundle(bundle_dir)
    manifest = validated["manifest"]
    paths = validated["paths"]
    source_prefix = f"bundle:{manifest['bundle_id']}"

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.stage-", dir=out_dir.parent)
    )
    try:
        ensure_dir(stage)
        studies, datasets = extract_metadata_cards(
            paths["repository_records"],
            stage,
            paths["publications"],
            require_publication_match=True,
            records_provenance_source=(
                f"{source_prefix}/{manifest['files']['repository_records']['path']}"
            ),
            publications_provenance_source=(
                f"{source_prefix}/{manifest['files']['publications']['path']}"
            ),
        )
        variables = extract_variable_inventory(
            paths["variable_dictionary"],
            stage,
            provenance_source=(
                f"{source_prefix}/{manifest['files']['variable_dictionary']['path']}"
            ),
        )
        mappings = build_crosswalk(paths["variable_dictionary"], stage)
        scores = score_quality(stage, stage)
        alignments = align_motrpac(stage, stage)

        mapping_rows = [to_plain(item) for item in mappings]
        limitations = [
            "No real-cohort accuracy or harmonization agreement is inferred.",
            "Review-required variable mappings remain ineligible for automatic ETL.",
            "MoTrPAC output is metadata readiness, not analysis reproduction.",
        ]
        if manifest["synthetic_data"]:
            limitations.insert(
                0, "The bundled demonstration cohorts and values are synthetic."
            )
        else:
            limitations.insert(
                0,
                "The bundle is declared non-synthetic, but subject provenance and "
                "external validity were not independently verified by this runner.",
            )
        result = {
            "schema_version": "1.0",
            "bundle_id": manifest["bundle_id"],
            "status": (
                "synthetic_interface_generalization_pass"
                if manifest["synthetic_data"]
                else "cohort_intake_complete_requires_external_adjudication"
            ),
            "synthetic_data": manifest["synthetic_data"],
            "study_ids": list(manifest["study_ids"]),
            "counts": {
                "study_cards": len(studies),
                "dataset_cards": len(datasets),
                "variable_cards": len(variables),
                "crosswalk_rows": len(mappings),
                "quality_scores": len(scores),
                "motrpac_alignments": len(alignments),
            },
            "evidence_gates": {
                "input_hashes_verified": True,
                "study_universe_match": True,
                "builtin_fixture_fallback_used": False,
                "unknown_human_evidence_count": sum(
                    item.human is None for item in studies
                ),
                "crosswalk_review_required_count": sum(
                    row["review_status"] == "requires_human_review"
                    for row in mapping_rows
                ),
            },
            "external_validation": False,
            "limitations": limitations,
        }
        validate_or_raise(
            result,
            project_schema_path("cohort_generalization_result.schema.json"),
            label="cohort generalization result",
        )
        result_path = write_json(stage / "cohort_generalization_result.json", result)
        report_path = write_text(
            stage / "cohort_generalization_report.md", _render_report(result)
        )

        output_paths = [
            stage / "study_cards.json",
            stage / "dataset_cards.json",
            stage / "variable_cards.json",
            stage / "variable_inventory.csv",
            stage / "crosswalk.json",
            stage / "crosswalk.csv",
            stage / "quality_scores.json",
            stage / "motrpac_alignment.json",
            result_path,
            report_path,
            *sorted((stage / "metadata_cards").glob("*.json")),
        ]
        run_manifest = {
            "schema_version": "1.0",
            "bundle_id": manifest["bundle_id"],
            "rule_set_version": "1.0",
            "inputs": validated["input_artifacts"],
            "outputs": [_output_artifact(path, stage) for path in output_paths],
            "portable_provenance": True,
            "generated_timestamp_included": False,
        }
        write_json(stage / "cohort_run_manifest.json", run_manifest)
        os.replace(stage, out_dir)
        return result
    finally:
        if stage.exists():
            shutil.rmtree(stage)

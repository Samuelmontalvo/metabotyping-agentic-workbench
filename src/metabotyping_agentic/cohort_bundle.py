"""Run the offline curation pipeline against an explicit cohort bundle.

The pilot intentionally uses built-in synthetic fixtures.  This module is the
portable boundary for an unseen cohort: every input is declared and hashed in a
bundle manifest, publication evidence is mandatory for every repository study,
and no path can fall back to the pilot fixtures.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from .evaluation.motrpac_alignment import align_motrpac
from .evaluation.quality_scoring import score_quality
from .extraction.metadata_cards import extract_metadata_cards
from .extraction.variable_inventory import extract_variable_inventory
from .harmonization.crosswalk import build_crosswalk
from .io import ensure_dir, read_json, to_plain, write_json, write_text
from .schemas import project_schema_path, validate_or_raise

BUNDLE_SCHEMA_VERSION = "1.0"
REQUIRED_FILE_ROLES = (
    "publications",
    "repository_records",
    "variable_dictionary",
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
    path = bundle_dir / relative
    if not path.is_file():
        raise CohortBundleError(f"Declared bundle input does not exist: {declared_path}")
    return path


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


def _validate_bundle(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        raise CohortBundleError(f"Bundle manifest does not exist: {manifest_path}")
    try:
        manifest = read_json(manifest_path)
    except (OSError, ValueError) as exc:
        raise CohortBundleError(f"Bundle manifest is not valid JSON: {exc}") from exc
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
    artifacts: list[dict[str, Any]] = []
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
        required_columns={"study_id", "title", "human", "metabolomics"},
        role="publications",
    )
    _, repository_rows = _read_csv_strict(
        paths["repository_records"],
        required_columns={
            "study_id",
            "repository",
            "accession",
            "has_metadata",
            "has_codebook",
            "has_data_files",
        },
        role="repository_records",
    )
    _, variable_rows = _read_csv_strict(
        paths["variable_dictionary"],
        required_columns={"study_id", "source_variable", "label", "unit", "timing"},
        role="variable_dictionary",
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
        if artifact["row_count"] != observed_counts[artifact["role"]]:
            raise CohortBundleError(
                f"{artifact['role']}: manifest row_count {artifact['row_count']} "
                f"does not match observed {observed_counts[artifact['role']]}"
            )

    publication_ids = {row["study_id"].strip() for row in publication_rows}
    repository_ids = {row["study_id"].strip() for row in repository_rows}
    variable_ids = {row["study_id"].strip() for row in variable_rows}
    expected_ids = set(manifest["study_ids"])
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
        (
            "It does not establish external scientific validity. Synthetic holdout "
            "performance cannot substitute for an independently curated real cohort."
        ),
        "",
    ]
    return "\n".join(lines)


def run_cohort_bundle(bundle_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Validate and run one explicit cohort bundle without hidden inputs."""

    bundle_dir = Path(bundle_dir)
    out_dir = Path(out_dir)
    validated = _validate_bundle(bundle_dir)
    manifest = validated["manifest"]
    paths = validated["paths"]
    source_prefix = f"bundle:{manifest['bundle_id']}"

    ensure_dir(out_dir)
    studies, datasets = extract_metadata_cards(
        paths["repository_records"],
        out_dir,
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
        out_dir,
        provenance_source=(
            f"{source_prefix}/{manifest['files']['variable_dictionary']['path']}"
        ),
    )
    mappings = build_crosswalk(paths["variable_dictionary"], out_dir)
    scores = score_quality(out_dir, out_dir)
    alignments = align_motrpac(out_dir, out_dir)

    mapping_rows = [to_plain(item) for item in mappings]
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
            "unknown_human_evidence_count": sum(item.human is None for item in studies),
            "crosswalk_review_required_count": sum(
                row["review_status"] == "requires_human_review" for row in mapping_rows
            ),
        },
        "external_validation": False,
        "limitations": [
            "The bundled demonstration cohorts and values are synthetic.",
            "No real-cohort accuracy or harmonization agreement is inferred.",
            "Review-required variable mappings remain ineligible for automatic ETL.",
            "MoTrPAC output is metadata readiness, not analysis reproduction.",
        ],
    }
    validate_or_raise(
        result,
        project_schema_path("cohort_generalization_result.schema.json"),
        label="cohort generalization result",
    )
    result_path = write_json(out_dir / "cohort_generalization_result.json", result)
    report_path = write_text(out_dir / "cohort_generalization_report.md", _render_report(result))

    output_paths = [
        out_dir / "study_cards.json",
        out_dir / "dataset_cards.json",
        out_dir / "variable_cards.json",
        out_dir / "variable_inventory.csv",
        out_dir / "crosswalk.json",
        out_dir / "crosswalk.csv",
        out_dir / "quality_scores.json",
        out_dir / "motrpac_alignment.json",
        result_path,
        report_path,
        *sorted((out_dir / "metadata_cards").glob("*.json")),
    ]
    run_manifest = {
        "schema_version": "1.0",
        "bundle_id": manifest["bundle_id"],
        "rule_set_version": "1.0",
        "inputs": validated["input_artifacts"],
        "outputs": [_output_artifact(path, out_dir) for path in output_paths],
        "portable_provenance": True,
        "generated_timestamp_included": False,
    }
    write_json(out_dir / "cohort_run_manifest.json", run_manifest)
    return result


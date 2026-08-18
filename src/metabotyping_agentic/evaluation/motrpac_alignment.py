"""MoTrPAC-style metadata-readiness scoring for comparison planning."""

from __future__ import annotations

from pathlib import Path

from ..io import read_json, to_plain, write_json
from ..models import MoTrPACAlignment, ReplicationFeasibilityTier
from ..schemas import project_schema_path, validate_or_raise


def _tier(score: float) -> ReplicationFeasibilityTier:
    if score >= 0.85:
        return ReplicationFeasibilityTier.HIGH
    if score >= 0.65:
        return ReplicationFeasibilityTier.MODERATE
    if score >= 0.40:
        return ReplicationFeasibilityTier.LOW
    return ReplicationFeasibilityTier.NOT_FEASIBLE


def _has(modalities: list[str], target: str) -> bool:
    return target in modalities


def align_one(dataset: dict, study: dict | None = None) -> MoTrPACAlignment:
    modalities = [str(item) for item in dataset.get("modalities", [])]
    documented_absent = [str(item) for item in dataset.get("documented_absent_modalities", [])]
    if study is not None:
        modalities = sorted(set(modalities + [str(item) for item in study.get("modalities", [])]))
    human_evidence = study is not None and bool(study.get("human"))
    checks = {
        "human participants": human_evidence,
        "metabolomics available": _has(modalities, "metabolomics"),
        "exercise/activity phenotype available": any(_has(modalities, item) for item in ["exercise", "actigraphy", "physical_activity"]),
        "biospecimen timing available": dataset.get("biospecimen_timing") not in {"unknown", "not_reported", ""},
        "sample matrix available": dataset.get("sample_matrix") not in {"unknown", "not_reported", ""},
        "assay platform available": dataset.get("assay_platform") not in {"unknown", "not_reported", ""},
        "genetics available or documented absent": _has(modalities, "genetics")
        or _has(documented_absent, "genetics"),
        "CPET/cardiorespiratory fitness phenotype available": _has(modalities, "cpet"),
        "body composition available": _has(modalities, "body_composition"),
        "diet metadata available": _has(modalities, "diet"),
        "variable dictionary available": bool(dataset.get("has_codebook")),
    }
    met = [name for name, ok in checks.items() if ok]
    missing = [name for name, ok in checks.items() if not ok]
    score = round(len(met) / len(checks), 3)
    tier = _tier(score) if human_evidence else ReplicationFeasibilityTier.NOT_FEASIBLE
    rationale = (
        f"{len(met)} of {len(checks)} MoTrPAC-style metadata-readiness "
        "criteria are documented."
    )
    if not human_evidence:
        rationale += (
            " Human-participant evidence is a hard gate, so the "
            "comparison-planning tier remains not feasible."
        )
    return MoTrPACAlignment(
        study_id=dataset["study_id"],
        score=score,
        tier=tier,
        met_criteria=met,
        missing_elements=missing,
        rationale=rationale,
    )


def align_motrpac(metadata_dir: str | Path, out_dir: str | Path) -> list[MoTrPACAlignment]:
    metadata_dir = Path(metadata_dir)
    datasets = read_json(metadata_dir / "dataset_cards.json")
    studies_path = metadata_dir / "study_cards.json"
    studies = read_json(studies_path) if studies_path.exists() else []
    study_by_id = {study["study_id"]: study for study in studies}
    alignments = [align_one(dataset, study_by_id.get(dataset["study_id"])) for dataset in datasets]
    rows = [to_plain(item) for item in alignments]
    schema_path = project_schema_path("motrpac_alignment.schema.json")
    for row in rows:
        validate_or_raise(row, schema_path, label=f"MoTrPAC alignment {row['study_id']}")
    write_json(Path(out_dir) / "motrpac_alignment.json", rows)
    return alignments

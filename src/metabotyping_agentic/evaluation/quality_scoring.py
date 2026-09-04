"""Transparent metadata-readiness scoring for deterministic curation triage."""

from __future__ import annotations

import math
from pathlib import Path

from ..io import read_json, to_plain, write_json
from ..models import QualityScore
from ..schemas import project_schema_path, validate_or_raise

# Bumped when a scoring rule changes, independently of the package release.
# 0.3.0: scope gate. A study documented as non-human no longer receives an
# overall readiness score (the scale is defined for human MoTrPAC-style
# comparison planning); undocumented human status is flagged, not scored down.
RULE_SET_VERSION = "0.3.0"

SCOPE_IN_SCOPE_HUMAN = "in_scope_human"
SCOPE_OUT_OF_SCOPE_NON_HUMAN = "out_of_scope_non_human"
SCOPE_HUMAN_STATUS_UNKNOWN = "human_status_unknown"
SCOPE_STATUSES = (
    SCOPE_IN_SCOPE_HUMAN,
    SCOPE_OUT_OF_SCOPE_NON_HUMAN,
    SCOPE_HUMAN_STATUS_UNKNOWN,
)

# Metadata values that mean "no usable evidence". Kept identical for every
# subscore and for the rationale so a dataset cannot be scored as unknown on
# one line and described as reported on the next.
UNREPORTED_VALUES = {"unknown", "not_reported", ""}

DEFAULT_WEIGHTS = {
    "study_design_rigor": 0.15,
    "metadata_completeness": 0.15,
    "metabolomics_quality": 0.15,
    "activity_quality": 0.10,
    "genetics_quality": 0.10,
    "cpet_quality": 0.10,
    "body_composition_quality": 0.05,
    "diet_quality": 0.05,
    "temporal_alignment": 0.10,
    "harmonization_feasibility": 0.05,
}


def _has(modalities: list[str], *targets: str) -> bool:
    return any(target in modalities for target in targets)


def scope_status_for(study: dict | None) -> str:
    """Return where one study sits relative to the human readiness scale.

    ``human`` on the study card is three-valued: ``True`` and ``False`` are
    documented evidence, ``None`` (or no study card at all) is an evidence gap.
    Only a documented non-human study is out of scope. Unknown status keeps a
    triage score and is flagged, because "not documented" is not "documented
    absent" -- the same distinction the mirage detector and MoTrPAC alignment
    draw.
    """

    if study is None or study.get("human") is None:
        return SCOPE_HUMAN_STATUS_UNKNOWN
    if bool(study.get("human")):
        return SCOPE_IN_SCOPE_HUMAN
    return SCOPE_OUT_OF_SCOPE_NON_HUMAN


def _score_dataset(dataset: dict, study: dict | None, weights: dict[str, float]) -> QualityScore:
    modalities = [str(item) for item in dataset.get("modalities", [])]
    if study is not None:
        modalities = sorted(set(modalities + [str(item) for item in study.get("modalities", [])]))

    sample_size = dataset.get("sample_size")
    has_sample = isinstance(sample_size, int) and sample_size > 0
    has_activity = _has(modalities, "exercise", "actigraphy", "physical_activity")

    study_design_rigor = 0.4
    if study and study.get("human"):
        study_design_rigor += 0.2
    if has_sample:
        study_design_rigor += 0.2 if sample_size >= 100 else 0.1
    if has_activity and _has(modalities, "metabolomics"):
        study_design_rigor += 0.2
    study_design_rigor = min(study_design_rigor, 1.0)

    completeness_items = [
        dataset.get("has_metadata"),
        dataset.get("has_codebook"),
        dataset.get("has_data_files"),
        dataset.get("assay_platform") not in UNREPORTED_VALUES,
        dataset.get("sample_matrix") not in UNREPORTED_VALUES,
        dataset.get("biospecimen_timing") not in UNREPORTED_VALUES,
        has_sample,
    ]
    metadata_completeness = sum(bool(item) for item in completeness_items) / len(completeness_items)

    metabolomics_quality = 0.0
    if _has(modalities, "metabolomics"):
        metabolomics_quality = 0.4
        if dataset.get("assay_platform") not in UNREPORTED_VALUES:
            metabolomics_quality += 0.25
        if dataset.get("sample_matrix") not in UNREPORTED_VALUES:
            metabolomics_quality += 0.15
        if dataset.get("has_data_files"):
            metabolomics_quality += 0.20

    genetics_quality = 0.8 if _has(modalities, "genetics") else 0.35
    activity_quality = 0.85 if _has(modalities, "actigraphy", "physical_activity") else 0.70 if _has(modalities, "exercise") else 0.25
    cpet_quality = 0.85 if _has(modalities, "cpet") else 0.25
    body_composition_quality = 0.80 if _has(modalities, "body_composition") else 0.30
    diet_quality = 0.75 if _has(modalities, "diet") else 0.30
    temporal_alignment = 0.80 if dataset.get("biospecimen_timing") not in UNREPORTED_VALUES and has_activity else 0.35
    harmonization_feasibility = 0.85 if dataset.get("has_codebook") and dataset.get("has_metadata") else 0.25

    subscores = {
        "study_design_rigor": round(study_design_rigor, 3),
        "metadata_completeness": round(metadata_completeness, 3),
        "metabolomics_quality": round(metabolomics_quality, 3),
        "activity_quality": round(activity_quality, 3),
        "genetics_quality": round(genetics_quality, 3),
        "cpet_quality": round(cpet_quality, 3),
        "body_composition_quality": round(body_composition_quality, 3),
        "diet_quality": round(diet_quality, 3),
        "temporal_alignment": round(temporal_alignment, 3),
        "harmonization_feasibility": round(harmonization_feasibility, 3),
    }
    # math.fsum, not sum(): CPython 3.12 gave sum() Neumaier compensated
    # summation for floats, so naive accumulation of these weighted subscores
    # lands on either side of a .0005 rounding boundary depending on the
    # interpreter version (SYN-CPET-RICH scored 0.817 on 3.11 and 0.818 on
    # 3.12+). fsum is exactly rounded on every version, which keeps a published
    # quality score independent of the interpreter that produced it.
    overall = math.fsum(subscores[name] * weights[name] for name in weights)
    scope_status = scope_status_for(study)
    rationale = []
    if scope_status == SCOPE_OUT_OF_SCOPE_NON_HUMAN:
        rationale.append(
            "Study participants are documented as non-human; the readiness scale is "
            "defined for human MoTrPAC-style comparison planning, so no overall score "
            "is reported. Subscores are retained for transparency."
        )
    elif scope_status == SCOPE_HUMAN_STATUS_UNKNOWN:
        rationale.append(
            "Human-participant status is not documented; the overall score is "
            "metadata-readiness triage only, and the MoTrPAC comparison tier stays not "
            "feasible until human evidence is recorded."
        )
    if not dataset.get("has_codebook"):
        rationale.append("Variable dictionary/codebook missing or incomplete.")
    if dataset.get("biospecimen_timing") in UNREPORTED_VALUES:
        rationale.append("Biospecimen timing is not sufficiently documented.")
    if _has(modalities, "metabolomics") and dataset.get("assay_platform") not in UNREPORTED_VALUES:
        rationale.append("Metabolomics assay platform is reported.")
    if _has(modalities, "cpet"):
        rationale.append("CPET phenotype is documented for comparison planning.")

    return QualityScore(
        study_id=dataset["study_id"],
        overall_score=(
            None if scope_status == SCOPE_OUT_OF_SCOPE_NON_HUMAN else round(overall, 3)
        ),
        scope_status=scope_status,
        weights=weights,
        rationale=rationale,
        **subscores,
    )


def score_quality(metadata_dir: str | Path, out_dir: str | Path, weights: dict[str, float] | None = None) -> list[QualityScore]:
    metadata_dir = Path(metadata_dir)
    weights = weights or DEFAULT_WEIGHTS
    datasets = read_json(metadata_dir / "dataset_cards.json")
    studies_path = metadata_dir / "study_cards.json"
    studies = read_json(studies_path) if studies_path.exists() else []
    study_by_id = {study["study_id"]: study for study in studies}
    scores = [_score_dataset(dataset, study_by_id.get(dataset["study_id"]), weights) for dataset in datasets]
    rows = [to_plain(score) for score in scores]
    schema_path = project_schema_path("quality_score.schema.json")
    for row in rows:
        validate_or_raise(row, schema_path, label=f"quality score {row['study_id']}")
    write_json(Path(out_dir) / "quality_scores.json", rows)
    return scores

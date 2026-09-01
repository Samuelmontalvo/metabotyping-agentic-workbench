"""Deterministic offline evaluation of a directional biomarker claim.

This module implements one deliberately narrow, post-hoc repository
After-versus-Before directional check motivated by the Li et al. 2022 Lac-Phe
exercise claim using Metabolomics Workbench study ST003662. The raw factor and
codebook snapshot is not bound, cohort independence is not established, and the
selected dataset is exploratory rather than a prespecified replication. It does
not reproduce the paper's datasets or its causal claims.

Only Python's standard library is used.  Every declared input is checksum-verified
before parsing, all scientific metadata are validated fail-closed, and no output
path is touched until the complete evaluation and output payloads are ready.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
from collections.abc import Iterable, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "1.1.0"
RESULT_VERSION = "1.1.0"
MANIFEST_VERSION = "1.1.0"

CASE_SCOPE = "post_hoc_repository_after_vs_before_directional_check"
SUPPORTED_OUTCOME = (
    "supports_repository_after_vs_before_direction_requires_identity_and_timing_review"
)
NEGATIVE_OUTCOME = "does_not_support"
BLOCKED_OUTCOME = "blocked"

EXPECTED_DOI = "10.1038/s41586-022-04828-5"
EXPECTED_PAPER_TITLE = "An exercise-inducible metabolite that suppresses feeding and obesity"
EXPECTED_STUDY_ID = "ST003662"
EXPECTED_REFMET_ID = "RM0131640"
REQUIRED_IDENTITY_STATUS = "requires_human_review"
REQUIRED_HARMONIZATION_ELIGIBILITY = "requires_assay_identity_review"
REQUIRED_TIMING_STATUS = "repository_derived_before_after_labels_raw_factor_context_not_bound"
EXPECTED_DIRECTION_EVIDENCE_PHRASES = (
    "exercise stimulates the production of N-lactoyl-phenylalanine (Lac-Phe)",
    "large activity-inducible increases in circulating Lac-Phe",
)

INPUT_ROLES = (
    "literature_record",
    "literature_review",
    "sample_pairs",
    "cached_effect",
    "retrieval_provenance",
    "metstat_locator",
    "analysis_metadata",
    "refmet_annotations",
)

SAMPLE_COLUMNS = (
    "study_id",
    "metabolite",
    "refmet_name",
    "participant_code",
    "sex",
    "pre_sample",
    "post_sample",
    "value_pre",
    "value_post",
    "unit",
)

EFFECT_COLUMNS = (
    "study_id",
    "stratum",
    "metabolite",
    "refmet_name",
    "log2fc",
    "p_value",
    "n_pairs",
    "mean_pre",
    "mean_post",
    "fdr",
    "neg_log10_p",
)

REFMET_COLUMNS = (
    "name",
    "super_class",
    "main_class",
    "sub_class",
    "refmet_id",
    "formula",
)

ANALYSIS_COLUMNS = (
    "study_id",
    "analysis_id",
    "analysis_summary",
    "analysis_type",
    "chromatography_type",
    "ms_instrument_type",
    "ion_mode",
    "units",
    "assay_scope",
    "assay_scope_basis",
    "chromatography system",
    "column_name",
    "ms_instrument_name",
    "ms_type",
    "nmr_experiment_type",
    "nmr_instrument_type",
    "nmr_solvent",
    "spectrometer_frequency",
)

METSTAT_COLUMNS = (
    "query_refmet_name",
    "match_basis",
    "review_status",
    "decision_scope",
    "harmonization_eligibility",
    "study_id",
    "analysis_id",
    "study_title",
    "species",
    "sample_source",
    "analysis_type",
    "polarity",
    "chromatography",
    "disease",
    "refmet_name",
    "refmet_id",
    "inchi_key",
    "pubchem_cid",
    "super_class",
    "main_class",
    "sub_class",
    "study_link",
    "source_system",
    "provenance_url",
)


class BiomarkerReproductionInputError(ValueError):
    """Raised before output when a case or source artifact is invalid."""


class BiomarkerReproductionHashError(BiomarkerReproductionInputError):
    """Raised when a declared input no longer matches its case-contract digest."""


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BiomarkerReproductionInputError(f"JSON object contains duplicate key {key!r}")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str) -> None:
    raise BiomarkerReproductionInputError(f"JSON contains non-standard numeric constant {value!r}")


def _read_json_strict(path: Path, *, label: str) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise BiomarkerReproductionInputError(f"{label}: input is not valid UTF-8") from exc
    try:
        return json.loads(
            raw,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except BiomarkerReproductionInputError:
        raise
    except json.JSONDecodeError as exc:
        raise BiomarkerReproductionInputError(
            f"{label}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BiomarkerReproductionInputError(f"{label}: expected a JSON object")
    return value


def _require_exact_keys(
    value: dict[str, Any],
    required: Iterable[str],
    *,
    label: str,
) -> None:
    required_set = set(required)
    observed = set(value)
    missing = sorted(required_set - observed)
    extra = sorted(observed - required_set)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise BiomarkerReproductionInputError(f"{label}: " + "; ".join(details))


def _require_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise BiomarkerReproductionInputError(
            f"{label}: expected non-empty text without surrounding whitespace"
        )
    return value


def _require_const(value: Any, expected: Any, *, label: str) -> None:
    if value != expected or type(value) is not type(expected):
        raise BiomarkerReproductionInputError(f"{label}: expected {expected!r}, observed {value!r}")


def _require_number(
    value: Any,
    *,
    label: str,
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive_minimum: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BiomarkerReproductionInputError(f"{label}: expected a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise BiomarkerReproductionInputError(f"{label}: expected a finite number")
    if minimum is not None:
        invalid = result <= minimum if exclusive_minimum else result < minimum
        if invalid:
            relation = "greater than" if exclusive_minimum else "at least"
            raise BiomarkerReproductionInputError(f"{label}: expected a value {relation} {minimum}")
    if maximum is not None and result > maximum:
        raise BiomarkerReproductionInputError(
            f"{label}: expected a value no greater than {maximum}"
        )
    return result


def _validate_contract(contract: Any) -> dict[str, Any]:
    contract = _require_mapping(contract, "case contract")
    _require_exact_keys(
        contract,
        (
            "contract_version",
            "case_id",
            "scope",
            "exact_paper_dataset",
            "input_root",
            "paper",
            "replication",
            "analysis_metadata",
            "provenance_expectations",
            "acceptance_rules",
            "inputs",
        ),
        label="case contract",
    )
    _require_const(contract["contract_version"], CONTRACT_VERSION, label="contract_version")
    _require_text(contract["case_id"], label="case_id")
    _require_const(contract["scope"], CASE_SCOPE, label="scope")
    _require_const(contract["exact_paper_dataset"], False, label="exact_paper_dataset")
    input_root = _require_text(contract["input_root"], label="input_root")
    if Path(input_root).is_absolute():
        raise BiomarkerReproductionInputError("input_root: absolute paths are not allowed")

    paper = _require_mapping(contract["paper"], "paper")
    _require_exact_keys(
        paper,
        (
            "doi",
            "title",
            "publication_year",
            "analyte_evidence_terms",
            "direction_evidence",
        ),
        label="paper",
    )
    _require_const(paper["doi"], EXPECTED_DOI, label="paper.doi")
    _require_const(paper["title"], EXPECTED_PAPER_TITLE, label="paper.title")
    _require_const(paper["publication_year"], "2022", label="paper.publication_year")
    terms = paper["analyte_evidence_terms"]
    if not isinstance(terms, list) or terms != ["N-lactoyl-phenylalanine", "Lac-Phe"]:
        raise BiomarkerReproductionInputError(
            "paper.analyte_evidence_terms: expected the ordered Li-record evidence terms"
        )
    direction_evidence = _require_mapping(
        paper["direction_evidence"], "paper.direction_evidence"
    )
    _require_exact_keys(
        direction_evidence,
        ("field", "source_system", "retrieved_via", "required_phrases"),
        label="paper.direction_evidence",
    )
    _require_const(
        direction_evidence["field"],
        "abstract",
        label="paper.direction_evidence.field",
    )
    _require_const(
        direction_evidence["source_system"],
        "europe_pmc",
        label="paper.direction_evidence.source_system",
    )
    _require_const(
        direction_evidence["retrieved_via"],
        "europe_pmc_rest_search",
        label="paper.direction_evidence.retrieved_via",
    )
    _require_const(
        direction_evidence["required_phrases"],
        list(EXPECTED_DIRECTION_EVIDENCE_PHRASES),
        label="paper.direction_evidence.required_phrases",
    )

    replication = _require_mapping(contract["replication"], "replication")
    _require_exact_keys(
        replication,
        (
            "study_id",
            "study_title",
            "species",
            "source_metabolite",
            "refmet_name",
            "refmet_id",
            "stratum",
            "sample_matrix",
            "unit",
            "pre_collectionpoint",
            "post_collectionpoint",
            "contrast",
            "orientation",
            "identity_status",
            "harmonization_eligibility",
            "matrix_relationship_to_paper",
            "matrix_mismatch_caveat",
            "timing_status",
            "timing_caveat",
            "cohort_independence_status",
            "dataset_selection_status",
            "dataset_selection_caveat",
        ),
        label="replication",
    )
    constants = {
        "study_id": EXPECTED_STUDY_ID,
        "species": "Homo sapiens",
        "source_metabolite": "Lactoyl Phenylalanine",
        "refmet_name": "N-Lactoyl phenylalanine",
        "refmet_id": EXPECTED_REFMET_ID,
        "stratum": "all",
        "sample_matrix": "whole blood",
        "unit": "umol/L whole blood (study-reported)",
        "pre_collectionpoint": "Before",
        "post_collectionpoint": "After",
        "contrast": (
            "repository-derived Collectionpoint After vs Before; "
            "exercise-timing interpretation unverified"
        ),
        "orientation": "positive log2fc = higher repository-derived After vs Before",
        "identity_status": REQUIRED_IDENTITY_STATUS,
        "harmonization_eligibility": REQUIRED_HARMONIZATION_ELIGIBILITY,
        "matrix_relationship_to_paper": "mismatch",
        "timing_status": REQUIRED_TIMING_STATUS,
        "cohort_independence_status": "not_established",
        "dataset_selection_status": "post_hoc_exploratory",
    }
    for field, expected in constants.items():
        _require_const(replication[field], expected, label=f"replication.{field}")
    _require_text(replication["study_title"], label="replication.study_title")
    matrix_caveat = _require_text(
        replication["matrix_mismatch_caveat"],
        label="replication.matrix_mismatch_caveat",
    )
    if "whole-blood" not in matrix_caveat or "comparability" not in matrix_caveat:
        raise BiomarkerReproductionInputError(
            "replication.matrix_mismatch_caveat must explicitly preserve the "
            "whole-blood comparability limitation"
        )
    timing_caveat = _require_text(replication["timing_caveat"], label="replication.timing_caveat")
    if (
        "raw factor/codebook snapshot is not bound" not in timing_caveat
        or "exercise relationship" not in timing_caveat
        or "Before/After" not in timing_caveat
    ):
        raise BiomarkerReproductionInputError(
            "replication.timing_caveat must preserve the repository-derived "
            "Before/After and unverified exercise-context limitation"
        )
    selection_caveat = _require_text(
        replication["dataset_selection_caveat"],
        label="replication.dataset_selection_caveat",
    )
    if "post hoc" not in selection_caveat.lower() or "independence" not in selection_caveat.lower():
        raise BiomarkerReproductionInputError(
            "replication.dataset_selection_caveat must state that selection was "
            "post hoc and cohort independence is not established"
        )

    analysis = _require_mapping(contract["analysis_metadata"], "analysis_metadata")
    _require_exact_keys(
        analysis,
        (
            "study_id",
            "analysis_id",
            "analysis_summary",
            "analysis_type",
            "chromatography_type",
            "ms_instrument_type",
            "ms_instrument_name",
            "units",
        ),
        label="analysis_metadata",
    )
    analysis_constants = {
        "study_id": EXPECTED_STUDY_ID,
        "analysis_id": "AN006016",
        "analysis_summary": "Reversed phase UNSPECIFIED ION MODE",
        "analysis_type": "MS",
        "chromatography_type": "Reversed phase",
        "ms_instrument_type": "Orbitrap",
        "ms_instrument_name": "Thermo Q Exactive HF hybrid Orbitrap",
        "units": "umol/L whole blood",
    }
    for field, expected in analysis_constants.items():
        _require_const(analysis[field], expected, label=f"analysis_metadata.{field}")

    provenance_expectations = _require_mapping(
        contract["provenance_expectations"], "provenance_expectations"
    )
    _require_exact_keys(
        provenance_expectations,
        ("match_basis", "license", "study_link"),
        label="provenance_expectations",
    )
    provenance_constants = {
        "match_basis": "normalized name containment across source name columns",
        "license": "CC BY 4.0",
        "study_link": (
            "https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662"
        ),
    }
    for field, expected in provenance_constants.items():
        _require_const(
            provenance_expectations[field],
            expected,
            label=f"provenance_expectations.{field}",
        )

    rules = _require_mapping(contract["acceptance_rules"], "acceptance_rules")
    _require_exact_keys(
        rules,
        (
            "minimum_complete_positive_pairs",
            "mean_paired_log2_change_operator",
            "mean_paired_log2_change_threshold",
            "responder_proportion_operator",
            "minimum_responder_proportion",
            "exact_sign_test_alternative",
            "maximum_exact_sign_test_p_value",
            "cached_log2fc_absolute_tolerance",
            "cached_mean_absolute_tolerance",
        ),
        label="acceptance_rules",
    )
    minimum_n = rules["minimum_complete_positive_pairs"]
    if isinstance(minimum_n, bool) or not isinstance(minimum_n, int) or minimum_n < 1:
        raise BiomarkerReproductionInputError(
            "acceptance_rules.minimum_complete_positive_pairs: expected a positive integer"
        )
    _require_const(
        rules["mean_paired_log2_change_operator"],
        "greater_than",
        label="acceptance_rules.mean_paired_log2_change_operator",
    )
    _require_const(
        rules["mean_paired_log2_change_threshold"],
        0.0,
        label="acceptance_rules.mean_paired_log2_change_threshold",
    )
    _require_const(
        rules["responder_proportion_operator"],
        "greater_than",
        label="acceptance_rules.responder_proportion_operator",
    )
    _require_number(
        rules["minimum_responder_proportion"],
        label="acceptance_rules.minimum_responder_proportion",
        minimum=0.5,
        maximum=1.0,
    )
    _require_const(
        rules["exact_sign_test_alternative"],
        "two_sided",
        label="acceptance_rules.exact_sign_test_alternative",
    )
    _require_number(
        rules["maximum_exact_sign_test_p_value"],
        label="acceptance_rules.maximum_exact_sign_test_p_value",
        minimum=0.0,
        maximum=1.0,
        exclusive_minimum=True,
    )
    _require_number(
        rules["cached_log2fc_absolute_tolerance"],
        label="acceptance_rules.cached_log2fc_absolute_tolerance",
        minimum=0.0,
        exclusive_minimum=True,
    )
    _require_number(
        rules["cached_mean_absolute_tolerance"],
        label="acceptance_rules.cached_mean_absolute_tolerance",
        minimum=0.0,
        exclusive_minimum=True,
    )

    inputs = contract["inputs"]
    if not isinstance(inputs, list) or len(inputs) != len(INPUT_ROLES):
        raise BiomarkerReproductionInputError(
            f"inputs: expected exactly {len(INPUT_ROLES)} declared artifacts"
        )
    for index, (entry, expected_role) in enumerate(zip(inputs, INPUT_ROLES)):
        entry = _require_mapping(entry, f"inputs[{index}]")
        _require_exact_keys(entry, ("role", "path", "sha256"), label=f"inputs[{index}]")
        _require_const(entry["role"], expected_role, label=f"inputs[{index}].role")
        declared_path = _require_text(entry["path"], label=f"inputs[{index}].path")
        declared_parts = Path(declared_path).parts
        if Path(declared_path).is_absolute() or ".." in declared_parts:
            raise BiomarkerReproductionInputError(
                f"inputs[{index}].path: absolute paths and '..' segments are not allowed"
            )
        digest = _require_text(entry["sha256"], label=f"inputs[{index}].sha256")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise BiomarkerReproductionInputError(
                f"inputs[{index}].sha256: expected a lowercase SHA-256 digest"
            )
    return contract


def _resolve_and_verify_inputs(
    contract: dict[str, Any], case_path: Path
) -> tuple[Path, str, dict[str, Path], list[dict[str, str]]]:
    case_directory = case_path.parent.resolve(strict=True)
    try:
        input_root = (case_directory / contract["input_root"]).resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise BiomarkerReproductionInputError(
            "input_root: declared root cannot be resolved"
        ) from exc
    if not input_root.is_dir():
        raise BiomarkerReproductionInputError("input_root: resolved path is not a directory")
    try:
        case_within_root = case_directory.relative_to(input_root).as_posix() or "."
    except ValueError as exc:
        raise BiomarkerReproductionInputError(
            "input_root: resolved root must contain the case directory"
        ) from exc
    paths: dict[str, Path] = {}
    manifest_rows: list[dict[str, str]] = []
    for entry in contract["inputs"]:
        role = entry["role"]
        declared_path = entry["path"]
        path = (input_root / declared_path).resolve()
        try:
            path.relative_to(input_root)
        except ValueError as exc:
            raise BiomarkerReproductionInputError(
                f"{role}: declared input resolves outside input_root"
            ) from exc
        if not path.is_file():
            raise BiomarkerReproductionInputError(
                f"{role}: declared input is missing: {declared_path}"
            )
        observed = _sha256_path(path)
        if observed != entry["sha256"]:
            raise BiomarkerReproductionHashError(
                f"{role}: SHA-256 mismatch for {declared_path}; expected "
                f"{entry['sha256']}, observed {observed}"
            )
        paths[role] = path
        manifest_rows.append(
            {
                "role": role,
                "path": declared_path,
                "sha256": observed,
            }
        )
    return input_root, case_within_root, paths, manifest_rows


def _read_csv_strict(
    path: Path,
    *,
    label: str,
    expected_columns: Sequence[str],
) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise BiomarkerReproductionInputError(f"{label}: input is not valid UTF-8") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        fieldnames = tuple(reader.fieldnames or ())
        rows = list(reader)
    except csv.Error as exc:
        raise BiomarkerReproductionInputError(f"{label}: invalid CSV: {exc}") from exc
    if fieldnames != tuple(expected_columns):
        raise BiomarkerReproductionInputError(
            f"{label}: expected exact columns {list(expected_columns)!r}, "
            f"observed {list(fieldnames)!r}"
        )
    if not rows:
        raise BiomarkerReproductionInputError(f"{label}: expected at least one data row")
    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise BiomarkerReproductionInputError(
                f"{label}: row {row_number} has more fields than the header"
            )
        if any(value is None for value in row.values()):
            raise BiomarkerReproductionInputError(
                f"{label}: row {row_number} has fewer fields than the header"
            )
        if not any(row.values()):
            raise BiomarkerReproductionInputError(f"{label}: blank row {row_number} is not allowed")
    return rows


def _normalize_evidence(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _validate_literature_record(raw: Any, contract: dict[str, Any]) -> dict[str, Any]:
    records: list[Any]
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        records = [raw]
    else:
        raise BiomarkerReproductionInputError(
            "literature_record: expected a record object or a list of record objects"
        )
    mapped_records = [
        _require_mapping(record, f"literature_record[{index}]")
        for index, record in enumerate(records)
    ]
    matches = [record for record in mapped_records if record.get("doi") == contract["paper"]["doi"]]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "literature_record: expected exactly one record with DOI "
            f"{contract['paper']['doi']}; observed {len(matches)}"
        )
    record = matches[0]
    required = (
        "doi",
        "title",
        "publication_year",
        "abstract",
        "queried_expression",
        "record_key",
        "pmid",
        "pmcid",
        "record_url",
        "source_url",
        "source_system",
        "retrieved_via",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise BiomarkerReproductionInputError(
            "literature_record: missing required fields: " + ", ".join(missing)
        )
    for field in required:
        _require_text(record[field], label=f"literature_record.{field}")
    _require_const(record["doi"], contract["paper"]["doi"], label="literature_record.doi")
    _require_const(record["title"], contract["paper"]["title"], label="literature_record.title")
    _require_const(
        record["publication_year"],
        contract["paper"]["publication_year"],
        label="literature_record.publication_year",
    )
    _require_const(
        record["record_key"],
        f"doi:{contract['paper']['doi']}",
        label="literature_record.record_key",
    )
    direction_contract = contract["paper"]["direction_evidence"]
    _require_const(
        record["source_system"],
        direction_contract["source_system"],
        label="literature_record.source_system",
    )
    _require_const(
        record["retrieved_via"],
        direction_contract["retrieved_via"],
        label="literature_record.retrieved_via",
    )
    # A retrieval query is not evidence about a paper. Only bibliographic content
    # from the matched DOI record may establish that the analyte is discussed.
    evidence = _normalize_evidence(" ".join([record["title"], record["abstract"]]))
    missing_terms = [
        term
        for term in contract["paper"]["analyte_evidence_terms"]
        if _normalize_evidence(term) not in evidence
    ]
    if missing_terms:
        raise BiomarkerReproductionInputError(
            "literature_record: DOI record lacks required analyte evidence term(s): "
            + ", ".join(missing_terms)
        )
    direction_text = _normalize_evidence(record[direction_contract["field"]])
    missing_direction_phrases = [
        phrase
        for phrase in direction_contract["required_phrases"]
        if _normalize_evidence(phrase) not in direction_text
    ]
    if missing_direction_phrases:
        raise BiomarkerReproductionInputError(
            "literature_record: abstract lacks contract-bound positive-direction "
            "evidence phrase(s): " + ", ".join(missing_direction_phrases)
        )
    return record


def _validate_literature_review(raw: Any, contract: dict[str, Any]) -> dict[str, str]:
    review = _require_mapping(raw, "literature_review")
    records = review.get("records")
    if not isinstance(records, list):
        raise BiomarkerReproductionInputError("literature_review.records: expected a list")
    matches = [
        _require_mapping(record, f"literature_review.records[{index}]")
        for index, record in enumerate(records)
        if isinstance(record, dict) and record.get("doi") == contract["paper"]["doi"]
    ]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "literature_review: expected exactly one screened record for the paper DOI"
        )
    record = matches[0]
    expected = {
        "title": contract["paper"]["title"],
        "publication_year": contract["paper"]["publication_year"],
        "record_key": f"doi:{contract['paper']['doi']}",
        "pmid": "35705806",
        "pmcid": "PMC9767481",
        "record_url": "https://europepmc.org/article/MED/35705806",
        "source_systems": "europe_pmc",
        "evidence_tier": "peer_reviewed_primary",
        "review_status": "requires_human_review",
        "subject_term_evidence": "subject_name_in_abstract",
        "screen_class": "direct_human_exercise",
        "species_scope": "human_and_animal",
        "species_basis": "title_abstract_text",
        "human_evidence": "yes:text_inference",
        "exercise_evidence": "yes:text_inference",
        "metabolomics_evidence": "yes:text_inference",
        "data_availability_evidence": "no_accession_in_retrieved_text",
    }
    for field, expected_value in expected.items():
        _require_const(
            record.get(field),
            expected_value,
            label=f"literature_review.{field}",
        )
    source_urls = _require_text(record.get("source_urls"), label="literature_review.source_urls")
    screen_basis = _require_text(
        record.get("screen_basis"), label="literature_review.screen_basis"
    )
    return {
        **expected,
        "source_urls": source_urls,
        "screen_basis": screen_basis,
    }


def _validate_provenance(raw: Any, contract: dict[str, Any]) -> dict[str, Any]:
    provenance = _require_mapping(raw, "retrieval_provenance")
    required = (
        "query_original",
        "review_status",
        "decision_scope",
        "harmonization_eligibility",
        "match_basis",
        "mw_studies",
    )
    missing = [field for field in required if field not in provenance]
    if missing:
        raise BiomarkerReproductionInputError(
            "retrieval_provenance: missing required fields: " + ", ".join(missing)
        )
    replication = contract["replication"]
    _require_const(
        provenance["query_original"],
        replication["refmet_name"],
        label="retrieval_provenance.query_original",
    )
    _require_const(
        provenance["review_status"],
        REQUIRED_IDENTITY_STATUS,
        label="retrieval_provenance.review_status",
    )
    _require_const(
        provenance["decision_scope"],
        "retrieval_and_effect_extraction_only",
        label="retrieval_provenance.decision_scope",
    )
    _require_const(
        provenance["harmonization_eligibility"],
        REQUIRED_HARMONIZATION_ELIGIBILITY,
        label="retrieval_provenance.harmonization_eligibility",
    )
    _require_const(
        provenance["match_basis"],
        contract["provenance_expectations"]["match_basis"],
        label="retrieval_provenance.match_basis",
    )
    studies = provenance["mw_studies"]
    if not isinstance(studies, list):
        raise BiomarkerReproductionInputError("retrieval_provenance.mw_studies: expected an array")
    matches = [
        study
        for study in studies
        if isinstance(study, dict) and study.get("study_id") == replication["study_id"]
    ]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "retrieval_provenance.mw_studies: expected exactly one ST003662 record"
        )
    study = matches[0]
    expected = {
        "study_id": replication["study_id"],
        "study_title": replication["study_title"],
        "species": replication["species"],
        "contrast": "post-exercise vs pre-exercise (Collectionpoint After vs Before)",
        "orientation": "positive log2fc = higher post-exercise",
        "license": contract["provenance_expectations"]["license"],
        "study_link": contract["provenance_expectations"]["study_link"],
    }
    for field, value in expected.items():
        if field not in study:
            raise BiomarkerReproductionInputError(
                f"retrieval_provenance.mw_studies.ST003662: missing {field}"
            )
        _require_const(study[field], value, label=f"retrieval_provenance.ST003662.{field}")
    return {
        "match_basis": provenance["match_basis"],
        "license": study["license"],
        "study_link": study["study_link"],
        "study": study,
        "source_asserted_contrast": study["contrast"],
        "source_asserted_orientation": study["orientation"],
        "timing_interpretation_status": REQUIRED_TIMING_STATUS,
    }


def _validate_metstat_locator(
    rows: list[dict[str, str]], contract: dict[str, Any]
) -> dict[str, str]:
    replication = contract["replication"]
    analysis = contract["analysis_metadata"]
    matches = [
        row
        for row in rows
        if row["query_refmet_name"] == replication["refmet_name"]
        and row["refmet_name"] == replication["refmet_name"]
        and row["study_id"] == replication["study_id"]
        and row["analysis_id"] == analysis["analysis_id"]
    ]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "metstat_locator: expected exactly one exact analyte/study/analysis row; "
            f"observed {len(matches)}"
        )
    row = matches[0]
    expected = {
        "match_basis": "refmet_name_exact",
        "review_status": REQUIRED_IDENTITY_STATUS,
        "decision_scope": "retrieval_only",
        "harmonization_eligibility": REQUIRED_HARMONIZATION_ELIGIBILITY,
        "study_title": replication["study_title"],
        "species": "Human",
        "sample_source": "Blood",
        "analysis_type": "LCMS",
        "polarity": "UNSPECIFIED",
        "chromatography": "Reversed phase",
        "study_link": contract["provenance_expectations"]["study_link"],
        "source_system": "metabolomics_workbench_metstat",
        "provenance_url": (
            "https://www.metabolomicsworkbench.org/rest/metstat/;;;;;;;"
            "N-Lactoyl%20phenylalanine"
        ),
    }
    for field, expected_value in expected.items():
        _require_const(row[field], expected_value, label=f"metstat_locator.{field}")
    return {
        "study_id": row["study_id"],
        "analysis_id": row["analysis_id"],
        "refmet_name": row["refmet_name"],
        "sample_source": row["sample_source"],
        "analysis_type": row["analysis_type"],
        "chromatography": row["chromatography"],
        "match_basis": row["match_basis"],
        "review_status": row["review_status"],
        "harmonization_eligibility": row["harmonization_eligibility"],
        "source_system": row["source_system"],
        "provenance_url": row["provenance_url"],
        "link_status": "metstat_row_links_analyte_study_and_analysis",
    }


def _validate_analysis_metadata(
    rows: list[dict[str, str]], contract: dict[str, Any]
) -> dict[str, str]:
    expected = contract["analysis_metadata"]
    matches = [
        row
        for row in rows
        if row["study_id"] == expected["study_id"] and row["analysis_id"] == expected["analysis_id"]
    ]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "analysis_metadata: expected exactly one ST003662/AN006016 row; "
            f"observed {len(matches)}"
        )
    row = matches[0]
    for field, value in expected.items():
        _require_const(row[field], value, label=f"analysis_metadata.{field}")
    return {field: row[field] for field in expected}


def _validate_refmet(rows: list[dict[str, str]], contract: dict[str, Any]) -> dict[str, str]:
    replication = contract["replication"]
    matches = [row for row in rows if row["refmet_id"] == replication["refmet_id"]]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "refmet_annotations: expected exactly one row for "
            f"{replication['refmet_id']}; observed {len(matches)}"
        )
    row = matches[0]
    _require_const(row["name"], replication["refmet_name"], label="refmet_annotations.name")
    for field in ("super_class", "main_class", "sub_class", "formula"):
        _require_text(row[field], label=f"refmet_annotations.{field}")
    return row


def _parse_optional_nonnegative_number(value: str, *, label: str) -> float | None:
    if value == "":
        return None
    if value != value.strip():
        raise BiomarkerReproductionInputError(
            f"{label}: numeric values may not contain surrounding whitespace"
        )
    try:
        result = float(value)
    except ValueError as exc:
        raise BiomarkerReproductionInputError(
            f"{label}: expected a number or an empty value"
        ) from exc
    if not math.isfinite(result) or result < 0:
        raise BiomarkerReproductionInputError(f"{label}: expected a finite nonnegative number")
    return result


def _paired_log2_change(pre: float, post: float) -> float:
    """Compute log2(post/pre) without losing adjacent-float changes.

    Separate logarithms remain safe when a direct ratio would overflow or
    underflow, but their subtraction can round a real near-unity change to zero.
    The relative-difference/log1p branch preserves that local precision.
    """

    if post == pre:
        return 0.0
    relative_difference = (post - pre) / pre
    if math.isfinite(relative_difference) and relative_difference > -1.0:
        return math.log1p(relative_difference) / math.log(2.0)
    return math.log2(post) - math.log2(pre)


def _finite_positive_mean(values: Sequence[float]) -> float:
    """Return an arithmetic mean without overflowing or losing subnormals."""

    scale = max(values)
    scaled_mean = math.fsum(value / scale for value in values) / len(values)
    return scale * min(scaled_mean, 1.0)


def _validate_and_compute_pairs(
    rows: list[dict[str, str]], contract: dict[str, Any]
) -> dict[str, Any]:
    replication = contract["replication"]
    seen_participants: set[str] = set()
    log2_changes: list[float] = []
    pair_directions: list[int] = []
    complete_pre_values: list[float] = []
    complete_post_values: list[float] = []
    total_rows = 0
    for row_number, row in enumerate(rows, start=2):
        total_rows += 1
        metadata = {
            "study_id": replication["study_id"],
            "metabolite": replication["source_metabolite"],
            "refmet_name": replication["refmet_name"],
            "unit": replication["unit"],
        }
        for field, expected in metadata.items():
            _require_const(row[field], expected, label=f"sample_pairs row {row_number} {field}")
        participant = _require_text(
            row["participant_code"],
            label=f"sample_pairs row {row_number} participant_code",
        )
        if participant in seen_participants:
            raise BiomarkerReproductionInputError(
                f"sample_pairs: duplicate participant_code {participant!r}"
            )
        seen_participants.add(participant)
        if row["sex"] not in {"f", "m", "unknown"}:
            raise BiomarkerReproductionInputError(
                f"sample_pairs row {row_number} sex: expected 'f', 'm', or 'unknown'"
            )
        expected_pre = f"{participant}_{replication['pre_collectionpoint']}"
        expected_post = f"{participant}_{replication['post_collectionpoint']}"
        _require_const(
            row["pre_sample"],
            expected_pre,
            label=f"sample_pairs row {row_number} pre_sample",
        )
        _require_const(
            row["post_sample"],
            expected_post,
            label=f"sample_pairs row {row_number} post_sample",
        )
        pre = _parse_optional_nonnegative_number(
            row["value_pre"], label=f"sample_pairs row {row_number} value_pre"
        )
        post = _parse_optional_nonnegative_number(
            row["value_post"], label=f"sample_pairs row {row_number} value_post"
        )
        if pre is not None and post is not None and pre > 0.0 and post > 0.0:
            log2_changes.append(_paired_log2_change(pre, post))
            pair_directions.append((post > pre) - (post < pre))
            complete_pre_values.append(pre)
            complete_post_values.append(post)

    if not log2_changes:
        return {
            "total_rows": total_rows,
            "complete_positive_pairs": 0,
            "excluded_incomplete_or_nonpositive_pairs": total_rows,
            "mean_paired_log2_change": None,
            "geometric_mean_fold_change": None,
            "geometric_mean_fold_change_status": "not_computed_no_complete_positive_pairs",
            "responder_count": 0,
            "responder_proportion": None,
            "nonresponder_count": 0,
            "tie_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "log2_changes": [],
            "mean_pre": None,
            "mean_post": None,
        }
    positive_count = pair_directions.count(1)
    negative_count = pair_directions.count(-1)
    tie_count = pair_directions.count(0)
    mean_change = math.fsum(log2_changes) / len(log2_changes)
    try:
        geometric_fold_change = 2.0**mean_change
    except OverflowError:
        geometric_fold_change = None
        fold_status = "unrepresentable_overflow"
    else:
        if geometric_fold_change == 0.0:
            geometric_fold_change = None
            fold_status = "unrepresentable_underflow"
        elif not math.isfinite(geometric_fold_change):
            geometric_fold_change = None
            fold_status = "unrepresentable_overflow"
        else:
            fold_status = "computed_finite"
    return {
        "total_rows": total_rows,
        "complete_positive_pairs": len(log2_changes),
        "excluded_incomplete_or_nonpositive_pairs": total_rows - len(log2_changes),
        "mean_paired_log2_change": mean_change,
        "geometric_mean_fold_change": geometric_fold_change,
        "geometric_mean_fold_change_status": fold_status,
        "responder_count": positive_count,
        "responder_proportion": positive_count / len(log2_changes),
        "nonresponder_count": negative_count + tie_count,
        "tie_count": tie_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "log2_changes": log2_changes,
        "mean_pre": _finite_positive_mean(complete_pre_values),
        "mean_post": _finite_positive_mean(complete_post_values),
    }


def _parse_finite_csv_number(value: str, *, label: str) -> float:
    if not value or value != value.strip():
        raise BiomarkerReproductionInputError(f"{label}: expected a finite number")
    try:
        result = float(value)
    except ValueError as exc:
        raise BiomarkerReproductionInputError(f"{label}: expected a finite number") from exc
    if not math.isfinite(result):
        raise BiomarkerReproductionInputError(f"{label}: expected a finite number")
    return result


def _validate_cached_effect(
    rows: list[dict[str, str]],
    contract: dict[str, Any],
    pair_metrics: dict[str, Any],
) -> dict[str, Any]:
    replication = contract["replication"]
    matches = [
        row
        for row in rows
        if row["study_id"] == replication["study_id"]
        and row["stratum"] == replication["stratum"]
        and row["metabolite"] == replication["source_metabolite"]
        and row["refmet_name"] == replication["refmet_name"]
    ]
    if len(matches) != 1:
        raise BiomarkerReproductionInputError(
            "cached_effect: expected exactly one exact study/analyte/all-stratum row; "
            f"observed {len(matches)}"
        )
    row = matches[0]
    numeric_fields = (
        "log2fc",
        "p_value",
        "mean_pre",
        "mean_post",
        "fdr",
        "neg_log10_p",
    )
    numbers = {
        field: _parse_finite_csv_number(row[field], label=f"cached_effect.{field}")
        for field in numeric_fields
    }
    for probability_field in ("p_value", "fdr"):
        if not 0.0 <= numbers[probability_field] <= 1.0:
            raise BiomarkerReproductionInputError(
                f"cached_effect.{probability_field}: expected a probability in [0, 1]"
            )
    if numbers["p_value"] == 0.0:
        raise BiomarkerReproductionInputError(
            "cached_effect.p_value: zero cannot be reconciled with a finite "
            "cached_effect.neg_log10_p; provide a positive p-value"
        )
    for positive_field in ("mean_pre", "mean_post"):
        if numbers[positive_field] <= 0.0:
            raise BiomarkerReproductionInputError(
                f"cached_effect.{positive_field}: expected a positive value"
            )
    if numbers["neg_log10_p"] < 0.0:
        raise BiomarkerReproductionInputError(
            "cached_effect.neg_log10_p: expected a nonnegative value"
        )
    try:
        n_pairs = int(row["n_pairs"])
    except ValueError as exc:
        raise BiomarkerReproductionInputError("cached_effect.n_pairs: expected an integer") from exc
    if str(n_pairs) != row["n_pairs"] or n_pairs < 0:
        raise BiomarkerReproductionInputError(
            "cached_effect.n_pairs: expected a canonical nonnegative integer"
        )
    if n_pairs != pair_metrics["complete_positive_pairs"]:
        raise BiomarkerReproductionInputError(
            "cached_effect.n_pairs does not equal the recomputed complete-positive pair count"
        )
    recomputed = pair_metrics["mean_paired_log2_change"]
    if recomputed is None:
        raise BiomarkerReproductionInputError(
            "cached_effect supplies an effect but the sample table has no complete positive pairs"
        )
    absolute_difference = abs(numbers["log2fc"] - recomputed)
    tolerance = float(contract["acceptance_rules"]["cached_log2fc_absolute_tolerance"])
    if absolute_difference > tolerance:
        raise BiomarkerReproductionInputError(
            "cached_effect.log2fc fails the strict sample-level cross-check: "
            f"absolute difference {absolute_difference!r} exceeds tolerance {tolerance!r}"
        )
    mean_tolerance = float(contract["acceptance_rules"]["cached_mean_absolute_tolerance"])
    mean_differences = {
        field: abs(numbers[field] - pair_metrics[field])
        for field in ("mean_pre", "mean_post")
    }
    for field, difference in mean_differences.items():
        if difference > mean_tolerance:
            raise BiomarkerReproductionInputError(
                f"cached_effect.{field} fails the strict sample-level cross-check: "
                f"absolute difference {difference!r} exceeds tolerance {mean_tolerance!r}"
            )
    neg_log10_p_difference = abs(
        numbers["neg_log10_p"] - (-math.log10(numbers["p_value"]))
    )
    neg_log10_p_consistent = neg_log10_p_difference <= 1e-12
    if not neg_log10_p_consistent:
        raise BiomarkerReproductionInputError(
            "cached_effect.neg_log10_p is inconsistent with cached_effect.p_value"
        )
    return {
        "cached_log2fc": numbers["log2fc"],
        "log2fc_absolute_difference": absolute_difference,
        "cached_p_value": numbers["p_value"],
        "cached_p_value_status": "not_independently_recomputed",
        "cached_fdr": numbers["fdr"],
        "cached_fdr_status": "not_independently_recomputed",
        "cached_mean_pre": numbers["mean_pre"],
        "recomputed_mean_pre": pair_metrics["mean_pre"],
        "mean_pre_absolute_difference": mean_differences["mean_pre"],
        "cached_mean_post": numbers["mean_post"],
        "recomputed_mean_post": pair_metrics["mean_post"],
        "mean_post_absolute_difference": mean_differences["mean_post"],
        "mean_absolute_tolerance": mean_tolerance,
        "means_within_tolerance": True,
        "cached_neg_log10_p": numbers["neg_log10_p"],
        "neg_log10_p_internal_consistency": neg_log10_p_consistent,
        "neg_log10_p_absolute_difference": neg_log10_p_difference,
    }


def _exact_two_sided_sign_test(positive_count: int, negative_count: int) -> dict[str, Any]:
    n_non_tied = positive_count + negative_count
    if n_non_tied == 0:
        return {
            "alternative": "two_sided",
            "positive_count": positive_count,
            "negative_count": negative_count,
            "n_non_tied": 0,
            "p_value": None,
            "p_value_status": "not_computed_no_non_tied_pairs",
            "exact_fraction": None,
        }
    smaller = min(positive_count, negative_count)
    denominator = 2**n_non_tied
    numerator = min(
        denominator,
        2 * sum(math.comb(n_non_tied, successes) for successes in range(smaller + 1)),
    )
    divisor = math.gcd(numerator, denominator)
    reduced_numerator = numerator // divisor
    reduced_denominator = denominator // divisor
    p_value = numerator / denominator
    if p_value == 0.0:
        p_value = None
        p_value_status = "underflow_exact_fraction_available"
    else:
        p_value_status = "computed_finite"
    return {
        "alternative": "two_sided",
        "positive_count": positive_count,
        "negative_count": negative_count,
        "n_non_tied": n_non_tied,
        "p_value": p_value,
        "p_value_status": p_value_status,
        "exact_fraction": f"{reduced_numerator}/{reduced_denominator}",
    }


def _outcome_and_checks(
    pair_metrics: dict[str, Any],
    sign_test: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    rules = contract["acceptance_rules"]
    mean_change = pair_metrics["mean_paired_log2_change"]
    responder_proportion = pair_metrics["responder_proportion"]
    exact_fraction = sign_test["exact_fraction"]
    sign_fraction = Fraction(exact_fraction) if exact_fraction is not None else None
    threshold_fraction = Fraction(str(rules["maximum_exact_sign_test_p_value"]))
    checks = {
        "minimum_complete_positive_pairs_met": (
            pair_metrics["complete_positive_pairs"] >= rules["minimum_complete_positive_pairs"]
        ),
        "mean_paired_log2_change_above_threshold": (
            mean_change is not None and mean_change > rules["mean_paired_log2_change_threshold"]
        ),
        "responder_proportion_above_threshold": (
            responder_proportion is not None
            and responder_proportion > rules["minimum_responder_proportion"]
        ),
        "exact_sign_test_p_value_within_threshold": (
            sign_fraction is not None and sign_fraction <= threshold_fraction
        ),
        "identity_review_gate_preserved": (
            contract["replication"]["identity_status"] == REQUIRED_IDENTITY_STATUS
        ),
        "matrix_mismatch_caveat_preserved": (
            contract["replication"]["matrix_relationship_to_paper"] == "mismatch"
        ),
        "timing_review_gate_preserved": (
            contract["replication"]["timing_status"] == REQUIRED_TIMING_STATUS
        ),
    }
    if not checks["minimum_complete_positive_pairs_met"] or sign_fraction is None:
        return BLOCKED_OUTCOME, checks
    directional_checks = (
        "mean_paired_log2_change_above_threshold",
        "responder_proportion_above_threshold",
        "exact_sign_test_p_value_within_threshold",
    )
    if all(checks[name] for name in directional_checks):
        return SUPPORTED_OUTCOME, checks
    return NEGATIVE_OUTCOME, checks


def _build_result(
    contract: dict[str, Any],
    literature_record: dict[str, Any],
    literature_review: dict[str, str],
    provenance: dict[str, Any],
    metstat_locator: dict[str, str],
    analysis_metadata: dict[str, str],
    refmet_row: dict[str, str],
    pair_metrics: dict[str, Any],
    cached_effect: dict[str, Any],
) -> dict[str, Any]:
    sign_test = _exact_two_sided_sign_test(
        pair_metrics["positive_count"], pair_metrics["negative_count"]
    )
    outcome, checks = _outcome_and_checks(pair_metrics, sign_test, contract)
    replication = contract["replication"]
    rules = contract["acceptance_rules"]
    provenance_study = provenance["study"]
    return {
        "result_version": RESULT_VERSION,
        "case_id": contract["case_id"],
        "scope": CASE_SCOPE,
        "exact_paper_dataset": False,
        "cohort_independence_status": "not_established",
        "dataset_selection_status": "post_hoc_exploratory",
        "outcome": outcome,
        "paper_claim": {
            "doi": contract["paper"]["doi"],
            "title": contract["paper"]["title"],
            "direction": "Lac-Phe is higher after exercise",
            "doi_verified_in_cached_record": literature_record["doi"] == EXPECTED_DOI,
            "analyte_evidence_verified_in_cached_record": True,
            "direction_evidence_field": contract["paper"]["direction_evidence"]["field"],
            "direction_evidence_phrases_verified": True,
            "source_system": literature_review["source_systems"],
            "record_url": literature_review["record_url"],
            "source_url": literature_review["source_urls"],
            "pmid": literature_review["pmid"],
            "pmcid": literature_review["pmcid"],
            "evidence_tier": literature_review["evidence_tier"],
            "review_status": literature_review["review_status"],
            "screen_basis": literature_review["screen_basis"],
            "data_availability_evidence": literature_review[
                "data_availability_evidence"
            ],
            "original_paper_dataset_used": False,
        },
        "replication_context": {
            "study_id": replication["study_id"],
            "study_title": provenance_study["study_title"],
            "species": replication["species"],
            "source_metabolite": replication["source_metabolite"],
            "refmet_name": refmet_row["name"],
            "refmet_id": refmet_row["refmet_id"],
            "stratum": replication["stratum"],
            "sample_matrix": replication["sample_matrix"],
            "unit": replication["unit"],
            "pre_collectionpoint": replication["pre_collectionpoint"],
            "post_collectionpoint": replication["post_collectionpoint"],
            "contrast": replication["contrast"],
            "orientation": replication["orientation"],
            "identity_status": REQUIRED_IDENTITY_STATUS,
            "harmonization_eligibility": REQUIRED_HARMONIZATION_ELIGIBILITY,
            "matrix_relationship_to_paper": "mismatch",
            "matrix_mismatch_caveat": replication["matrix_mismatch_caveat"],
            "timing_status": replication["timing_status"],
            "timing_caveat": replication["timing_caveat"],
            "cohort_independence_status": replication["cohort_independence_status"],
            "dataset_selection_status": replication["dataset_selection_status"],
            "dataset_selection_caveat": replication["dataset_selection_caveat"],
            "refmet_release_status": "not_recorded_in_cached_annotation_file",
        },
        "analysis_metadata": analysis_metadata,
        "source_locator": metstat_locator,
        "source_provenance": {
            "match_basis": provenance["match_basis"],
            "license": provenance["license"],
            "study_link": provenance["study_link"],
            "source_asserted_contrast": provenance["source_asserted_contrast"],
            "source_asserted_orientation": provenance["source_asserted_orientation"],
            "timing_interpretation_status": provenance["timing_interpretation_status"],
        },
        "paired_statistics": {
            "total_queried_rows": pair_metrics["total_rows"],
            "complete_positive_pairs": pair_metrics["complete_positive_pairs"],
            "excluded_incomplete_or_nonpositive_pairs": pair_metrics[
                "excluded_incomplete_or_nonpositive_pairs"
            ],
            "mean_paired_log2_change": pair_metrics["mean_paired_log2_change"],
            "geometric_mean_fold_change": pair_metrics["geometric_mean_fold_change"],
            "geometric_mean_fold_change_status": pair_metrics["geometric_mean_fold_change_status"],
            "responder_count": pair_metrics["responder_count"],
            "nonresponder_count": pair_metrics["nonresponder_count"],
            "responder_proportion": pair_metrics["responder_proportion"],
            "tie_count": pair_metrics["tie_count"],
            "exact_sign_test": sign_test,
        },
        "cached_effect_crosscheck": {
            "study_id": replication["study_id"],
            "stratum": replication["stratum"],
            "cached_log2fc": cached_effect["cached_log2fc"],
            "recomputed_mean_paired_log2_change": pair_metrics["mean_paired_log2_change"],
            "absolute_difference": cached_effect["log2fc_absolute_difference"],
            "absolute_tolerance": rules["cached_log2fc_absolute_tolerance"],
            "within_tolerance": True,
            "cached_p_value": cached_effect["cached_p_value"],
            "cached_p_value_status": cached_effect["cached_p_value_status"],
            "cached_fdr": cached_effect["cached_fdr"],
            "cached_fdr_status": cached_effect["cached_fdr_status"],
            "cached_mean_pre": cached_effect["cached_mean_pre"],
            "recomputed_mean_pre": cached_effect["recomputed_mean_pre"],
            "mean_pre_absolute_difference": cached_effect["mean_pre_absolute_difference"],
            "cached_mean_post": cached_effect["cached_mean_post"],
            "recomputed_mean_post": cached_effect["recomputed_mean_post"],
            "mean_post_absolute_difference": cached_effect["mean_post_absolute_difference"],
            "mean_absolute_tolerance": cached_effect["mean_absolute_tolerance"],
            "means_within_tolerance": cached_effect["means_within_tolerance"],
            "cached_neg_log10_p": cached_effect["cached_neg_log10_p"],
            "neg_log10_p_internal_consistency": cached_effect["neg_log10_p_internal_consistency"],
            "neg_log10_p_absolute_difference": cached_effect["neg_log10_p_absolute_difference"],
        },
        "acceptance_rules": rules.copy(),
        "acceptance_checks": checks,
        "interpretation": (
            "This is a post-hoc repository After-versus-Before directional "
            "check in ST003662, not an established corroboration or exact "
            "reproduction of the Li et al. "
            "datasets or causal feeding/obesity findings. The cached source calls "
            "the contrast post-versus-pre exercise, but no raw factor/codebook "
            "snapshot is bound, so that exercise-timing interpretation is not "
            "independently verified. Dataset selection was exploratory, cohort "
            "independence is not established, metabolite identity still requires "
            "human review, and whole-blood comparability remains unresolved."
        ),
    }


def _format_number(value: float | int | None, digits: int = 6) -> str:
    if value is None:
        return "not available"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}g}"


def _render_report(result: dict[str, Any]) -> str:
    context = result["replication_context"]
    analysis = result["analysis_metadata"]
    locator = result["source_locator"]
    provenance = result["source_provenance"]
    statistics = result["paired_statistics"]
    sign_test = statistics["exact_sign_test"]
    crosscheck = result["cached_effect_crosscheck"]
    checks = result["acceptance_checks"]
    rule_lines = "\n".join(
        f"- `{name}`: {'pass' if passed else 'fail'}" for name, passed in checks.items()
    )
    return (
        "# Li et al. Lac-Phe post-hoc repository After-vs-Before directional check\n\n"
        f"**Outcome:** `{result['outcome']}`\n\n"
        "This exploratory evaluation tests whether a post-hoc selected Metabolomics "
        "Workbench dataset shows a positive repository-derived After-versus-Before "
        "direction consistent with the 2022 Li et al. claim. The cached source calls "
        "the contrast post-versus-pre exercise, but the raw factor/codebook snapshot "
        "is not bound, so that timing interpretation and cohort independence are not "
        "established. It does not use the paper's datasets or reproduce its causal "
        "feeding or obesity results.\n\n"
        "## Evidence contract\n\n"
        f"- Paper DOI: `{result['paper_claim']['doi']}` (verified in the cached record)\n"
        f"- Screened paper evidence: `{result['paper_claim']['evidence_tier']}`; "
        f"PMID `{result['paper_claim']['pmid']}`; PMCID `{result['paper_claim']['pmcid']}`; "
        f"review status `{result['paper_claim']['review_status']}`\n"
        f"- Direction evidence: `{result['paper_claim']['direction_evidence_field']}` "
        "phrases verified in the matched Europe PMC record\n"
        f"- Paper record: {result['paper_claim']['record_url']}\n"
        f"- Original-paper data availability: "
        f"`{result['paper_claim']['data_availability_evidence']}`; original paper "
        "dataset not used\n"
        f"- Repository dataset: `{context['study_id']}` — {context['study_title']}\n"
        f"- Scientific scope: `{result['scope']}`\n"
        f"- Cohort independence: `{result['cohort_independence_status']}`\n"
        f"- Dataset selection: `{result['dataset_selection_status']}`\n"
        f"- Analyte: {context['source_metabolite']} / {context['refmet_name']} "
        f"(`{context['refmet_id']}`)\n"
        f"- RefMet release status: `{context['refmet_release_status']}`\n"
        f"- Contrast: {context['contrast']}\n"
        f"- Orientation: {context['orientation']}\n"
        f"- Exact paper dataset: `{str(result['exact_paper_dataset']).lower()}`\n\n"
        "## Assay and source metadata\n\n"
        f"- Analysis: `{analysis['analysis_id']}` — {analysis['analysis_summary']}\n"
        f"- Analysis type/chromatography: {analysis['analysis_type']} / "
        f"{analysis['chromatography_type']}\n"
        f"- MS instrument: {analysis['ms_instrument_type']} — "
        f"{analysis['ms_instrument_name']}\n"
        f"- Analysis units: {analysis['units']}\n"
        f"- MetStat locator: `{locator['study_id']}/{locator['analysis_id']}`; "
        f"{locator['refmet_name']}; `{locator['link_status']}`\n"
        f"- MetStat locator review: `{locator['review_status']}`; "
        f"`{locator['harmonization_eligibility']}`\n"
        f"- Retrieval match basis: {provenance['match_basis']}\n"
        f"- Source license: {provenance['license']}\n"
        f"- Study link: {provenance['study_link']}\n"
        f"- Cached source contrast assertion: {provenance['source_asserted_contrast']}\n"
        f"- Timing interpretation status: `{provenance['timing_interpretation_status']}`\n\n"
        "## Recomputed paired result\n\n"
        f"- Queried rows: {statistics['total_queried_rows']}\n"
        f"- Complete positive pairs: {statistics['complete_positive_pairs']}\n"
        f"- Excluded incomplete/nonpositive pairs: "
        f"{statistics['excluded_incomplete_or_nonpositive_pairs']}\n"
        f"- Mean paired log2 change: "
        f"{_format_number(statistics['mean_paired_log2_change'])}\n"
        f"- Geometric mean fold change: "
        f"{_format_number(statistics['geometric_mean_fold_change'])} "
        f"(`{statistics['geometric_mean_fold_change_status']}`)\n"
        f"- Responders: {statistics['responder_count']}/"
        f"{statistics['complete_positive_pairs']} "
        f"({_format_number(statistics['responder_proportion'])})\n"
        f"- Sign-test denominator: {sign_test['n_non_tied']} non-tied pairs; "
        f"{statistics['tie_count']} ties excluded\n"
        f"- Exact two-sided sign-test p-value: "
        f"{_format_number(sign_test['p_value'])} "
        f"(`{sign_test['p_value_status']}`; exact fraction "
        f"{sign_test['exact_fraction'] or 'not available'})\n"
        f"- Cached all-stratum log2FC: {_format_number(crosscheck['cached_log2fc'])}; "
        f"absolute recomputation difference "
        f"{_format_number(crosscheck['absolute_difference'])} "
        f"(tolerance {_format_number(crosscheck['absolute_tolerance'])})\n"
        f"- Cached/recomputed arithmetic mean pre: "
        f"{_format_number(crosscheck['cached_mean_pre'])} / "
        f"{_format_number(crosscheck['recomputed_mean_pre'])}; absolute difference "
        f"{_format_number(crosscheck['mean_pre_absolute_difference'])}\n"
        f"- Cached/recomputed arithmetic mean post: "
        f"{_format_number(crosscheck['cached_mean_post'])} / "
        f"{_format_number(crosscheck['recomputed_mean_post'])}; absolute difference "
        f"{_format_number(crosscheck['mean_post_absolute_difference'])} "
        f"(tolerance {_format_number(crosscheck['mean_absolute_tolerance'])})\n"
        f"- Cached p-value: {_format_number(crosscheck['cached_p_value'])} "
        f"(`{crosscheck['cached_p_value_status']}`)\n"
        f"- Cached FDR: {_format_number(crosscheck['cached_fdr'])} "
        f"(`{crosscheck['cached_fdr_status']}`)\n"
        f"- Cached -log10(p) internal consistency: "
        f"`{str(crosscheck['neg_log10_p_internal_consistency']).lower()}`\n\n"
        "## Acceptance checks\n\n"
        f"{rule_lines}\n\n"
        "## Required limitations\n\n"
        f"- Identity status remains `{context['identity_status']}`; the RefMet name "
        "match is not permission to merge or pool assays.\n"
        f"- Matrix caveat: {context['matrix_mismatch_caveat']}\n"
        f"- Timing caveat: {context['timing_caveat']}\n"
        f"- Selection caveat: {context['dataset_selection_caveat']}\n\n"
        "## Interpretation boundary\n\n"
        f"{result['interpretation']}\n"
    )


def _validate_result_payload(result: dict[str, Any]) -> None:
    if result["outcome"] not in {
        SUPPORTED_OUTCOME,
        NEGATIVE_OUTCOME,
        BLOCKED_OUTCOME,
    }:
        raise RuntimeError("internal error: invalid biomarker reproduction outcome")
    if result["exact_paper_dataset"] is not False:
        raise RuntimeError("internal error: exact_paper_dataset must remain false")
    if result["scope"] != CASE_SCOPE:
        raise RuntimeError("internal error: scientific scope was not preserved")
    if result["cohort_independence_status"] != "not_established":
        raise RuntimeError("internal error: cohort independence must remain unestablished")
    if result["dataset_selection_status"] != "post_hoc_exploratory":
        raise RuntimeError("internal error: dataset selection status was not preserved")
    if result["replication_context"]["identity_status"] != REQUIRED_IDENTITY_STATUS:
        raise RuntimeError("internal error: identity review gate was not preserved")
    if result["replication_context"]["matrix_relationship_to_paper"] != "mismatch":
        raise RuntimeError("internal error: matrix mismatch caveat was not preserved")
    if result["replication_context"]["timing_status"] != REQUIRED_TIMING_STATUS:
        raise RuntimeError("internal error: timing review boundary was not preserved")
    if result["paper_claim"]["direction_evidence_phrases_verified"] is not True:
        raise RuntimeError("internal error: paper direction evidence was not preserved")
    if result["paper_claim"]["original_paper_dataset_used"] is not False:
        raise RuntimeError("internal error: original paper dataset use was overstated")
    if result["source_locator"]["analysis_id"] != "AN006016":
        raise RuntimeError("internal error: source analysis locator was not preserved")


def _destination_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _write_staged_file(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _publish_output_bundle(destination: Path, payloads: dict[str, bytes]) -> None:
    if _destination_exists(destination):
        raise BiomarkerReproductionInputError(
            f"output destination already exists or is a symlink: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging.", dir=destination.parent))
    try:
        for name, content in payloads.items():
            _write_staged_file(staging / name, content)
        if _destination_exists(destination):
            raise BiomarkerReproductionInputError(
                f"output destination appeared during publication: {destination}"
            )
        os.rename(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def evaluate_biomarker_reproduction(
    case_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate a checksum-bound, post-hoc Lac-Phe After-versus-Before check.

    ``case_path`` may be either a ``case.json`` file or a directory containing it.
    Inputs are validated in full before ``output_dir`` is created or modified.
    The destination must not already exist and is published as one staged bundle.
    The returned dictionary is byte-identical to the emitted ``result.json``.
    """

    case_path = Path(case_path)
    if case_path.is_dir():
        case_path = case_path / "case.json"
    if not case_path.is_file():
        raise BiomarkerReproductionInputError(f"case contract is missing: {case_path}")
    case_path = case_path.resolve(strict=True)
    contract = _validate_contract(_read_json_strict(case_path, label="case contract"))
    _, case_within_root, input_paths, manifest_inputs = _resolve_and_verify_inputs(
        contract, case_path
    )

    literature_record = _validate_literature_record(
        _read_json_strict(input_paths["literature_record"], label="literature_record"),
        contract,
    )
    literature_review = _validate_literature_review(
        _read_json_strict(input_paths["literature_review"], label="literature_review"),
        contract,
    )
    for raw_field, review_field in (
        ("pmid", "pmid"),
        ("pmcid", "pmcid"),
        ("record_url", "record_url"),
        ("source_url", "source_urls"),
        ("source_system", "source_systems"),
    ):
        _require_const(
            literature_record[raw_field],
            literature_review[review_field],
            label=f"literature_record.{raw_field} versus screened review",
        )
    provenance = _validate_provenance(
        _read_json_strict(input_paths["retrieval_provenance"], label="retrieval_provenance"),
        contract,
    )
    metstat_rows = _read_csv_strict(
        input_paths["metstat_locator"],
        label="metstat_locator",
        expected_columns=METSTAT_COLUMNS,
    )
    metstat_locator = _validate_metstat_locator(metstat_rows, contract)
    analysis_rows = _read_csv_strict(
        input_paths["analysis_metadata"],
        label="analysis_metadata",
        expected_columns=ANALYSIS_COLUMNS,
    )
    analysis_metadata = _validate_analysis_metadata(analysis_rows, contract)
    refmet_rows = _read_csv_strict(
        input_paths["refmet_annotations"],
        label="refmet_annotations",
        expected_columns=REFMET_COLUMNS,
    )
    refmet_row = _validate_refmet(refmet_rows, contract)
    sample_rows = _read_csv_strict(
        input_paths["sample_pairs"],
        label="sample_pairs",
        expected_columns=SAMPLE_COLUMNS,
    )
    pair_metrics = _validate_and_compute_pairs(sample_rows, contract)
    effect_rows = _read_csv_strict(
        input_paths["cached_effect"],
        label="cached_effect",
        expected_columns=EFFECT_COLUMNS,
    )
    cached_effect = _validate_cached_effect(effect_rows, contract, pair_metrics)
    result = _build_result(
        contract,
        literature_record,
        literature_review,
        provenance,
        metstat_locator,
        analysis_metadata,
        refmet_row,
        pair_metrics,
        cached_effect,
    )
    _validate_result_payload(result)
    result_bytes = _json_bytes(result)
    report_bytes = _render_report(result).encode("utf-8")

    # The manifest is assembled before touching the destination.  It records only
    # contract-relative input paths and output filenames, never resolved machine paths.
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "case_id": contract["case_id"],
        "case_contract": {
            "path": case_path.name,
            "sha256": _sha256_path(case_path),
        },
        "input_root": {
            "declared_path": contract["input_root"],
            "case_directory": case_within_root,
        },
        "inputs": manifest_inputs,
        "outputs": [
            {
                "role": "result",
                "path": "result.json",
                "sha256": _sha256_bytes(result_bytes),
            },
            {
                "role": "report",
                "path": "report.md",
                "sha256": _sha256_bytes(report_bytes),
            },
        ],
        "human_readable_output": "report.md",
    }
    manifest_bytes = _json_bytes(manifest)

    destination = Path(output_dir)
    _publish_output_bundle(
        destination,
        {
            "result.json": result_bytes,
            "report.md": report_bytes,
            "manifest.json": manifest_bytes,
        },
    )
    return result


def run_biomarker_reproduction(case_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Backward-readable alias for :func:`evaluate_biomarker_reproduction`."""

    return evaluate_biomarker_reproduction(case_path, output_dir)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the offline Li et al. Lac-Phe-motivated post-hoc repository "
            "After-versus-Before directional check."
        )
    )
    parser.add_argument("--case", required=True, help="case.json path or case directory")
    parser.add_argument("--out", required=True, help="output directory")
    arguments = parser.parse_args(argv)
    result = evaluate_biomarker_reproduction(arguments.case, arguments.out)
    print(result["outcome"])
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by explicit artifact builds
    raise SystemExit(main())

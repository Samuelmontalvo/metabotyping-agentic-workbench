import csv
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.evaluation.biomarker_reproduction import (
    ANALYSIS_COLUMNS,
    BLOCKED_OUTCOME,
    EFFECT_COLUMNS,
    NEGATIVE_OUTCOME,
    REFMET_COLUMNS,
    SAMPLE_COLUMNS,
    SUPPORTED_OUTCOME,
    BiomarkerReproductionHashError,
    BiomarkerReproductionInputError,
    evaluate_biomarker_reproduction,
)
from metabotyping_agentic.schemas import project_schema_path, validate_against_schema


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, object]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base_contract() -> dict[str, object]:
    return {
        "contract_version": "1.0.0",
        "case_id": "synthetic_lacphe_directional_case",
        "scope": "post_hoc_external_dataset_directional_corroboration",
        "exact_paper_dataset": False,
        "input_root": ".",
        "paper": {
            "doi": "10.1038/s41586-022-04828-5",
            "title": "An exercise-inducible metabolite that suppresses feeding and obesity",
            "publication_year": "2022",
            "analyte_evidence_terms": ["N-lactoyl-phenylalanine", "Lac-Phe"],
        },
        "replication": {
            "cohort_independence_status": "not_established",
            "dataset_selection_status": "post_hoc_exploratory",
            "dataset_selection_caveat": (
                "This dataset was selected post hoc and cohort independence from "
                "the paper is not established."
            ),
            "study_id": "ST003662",
            "study_title": "Synthetic external exercise dataset",
            "species": "Homo sapiens",
            "source_metabolite": "Lactoyl Phenylalanine",
            "refmet_name": "N-Lactoyl phenylalanine",
            "refmet_id": "RM0131640",
            "stratum": "all",
            "sample_matrix": "whole blood",
            "unit": "umol/L whole blood (study-reported)",
            "pre_collectionpoint": "Before",
            "post_collectionpoint": "After",
            "contrast": "post-exercise vs pre-exercise (Collectionpoint After vs Before)",
            "orientation": "positive log2fc = higher post-exercise",
            "identity_status": "requires_human_review",
            "harmonization_eligibility": "requires_assay_identity_review",
            "matrix_relationship_to_paper": "mismatch",
            "matrix_mismatch_caveat": (
                "Synthetic ST003662 reports whole-blood abundance; matrix and quantitative "
                "comparability to the paper are not established."
            ),
            "timing_status": "before_after_labels_verified_protocol_timing_not_reported",
            "timing_caveat": (
                "Synthetic ST003662 Collectionpoint Before/After does not report the "
                "post-exercise sampling delay."
            ),
        },
        "analysis_metadata": {
            "study_id": "ST003662",
            "analysis_id": "AN006016",
            "analysis_summary": "Reversed phase UNSPECIFIED ION MODE",
            "analysis_type": "MS",
            "chromatography_type": "Reversed phase",
            "ms_instrument_type": "Orbitrap",
            "ms_instrument_name": "Thermo Q Exactive HF hybrid Orbitrap",
            "units": "umol/L whole blood",
        },
        "provenance_expectations": {
            "match_basis": "normalized name containment across source name columns",
            "license": "CC BY 4.0",
            "study_link": (
                "https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662"
            ),
        },
        "acceptance_rules": {
            "minimum_complete_positive_pairs": 5,
            "mean_paired_log2_change_operator": "greater_than",
            "mean_paired_log2_change_threshold": 0.0,
            "responder_proportion_operator": "greater_than",
            "minimum_responder_proportion": 0.5,
            "exact_sign_test_alternative": "two_sided",
            "maximum_exact_sign_test_p_value": 0.05,
            "cached_log2fc_absolute_tolerance": 1e-12,
        },
        "inputs": [],
    }


def _sample_rows(pairs: list[tuple[object, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (pre, post) in enumerate(pairs, start=1):
        participant = f"S{index:02d}"
        rows.append(
            {
                "study_id": "ST003662",
                "metabolite": "Lactoyl Phenylalanine",
                "refmet_name": "N-Lactoyl phenylalanine",
                "participant_code": participant,
                "sex": "f" if index % 2 else "m",
                "pre_sample": f"{participant}_Before",
                "post_sample": f"{participant}_After",
                "value_pre": pre,
                "value_post": post,
                "unit": "umol/L whole blood (study-reported)",
            }
        )
    return rows


def _complete_changes(pairs: list[tuple[object, object]]) -> list[float]:
    changes: list[float] = []
    for pre, post in pairs:
        if pre == "" or post == "":
            continue
        pre_number = float(pre)
        post_number = float(post)
        if pre_number > 0 and post_number > 0:
            changes.append(math.log2(post_number) - math.log2(pre_number))
    return changes


def _make_case(
    root: Path,
    *,
    pairs: list[tuple[object, object]] | None = None,
    minimum_n: int = 5,
) -> Path:
    case_dir = root / "case"
    case_dir.mkdir(parents=True)
    pairs = pairs or [(1, 2)] * 8 + [("", 3)]

    literature = [
        {
            "doi": "10.1038/s41586-022-04828-5",
            "title": "An exercise-inducible metabolite that suppresses feeding and obesity",
            "publication_year": "2022",
            "abstract": (
                "Exercise stimulates N-lactoyl-phenylalanine (Lac-Phe), an "
                "exercise-inducible circulating metabolite."
            ),
            "queried_expression": "N-lactoyl-phenylalanine OR Lac-Phe",
            "record_key": "doi:10.1038/s41586-022-04828-5",
            "source_system": "synthetic_literature_cache",
            "retrieved_via": "synthetic_offline_fixture",
        }
    ]
    _write_json(case_dir / "literature.json", literature)

    _write_csv(case_dir / "samples.csv", _sample_rows(pairs), SAMPLE_COLUMNS)
    changes = _complete_changes(pairs)
    mean_change = math.fsum(changes) / len(changes)
    _write_csv(
        case_dir / "effect.csv",
        [
            {
                "study_id": "ST003662",
                "stratum": "all",
                "metabolite": "Lactoyl Phenylalanine",
                "refmet_name": "N-Lactoyl phenylalanine",
                "log2fc": repr(mean_change),
                "p_value": "0.01",
                "n_pairs": str(len(changes)),
                "mean_pre": "1.0",
                "mean_post": "2.0",
                "fdr": "0.02",
                "neg_log10_p": "2.0",
            }
        ],
        EFFECT_COLUMNS,
    )
    _write_json(
        case_dir / "provenance.json",
        {
            "query_original": "N-Lactoyl phenylalanine",
            "match_basis": "normalized name containment across source name columns",
            "review_status": "requires_human_review",
            "decision_scope": "retrieval_and_effect_extraction_only",
            "harmonization_eligibility": "requires_assay_identity_review",
            "mw_studies": [
                {
                    "study_id": "ST003662",
                    "study_title": "Synthetic external exercise dataset",
                    "species": "Homo sapiens",
                    "contrast": ("post-exercise vs pre-exercise (Collectionpoint After vs Before)"),
                    "orientation": "positive log2fc = higher post-exercise",
                    "license": "CC BY 4.0",
                    "study_link": (
                        "https://www.metabolomicsworkbench.org/data/"
                        "DRCCMetadata.php?StudyID=ST003662"
                    ),
                }
            ],
        },
    )
    _write_csv(
        case_dir / "analyses.csv",
        [
            {
                "study_id": "ST003662",
                "analysis_id": "AN006016",
                "analysis_summary": "Reversed phase UNSPECIFIED ION MODE",
                "analysis_type": "MS",
                "chromatography_type": "Reversed phase",
                "ms_instrument_type": "Orbitrap",
                "ion_mode": "UNSPECIFIED",
                "units": "umol/L whole blood",
                "assay_scope": "unclassified_or_other",
                "assay_scope_basis": "no explicit targeted/untargeted label",
                "chromatography system": "Thermo Vanquish",
                "column_name": "Waters ACQUITY UPLC HSS T3",
                "ms_instrument_name": "Thermo Q Exactive HF hybrid Orbitrap",
                "ms_type": "ESI",
                "nmr_experiment_type": "",
                "nmr_instrument_type": "",
                "nmr_solvent": "",
                "spectrometer_frequency": "",
            }
        ],
        ANALYSIS_COLUMNS,
    )
    _write_csv(
        case_dir / "refmet.csv",
        [
            {
                "name": "N-Lactoyl phenylalanine",
                "super_class": "Organic acids",
                "main_class": "Amino acids and peptides",
                "sub_class": "Amino acids",
                "refmet_id": "RM0131640",
                "formula": "C12H15NO4",
            }
        ],
        REFMET_COLUMNS,
    )

    contract = _base_contract()
    contract["acceptance_rules"]["minimum_complete_positive_pairs"] = minimum_n
    roles_and_paths = [
        ("literature_record", "literature.json"),
        ("sample_pairs", "samples.csv"),
        ("cached_effect", "effect.csv"),
        ("retrieval_provenance", "provenance.json"),
        ("analysis_metadata", "analyses.csv"),
        ("refmet_annotations", "refmet.csv"),
    ]
    contract["inputs"] = [
        {"role": role, "path": path, "sha256": _digest(case_dir / path)}
        for role, path in roles_and_paths
    ]
    _write_json(case_dir / "case.json", contract)
    return case_dir


def _refresh_digest(case_dir: Path, role: str) -> None:
    contract = _read_json(case_dir / "case.json")
    entry = next(item for item in contract["inputs"] if item["role"] == role)
    input_root = (case_dir / contract["input_root"]).resolve()
    entry["sha256"] = _digest(input_root / entry["path"])
    _write_json(case_dir / "case.json", contract)


class BiomarkerReproductionTests(unittest.TestCase):
    def test_directional_support_recomputes_all_required_statistics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            output_dir = root / "out"
            result = evaluate_biomarker_reproduction(case_dir, output_dir)

            self.assertEqual(result["outcome"], SUPPORTED_OUTCOME)
            self.assertFalse(result["exact_paper_dataset"])
            self.assertEqual(
                result["scope"],
                "post_hoc_external_dataset_directional_corroboration",
            )
            self.assertEqual(result["cohort_independence_status"], "not_established")
            self.assertEqual(result["dataset_selection_status"], "post_hoc_exploratory")
            statistics = result["paired_statistics"]
            self.assertEqual(statistics["total_queried_rows"], 9)
            self.assertEqual(statistics["complete_positive_pairs"], 8)
            self.assertEqual(statistics["excluded_incomplete_or_nonpositive_pairs"], 1)
            self.assertEqual(statistics["mean_paired_log2_change"], 1.0)
            self.assertEqual(statistics["geometric_mean_fold_change"], 2.0)
            self.assertEqual(statistics["geometric_mean_fold_change_status"], "computed_finite")
            self.assertEqual(statistics["responder_count"], 8)
            self.assertEqual(statistics["responder_proportion"], 1.0)
            self.assertEqual(statistics["exact_sign_test"]["p_value"], 1 / 128)
            self.assertEqual(statistics["exact_sign_test"]["exact_fraction"], "1/128")
            self.assertEqual(
                result["replication_context"]["identity_status"],
                "requires_human_review",
            )
            self.assertEqual(
                result["replication_context"]["matrix_relationship_to_paper"],
                "mismatch",
            )
            self.assertEqual(result["analysis_metadata"]["analysis_id"], "AN006016")
            self.assertEqual(
                result["replication_context"]["refmet_release_status"],
                "not_recorded_in_cached_annotation_file",
            )
            crosscheck = result["cached_effect_crosscheck"]
            self.assertEqual(
                crosscheck["cached_p_value_status"],
                "not_independently_recomputed",
            )
            self.assertEqual(
                crosscheck["cached_fdr_status"],
                "not_independently_recomputed",
            )
            self.assertTrue(crosscheck["neg_log10_p_internal_consistency"])
            self.assertEqual(
                {path.name for path in output_dir.iterdir()},
                {"result.json", "report.md", "manifest.json"},
            )

    def test_opposite_direction_does_not_support_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root, pairs=[(2, 1)] * 8)
            result = evaluate_biomarker_reproduction(case_dir, root / "out")

            self.assertEqual(result["outcome"], NEGATIVE_OUTCOME)
            self.assertLess(result["paired_statistics"]["mean_paired_log2_change"], 0)
            self.assertEqual(result["paired_statistics"]["responder_count"], 0)
            self.assertFalse(result["acceptance_checks"]["mean_paired_log2_change_above_threshold"])

    def test_valid_but_underpowered_case_is_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root, pairs=[(1, 2)] * 8, minimum_n=9)
            result = evaluate_biomarker_reproduction(case_dir, root / "out")

            self.assertEqual(result["outcome"], BLOCKED_OUTCOME)
            self.assertFalse(result["acceptance_checks"]["minimum_complete_positive_pairs_met"])

    def test_outputs_and_manifest_are_byte_deterministic_and_relative(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            first = root / "first"
            second = root / "second"
            evaluate_biomarker_reproduction(case_dir, first)
            evaluate_biomarker_reproduction(case_dir, second)

            for filename in ("result.json", "report.md", "manifest.json"):
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
            manifest = _read_json(first / "manifest.json")
            self.assertEqual(
                manifest["input_root"],
                {"declared_path": ".", "case_directory": "."},
            )
            all_paths = [manifest["case_contract"]["path"]] + [
                item["path"] for item in manifest["inputs"] + manifest["outputs"]
            ]
            self.assertTrue(all(not Path(path).is_absolute() for path in all_paths))
            serialized = (first / "manifest.json").read_text(encoding="utf-8")
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("timestamp", serialized.lower())
            for output in manifest["outputs"]:
                self.assertEqual(output["sha256"], _digest(first / output["path"]))

    def test_synthetic_case_result_and_manifest_validate_against_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            output_dir = root / "out"
            evaluate_biomarker_reproduction(case_dir, output_dir)

            validations = [
                (
                    _read_json(case_dir / "case.json"),
                    "biomarker_reproduction_case.schema.json",
                ),
                (
                    _read_json(output_dir / "result.json"),
                    "biomarker_reproduction_result.schema.json",
                ),
                (
                    _read_json(output_dir / "manifest.json"),
                    "biomarker_reproduction_manifest.schema.json",
                ),
            ]
            for value, schema_name in validations:
                self.assertEqual(
                    validate_against_schema(value, project_schema_path(schema_name)), []
                )

    def test_mutated_input_hash_stops_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            with (case_dir / "samples.csv").open("a", encoding="utf-8") as handle:
                handle.write("mutated\n")
            output_dir = root / "out"

            with self.assertRaises(BiomarkerReproductionHashError):
                evaluate_biomarker_reproduction(case_dir, output_dir)
            self.assertFalse(output_dir.exists())

    def test_missing_or_mismatched_doi_fails_closed(self):
        for mutation in ("missing", "mismatched"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                case_dir = _make_case(root)
                records = _read_json(case_dir / "literature.json")
                if mutation == "missing":
                    records[0].pop("doi")
                else:
                    records[0]["doi"] = "10.0000/not-the-li-paper"
                _write_json(case_dir / "literature.json", records)
                _refresh_digest(case_dir, "literature_record")
                output_dir = root / "out"

                with self.assertRaises(BiomarkerReproductionInputError):
                    evaluate_biomarker_reproduction(case_dir, output_dir)
                self.assertFalse(output_dir.exists())

    def test_contract_doi_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            contract = _read_json(case_dir / "case.json")
            contract["paper"]["doi"] = "10.0000/not-the-li-paper"
            _write_json(case_dir / "case.json", contract)

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")
            self.assertFalse((root / "out").exists())

    def test_missing_literature_analyte_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            records = _read_json(case_dir / "literature.json")
            records[0]["abstract"] = "A synthetic abstract about an unrelated molecule."
            records[0]["queried_expression"] = "N-lactoyl-phenylalanine OR Lac-Phe"
            _write_json(case_dir / "literature.json", records)
            _refresh_digest(case_dir, "literature_record")

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")
            self.assertFalse((root / "out").exists())

    def test_sample_analyte_and_refmet_mismatches_fail_closed(self):
        mutations = (
            ("metabolite", "Different feature"),
            ("refmet_name", "Different RefMet name"),
        )
        for field, value in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                case_dir = _make_case(root)
                with (case_dir / "samples.csv").open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                rows[0][field] = value
                _write_csv(case_dir / "samples.csv", rows, SAMPLE_COLUMNS)
                _refresh_digest(case_dir, "sample_pairs")

                with self.assertRaises(BiomarkerReproductionInputError):
                    evaluate_biomarker_reproduction(case_dir, root / "out")
                self.assertFalse((root / "out").exists())

    def test_timing_label_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            with (case_dir / "samples.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["post_sample"] = "S01_Later"
            _write_csv(case_dir / "samples.csv", rows, SAMPLE_COLUMNS)
            _refresh_digest(case_dir, "sample_pairs")

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")
            self.assertFalse((root / "out").exists())

    def test_identity_gate_mismatch_in_contract_or_provenance_fails_closed(self):
        for location in ("contract", "provenance"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                case_dir = _make_case(root)
                if location == "contract":
                    contract = _read_json(case_dir / "case.json")
                    contract["replication"]["identity_status"] = "accepted"
                    _write_json(case_dir / "case.json", contract)
                else:
                    provenance = _read_json(case_dir / "provenance.json")
                    provenance["review_status"] = "accepted"
                    _write_json(case_dir / "provenance.json", provenance)
                    _refresh_digest(case_dir, "retrieval_provenance")

                with self.assertRaises(BiomarkerReproductionInputError):
                    evaluate_biomarker_reproduction(case_dir, root / "out")
                self.assertFalse((root / "out").exists())

    def test_missing_and_inconsistent_provenance_fail_closed(self):
        for mutation in ("missing", "orientation"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                case_dir = _make_case(root)
                if mutation == "missing":
                    (case_dir / "provenance.json").unlink()
                else:
                    provenance = _read_json(case_dir / "provenance.json")
                    provenance["mw_studies"][0]["orientation"] = (
                        "negative log2fc = higher post-exercise"
                    )
                    _write_json(case_dir / "provenance.json", provenance)
                    _refresh_digest(case_dir, "retrieval_provenance")

                with self.assertRaises(BiomarkerReproductionInputError):
                    evaluate_biomarker_reproduction(case_dir, root / "out")
                self.assertFalse((root / "out").exists())

    def test_refmet_identity_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            _write_csv(
                case_dir / "refmet.csv",
                [
                    {
                        "name": "N-Lactoyl phenylalanine",
                        "super_class": "Organic acids",
                        "main_class": "Amino acids and peptides",
                        "sub_class": "Amino acids",
                        "refmet_id": "RM0000000",
                        "formula": "C12H15NO4",
                    }
                ],
                REFMET_COLUMNS,
            )
            _refresh_digest(case_dir, "refmet_annotations")

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")
            self.assertFalse((root / "out").exists())

    def test_cached_log2fc_mismatch_fails_strict_crosscheck(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            with (case_dir / "effect.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["log2fc"] = "1.00000001"
            _write_csv(case_dir / "effect.csv", rows, EFFECT_COLUMNS)
            _refresh_digest(case_dir, "cached_effect")

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")
            self.assertFalse((root / "out").exists())

    def test_extreme_finite_pairs_do_not_emit_nonstandard_numbers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pairs = [(5e-324, 1.7976931348623157e308)] * 8
            case_dir = _make_case(root, pairs=pairs)
            output_dir = root / "out"
            result = evaluate_biomarker_reproduction(case_dir, output_dir)

            statistics = result["paired_statistics"]
            self.assertTrue(math.isfinite(statistics["mean_paired_log2_change"]))
            self.assertIsNone(statistics["geometric_mean_fold_change"])
            self.assertEqual(
                statistics["geometric_mean_fold_change_status"],
                "unrepresentable_overflow",
            )
            serialized = (output_dir / "result.json").read_text(encoding="utf-8")
            self.assertNotIn("NaN", serialized)
            self.assertNotIn("Infinity", serialized)

    def test_cached_neg_log10_p_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            with (case_dir / "effect.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["neg_log10_p"] = "1.9"
            _write_csv(case_dir / "effect.csv", rows, EFFECT_COLUMNS)
            _refresh_digest(case_dir, "cached_effect")

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")

    def test_analysis_and_source_provenance_mismatches_fail_closed(self):
        for role, filename, field, value in (
            ("analysis_metadata", "analyses.csv", "analysis_id", "AN006015"),
            ("retrieval_provenance", "provenance.json", "match_basis", "name guess"),
        ):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                case_dir = _make_case(root)
                if filename.endswith(".csv"):
                    with (case_dir / filename).open(newline="", encoding="utf-8") as handle:
                        rows = list(csv.DictReader(handle))
                    rows[0][field] = value
                    _write_csv(case_dir / filename, rows, ANALYSIS_COLUMNS)
                else:
                    payload = _read_json(case_dir / filename)
                    payload[field] = value
                    _write_json(case_dir / filename, payload)
                _refresh_digest(case_dir, role)

                with self.assertRaises(BiomarkerReproductionInputError):
                    evaluate_biomarker_reproduction(case_dir, root / "out")

    def test_input_paths_reject_traversal_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            contract = _read_json(case_dir / "case.json")
            contract["inputs"][0]["path"] = "../outside.json"
            _write_json(case_dir / "case.json", contract)
            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out-traversal")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            outside = root / "outside.csv"
            outside.write_bytes((case_dir / "samples.csv").read_bytes())
            symlink = case_dir / "linked-samples.csv"
            symlink.symlink_to(outside)
            contract = _read_json(case_dir / "case.json")
            entry = next(item for item in contract["inputs"] if item["role"] == "sample_pairs")
            entry["path"] = symlink.name
            entry["sha256"] = _digest(outside)
            _write_json(case_dir / "case.json", contract)
            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out-symlink")

    def test_input_root_must_resolve_to_ancestor_of_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_dir = _make_case(root)
            unrelated_root = root / "unrelated-root"
            unrelated_root.mkdir()
            contract = _read_json(case_dir / "case.json")
            contract["input_root"] = "../unrelated-root"
            _write_json(case_dir / "case.json", contract)

            with self.assertRaises(BiomarkerReproductionInputError):
                evaluate_biomarker_reproduction(case_dir, root / "out")

    def test_existing_or_symlink_output_destination_is_rejected_untouched(self):
        for destination_kind in ("directory", "symlink"):
            with (
                self.subTest(destination_kind=destination_kind),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                case_dir = _make_case(root)
                destination = root / "out"
                if destination_kind == "directory":
                    destination.mkdir()
                    sentinel = destination / "sentinel.txt"
                    sentinel.write_text("preserve", encoding="utf-8")
                else:
                    target = root / "target"
                    target.mkdir()
                    destination.symlink_to(target, target_is_directory=True)
                    sentinel = target / "sentinel.txt"
                    sentinel.write_text("preserve", encoding="utf-8")

                with self.assertRaises(BiomarkerReproductionInputError):
                    evaluate_biomarker_reproduction(case_dir, destination)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")
                self.assertFalse(any(root.glob(".out.staging.*")))

    def test_real_case_matches_checked_in_golden_artifacts_byte_for_byte(self):
        repository = Path(__file__).resolve().parents[1]
        case_dir = repository / "data" / "live" / "biomarker_reproduction" / "lacphe_li_2022"
        golden_dir = repository / "reports_live" / "biomarker_reproduction" / "lacphe_li_2022"
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "real-case"
            result = evaluate_biomarker_reproduction(case_dir, output_dir)

            self.assertEqual(result["paired_statistics"]["total_queried_rows"], 137)
            self.assertEqual(result["paired_statistics"]["complete_positive_pairs"], 116)
            self.assertEqual(result["paired_statistics"]["responder_count"], 92)
            self.assertAlmostEqual(
                result["paired_statistics"]["mean_paired_log2_change"],
                1.1586026041398587,
                places=14,
            )
            self.assertAlmostEqual(
                result["paired_statistics"]["geometric_mean_fold_change"],
                2.2324109131516057,
                places=14,
            )
            self.assertAlmostEqual(
                result["paired_statistics"]["exact_sign_test"]["p_value"],
                1.4181822700488305e-10,
                places=22,
            )
            for filename in ("result.json", "report.md", "manifest.json"):
                self.assertEqual(
                    (output_dir / filename).read_bytes(),
                    (golden_dir / filename).read_bytes(),
                )

            for value, schema_name in (
                (
                    _read_json(case_dir / "case.json"),
                    "biomarker_reproduction_case.schema.json",
                ),
                (
                    _read_json(output_dir / "result.json"),
                    "biomarker_reproduction_result.schema.json",
                ),
                (
                    _read_json(output_dir / "manifest.json"),
                    "biomarker_reproduction_manifest.schema.json",
                ),
            ):
                self.assertEqual(
                    validate_against_schema(value, project_schema_path(schema_name)), []
                )


if __name__ == "__main__":
    unittest.main()

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.evaluation.harmonization_reference import (
    COMPARISON_FILENAME,
    DISAGREEMENT_FILENAME,
    MANIFEST_FILENAME,
    REPORT_FILENAME,
    HarmonizationReferenceInputError,
    compare_harmonization_reference,
)
from metabotyping_agentic.io import write_csv_rows
from metabotyping_agentic.schemas import (
    project_schema_path,
    validate_against_schema,
)

ROOT = Path(__file__).resolve().parents[1]
PREDICTED_FIELDS = [
    "source_study",
    "source_variable",
    "proposed_common_variable",
    "review_status",
]
REFERENCE_FIELDS = [
    "source_study",
    "source_variable",
    "common_variable",
    "review_status",
]
BLOCKED_OUTPUTS = {
    COMPARISON_FILENAME,
    REPORT_FILENAME,
    MANIFEST_FILENAME,
}
COMPLETE_OUTPUTS = BLOCKED_OUTPUTS | {DISAGREEMENT_FILENAME}


def predicted_row(
    source_variable: str,
    common_variable: str,
    review_status: str,
    *,
    source_study: str = "SYN-COHORT",
) -> dict[str, str]:
    return {
        "source_study": source_study,
        "source_variable": source_variable,
        "proposed_common_variable": common_variable,
        "review_status": review_status,
    }


def reference_row(
    source_variable: str,
    common_variable: str,
    review_status: str,
    *,
    source_study: str = "SYN-COHORT",
) -> dict[str, str]:
    return {
        "source_study": source_study,
        "source_variable": source_variable,
        "common_variable": common_variable,
        "review_status": review_status,
    }


def write_inputs(
    root: Path,
    predicted_rows: list[dict[str, str]],
    reference_rows: list[dict[str, str]],
) -> tuple[Path, Path, Path]:
    predicted_path = root / "inputs" / "crosswalk.csv"
    reference_path = root / "inputs" / "curator_reference.csv"
    output_dir = root / "outputs"
    write_csv_rows(predicted_path, predicted_rows, PREDICTED_FIELDS)
    write_csv_rows(reference_path, reference_rows, REFERENCE_FIELDS)
    return predicted_path, reference_path, output_dir


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class HarmonizationReferenceComparisonTests(unittest.TestCase):
    def test_exact_universe_perfect_agreement_unlocks_metrics(self):
        predicted = [
            predicted_row("age", "age", "accepted"),
            predicted_row("peak_vo2", "vo2max", "requires_human_review"),
            predicted_row("unknown_feature", "not_mapped", "rejected"),
        ]
        reference = [
            reference_row("unknown_feature", "not_mapped", "rejected"),
            reference_row("peak_vo2", "vo2max", "requires_human_review"),
            reference_row("age", "age", "accepted"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            predicted_path, reference_path, output_dir = write_inputs(
                Path(tmp), predicted, reference
            )
            result = compare_harmonization_reference(
                predicted_path,
                reference_path,
                output_dir,
                predicted_declared_path="data/extracted/crosswalk.csv",
                reference_declared_path="data/external/curator_reference.csv",
            )

            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["headline_metrics_available"])
            self.assertTrue(result["dataset_universe"]["exact_match"])
            self.assertEqual(result["disagreement_count"], 0)
            self.assertEqual(
                {path.name for path in output_dir.iterdir()}, COMPLETE_OUTPUTS
            )
            self.assertEqual(
                (output_dir / DISAGREEMENT_FILENAME).read_text(encoding="utf-8"),
                ",".join(
                    [
                        "source_study",
                        "source_variable",
                        "reference_common_variable",
                        "predicted_common_variable",
                        "reference_review_status",
                        "predicted_review_status",
                        "reason_codes",
                    ]
                )
                + "\n",
            )

            metrics = result["metrics"]
            for name in (
                "exact_mapping_agreement",
                "review_status_accuracy",
                "accepted_mapping_precision",
                "accepted_mapping_recall",
                "review_required_capture",
            ):
                self.assertEqual(metrics[name]["value"], 1.0)
                self.assertGreater(metrics[name]["denominator"], 0)
            self.assertEqual(metrics["unsafe_auto_accept_count"]["value"], 0)
            self.assertEqual(metrics["unsafe_auto_accept_rate"]["value"], 0.0)

            serialized = read_json(output_dir / COMPARISON_FILENAME)
            self.assertEqual(
                validate_against_schema(
                    serialized,
                    project_schema_path(
                        "harmonization_reference_comparison.schema.json"
                    ),
                ),
                [],
            )
            manifest = read_json(output_dir / MANIFEST_FILENAME)
            for output in manifest["outputs"]:
                artifact_path = output_dir / output["path"]
                self.assertEqual(
                    output["sha256"],
                    hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                )
            all_output_text = "".join(
                path.read_text(encoding="utf-8") for path in output_dir.iterdir()
            )
            self.assertNotIn(tmp, all_output_text)

    def test_disagreements_and_unsafe_auto_accepts_are_separate(self):
        predicted = [
            predicted_row("A", "wrong_A", "accepted"),
            predicted_row("B", "common_B", "accepted"),
            predicted_row("C", "wrong_C", "requires_human_review"),
            predicted_row("D", "common_D", "rejected"),
        ]
        reference = [
            reference_row("A", "common_A", "accepted"),
            reference_row("B", "common_B", "requires_human_review"),
            reference_row("C", "common_C", "requires_human_review"),
            reference_row("D", "common_D", "accepted"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            predicted_path, reference_path, output_dir = write_inputs(
                Path(tmp), predicted, reference
            )
            result = compare_harmonization_reference(
                predicted_path, reference_path, output_dir
            )
            with (output_dir / DISAGREEMENT_FILENAME).open(
                newline="", encoding="utf-8"
            ) as handle:
                disagreements = list(csv.DictReader(handle))

        metrics = result["metrics"]
        self.assertEqual(metrics["exact_mapping_agreement"]["value"], 0.5)
        self.assertEqual(metrics["review_status_accuracy"]["value"], 0.5)
        self.assertEqual(metrics["accepted_mapping_precision"]["value"], 0.0)
        self.assertEqual(metrics["accepted_mapping_recall"]["value"], 0.0)
        self.assertEqual(metrics["unsafe_auto_accept_count"]["value"], 2)
        self.assertEqual(metrics["unsafe_auto_accept_rate"]["value"], 1.0)
        self.assertEqual(metrics["review_required_capture"]["value"], 0.0)
        self.assertEqual(result["disagreement_count"], 4)
        self.assertEqual([row["source_variable"] for row in disagreements], list("ABCD"))
        self.assertEqual(
            disagreements[0]["reason_codes"],
            "common_variable_mismatch;unsafe_auto_accept",
        )
        self.assertEqual(
            disagreements[1]["reason_codes"],
            "review_status_mismatch;unsafe_auto_accept",
        )

    def test_missing_and_empty_references_emit_blocked_artifacts_without_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_path = root / "crosswalk.csv"
            missing_reference = root / "missing_reference.csv"
            write_csv_rows(
                predicted_path,
                [predicted_row("age", "age", "accepted")],
                PREDICTED_FIELDS,
            )
            missing_output = root / "missing_output"
            missing_result = compare_harmonization_reference(
                predicted_path,
                missing_reference,
                missing_output,
                reference_declared_path="data/external/curator_reference.csv",
            )

            self.assertEqual(missing_result["status"], "blocked_missing_reference")
            self.assertIsNone(missing_result["metrics"])
            self.assertFalse(missing_result["headline_metrics_available"])
            self.assertEqual(
                {path.name for path in missing_output.iterdir()}, BLOCKED_OUTPUTS
            )
            self.assertIsNone(missing_result["inputs"][1]["sha256"])
            self.assertIsNone(missing_result["inputs"][1]["row_count"])
            self.assertNotIn(
                "Headline metrics\n",
                (missing_output / REPORT_FILENAME).read_text(encoding="utf-8"),
            )

            empty_reference = root / "empty_reference.csv"
            write_csv_rows(empty_reference, [], REFERENCE_FIELDS)
            empty_output = root / "empty_output"
            empty_result = compare_harmonization_reference(
                predicted_path, empty_reference, empty_output
            )
            self.assertEqual(empty_result["status"], "blocked_empty_reference")
            self.assertIsNone(empty_result["metrics"])
            self.assertEqual(empty_result["dataset_universe"]["reference_count"], 0)
            self.assertEqual(
                {path.name for path in empty_output.iterdir()}, BLOCKED_OUTPUTS
            )
            self.assertEqual(empty_result["inputs"][1]["state"], "present")
            self.assertIsNotNone(empty_result["inputs"][1]["sha256"])

            zero_byte_reference = root / "zero_byte_reference.csv"
            zero_byte_reference.touch()
            zero_byte_output = root / "zero_byte_output"
            zero_byte_result = compare_harmonization_reference(
                predicted_path, zero_byte_reference, zero_byte_output
            )
            self.assertEqual(
                zero_byte_result["status"], "blocked_empty_reference"
            )
            self.assertIsNone(zero_byte_result["metrics"])
            self.assertEqual(
                {path.name for path in zero_byte_output.iterdir()}, BLOCKED_OUTPUTS
            )

    def test_partial_and_extra_universe_blocks_all_headline_metrics(self):
        predicted = [
            predicted_row("A", "common_A", "accepted"),
            predicted_row("B", "common_B", "accepted"),
        ]
        reference = [
            reference_row("A", "common_A", "accepted"),
            reference_row("C", "common_C", "accepted"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            predicted_path, reference_path, output_dir = write_inputs(
                Path(tmp), predicted, reference
            )
            result = compare_harmonization_reference(
                predicted_path, reference_path, output_dir
            )

            self.assertEqual(
                result["status"], "blocked_dataset_universe_mismatch"
            )
            self.assertIsNone(result["metrics"])
            self.assertFalse(result["headline_metrics_available"])
            self.assertEqual(
                result["dataset_universe"]["missing_from_prediction"],
                [{"source_study": "SYN-COHORT", "source_variable": "C"}],
            )
            self.assertEqual(
                result["dataset_universe"]["extra_in_prediction"],
                [{"source_study": "SYN-COHORT", "source_variable": "B"}],
            )
            self.assertEqual(
                {path.name for path in output_dir.iterdir()}, BLOCKED_OUTPUTS
            )

    def test_malformed_duplicates_conflicts_and_statuses_fail_before_write(self):
        cases = [
            (
                [
                    predicted_row("A", "common_A", "accepted"),
                    predicted_row("A", "common_A", "accepted"),
                ],
                [reference_row("A", "common_A", "accepted")],
                "duplicate entity key",
            ),
            (
                [predicted_row("A", "common_A", "accepted")],
                [
                    reference_row("A", "common_A", "accepted"),
                    reference_row("A", "other_A", "requires_human_review"),
                ],
                "conflicting duplicate entity key",
            ),
            (
                [predicted_row("A", "common_A", "auto_accepted")],
                [reference_row("A", "common_A", "accepted")],
                "invalid review_status",
            ),
        ]
        for predicted, reference, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                with tempfile.TemporaryDirectory() as tmp:
                    predicted_path, reference_path, output_dir = write_inputs(
                        Path(tmp), predicted, reference
                    )
                    with self.assertRaisesRegex(
                        HarmonizationReferenceInputError, expected_message
                    ):
                        compare_harmonization_reference(
                            predicted_path, reference_path, output_dir
                        )
                    self.assertFalse(output_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_path = root / "crosswalk.csv"
            write_csv_rows(
                predicted_path,
                [
                    predicted_row("A", "common_A", "accepted"),
                    predicted_row("A", "other_A", "accepted"),
                ],
                PREDICTED_FIELDS,
            )
            output_dir = root / "output"
            with self.assertRaises(HarmonizationReferenceInputError):
                compare_harmonization_reference(
                    predicted_path, root / "still_missing.csv", output_dir
                )
            self.assertFalse(output_dir.exists())

    def test_complete_outputs_are_byte_deterministic(self):
        predicted = [
            predicted_row("B", "common_B", "requires_human_review"),
            predicted_row("A", "wrong_A", "accepted"),
        ]
        reference = [
            reference_row("A", "common_A", "requires_human_review"),
            reference_row("B", "common_B", "requires_human_review"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_predicted, first_reference, first_output = write_inputs(
                root / "first", predicted, reference
            )
            second_predicted, second_reference, second_output = write_inputs(
                root / "second", predicted, reference
            )
            for predicted_path, reference_path, output_dir in (
                (first_predicted, first_reference, first_output),
                (second_predicted, second_reference, second_output),
            ):
                compare_harmonization_reference(
                    predicted_path,
                    reference_path,
                    output_dir,
                    predicted_declared_path="data/extracted/crosswalk.csv",
                    reference_declared_path="data/external/curator_reference.csv",
                )

            self.assertEqual(
                {path.name for path in first_output.iterdir()}, COMPLETE_OUTPUTS
            )
            for filename in COMPLETE_OUTPUTS:
                self.assertEqual(
                    (first_output / filename).read_bytes(),
                    (second_output / filename).read_bytes(),
                    filename,
                )

    def test_checked_in_template_is_header_only_and_neutrally_labeled(self):
        template = ROOT / "data/reference_templates/harmonization_reference_template.csv"
        text = template.read_text(encoding="utf-8")
        self.assertEqual(text, ",".join(REFERENCE_FIELDS) + "\n")
        self.assertNotIn("hardik", text.lower())
        manifest_template = read_json(
            ROOT / "data/reference_templates/reference_manifest.template.json"
        )
        self.assertEqual(
            manifest_template["reference_role"], "independent_curator_reference"
        )
        self.assertIn("REPLACE", manifest_template["reference_sha256"])


if __name__ == "__main__":
    unittest.main()

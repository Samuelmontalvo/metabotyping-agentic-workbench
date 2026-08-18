import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from metabotyping_agentic.evaluation.benchmark import (
    BenchmarkInputError,
    CASE_OUTCOME_PRECEDENCE,
    METRIC_NAMES,
    benchmark,
)
from metabotyping_agentic.io import read_json, write_csv_rows, write_json
from metabotyping_agentic.schemas import project_schema_path, validate_against_schema


ROOT = Path(__file__).resolve().parents[1]
PREDICTED_FIELDS = [
    "source_study",
    "source_variable",
    "proposed_common_variable",
    "review_status",
]
GOLD_FIELDS = [
    "source_study",
    "source_variable",
    "common_variable",
    "review_status",
]
EXPECTED_OUTPUTS = {
    "benchmark_results.json",
    "benchmark_case_results.json",
    "benchmark_disagreements.csv",
    "benchmark_report.md",
    "benchmark_manifest.json",
}


def predicted_mapping(
    source_variable: str,
    status: str,
    *,
    study: str = "SYN",
    common_variable: str | None = None,
) -> dict[str, str]:
    return {
        "source_study": study,
        "source_variable": source_variable,
        "proposed_common_variable": (
            common_variable
            if common_variable is not None
            else f"common_{source_variable}"
        ),
        "review_status": status,
    }


def gold_mapping(
    source_variable: str,
    status: str,
    *,
    study: str = "SYN",
    common_variable: str | None = None,
) -> dict[str, str]:
    return {
        "source_study": study,
        "source_variable": source_variable,
        "common_variable": (
            common_variable
            if common_variable is not None
            else f"common_{source_variable}"
        ),
        "review_status": status,
    }


def write_mapping_inputs(
    root: Path,
    predicted_rows: list[dict[str, str]],
    gold_rows: list[dict[str, str]],
) -> tuple[Path, Path, Path]:
    predicted_dir = root / "predicted"
    gold_dir = root / "gold"
    out_dir = root / "out"
    write_csv_rows(
        predicted_dir / "crosswalk.csv",
        predicted_rows,
        fieldnames=PREDICTED_FIELDS,
    )
    write_csv_rows(
        gold_dir / "expert_variable_mappings.csv",
        gold_rows,
        fieldnames=GOLD_FIELDS,
    )
    return predicted_dir, gold_dir, out_dir


def write_quality_inputs(
    predicted_dir: Path,
    gold_dir: Path,
    predicted_scores: list[tuple[str, str | float]],
    gold_scores: list[tuple[str, str | float]],
) -> None:
    write_json(
        predicted_dir / "quality_scores.json",
        [
            {"study_id": study_id, "overall_score": score}
            for study_id, score in predicted_scores
        ],
    )
    write_csv_rows(
        gold_dir / "expert_quality_scores.csv",
        [
            {"study_id": study_id, "overall_score": score}
            for study_id, score in gold_scores
        ],
        fieldnames=["study_id", "overall_score"],
    )


class BenchmarkTests(unittest.TestCase):
    def test_candidate_and_automatic_acceptance_metrics_are_separate(self):
        predicted = [
            ("A", "accepted"),
            ("B", "accepted"),
            ("C", "requires_human_review"),
            ("D", "requires_human_review"),
            ("E", "rejected"),
        ]
        gold = [
            ("A", "accepted"),
            ("B", "requires_human_review"),
            ("C", "accepted"),
            ("D", "requires_human_review"),
            ("E", "rejected"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping(source, status) for source, status in predicted],
                [gold_mapping(source, status) for source, status in gold],
            )
            results = benchmark(predicted_dir, gold_dir, out_dir)
            report_text = (out_dir / "benchmark_report.md").read_text(
                encoding="utf-8"
            )

            self.assertEqual(
                {path.name for path in out_dir.iterdir()},
                EXPECTED_OUTPUTS,
            )
            self.assertFalse((predicted_dir / "benchmark_results.json").exists())

        status_only_line = next(
            line
            for line in report_text.splitlines()
            if line.startswith("| mapping | SYN | B |")
        )
        self.assertIn("requires_human_review", status_only_line)
        self.assertIn("accepted", status_only_line)
        self.assertEqual([result.metric_name for result in results], METRIC_NAMES)
        values = {result.metric_name: result.value for result in results}
        self.assertEqual(values["candidate_precision"], 0.5)
        self.assertEqual(values["candidate_recall"], 0.5)
        self.assertEqual(values["candidate_f1"], 0.5)
        self.assertEqual(values["auto_accept_precision"], 0.5)
        self.assertEqual(values["auto_accept_recall"], 0.5)
        self.assertEqual(values["unsafe_auto_accept_rate"], 0.5)
        self.assertEqual(values["review_capture_rate"], 0.5)
        self.assertEqual(values["review_status_accuracy"], 0.6)
        self.assertIsNone(values["quality_score_agreement_within_0.15"])
        for result in results:
            self.assertTrue(
                {
                    "numerator",
                    "denominator",
                    "definition",
                    "applicability",
                    "undefined_reason",
                    "wilson_95_interval",
                }
                <= set(result.details)
            )
        self.assertIsNone(
            next(
                item
                for item in results
                if item.metric_name == "candidate_f1"
            ).details["wilson_95_interval"]
        )

    def test_full_union_reason_codes_decimal_tolerance_and_gold_denominators(self):
        predicted_rows = [
            predicted_mapping("X", "accepted"),
            predicted_mapping("C", "requires_human_review", common_variable="wrong_C"),
            predicted_mapping("A", "accepted"),
            predicted_mapping("B", "accepted"),
        ]
        gold_rows = [
            gold_mapping("E", "rejected"),
            gold_mapping("C", "accepted"),
            gold_mapping("A", "accepted"),
            gold_mapping("D", "requires_human_review"),
            gold_mapping("B", "requires_human_review"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root, predicted_rows, gold_rows
            )
            write_quality_inputs(
                predicted_dir,
                gold_dir,
                [("Q4", "0.20"), ("Q2", "0.6501"), ("Q1", "0.65")],
                [("Q3", "0.50"), ("Q1", "0.50"), ("Q2", "0.50")],
            )
            results = benchmark(predicted_dir, gold_dir, out_dir)
            cases = read_json(out_dir / "benchmark_case_results.json")
            with (out_dir / "benchmark_disagreements.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                disagreements = list(csv.DictReader(handle))

        values = {result.metric_name: result.value for result in results}
        self.assertEqual(values["candidate_precision"], 0.25)
        self.assertEqual(values["candidate_recall"], 0.25)
        self.assertEqual(values["candidate_f1"], 0.25)
        self.assertEqual(values["auto_accept_precision"], 0.333)
        self.assertEqual(values["auto_accept_recall"], 0.5)
        self.assertEqual(values["unsafe_auto_accept_rate"], 0.667)
        self.assertEqual(values["review_capture_rate"], 0.0)
        self.assertEqual(values["review_status_accuracy"], 0.2)
        self.assertEqual(values["quality_score_agreement_within_0.15"], 0.333)

        by_entity = {
            (case["case_type"], case["source_study"], case["source_variable"]): case
            for case in cases
        }
        self.assertEqual(
            by_entity[("mapping", "SYN", "B")]["reason_codes"],
            ["review_status_mismatch", "unsafe_auto_accept"],
        )
        self.assertEqual(
            by_entity[("mapping", "SYN", "B")]["outcome"],
            "review_status_mismatch",
        )
        self.assertEqual(
            by_entity[("mapping", "SYN", "X")]["reason_codes"],
            ["unexpected_prediction", "unsafe_auto_accept"],
        )
        self.assertEqual(
            by_entity[("mapping", "SYN", "X")]["outcome"],
            "unexpected_prediction",
        )
        self.assertEqual(
            by_entity[("quality", "Q1", None)]["outcome"],
            "correct",
        )
        self.assertEqual(
            by_entity[("quality", "Q2", None)]["reason_codes"],
            ["quality_score_outside_tolerance"],
        )
        self.assertEqual(
            by_entity[("quality", "Q3", None)]["reason_codes"],
            ["missing_prediction"],
        )
        self.assertEqual(
            by_entity[("quality", "Q4", None)]["reason_codes"],
            ["unexpected_prediction"],
        )
        self.assertEqual(
            [
                (
                    case["case_type"],
                    case["source_study"],
                    case["source_variable"],
                )
                for case in cases
            ],
            [
                ("mapping", "SYN", source_variable)
                for source_variable in ("A", "B", "C", "D", "E", "X")
            ]
            + [
                ("quality", study_id, None)
                for study_id in ("Q1", "Q2", "Q3", "Q4")
            ],
        )
        self.assertEqual(len(disagreements), 8)
        self.assertEqual(
            [
                (
                    row["case_type"],
                    row["source_study"],
                    row["source_variable"] or None,
                )
                for row in disagreements
            ],
            [
                ("mapping", "SYN", source_variable)
                for source_variable in ("B", "C", "D", "E", "X")
            ]
            + [
                ("quality", study_id, None)
                for study_id in ("Q2", "Q3", "Q4")
            ],
        )

    def test_zero_denominators_are_null_and_one_sided_empty_is_defined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(root, [], [])
            write_quality_inputs(predicted_dir, gold_dir, [], [])
            empty_results = benchmark(predicted_dir, gold_dir, out_dir)
            self.assertTrue(all(result.value is None for result in empty_results))
            self.assertTrue(
                all(result.details["denominator"] is None for result in empty_results)
            )
            self.assertTrue(
                all(
                    result.details["undefined_reason"] == "zero_denominator"
                    for result in empty_results
                )
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [],
                [gold_mapping("A", "accepted")],
            )
            results = benchmark(predicted_dir, gold_dir, out_dir)
        values = {result.metric_name: result.value for result in results}
        self.assertIsNone(values["candidate_precision"])
        self.assertEqual(values["candidate_recall"], 0.0)
        self.assertEqual(values["candidate_f1"], 0.0)
        self.assertIsNone(values["auto_accept_precision"])
        self.assertEqual(values["auto_accept_recall"], 0.0)
        self.assertEqual(values["review_status_accuracy"], 0.0)

    def test_report_preserves_zero_quality_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            write_quality_inputs(
                predicted_dir,
                gold_dir,
                [("Q1", "0.20"), ("Q2", "0.00")],
                [("Q1", "0.00"), ("Q2", "0.20")],
            )
            benchmark(predicted_dir, gold_dir, out_dir)
            report_text = (out_dir / "benchmark_report.md").read_text(
                encoding="utf-8"
            )

        q1_line = next(
            line
            for line in report_text.splitlines()
            if line.startswith("| quality | Q1 |")
        )
        q2_line = next(
            line
            for line in report_text.splitlines()
            if line.startswith("| quality | Q2 |")
        )
        self.assertIn("| 0.0 | 0.2 |", q1_line)
        self.assertIn("| 0.2 | 0.0 |", q2_line)

    def test_duplicate_and_asymmetric_inputs_fail_before_output(self):
        duplicate_rows = [
            predicted_mapping("A", "accepted"),
            predicted_mapping("A", "accepted"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root, duplicate_rows, [gold_mapping("A", "accepted")]
            )
            with self.assertRaisesRegex(
                BenchmarkInputError,
                r"crosswalk\.csv: duplicate mapping.*rows 2 and 3",
            ):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [
                    gold_mapping("A", "accepted"),
                    gold_mapping("A", "requires_human_review"),
                ],
            )
            with self.assertRaisesRegex(
                BenchmarkInputError,
                r"expert_variable_mappings\.csv: duplicate mapping.*rows 2 and 3",
            ):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            write_json(
                predicted_dir / "quality_scores.json",
                [{"study_id": "S1", "overall_score": 0.5}],
            )
            with self.assertRaisesRegex(FileNotFoundError, "asymmetric"):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            write_csv_rows(
                gold_dir / "expert_quality_scores.csv",
                [{"study_id": "S1", "overall_score": 0.5}],
                fieldnames=["study_id", "overall_score"],
            )
            with self.assertRaisesRegex(FileNotFoundError, "asymmetric"):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

    def test_invalid_not_mapped_status_and_quality_duplicate_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [
                    predicted_mapping(
                        "A",
                        "accepted",
                        common_variable="not_mapped",
                    )
                ],
                [gold_mapping("A", "accepted")],
            )
            with self.assertRaisesRegex(BenchmarkInputError, "not_mapped"):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            write_quality_inputs(
                predicted_dir,
                gold_dir,
                [("S1", 0.5), ("S1", 0.6)],
                [("S1", 0.5)],
            )
            with self.assertRaisesRegex(
                BenchmarkInputError,
                "duplicate quality.*rows 1 and 2",
            ):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            write_quality_inputs(
                predicted_dir,
                gold_dir,
                [("S1", 0.5)],
                [("S1", 0.5), ("S1", 0.6)],
            )
            with self.assertRaisesRegex(
                BenchmarkInputError,
                "duplicate quality.*rows 2 and 3",
            ):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

    def test_strict_mapping_input_contract_table(self):
        def missing_status_header(
            predicted_dir: Path,
            _gold_dir: Path,
        ) -> None:
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [
                    {
                        "source_study": "SYN",
                        "source_variable": "A",
                        "proposed_common_variable": "common_A",
                    }
                ],
                fieldnames=[
                    "source_study",
                    "source_variable",
                    "proposed_common_variable",
                ],
            )

        def invalid_header(predicted_dir: Path, _gold_dir: Path) -> None:
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [],
                fieldnames=["invalid_column"],
            )

        def blank_header_name(predicted_dir: Path, _gold_dir: Path) -> None:
            row = predicted_mapping("A", "accepted")
            row[""] = "unexpected"
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [row],
                fieldnames=PREDICTED_FIELDS + [""],
            )

        def whitespace_header_name(predicted_dir: Path, _gold_dir: Path) -> None:
            row = predicted_mapping("A", "accepted")
            row[" source_note "] = "unexpected"
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [row],
                fieldnames=PREDICTED_FIELDS + [" source_note "],
            )

        def blank_source_study(predicted_dir: Path, _gold_dir: Path) -> None:
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [predicted_mapping("A", "accepted", study="")],
                fieldnames=PREDICTED_FIELDS,
            )

        def blank_source_variable(predicted_dir: Path, _gold_dir: Path) -> None:
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [predicted_mapping("", "accepted")],
                fieldnames=PREDICTED_FIELDS,
            )

        def unknown_status(predicted_dir: Path, _gold_dir: Path) -> None:
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [predicted_mapping("A", "maybe")],
                fieldnames=PREDICTED_FIELDS,
            )

        def gold_unknown_status(_predicted_dir: Path, gold_dir: Path) -> None:
            write_csv_rows(
                gold_dir / "expert_variable_mappings.csv",
                [gold_mapping("A", "maybe")],
                fieldnames=GOLD_FIELDS,
            )

        def gold_blank_source_study(
            _predicted_dir: Path,
            gold_dir: Path,
        ) -> None:
            write_csv_rows(
                gold_dir / "expert_variable_mappings.csv",
                [gold_mapping("A", "accepted", study="")],
                fieldnames=GOLD_FIELDS,
            )

        def common_alias_conflict(predicted_dir: Path, _gold_dir: Path) -> None:
            row = predicted_mapping("A", "accepted")
            row["common_variable"] = "different_common"
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [row],
                fieldnames=PREDICTED_FIELDS + ["common_variable"],
            )

        def study_alias_conflict(predicted_dir: Path, _gold_dir: Path) -> None:
            row = predicted_mapping("A", "accepted")
            row["study_id"] = "OTHER"
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [row],
                fieldnames=PREDICTED_FIELDS + ["study_id"],
            )

        def identical_duplicate(predicted_dir: Path, _gold_dir: Path) -> None:
            row = predicted_mapping("A", "accepted")
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [row, dict(row)],
                fieldnames=PREDICTED_FIELDS,
            )

        def conflicting_duplicate(predicted_dir: Path, _gold_dir: Path) -> None:
            write_csv_rows(
                predicted_dir / "crosswalk.csv",
                [
                    predicted_mapping("A", "accepted"),
                    predicted_mapping(
                        "A",
                        "requires_human_review",
                        common_variable="other_A",
                    ),
                ],
                fieldnames=PREDICTED_FIELDS,
            )

        scenarios = [
            ("missing_header", missing_status_header, "missing required columns"),
            ("invalid_header", invalid_header, "missing required columns"),
            ("blank_header_name", blank_header_name, "blank column name"),
            (
                "whitespace_header_name",
                whitespace_header_name,
                "surrounding whitespace",
            ),
            ("blank_study", blank_source_study, "missing source_study"),
            ("blank_variable", blank_source_variable, "source_variable"),
            ("unknown_status", unknown_status, "invalid review_status"),
            ("gold_unknown_status", gold_unknown_status, "invalid review_status"),
            ("gold_blank_study", gold_blank_source_study, "missing source_study"),
            ("common_alias_conflict", common_alias_conflict, "conflicting proposed"),
            ("study_alias_conflict", study_alias_conflict, "conflicting source_study"),
            ("identical_duplicate", identical_duplicate, "duplicate mapping"),
            ("conflicting_duplicate", conflicting_duplicate, "duplicate mapping"),
        ]
        for name, mutate, message in scenarios:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                    root,
                    [predicted_mapping("A", "accepted")],
                    [gold_mapping("A", "accepted")],
                )
                mutate(predicted_dir, gold_dir)
                with self.assertRaisesRegex(BenchmarkInputError, message):
                    benchmark(predicted_dir, gold_dir, out_dir)
                self.assertFalse(out_dir.exists())

    def test_strict_quality_scores_and_missing_mapping_file(self):
        invalid_scores = ["NaN", "Infinity", "-0.01", "1.01"]
        for side in ("predicted", "gold"):
            for score in invalid_scores:
                with (
                    self.subTest(side=side, score=score),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    root = Path(tmp)
                    predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                        root,
                        [predicted_mapping("A", "accepted")],
                        [gold_mapping("A", "accepted")],
                    )
                    predicted_score = score if side == "predicted" else "0.5"
                    gold_score = score if side == "gold" else "0.5"
                    write_quality_inputs(
                        predicted_dir,
                        gold_dir,
                        [("Q1", predicted_score)],
                        [("Q1", gold_score)],
                    )
                    with self.assertRaisesRegex(
                        BenchmarkInputError,
                        "finite decimal|between 0 and 1",
                    ):
                        benchmark(predicted_dir, gold_dir, out_dir)
                    self.assertFalse(out_dir.exists())

        for invalid_study_id in (7, True, ["Q1"], {"id": "Q1"}):
            with (
                self.subTest(invalid_study_id=invalid_study_id),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                    root,
                    [predicted_mapping("A", "accepted")],
                    [gold_mapping("A", "accepted")],
                )
                write_json(
                    predicted_dir / "quality_scores.json",
                    [{"study_id": invalid_study_id, "overall_score": "0.5"}],
                )
                write_csv_rows(
                    gold_dir / "expert_quality_scores.csv",
                    [{"study_id": "Q1", "overall_score": "0.5"}],
                    fieldnames=["study_id", "overall_score"],
                )
                with self.assertRaisesRegex(
                    BenchmarkInputError,
                    "study_id must be a nonempty string",
                ):
                    benchmark(predicted_dir, gold_dir, out_dir)
                self.assertFalse(out_dir.exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            (predicted_dir / "crosswalk.csv").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "mapping inputs"):
                benchmark(predicted_dir, gold_dir, out_dir)
            self.assertFalse(out_dir.exists())

    def test_both_quality_inputs_absent_are_inventoried_as_not_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            results = benchmark(predicted_dir, gold_dir, out_dir)
            manifest = read_json(out_dir / "benchmark_manifest.json")

        quality_metric = next(
            result
            for result in results
            if result.metric_name == "quality_score_agreement_within_0.15"
        )
        self.assertIsNone(quality_metric.value)
        self.assertIsNone(quality_metric.details["denominator"])
        self.assertEqual(
            quality_metric.details["undefined_reason"],
            "quality_inputs_not_provided",
        )
        quality_inputs = [
            item for item in manifest["inputs"] if "quality" in item["role"]
        ]
        self.assertEqual(len(quality_inputs), 2)
        self.assertTrue(
            all(item["state"] == "not_provided" for item in quality_inputs)
        )
        self.assertTrue(all(item["sha256"] is None for item in quality_inputs))
        self.assertTrue(all(item["row_count"] is None for item in quality_inputs))
        self.assertTrue(all(item["columns"] == [] for item in quality_inputs))

    def test_legacy_predicted_benchmark_result_is_untouched(self):
        sentinel = b"legacy benchmark result must remain byte-identical\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "accepted")],
            )
            legacy_path = predicted_dir / "benchmark_results.json"
            legacy_path.write_bytes(sentinel)
            benchmark(predicted_dir, gold_dir, out_dir)
            self.assertEqual(legacy_path.read_bytes(), sentinel)
            self.assertTrue((out_dir / "benchmark_results.json").exists())

    def test_outputs_are_byte_reproducible_and_manifest_hashes_are_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, _ = write_mapping_inputs(
                root,
                [
                    predicted_mapping("B", "requires_human_review"),
                    predicted_mapping("A", "accepted"),
                ],
                [
                    gold_mapping("A", "accepted"),
                    gold_mapping("B", "accepted"),
                ],
            )
            write_quality_inputs(
                predicted_dir,
                gold_dir,
                [("Q1", "0.70")],
                [("Q1", "0.60")],
            )
            out_one = root / "one"
            out_two = root / "two"
            benchmark(predicted_dir, gold_dir, out_one)
            benchmark(predicted_dir, gold_dir, out_two)

            for filename in EXPECTED_OUTPUTS:
                self.assertEqual(
                    (out_one / filename).read_bytes(),
                    (out_two / filename).read_bytes(),
                    filename,
                )

            manifest = read_json(out_one / "benchmark_manifest.json")
            self.assertEqual(manifest["manifest_version"], "1.0.0")
            self.assertEqual(manifest["benchmark_rule_set_version"], "0.2.0")
            self.assertEqual(manifest["software_version"], "0.2.0")
            self.assertEqual(
                manifest["parameters"]["case_outcome_precedence"],
                CASE_OUTCOME_PRECEDENCE,
            )
            self.assertEqual(len(manifest["inputs"]), 4)
            self.assertEqual(
                [item["role"] for item in manifest["inputs"]],
                [
                    "predicted_crosswalk",
                    "predicted_quality_scores",
                    "gold_variable_mappings",
                    "gold_quality_scores",
                ],
            )
            self.assertEqual(
                [item["path"] for item in manifest["outputs"]],
                [
                    "benchmark_results.json",
                    "benchmark_case_results.json",
                    "benchmark_disagreements.csv",
                    "benchmark_report.md",
                ],
            )
            required_artifact_fields = {
                "role",
                "path",
                "state",
                "row_count",
                "columns",
                "sha256",
            }
            for item in manifest["inputs"] + manifest["outputs"]:
                self.assertEqual(set(item), required_artifact_fields)
                self.assertFalse(Path(item["path"]).is_absolute())
            for item in manifest["outputs"]:
                expected_hash = hashlib.sha256(
                    (out_one / item["path"]).read_bytes()
                ).hexdigest()
                self.assertEqual(item["sha256"], expected_hash)
            manifest_text = json.dumps(manifest)
            self.assertNotIn(str(root), manifest_text)
            self.assertNotIn("generated_at", manifest_text)

    def test_artifacts_validate_against_benchmark_schemas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            predicted_dir, gold_dir, out_dir = write_mapping_inputs(
                root,
                [predicted_mapping("A", "accepted")],
                [gold_mapping("A", "requires_human_review")],
            )
            benchmark(predicted_dir, gold_dir, out_dir)

            for result in read_json(out_dir / "benchmark_results.json"):
                self.assertEqual(
                    validate_against_schema(
                        result,
                        project_schema_path("benchmark_result.schema.json"),
                    ),
                    [],
                )
            for case in read_json(out_dir / "benchmark_case_results.json"):
                self.assertEqual(
                    validate_against_schema(
                        case,
                        project_schema_path("benchmark_case_result.schema.json"),
                    ),
                    [],
                )
            self.assertEqual(
                validate_against_schema(
                    read_json(out_dir / "benchmark_manifest.json"),
                    project_schema_path("benchmark_manifest.schema.json"),
                ),
                [],
            )

        manifest_schema = read_json(
            project_schema_path("benchmark_manifest.schema.json")
        )
        properties = manifest_schema["properties"]
        self.assertEqual(
            [
                item["const"]
                for item in properties["metric_names"]["prefixItems"]
            ],
            METRIC_NAMES,
        )
        self.assertEqual(properties["metric_names"]["minItems"], 9)
        self.assertEqual(properties["inputs"]["minItems"], 4)
        self.assertEqual(properties["outputs"]["minItems"], 4)
        self.assertEqual(
            properties["parameters"]["properties"]["mapping_entity_key"][
                "minItems"
            ],
            2,
        )
        self.assertEqual(
            properties["parameters"]["properties"]["case_outcome_precedence"][
                "minItems"
            ],
            len(CASE_OUTCOME_PRECEDENCE),
        )

    def test_frozen_pilot_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            results = benchmark(
                ROOT / "data/extracted",
                ROOT / "data/examples",
                out_dir,
            )
            with (out_dir / "benchmark_disagreements.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                disagreements = list(csv.DictReader(handle))
        values = [result.value for result in results]
        self.assertEqual(values, [1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.8])
        by_name = {result.metric_name: result.details for result in results}
        expected_counts = {
            "candidate_precision": (24, 24),
            "candidate_recall": (24, 24),
            "auto_accept_precision": (12, 12),
            "auto_accept_recall": (12, 12),
            "unsafe_auto_accept_rate": (0, 12),
            "review_capture_rate": (12, 12),
            "review_status_accuracy": (26, 26),
            "quality_score_agreement_within_0.15": (8, 10),
        }
        for metric_name, (numerator, denominator) in expected_counts.items():
            with self.subTest(metric_name=metric_name):
                self.assertEqual(by_name[metric_name]["numerator"], numerator)
                self.assertEqual(by_name[metric_name]["denominator"], denominator)
        quality_disagreements = [
            row
            for row in disagreements
            if row["outcome"] == "quality_score_outside_tolerance"
        ]
        self.assertEqual(
            {row["source_study"] for row in quality_disagreements},
            {"SYN-ANIMAL-MET", "SYN-EXER-NODATA"},
        )


if __name__ == "__main__":
    unittest.main()

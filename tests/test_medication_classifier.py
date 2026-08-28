import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.evaluation.medication_classifier import (
    FeatureCatalog,
    MedicationClassifierInputError,
    _auroc,
    run_cold_synthetic_evaluation,
)
from metabotyping_agentic.schemas import project_schema_path, validate_against_schema

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "examples" / "medication_classifier"
EXPECTED_OUTPUTS = {
    "model.json",
    "predictions.csv",
    "metrics.json",
    "model_card.md",
    "run_manifest.json",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _summary(path: Path) -> dict:
    _, rows = _read_csv(path)
    return {
        "sample_count": len(rows),
        "cohort_ids": sorted({row["cohort_id"] for row in rows}),
        "class_counts": {
            "0": sum(row["statin_exposure"] == "0" for row in rows),
            "1": sum(row["statin_exposure"] == "1" for row in rows),
        },
    }


def _refresh_manifest(bundle: Path) -> None:
    manifest_path = bundle / "split_manifest.json"
    manifest = _read_json(manifest_path)
    feature_catalog_path = bundle / "feature_catalog.json"
    manifest["artifacts"]["feature_catalog"]["sha256"] = _sha256(
        feature_catalog_path
    )
    for role in ("train", "test"):
        path = bundle / f"{role}.csv"
        manifest["artifacts"][role] = {
            "path": path.name,
            "sha256": _sha256(path),
            **_summary(path),
        }
    _write_json(manifest_path, manifest)


def _copy_bundle(root: Path, name: str = "inputs") -> Path:
    destination = root / name
    shutil.copytree(DATA_DIR, destination)
    return destination


def _prediction_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class MedicationClassifierTests(unittest.TestCase):
    def test_cold_split_produces_provenanced_synthetic_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            run_cold_synthetic_evaluation(DATA_DIR, out_dir)

            self.assertEqual({path.name for path in out_dir.iterdir()}, EXPECTED_OUTPUTS)
            model = _read_json(out_dir / "model.json")
            metrics = _read_json(out_dir / "metrics.json")
            run_manifest = _read_json(out_dir / "run_manifest.json")
            split_manifest = _read_json(DATA_DIR / "split_manifest.json")
            feature_catalog = _read_json(DATA_DIR / "feature_catalog.json")
            predictions = _prediction_rows(out_dir / "predictions.csv")
            card = (out_dir / "model_card.md").read_text(encoding="utf-8")
            actual_output_digests = {
                filename: _sha256(out_dir / filename)
                for filename in (
                    "model.json",
                    "predictions.csv",
                    "metrics.json",
                    "model_card.md",
                )
            }

        train_cohorts = set(
            split_manifest["artifacts"]["train"]["cohort_ids"]
        )
        test_cohorts = set(split_manifest["artifacts"]["test"]["cohort_ids"])
        self.assertGreaterEqual(len(train_cohorts), 2)
        self.assertTrue(train_cohorts.isdisjoint(test_cohorts))
        self.assertEqual(model["preprocessing"]["fit_scope"], "training_data_only")
        self.assertEqual(
            model["feature_allowlist"],
            [feature["name"] for feature in feature_catalog["features"]],
        )
        self.assertFalse(model["clinically_validated"])
        self.assertTrue(metrics["synthetic_data"])
        self.assertFalse(metrics["clinically_validated"])
        self.assertEqual(metrics["metrics"]["balanced_accuracy"]["value"], 1.0)
        self.assertEqual(metrics["metrics"]["positive_precision"]["value"], 1.0)
        self.assertEqual(metrics["metrics"]["positive_recall"]["value"], 1.0)
        self.assertEqual(metrics["metrics"]["f1_score"]["value"], 1.0)
        self.assertEqual(metrics["metrics"]["scored_coverage"]["value"], 1.0)
        self.assertEqual(metrics["metrics"]["abstention_rate"]["value"], 0.0)
        self.assertEqual(metrics["metrics"]["auroc"]["value"], 1.0)
        self.assertEqual(metrics["metrics"]["auroc"]["ranking_score"], "log_odds")
        self.assertEqual(metrics["baseline"]["value"], 0.5)
        self.assertEqual(metrics["confusion_matrix"]["true_positive"]["denominator"], 12)
        self.assertEqual(metrics["confusion_matrix"]["true_negative"]["denominator"], 12)
        self.assertTrue(all(row["decision_status"] == "scored" for row in predictions))
        self.assertTrue(all(row["features_used"] for row in predictions))

        output_digests = {
            item["path"]: item["sha256"] for item in run_manifest["outputs"]
        }
        for filename in (
            "model.json",
            "predictions.csv",
            "metrics.json",
            "model_card.md",
        ):
            self.assertEqual(output_digests[filename], actual_output_digests[filename])
        self.assertFalse(run_manifest["guards"]["test_labels_used_for_model_fitting"])
        self.assertFalse(run_manifest["guards"]["test_labels_used_for_scoring"])
        self.assertFalse(run_manifest["guards"]["missing_features_zero_filled"])
        self.assertIn("not clinically validated", card)
        self.assertIn("never zero-fill", card)

        schema_cases = (
            (
                feature_catalog,
                "medication_classifier_feature_catalog.schema.json",
            ),
            (
                split_manifest,
                "medication_classifier_split_manifest.schema.json",
            ),
            (model, "medication_classifier_model.schema.json"),
            (metrics, "medication_classifier_metrics.schema.json"),
            (
                run_manifest,
                "medication_classifier_run_manifest.schema.json",
            ),
        )
        for value, schema_name in schema_cases:
            with self.subTest(schema=schema_name):
                self.assertEqual(
                    validate_against_schema(value, project_schema_path(schema_name)),
                    [],
                )

    def test_two_runs_have_identical_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            run_cold_synthetic_evaluation(DATA_DIR, first)
            run_cold_synthetic_evaluation(DATA_DIR, second)
            first_payloads = {
                path.name: path.read_bytes() for path in sorted(first.iterdir())
            }
            second_payloads = {
                path.name: path.read_bytes() for path in sorted(second.iterdir())
            }

        self.assertEqual(first_payloads, second_payloads)
        for payload in first_payloads.values():
            self.assertNotIn(str(first).encode(), payload)
            self.assertNotIn(str(second).encode(), payload)

    def test_nonfinite_training_input_fails_before_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            train_path = bundle / "train.csv"
            fieldnames, rows = _read_csv(train_path)
            rows[0]["ldl_particle_signal"] = "NaN"
            _write_csv(train_path, fieldnames, rows)
            _refresh_manifest(bundle)
            out_dir = root / "out"

            with self.assertRaisesRegex(MedicationClassifierInputError, "not finite"):
                run_cold_synthetic_evaluation(bundle, out_dir)

            self.assertFalse(out_dir.exists())

    def test_extreme_finite_training_input_fails_before_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            train_path = bundle / "train.csv"
            fieldnames, rows = _read_csv(train_path)
            rows[0]["ldl_particle_signal"] = "1e308"
            rows[1]["ldl_particle_signal"] = "-1e308"
            _write_csv(train_path, fieldnames, rows)
            _refresh_manifest(bundle)
            out_dir = root / "out"

            with self.assertRaisesRegex(
                MedicationClassifierInputError, "Non-finite training computation"
            ):
                run_cold_synthetic_evaluation(bundle, out_dir)

            self.assertFalse(out_dir.exists())

    def test_hash_mismatch_fails_before_writing_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            test_path = bundle / "test.csv"
            fieldnames, rows = _read_csv(test_path)
            rows[0]["ldl_particle_signal"] = "9.000000"
            _write_csv(test_path, fieldnames, rows)
            out_dir = root / "out"

            with self.assertRaisesRegex(MedicationClassifierInputError, "SHA-256 mismatch"):
                run_cold_synthetic_evaluation(bundle, out_dir)

            self.assertFalse(out_dir.exists())

    def test_sample_and_cohort_overlap_are_rejected(self):
        for overlap_kind in ("sample", "cohort"):
            with self.subTest(overlap=overlap_kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bundle = _copy_bundle(root)
                _, train_rows = _read_csv(bundle / "train.csv")
                fieldnames, test_rows = _read_csv(bundle / "test.csv")
                if overlap_kind == "sample":
                    test_rows[0]["sample_id"] = train_rows[0]["sample_id"]
                    expected = "sample identifiers overlap"
                else:
                    for row in test_rows:
                        row["cohort_id"] = train_rows[0]["cohort_id"]
                    expected = "cohort identifiers overlap"
                _write_csv(bundle / "test.csv", fieldnames, test_rows)
                _refresh_manifest(bundle)
                out_dir = root / "out"

                with self.assertRaisesRegex(MedicationClassifierInputError, expected):
                    run_cold_synthetic_evaluation(bundle, out_dir)
                self.assertFalse(out_dir.exists())

    def test_renamed_duplicate_feature_vector_across_splits_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            _, train_rows = _read_csv(bundle / "train.csv")
            fieldnames, test_rows = _read_csv(bundle / "test.csv")
            feature_names = [
                feature["name"]
                for feature in _read_json(bundle / "feature_catalog.json")["features"]
            ]
            for feature_name in feature_names:
                test_rows[0][feature_name] = train_rows[0][feature_name]
            _write_csv(bundle / "test.csv", fieldnames, test_rows)
            _refresh_manifest(bundle)
            out_dir = root / "out"

            with self.assertRaisesRegex(
                MedicationClassifierInputError, "feature vectors overlap"
            ):
                run_cold_synthetic_evaluation(bundle, out_dir)

            self.assertFalse(out_dir.exists())

    def test_allowlisted_exact_label_encoding_feature_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            train_path = bundle / "train.csv"
            fieldnames, rows = _read_csv(train_path)
            for row in rows:
                row["neutral_reference_signal"] = (
                    "20" if row["statin_exposure"] == "1" else "10"
                )
            _write_csv(train_path, fieldnames, rows)
            _refresh_manifest(bundle)
            out_dir = root / "out"

            with self.assertRaisesRegex(
                MedicationClassifierInputError, "exactly encode the binary target"
            ):
                run_cold_synthetic_evaluation(bundle, out_dir)

            self.assertFalse(out_dir.exists())

    def test_insufficient_test_feature_coverage_abstains_without_zero_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            catalog = _read_json(bundle / "feature_catalog.json")
            feature_names = [feature["name"] for feature in catalog["features"]]
            fieldnames, rows = _read_csv(bundle / "test.csv")
            retained_fields = [name for name in fieldnames if name not in feature_names[3:]]
            reduced_rows = [
                {name: row[name] for name in retained_fields} for row in rows
            ]
            _write_csv(bundle / "test.csv", retained_fields, reduced_rows)
            _refresh_manifest(bundle)
            out_dir = root / "out"
            run_cold_synthetic_evaluation(bundle, out_dir)

            predictions = _prediction_rows(out_dir / "predictions.csv")
            metrics = _read_json(out_dir / "metrics.json")

        self.assertTrue(predictions)
        for row in predictions:
            self.assertEqual(row["decision_status"], "abstained")
            self.assertEqual(row["abstention_reason"], "insufficient_feature_coverage")
            self.assertEqual(row["predicted_statin_exposure"], "")
            self.assertEqual(row["statin_probability"], "")
            self.assertEqual(row["feature_count_used"], "3")
        self.assertEqual(metrics["sample_counts"]["scored"], 0)
        self.assertEqual(metrics["sample_counts"]["abstained"], len(predictions))
        self.assertIsNone(metrics["metrics"]["balanced_accuracy"]["value"])
        self.assertIsNone(metrics["metrics"]["auroc"]["value"])

    def test_extreme_finite_test_features_abstain_without_nonfinite_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = _copy_bundle(root)
            test_path = bundle / "test.csv"
            fieldnames, rows = _read_csv(test_path)
            rows[0]["ldl_particle_signal"] = "1e308"
            rows[0]["cholesteryl_ester_signal"] = "-1e308"
            _write_csv(test_path, fieldnames, rows)
            _refresh_manifest(bundle)
            out_dir = root / "out"
            run_cold_synthetic_evaluation(bundle, out_dir)

            predictions = _prediction_rows(out_dir / "predictions.csv")
            metrics = _read_json(out_dir / "metrics.json")
            payload = (out_dir / "predictions.csv").read_text(encoding="utf-8").lower()

        unstable = predictions[0]
        self.assertEqual(unstable["decision_status"], "abstained")
        self.assertEqual(unstable["abstention_reason"], "numerical_instability")
        self.assertEqual(unstable["statin_probability"], "")
        self.assertEqual(unstable["log_odds"], "")
        self.assertNotIn("nan", payload)
        self.assertNotIn("inf", payload)
        self.assertEqual(metrics["sample_counts"]["abstained"], 1)
        self.assertEqual(metrics["metrics"]["scored_coverage"]["denominator"], 24)
        self.assertEqual(metrics["metrics"]["abstention_rate"]["numerator"], 1)

    def test_auroc_ranks_log_odds_when_probabilities_saturate(self):
        catalog = FeatureCatalog(
            catalog_id="test",
            target_column="statin_exposure",
            sample_id_column="sample_id",
            cohort_id_column="cohort_id",
            negative_label="0",
            positive_label="1",
            feature_names=("feature_a", "feature_b"),
            minimum_feature_count=1,
            raw={},
        )
        scored = [
            {
                "observed_statin_exposure": "1",
                "statin_probability": "1",
                "log_odds": "31",
            },
            {
                "observed_statin_exposure": "0",
                "statin_probability": "1",
                "log_odds": "30",
            },
        ]

        result = _auroc(scored, catalog)

        self.assertEqual(result["value"], 1.0)
        self.assertEqual(result["concordant_pairs"], 1)
        self.assertEqual(result["tied_pairs"], 0)
        self.assertEqual(result["ranking_score"], "log_odds")

    def test_existing_output_directory_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            stale = out_dir / "stale.json"
            out_dir.mkdir()
            stale.write_text('{"old": true}\n', encoding="utf-8")

            with self.assertRaisesRegex(MedicationClassifierInputError, "already exists"):
                run_cold_synthetic_evaluation(DATA_DIR, out_dir)

            self.assertEqual(stale.read_text(encoding="utf-8"), '{"old": true}\n')
            self.assertEqual({path.name for path in out_dir.iterdir()}, {"stale.json"})

    def test_test_label_changes_do_not_change_model_or_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_bundle = _copy_bundle(root, "original_inputs")
            flipped_bundle = _copy_bundle(root, "flipped_inputs")
            fieldnames, flipped_rows = _read_csv(flipped_bundle / "test.csv")
            for row in flipped_rows:
                row["statin_exposure"] = "1" if row["statin_exposure"] == "0" else "0"
            _write_csv(flipped_bundle / "test.csv", fieldnames, flipped_rows)
            _refresh_manifest(flipped_bundle)
            original_out = root / "original_out"
            flipped_out = root / "flipped_out"
            run_cold_synthetic_evaluation(original_bundle, original_out)
            run_cold_synthetic_evaluation(flipped_bundle, flipped_out)

            original_model = (original_out / "model.json").read_bytes()
            flipped_model = (flipped_out / "model.json").read_bytes()
            original_predictions = _prediction_rows(
                original_out / "predictions.csv"
            )
            flipped_predictions = _prediction_rows(flipped_out / "predictions.csv")
            original_metrics = _read_json(original_out / "metrics.json")
            flipped_metrics = _read_json(flipped_out / "metrics.json")

        self.assertEqual(original_model, flipped_model)
        score_fields = (
            "sample_id",
            "cohort_id",
            "decision_status",
            "predicted_statin_exposure",
            "statin_probability",
            "log_odds",
            "feature_count_used",
            "feature_coverage",
            "abstention_reason",
        )
        self.assertEqual(
            [tuple(row[name] for name in score_fields) for row in original_predictions],
            [tuple(row[name] for name in score_fields) for row in flipped_predictions],
        )
        self.assertNotEqual(
            original_metrics["confusion_matrix"], flipped_metrics["confusion_matrix"]
        )

    def test_undeclared_leakage_column_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_bundle = _copy_bundle(root, "base_inputs")
            leak_bundle = _copy_bundle(root, "leak_inputs")
            for split in ("train", "test"):
                path = leak_bundle / f"{split}.csv"
                fieldnames, rows = _read_csv(path)
                fieldnames.append("undeclared_perfect_label_leak")
                for row in rows:
                    row["undeclared_perfect_label_leak"] = row["statin_exposure"]
                _write_csv(path, fieldnames, rows)
            _refresh_manifest(leak_bundle)
            base_out = root / "base_out"
            leak_out = root / "leak_out"
            run_cold_synthetic_evaluation(base_bundle, base_out)
            run_cold_synthetic_evaluation(leak_bundle, leak_out)

            base_model = _read_json(base_out / "model.json")
            leak_model = _read_json(leak_out / "model.json")
            base_predictions = _prediction_rows(base_out / "predictions.csv")
            leak_predictions = _prediction_rows(leak_out / "predictions.csv")

        self.assertNotIn(
            "undeclared_perfect_label_leak", leak_model["feature_allowlist"]
        )
        self.assertEqual(base_model["parameters"], leak_model["parameters"])
        score_fields = ("sample_id", "statin_probability", "log_odds")
        self.assertEqual(
            [tuple(row[name] for name in score_fields) for row in base_predictions],
            [tuple(row[name] for name in score_fields) for row in leak_predictions],
        )


if __name__ == "__main__":
    unittest.main()

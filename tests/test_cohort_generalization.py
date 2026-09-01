from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.cohort_bundle import CohortBundleError, run_cohort_bundle
from metabotyping_agentic.io import read_json

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data/examples/unseen_cohort"


def _artifact_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_bundle_hashes(bundle: Path) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"].values():
        entry["sha256"] = _sha256(bundle / entry["path"])
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class CohortGeneralizationTests(unittest.TestCase):
    def test_explicit_unseen_bundle_runs_without_pilot_fixture_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            result = run_cohort_bundle(BUNDLE, out)

            self.assertEqual(result["status"], "synthetic_interface_generalization_pass")
            self.assertFalse(result["external_validation"])
            self.assertFalse(result["evidence_gates"]["builtin_fixture_fallback_used"])
            self.assertEqual(result["evidence_gates"]["unknown_human_evidence_count"], 0)
            self.assertEqual(result["counts"]["study_cards"], 2)
            self.assertEqual(result["counts"]["variable_cards"], 7)

            payload = b"\n".join(_artifact_bytes(out).values())
            self.assertNotIn(b"SYN-METEX-GEN", payload)
            self.assertNotIn(str(ROOT).encode(), payload)
            studies = read_json(out / "study_cards.json")
            self.assertEqual({row["human"] for row in studies}, {True})
            self.assertTrue(
                all(str(row["provenance"]["source"]).startswith("bundle:") for row in studies)
            )

    def test_two_runs_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"

            run_cohort_bundle(BUNDLE, first)
            run_cohort_bundle(BUNDLE, second)

            self.assertEqual(_artifact_bytes(first), _artifact_bytes(second))

    def test_existing_output_is_rejected_without_listing_stale_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            stale = out / "metadata_cards/stale_pilot_card.json"
            stale.parent.mkdir(parents=True)
            stale.write_text('{"study_id": "SYN-METEX-GEN"}\n', encoding="utf-8")

            with self.assertRaisesRegex(CohortBundleError, "already exists"):
                run_cohort_bundle(BUNDLE, out)

            self.assertEqual(
                stale.read_text(encoding="utf-8"),
                '{"study_id": "SYN-METEX-GEN"}\n',
            )
            self.assertFalse((out / "cohort_run_manifest.json").exists())

    def test_run_manifest_binds_bundle_manifest_and_every_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            run_cohort_bundle(BUNDLE, out)

            run_manifest = read_json(out / "cohort_run_manifest.json")
            inputs = {entry["role"]: entry for entry in run_manifest["inputs"]}
            self.assertEqual(inputs["bundle_manifest"]["path"], "manifest.json")
            self.assertEqual(inputs["bundle_manifest"]["sha256"], _sha256(BUNDLE / "manifest.json"))

            declared_outputs = {entry["path"] for entry in run_manifest["outputs"]}
            observed_outputs = {
                path.relative_to(out).as_posix()
                for path in out.rglob("*")
                if path.is_file() and path.name != "cohort_run_manifest.json"
            }
            self.assertEqual(declared_outputs, observed_outputs)

    def test_hash_mismatch_fails_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            with (bundle / "variable_dictionary.csv").open("a", encoding="utf-8") as handle:
                handle.write("SYN-UNSEEN-ACTIVITY,late_mutation,Mutation,unknown,unknown,unknown,\n")

            with self.assertRaisesRegex(CohortBundleError, "SHA-256 mismatch"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_mismatched_study_universe_fails_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            publication_path = bundle / "publications.csv"
            lines = publication_path.read_text(encoding="utf-8").splitlines()
            publication_path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["publications"]["row_count"] = 1
            manifest["files"]["publications"]["sha256"] = _sha256(publication_path)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CohortBundleError, "study universes"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_parent_traversal_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["publications"]["path"] = "../publications.csv"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CohortBundleError, "beneath the bundle"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_symlink_escape_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            outside = root / "outside_publications.csv"
            outside.write_bytes((bundle / "publications.csv").read_bytes())
            link = bundle / "linked_publications.csv"
            link.symlink_to(outside)
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["publications"]["path"] = link.name
            manifest["files"]["publications"]["sha256"] = _sha256(outside)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CohortBundleError, "escapes the bundle"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_duplicate_manifest_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            manifest_path = bundle / "manifest.json"
            payload = manifest_path.read_text(encoding="utf-8").replace(
                '"synthetic_data": true',
                '"synthetic_data": true,\n  "synthetic_data": false',
            )
            manifest_path.write_text(payload, encoding="utf-8")

            with self.assertRaisesRegex(CohortBundleError, "duplicate key"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_unknown_boolean_evidence_is_not_collapsed_to_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            publications = bundle / "publications.csv"
            payload = publications.read_text(encoding="utf-8").replace(
                ",true,true,false,true,false,true,true,false,",
                ",unknown,true,false,definitely,false,true,true,false,",
                1,
            )
            publications.write_text(payload, encoding="utf-8")
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["publications"]["sha256"] = _sha256(publications)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CohortBundleError, "explicitly true or false"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_missing_modality_boolean_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            publications = bundle / "publications.csv"
            with publications.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                fieldnames = [name for name in (reader.fieldnames or []) if name != "exercise"]
                rows = [
                    {name: row[name] for name in fieldnames}
                    for row in rows
                ]
            with publications.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=fieldnames, lineterminator="\n"
                )
                writer.writeheader()
                writer.writerows(rows)
            _refresh_bundle_hashes(bundle)

            with self.assertRaisesRegex(CohortBundleError, "missing required columns"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())

    def test_colliding_study_card_filenames_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            out = root / "out"
            shutil.copytree(BUNDLE, bundle)
            replacements = {
                "SYN-UNSEEN-ENDURANCE": "A/B",
                "SYN-UNSEEN-ACTIVITY": "A B",
            }
            for filename in (
                "publications.csv",
                "repository_records.csv",
                "variable_dictionary.csv",
            ):
                path = bundle / filename
                payload = path.read_text(encoding="utf-8")
                for before, after in replacements.items():
                    payload = payload.replace(before, after)
                path.write_text(payload, encoding="utf-8")
            manifest_path = bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["study_ids"] = ["A/B", "A B"]
            for entry in manifest["files"].values():
                entry["sha256"] = _sha256(bundle / entry["path"])
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CohortBundleError, "same metadata-card filename"):
                run_cohort_bundle(bundle, out)

            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

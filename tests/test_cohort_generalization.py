from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()

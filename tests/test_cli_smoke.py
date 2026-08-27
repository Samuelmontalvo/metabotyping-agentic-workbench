import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.cli import discover_command, main

ROOT = Path(__file__).resolve().parents[1]


class CliSmokeTests(unittest.TestCase):
    """Exercise the CLI in an isolated workspace.

    These tests must never run the pilot against the repository root. The pilot
    writes into tracked trees (``reports/``, ``data/extracted/``,
    ``data/review/``), so running it here would rewrite committed scientific
    artifacts as a side effect of running the test suite, and a reviewer
    diffing ``reports/`` would see results from a test query.
    """

    def _workspace(self, tmp: str) -> Path:
        workspace = Path(tmp)
        shutil.copytree(ROOT / "data/examples", workspace / "data/examples")
        return workspace

    def test_cli_run_pilot_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            previous_cwd = Path.cwd()
            try:
                os.chdir(workspace)
                main(["run-pilot", "--out", "reports"])
            finally:
                os.chdir(previous_cwd)

            self.assertTrue((workspace / "reports/aim1_catalog_report.md").exists())
            self.assertTrue((workspace / "reports/aim2_harmonization_report.md").exists())
            self.assertTrue((workspace / "reports/benchmark_report.md").exists())

    def test_discover_command_writes_only_inside_its_out_directory(self):
        """discover must not touch any path outside --out.

        Regression guard: discover_command used to render the catalog report
        into a hardcoded "reports" directory, ignoring --out entirely.
        """

        with tempfile.TemporaryDirectory() as tmp:
            workspace = self._workspace(tmp)
            criteria_path = workspace / "criteria.json"
            criteria_path.write_text(
                json.dumps(
                    {
                        "query": "human metabolomics genetics required",
                        "required_terms": ["human", "metabolomics", "genetics"],
                        "preferred_terms": ["diet"],
                        "complementary_terms": [],
                        "exclusions": ["animal-only", "no metabolomics"],
                        "notes": [],
                    }
                ),
                encoding="utf-8",
            )
            out_dir = workspace / "out"
            previous_cwd = Path.cwd()
            try:
                os.chdir(workspace)
                recommendations = discover_command(str(criteria_path), str(out_dir))
            finally:
                os.chdir(previous_cwd)

            by_study = {item.study_id: item for item in recommendations}
            self.assertEqual(by_study["SYN-ACTI-MET"].recommendation_class, "excluded")

            self.assertFalse(
                (workspace / "reports").exists(),
                "discover wrote outside --out; it must not create a reports/ tree",
            )
            written = sorted(path.name for path in out_dir.iterdir())
            self.assertEqual(written, ["recommendations.csv", "recommendations.json"])


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.cli import discover_command, main

ROOT = Path(__file__).resolve().parents[1]


class CliSmokeTests(unittest.TestCase):
    def test_cli_run_pilot_smoke(self):
        old_cwd = Path.cwd()
        try:
            os.chdir(ROOT)
            main(["run-pilot", "--out", "reports"])
        finally:
            os.chdir(old_cwd)

        self.assertTrue((ROOT / "reports/aim1_catalog_report.md").exists())
        self.assertTrue((ROOT / "reports/aim2_harmonization_report.md").exists())
        self.assertTrue((ROOT / "reports/benchmark_report.md").exists())

    def test_discover_command_uses_criteria_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            criteria_path = tmp_path / "criteria.json"
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
            old_cwd = Path.cwd()
            try:
                os.chdir(ROOT)
                recommendations = discover_command(str(criteria_path), str(tmp_path / "out"))
            finally:
                os.chdir(old_cwd)

        by_study = {item.study_id: item for item in recommendations}
        self.assertEqual(by_study["SYN-ACTI-MET"].recommendation_class, "excluded")


if __name__ == "__main__":
    unittest.main()

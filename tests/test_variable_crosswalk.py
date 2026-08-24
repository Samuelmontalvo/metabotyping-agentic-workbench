import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.harmonization.crosswalk import build_crosswalk

ROOT = Path(__file__).resolve().parents[1]


class VariableCrosswalkTests(unittest.TestCase):
    def test_crosswalk_routes_vo2peak_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            mappings = build_crosswalk(ROOT / "data/examples/mock_variable_dictionary.csv", Path(tmp))
        by_var = {(m.source_study, m.source_variable): m for m in mappings}

        self.assertEqual(by_var[("SYN-CPET-RICH", "vo2peak")].proposed_common_variable, "vo2max")
        self.assertEqual(by_var[("SYN-CPET-RICH", "vo2peak")].review_status, "requires_human_review")
        self.assertEqual(by_var[("SYN-MOTRPAC-LIKE", "steps_per_day")].review_status, "accepted")


if __name__ == "__main__":
    unittest.main()


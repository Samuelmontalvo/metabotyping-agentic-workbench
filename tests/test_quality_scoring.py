from pathlib import Path
import tempfile
import unittest

from metabotyping_agentic.evaluation.quality_scoring import score_quality
from metabotyping_agentic.extraction.metadata_cards import extract_metadata_cards


ROOT = Path(__file__).resolve().parents[1]


class QualityScoringTests(unittest.TestCase):
    def test_quality_scores_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            extract_metadata_cards(
                ROOT / "data/examples/mock_repository_records.csv",
                tmp_path,
                ROOT / "data/examples/mock_publications.csv",
            )

            scores = score_quality(tmp_path, tmp_path)

        self.assertTrue(scores)
        self.assertTrue(all(0 <= score.overall_score <= 1 for score in scores))


if __name__ == "__main__":
    unittest.main()


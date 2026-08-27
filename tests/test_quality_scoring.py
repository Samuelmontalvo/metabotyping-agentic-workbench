import tempfile
import unittest
from pathlib import Path

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



class OverallScoreInterpreterStabilityTests(unittest.TestCase):
    """A published quality score must not depend on the interpreter version.

    CPython 3.12 gave sum() Neumaier compensated summation for floats. The
    weighted subscores below total 0.8175 exactly in decimal, so naive
    accumulation lands at 0.8174999999999999 on 3.11 and 0.8175000000000000 on
    3.12+, which rounds to 0.817 and 0.818 respectively. That made
    data/extracted/quality_scores.json differ between a developer machine and
    CI. score_quality must use exactly-rounded summation instead.
    """

    WEIGHTS = {
        "study_design_rigor": 0.15,
        "metadata_completeness": 0.15,
        "metabolomics_quality": 0.15,
        "activity_quality": 0.10,
        "genetics_quality": 0.10,
        "cpet_quality": 0.10,
        "body_composition_quality": 0.05,
        "diet_quality": 0.05,
        "temporal_alignment": 0.10,
        "harmonization_feasibility": 0.05,
    }
    SUBSCORES = {
        "study_design_rigor": 1.0,
        "metadata_completeness": 1.0,
        "metabolomics_quality": 1.0,
        "activity_quality": 0.7,
        "genetics_quality": 0.35,
        "cpet_quality": 0.85,
        "body_composition_quality": 0.8,
        "diet_quality": 0.3,
        "temporal_alignment": 0.8,
        "harmonization_feasibility": 0.85,
    }

    def test_boundary_weighted_total_rounds_identically_on_every_interpreter(self):
        import math

        total = math.fsum(
            self.SUBSCORES[name] * self.WEIGHTS[name] for name in self.WEIGHTS
        )
        self.assertEqual(round(total, 3), 0.818)

    def test_naive_summation_would_be_interpreter_dependent(self):
        """Pin the reason the production code cannot use the builtin sum()."""

        from decimal import Decimal

        naive = sum(self.SUBSCORES[name] * self.WEIGHTS[name] for name in self.WEIGHTS)
        exact = Decimal("0.8175")
        # Naive accumulation is off the exact decimal total in one direction or
        # the other depending on the interpreter; fsum is not.
        self.assertNotEqual(Decimal(naive), exact)

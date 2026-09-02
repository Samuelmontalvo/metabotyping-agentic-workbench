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
        reported = [score for score in scores if score.overall_score is not None]
        self.assertTrue(all(0 <= score.overall_score <= 1 for score in reported))
        withheld = {score.study_id: score.scope_status for score in scores if score not in reported}
        # The only fixture documented as non-human is the one study with no score.
        self.assertEqual(withheld, {"SYN-ANIMAL-MET": "out_of_scope_non_human"})
        self.assertTrue(
            all(score.scope_status == "in_scope_human" for score in reported)
        )


class UnreportedMetadataRationaleTests(unittest.TestCase):
    """A not_reported platform must not be described as reported."""

    def _score(self, assay_platform: str):
        from metabotyping_agentic.evaluation.quality_scoring import DEFAULT_WEIGHTS, _score_dataset

        dataset = {
            "study_id": "SYN-RATIONALE",
            "modalities": ["metabolomics", "exercise"],
            "has_metadata": True,
            "has_codebook": True,
            "has_data_files": True,
            "assay_platform": assay_platform,
            "sample_matrix": "plasma",
            "biospecimen_timing": "baseline",
            "sample_size": 50,
        }
        return _score_dataset(dataset, {"study_id": "SYN-RATIONALE", "human": True, "modalities": []}, DEFAULT_WEIGHTS)

    def test_not_reported_platform_is_scored_and_described_as_unreported(self):
        reported = self._score("LC-MS")
        for value in ("unknown", "not_reported", ""):
            with self.subTest(value=value):
                score = self._score(value)
                self.assertNotIn("Metabolomics assay platform is reported.", score.rationale)
                self.assertLess(score.metabolomics_quality, reported.metabolomics_quality)
                self.assertLess(score.metadata_completeness, reported.metadata_completeness)
        self.assertIn("Metabolomics assay platform is reported.", reported.rationale)


class ScopeStatusGateTests(unittest.TestCase):
    """The readiness scale is human-only; non-human is withheld, unknown is flagged."""

    DATASET = {
        "study_id": "SYN-SCOPE",
        "modalities": ["metabolomics", "exercise", "cpet"],
        "has_metadata": True,
        "has_codebook": True,
        "has_data_files": True,
        "assay_platform": "LC-MS",
        "sample_matrix": "plasma",
        "biospecimen_timing": "pre and post",
        "sample_size": 120,
    }

    def _score(self, study):
        from metabotyping_agentic.evaluation.quality_scoring import DEFAULT_WEIGHTS, _score_dataset

        return _score_dataset(dict(self.DATASET), study, DEFAULT_WEIGHTS)

    def test_documented_non_human_study_has_no_overall_score(self):
        score = self._score({"study_id": "SYN-SCOPE", "human": False, "modalities": []})
        self.assertEqual(score.scope_status, "out_of_scope_non_human")
        self.assertIsNone(score.overall_score)
        # Subscores stay visible so the withheld score is auditable.
        self.assertGreater(score.metabolomics_quality, 0)
        self.assertTrue(any("non-human" in item for item in score.rationale))

    def test_human_study_is_in_scope_with_a_score(self):
        score = self._score({"study_id": "SYN-SCOPE", "human": True, "modalities": []})
        self.assertEqual(score.scope_status, "in_scope_human")
        self.assertIsNotNone(score.overall_score)
        self.assertFalse(any("not documented" in item for item in score.rationale))

    def test_undocumented_human_status_is_flagged_not_withheld(self):
        from metabotyping_agentic.evaluation.quality_scoring import scope_status_for

        for study in (None, {"study_id": "SYN-SCOPE", "human": None, "modalities": []}):
            with self.subTest(study=study):
                score = self._score(study)
                self.assertEqual(score.scope_status, "human_status_unknown")
                self.assertIsNotNone(score.overall_score)
                self.assertTrue(any("not documented" in item for item in score.rationale))
        self.assertEqual(scope_status_for({"human": False}), "out_of_scope_non_human")

    def test_written_rows_validate_against_the_quality_schema(self):
        from metabotyping_agentic.io import read_json
        from metabotyping_agentic.schemas import project_schema_path, validate_against_schema

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            extract_metadata_cards(
                ROOT / "data/examples/mock_repository_records.csv",
                tmp_path,
                ROOT / "data/examples/mock_publications.csv",
            )
            score_quality(tmp_path, tmp_path)
            rows = read_json(tmp_path / "quality_scores.json")
        schema = project_schema_path("quality_score.schema.json")
        for row in rows:
            with self.subTest(study_id=row["study_id"]):
                self.assertEqual(validate_against_schema(row, schema), [])


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


if __name__ == "__main__":
    unittest.main()

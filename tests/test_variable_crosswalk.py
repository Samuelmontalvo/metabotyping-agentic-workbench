import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.harmonization.crosswalk import (
    build_crosswalk,
    choose_transform,
    common_variable_for,
)
from metabotyping_agentic.harmonization.skeptic import human_review_reason
from metabotyping_agentic.models import Modality, VariableCard

ROOT = Path(__file__).resolve().parents[1]


class VariableCrosswalkTests(unittest.TestCase):
    def test_crosswalk_routes_vo2peak_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            mappings = build_crosswalk(ROOT / "data/examples/mock_variable_dictionary.csv", Path(tmp))
        by_var = {(m.source_study, m.source_variable): m for m in mappings}

        self.assertEqual(by_var[("SYN-CPET-RICH", "vo2peak")].proposed_common_variable, "vo2max")
        self.assertEqual(by_var[("SYN-CPET-RICH", "vo2peak")].review_status, "requires_human_review")
        self.assertEqual(by_var[("SYN-MOTRPAC-LIKE", "steps_per_day")].review_status, "accepted")

    def test_gender_to_sex_is_flagged_as_a_construct_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            mappings = build_crosswalk(ROOT / "data/examples/mock_variable_dictionary.csv", Path(tmp))
        mapping = next(m for m in mappings if m.source_variable == "gender")

        self.assertEqual(mapping.proposed_common_variable, "sex")
        self.assertEqual(mapping.review_status, "requires_human_review")
        self.assertLessEqual(mapping.confidence, 0.78)
        self.assertIn("distinct constructs", mapping.evidence)
        reason = human_review_reason(
            {
                "review_status": mapping.review_status,
                "proposed_common_variable": mapping.proposed_common_variable,
                "evidence": mapping.evidence,
                "transform": mapping.transform,
            }
        )
        self.assertIn("gender identity", reason)

    def test_unit_conversions_are_analyte_specific(self):
        self.assertEqual(
            choose_transform("fasting_glucose", "mmol/L", "mg/dL"),
            ("multiply_by_18.0182", True),
        )
        # The glucose molar-mass factor must not be applied to any other analyte.
        self.assertEqual(
            choose_transform("insulin", "mmol/L", "mg/dL"),
            ("unit_conversion_requires_review", False),
        )
        self.assertEqual(choose_transform("bmi", "kg/m^2", "kg/m^2"), ("identity", True))
        self.assertEqual(choose_transform("age", "unknown", "years"), ("not_available", False))

    def test_partial_matching_uses_token_boundaries(self):
        card = VariableCard(
            study_id="SYN-UNSEEN",
            source_variable="oxygen_uptake_highest_stage",
            label="Highest attained oxygen uptake",
            unit="mL/kg/min",
            timing="baseline",
            modality=Modality.CPET,
        )

        self.assertEqual(common_variable_for(card), ("not_mapped", "no_supported_synonym"))

    def test_unseen_mvpa_wording_remains_review_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            mappings = build_crosswalk(
                ROOT / "data/examples/unseen_cohort/variable_dictionary.csv",
                Path(tmp),
            )
        by_var = {mapping.source_variable: mapping for mapping in mappings}

        mapping = by_var["moderate_vigorous_minutes_14d"]
        self.assertEqual(mapping.proposed_common_variable, "mvpa_minutes")
        self.assertEqual(mapping.review_status, "requires_human_review")


if __name__ == "__main__":
    unittest.main()

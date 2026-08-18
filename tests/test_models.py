import unittest

from metabotyping_agentic.models import InclusionCriteria, Modality, VariableCard


class ModelTests(unittest.TestCase):
    def test_model_dump_handles_enums(self):
        card = VariableCard(
            study_id="S1",
            source_variable="vo2max",
            label="VO2max",
            unit="mL/kg/min",
            timing="baseline",
            modality=Modality.CPET,
        )

        self.assertEqual(card.model_dump()["modality"], "cpet")

    def test_inclusion_defaults(self):
        criteria = InclusionCriteria(query="human metabolomics exercise")

        self.assertIn("human", criteria.required_terms)
        self.assertIn("metabolomics", criteria.required_terms)


if __name__ == "__main__":
    unittest.main()


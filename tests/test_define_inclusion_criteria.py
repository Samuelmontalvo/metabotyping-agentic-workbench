import unittest

from metabotyping_agentic.discovery.criteria import define_inclusion_criteria


class InclusionCriteriaTests(unittest.TestCase):
    def test_define_inclusion_criteria_extracts_preferred_terms(self):
        criteria = define_inclusion_criteria("human metabolomics with actigraphy genetics and CPET")

        self.assertEqual(criteria.required_terms, ["human", "metabolomics"])
        self.assertIn("actigraphy", criteria.preferred_terms)
        self.assertIn("genetics", criteria.preferred_terms)
        self.assertIn("cpet", criteria.preferred_terms)


if __name__ == "__main__":
    unittest.main()


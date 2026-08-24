import unittest
from pathlib import Path

from metabotyping_agentic.discovery.literature import load_publications
from metabotyping_agentic.discovery.recommender import build_recommendations
from metabotyping_agentic.discovery.repositories import load_repository_records, repository_by_study
from metabotyping_agentic.models import InclusionCriteria, PublicationRecord, RepositoryRecord

ROOT = Path(__file__).resolve().parents[1]


class DiscoveryRecommenderTests(unittest.TestCase):
    def test_recommendations_rank_motrpac_like_highly(self):
        pubs = load_publications(ROOT / "data/examples/mock_publications.csv")
        repos = repository_by_study(load_repository_records(ROOT / "data/examples/mock_repository_records.csv"))

        recommendations = build_recommendations(pubs, repos)

        self.assertEqual(recommendations[0].study_id, "SYN-MOTRPAC-LIKE")
        excluded = {item.study_id for item in recommendations if item.recommendation_class == "excluded"}
        self.assertIn("SYN-ANIMAL-MET", excluded)

    def test_metabolomics_workbench_non_blood_derived_matrix_is_excluded(self):
        publication = PublicationRecord(
            study_id="MW-MUSCLE-ONLY",
            title="Human exercise muscle metabolomics",
            human=True,
            exercise=True,
            metabolomics=True,
            repository_accession="MWB-MUSCLE-ONLY",
        )
        repository = RepositoryRecord(
            study_id="MW-MUSCLE-ONLY",
            repository="Metabolomics Workbench",
            accession="MWB-MUSCLE-ONLY",
            has_metadata=True,
            has_codebook=True,
            has_data_files=True,
            sample_matrix="skeletal muscle",
            biospecimen_timing="acute post exercise",
            sample_size=24,
        )

        recommendation = build_recommendations([publication], {"MW-MUSCLE-ONLY": repository})[0]

        self.assertEqual(recommendation.recommendation_class, "excluded")
        self.assertEqual(recommendation.score, 0.0)
        self.assertIn("blood-derived", recommendation.rationale)

    def test_metabolomics_workbench_accession_without_matrix_evidence_is_excluded(self):
        publication = PublicationRecord(
            study_id="MW-NO-REPO",
            title="Human exercise metabolomics",
            human=True,
            exercise=True,
            metabolomics=True,
            repository_accession="ST123456",
        )

        recommendation = build_recommendations([publication], {})[0]

        self.assertEqual(recommendation.recommendation_class, "excluded")
        self.assertEqual(recommendation.score, 0.0)
        self.assertIn("sample matrix evidence", recommendation.rationale)

    def test_metabolomics_workbench_blood_derived_matrix_remains_eligible(self):
        publication = PublicationRecord(
            study_id="MW-SERUM",
            title="Human serum metabolomics",
            human=True,
            metabolomics=True,
            repository_accession="MWB-SERUM",
        )
        repository = RepositoryRecord(
            study_id="MW-SERUM",
            repository="Metabolomics Workbench",
            accession="MWB-SERUM",
            has_metadata=True,
            has_codebook=True,
            has_data_files=True,
            sample_matrix="Blood (serum)",
            biospecimen_timing="baseline fasting",
            sample_size=24,
        )

        recommendation = build_recommendations([publication], {"MW-SERUM": repository})[0]

        self.assertNotEqual(recommendation.recommendation_class, "excluded")

    def test_required_criteria_change_eligibility(self):
        publication = PublicationRecord(
            study_id="NO-GENETICS",
            title="Human exercise metabolomics",
            human=True,
            exercise=True,
            metabolomics=True,
        )
        criteria = InclusionCriteria(
            query="human metabolomics and genetics",
            required_terms=["human", "metabolomics", "genetics"],
            preferred_terms=["exercise"],
        )

        recommendation = build_recommendations([publication], {}, criteria)[0]

        self.assertEqual(recommendation.recommendation_class, "excluded")
        self.assertIn("genetics", recommendation.rationale)

    def test_preferred_criteria_change_score(self):
        publication = PublicationRecord(
            study_id="CPET-ONLY",
            title="Human CPET metabolomics",
            human=True,
            metabolomics=True,
            cpet=True,
        )
        cpet_criteria = InclusionCriteria(query="cpet", preferred_terms=["cpet"])
        diet_criteria = InclusionCriteria(query="diet", preferred_terms=["diet"])

        cpet_score = build_recommendations([publication], {}, cpet_criteria)[0].score
        diet_score = build_recommendations([publication], {}, diet_criteria)[0].score

        self.assertGreater(cpet_score, diet_score)


if __name__ == "__main__":
    unittest.main()

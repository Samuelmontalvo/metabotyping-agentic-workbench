import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.evaluation.motrpac_alignment import align_motrpac, align_one
from metabotyping_agentic.extraction.metadata_cards import extract_metadata_cards

ROOT = Path(__file__).resolve().parents[1]


class MotrpacAlignmentTests(unittest.TestCase):
    def test_motrpac_like_dataset_is_high_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            extract_metadata_cards(
                ROOT / "data/examples/mock_repository_records.csv",
                tmp_path,
                ROOT / "data/examples/mock_publications.csv",
            )

            alignments = align_motrpac(tmp_path, tmp_path)
        by_study = {item.study_id: item for item in alignments}

        self.assertEqual(by_study["SYN-MOTRPAC-LIKE"].tier, "high")
        self.assertEqual(by_study["SYN-ANIMAL-MET"].tier, "not_feasible")

    def test_missing_genetics_is_not_treated_as_documented_absent(self):
        dataset = {
            "study_id": "GENETICS-UNKNOWN",
            "modalities": ["metabolomics", "exercise"],
            "documented_absent_modalities": [],
            "biospecimen_timing": "post exercise",
            "sample_matrix": "plasma",
            "assay_platform": "LC-MS",
            "has_codebook": True,
        }

        alignment = align_one(dataset, {"human": True, "modalities": []})

        self.assertIn("genetics available or documented absent", alignment.missing_elements)

    def test_documented_absent_genetics_satisfies_criterion(self):
        dataset = {
            "study_id": "GENETICS-ABSENT",
            "modalities": ["metabolomics", "exercise"],
            "documented_absent_modalities": ["genetics"],
            "biospecimen_timing": "post exercise",
            "sample_matrix": "plasma",
            "assay_platform": "LC-MS",
            "has_codebook": True,
        }

        alignment = align_one(dataset, {"human": True, "modalities": []})

        self.assertIn("genetics available or documented absent", alignment.met_criteria)

    def test_missing_human_evidence_is_hard_gate(self):
        dataset = {
            "study_id": "HUMAN-UNKNOWN",
            "modalities": [
                "metabolomics",
                "exercise",
                "genetics",
                "cpet",
                "body_composition",
                "diet",
            ],
            "biospecimen_timing": "post exercise",
            "sample_matrix": "plasma",
            "assay_platform": "LC-MS",
            "has_codebook": True,
        }

        alignment = align_one(dataset)

        self.assertEqual(alignment.tier, "not_feasible")
        self.assertIn("hard gate", alignment.rationale)


if __name__ == "__main__":
    unittest.main()

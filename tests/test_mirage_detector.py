import unittest
from pathlib import Path

from metabotyping_agentic.discovery.literature import load_publications
from metabotyping_agentic.discovery.mirage_detector import detect_mirage_flags
from metabotyping_agentic.discovery.repositories import load_repository_records, repository_by_study

ROOT = Path(__file__).resolve().parents[1]


class MirageDetectorTests(unittest.TestCase):
    def test_mirage_detector_flags_no_repository_assets(self):
        pubs = {p.study_id: p for p in load_publications(ROOT / "data/examples/mock_publications.csv")}
        repos = repository_by_study(load_repository_records(ROOT / "data/examples/mock_repository_records.csv"))

        flags = detect_mirage_flags(pubs["SYN-EXER-NODATA"], repos["SYN-EXER-NODATA"])

        self.assertIn("no_repository_accession", flags)
        self.assertIn("no_downloadable_metadata", flags)
        self.assertIn("no_variable_dictionary_or_codebook", flags)


if __name__ == "__main__":
    unittest.main()


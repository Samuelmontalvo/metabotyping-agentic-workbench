import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.discovery.repositories import (
    load_repository_records,
    repositories_by_study,
    repository_by_study,
)
from metabotyping_agentic.extraction.metadata_cards import extract_metadata_cards
from metabotyping_agentic.io import read_json, to_plain, write_csv_rows
from metabotyping_agentic.schemas import (
    project_schema_path,
    validate_against_schema,
    validate_or_raise,
)

ROOT = Path(__file__).resolve().parents[1]


class MetadataExtractionTests(unittest.TestCase):
    def test_metadata_extraction_writes_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            studies, datasets = extract_metadata_cards(
                ROOT / "data/examples/mock_repository_records.csv",
                tmp_path,
                ROOT / "data/examples/mock_publications.csv",
            )

            self.assertEqual(len(studies), 10)
            self.assertEqual(len(datasets), 10)
            dataset_paths = list(
                (tmp_path / "metadata_cards").glob("dataset_SYN-MOTRPAC-LIKE__*.json")
            )
            self.assertEqual(len(dataset_paths), 1)
            self.assertIn("genetics", to_plain(datasets[1])["documented_absent_modalities"])

            study_payload = read_json(tmp_path / "metadata_cards/study_SYN-MOTRPAC-LIKE.json")
            dataset_payload = read_json(dataset_paths[0])
            self.assertEqual(study_payload["repository_accessions"], ["MWB-SYN-008"])
            self.assertEqual(
                validate_against_schema(study_payload, project_schema_path("study_card.schema.json")),
                [],
            )
            self.assertEqual(
                validate_against_schema(dataset_payload, project_schema_path("dataset_card.schema.json")),
                [],
            )

    def test_schema_validation_raises_for_invalid_card(self):
        with self.assertRaisesRegex(ValueError, "failed schema validation"):
            validate_or_raise(
                {"study_id": "incomplete"},
                project_schema_path("dataset_card.schema.json"),
                label="test dataset card",
            )

    def test_duplicate_study_repositories_are_grouped_and_emit_collision_safe_cards(self):
        rows = [
            {
                "study_id": "SYN-MULTI-DB",
                "repository": "Metabolomics Workbench",
                "accession": "ST000001",
                "public_status": "public",
                "has_metadata": "true",
                "has_codebook": "true",
                "has_data_files": "true",
                "assay_platform": "LC-MS",
                "sample_matrix": "plasma",
                "biospecimen_timing": "baseline",
                "sample_size": "12",
                "modalities": "metabolomics;exercise",
                "documented_absent_modalities": "",
            },
            {
                "study_id": "SYN-MULTI-DB",
                "repository": "MetaboLights",
                "accession": "MTBLS0001",
                "public_status": "public",
                "has_metadata": "true",
                "has_codebook": "true",
                "has_data_files": "false",
                "assay_platform": "NMR",
                "sample_matrix": "serum",
                "biospecimen_timing": "post exercise",
                "sample_size": "12",
                "modalities": "metabolomics;exercise",
                "documented_absent_modalities": "",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            records_path = write_csv_rows(tmp_path / "repositories.csv", rows)
            records = load_repository_records(records_path)

            grouped = repositories_by_study(records)
            self.assertEqual(
                [item.accession for item in grouped["SYN-MULTI-DB"]],
                ["ST000001", "MTBLS0001"],
            )
            with self.assertRaisesRegex(ValueError, "Use repositories_by_study"):
                repository_by_study(records)

            studies, datasets = extract_metadata_cards(records_path, tmp_path / "out")

            self.assertEqual(len(studies), 1)
            self.assertEqual(len(datasets), 2)
            self.assertIsNone(studies[0].human)
            self.assertIn("publication_metadata_missing", studies[0].mirage_flags)
            self.assertEqual(
                studies[0].provenance["publication_evidence"],
                "unknown_not_supplied_or_unmatched",
            )
            self.assertEqual(studies[0].repository_accession, "ST000001")
            self.assertEqual(studies[0].repository_accessions, ["ST000001", "MTBLS0001"])
            row_keys = [dataset.provenance["row_key"] for dataset in datasets]
            self.assertEqual(len(set(row_keys)), 2)
            self.assertEqual(
                {dataset.provenance["source_row_number"] for dataset in datasets},
                {2, 3},
            )
            dataset_paths = sorted((tmp_path / "out/metadata_cards").glob("dataset_*.json"))
            self.assertEqual(len(dataset_paths), 2)
            self.assertTrue(
                any("Metabolomics-Workbench__ST000001" in path.name for path in dataset_paths)
            )
            self.assertTrue(any("MetaboLights__MTBLS0001" in path.name for path in dataset_paths))

    def test_required_publication_universe_mismatch_fails_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "out"

            with self.assertRaisesRegex(ValueError, "study universes must match exactly"):
                extract_metadata_cards(
                    ROOT / "data/examples/mock_repository_records.csv",
                    out,
                    ROOT / "data/examples/unseen_cohort/publications.csv",
                    require_publication_match=True,
                )

            self.assertFalse(out.exists())

    def test_explicit_missing_publications_file_fails_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "out"

            with self.assertRaises(FileNotFoundError):
                extract_metadata_cards(
                    ROOT / "data/examples/mock_repository_records.csv",
                    out,
                    tmp_path / "missing_publications.csv",
                )

            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

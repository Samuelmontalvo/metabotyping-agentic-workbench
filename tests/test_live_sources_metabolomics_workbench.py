import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.live_sources.metabolomics_workbench import (
    ingest_metabolomics_workbench_study,
)


def fake_fetcher(url: str):
    if url.endswith("/summary"):
        return {
            "study_id": "ST001789",
            "study_title": "Acute metabolomic changes of plasma in response to endurance exercise",
            "species": "Homo sapiens",
            "analysis_type": "LC-MS",
            "number_of_samples": "3",
            "license": "CC BY 4.0",
            "study_url": "https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001789",
        }
    if url.endswith("/analysis"):
        return {
            "1": {
                "study_id": "ST001789",
                "analysis_id": "AN002901",
                "analysis_type": "MS",
                "chromatography_type": "HILIC",
                "ms_instrument_type": "Triple quadrupole",
                "units": "peak area",
            }
        }
    if url.endswith("/factors"):
        return {
            "1": {
                "study_id": "ST001789",
                "local_sample_id": "sample-1",
                "sample_source": "Blood (plasma)",
                "factors": "Group:Pre",
                "mb_sample_id": "SA1",
            },
            "2": {
                "study_id": "ST001789",
                "local_sample_id": "sample-2",
                "sample_source": "Blood (plasma)",
                "factors": "Group:Time 0",
                "mb_sample_id": "SA2",
            },
            "3": {
                "study_id": "ST001789",
                "local_sample_id": "sample-3",
                "sample_source": "Blood (plasma)",
                "factors": "Group:Time 60",
                "mb_sample_id": "SA3",
            },
        }
    if url.endswith("/metabolites"):
        return {
            "1": {
                "study_id": "ST001789",
                "analysis_id": "AN002901",
                "metabolite_name": "Lactate",
                "refmet_name": "Lactic acid",
            },
            "2": {
                "study_id": "ST001789",
                "analysis_id": "AN002901",
                "metabolite_name": "Glucose",
                "refmet_name": "Glucose",
            },
        }
    raise AssertionError(f"Unexpected URL: {url}")


def non_blood_derived_fetcher(url: str):
    payload = fake_fetcher(url)
    if url.endswith("/factors"):
        return {
            key: {
                **record,
                "sample_source": "Skeletal muscle",
            }
            for key, record in payload.items()
        }
    return payload


class MetabolomicsWorkbenchLiveSourceTests(unittest.TestCase):
    def test_live_intake_normalizes_metadata_without_persisting_sample_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ingest_metabolomics_workbench_study(
                "ST001789",
                Path(tmp),
                fetcher=fake_fetcher,
                availability_checker=lambda url: True,
            )

            self.assertEqual(result.metabolite_count, 2)
            self.assertEqual(result.sample_count, 3)
            self.assertTrue(result.data_endpoint_available)
            self.assertTrue((result.extracted_dir / "dataset_cards.json").exists())
            self.assertTrue((result.extracted_dir / "variable_inventory.csv").exists())
            self.assertTrue((result.reports_dir / "motrpac_alignment_report.md").exists())

            source_summary = (Path(tmp) / "source_summaries/metabolomics_workbench_summary.json").read_text()
            self.assertNotIn("sample-1", source_summary)
            self.assertIn("Group:Time 60", source_summary)

    def test_live_intake_rejects_non_blood_derived_sample_matrix_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "blood-derived"):
                ingest_metabolomics_workbench_study(
                    "ST001789",
                    Path(tmp),
                    fetcher=non_blood_derived_fetcher,
                    availability_checker=lambda url: True,
                )

    def test_live_intake_can_allow_non_blood_derived_sample_matrix_for_manual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ingest_metabolomics_workbench_study(
                "ST001789",
                Path(tmp),
                fetcher=non_blood_derived_fetcher,
                availability_checker=lambda url: True,
                require_blood_derived_sample_matrix=False,
            )

            self.assertEqual(result.sample_count, 3)
            source_summary = (Path(tmp) / "source_summaries/metabolomics_workbench_summary.json").read_text()
            self.assertIn("Skeletal muscle", source_summary)


if __name__ == "__main__":
    unittest.main()

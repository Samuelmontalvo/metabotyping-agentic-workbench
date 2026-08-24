import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.cli import main
from metabotyping_agentic.io import read_json
from metabotyping_agentic.knowledge.source_registry import (
    SOURCE_REGISTRY,
    build_retrieval_plan,
    infer_identifier_namespace,
    validate_registry,
)


class SourceRegistryTests(unittest.TestCase):
    def test_registry_is_structurally_valid_and_unique(self):
        self.assertEqual(validate_registry(), [])
        ids = [source.source_id for source in SOURCE_REGISTRY]
        self.assertEqual(len(ids), len(set(ids)))

    def test_identifier_namespace_detection_is_conservative(self):
        cases = {
            "CHEBI:17234": "chebi",
            "HMDB0000122": "hmdb",
            "RM0123456": "refmet",
            "MTBLS1": "metabolights",
            "ST004303": "metabolomics_workbench",
            "PXD001357": "pride",
            "R-HSA-199420": "reactome",
            "BSYNRYMUTXBXSQ-UHFFFAOYSA-N": "inchikey",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(infer_identifier_namespace(value), expected)
        self.assertIsNone(infer_identifier_namespace("leucine"))
        self.assertIsNone(infer_identifier_namespace("12345"))

    def test_chemical_identity_plan_routes_identifier_sources_without_claiming_resolution(self):
        plan = build_retrieval_plan(
            ["metabolite", "classification"],
            ["HMDB0000122", "leucine"],
        )
        source_ids = [row["source_id"] for row in plan["sources"]]
        self.assertIn("hmdb", source_ids)
        self.assertIn("chebi", source_ids)
        self.assertIn("refmet", source_ids)
        self.assertEqual(plan["identifiers"][0]["status"], "recognized_identifier")
        self.assertEqual(plan["identifiers"][1]["status"], "requires_entity_resolution")
        self.assertTrue(any("cannot establish metabolite identity" in value for value in plan["warnings"]))
        self.assertIn("Names and synonyms alone never authorize", " ".join(plan["decision_rules"]))

    def test_dataset_and_exercise_plan_retains_complementary_sources(self):
        plan = build_retrieval_plan(
            ["dataset", "exercise", "assay"],
            ["MTBLS1", "ST004303"],
            max_sources=None,
        )
        source_ids = {row["source_id"] for row in plan["sources"]}
        self.assertTrue({"metabolights", "metabolomics_workbench", "motrpac_datahub"}.issubset(source_ids))
        self.assertEqual(plan["missing_lanes"], [])

    def test_restricted_sources_are_explicitly_excluded_or_retained(self):
        open_plan = build_retrieval_plan(["pathway"], require_open=True, max_sources=None)
        all_plan = build_retrieval_plan(["pathway"], require_open=False, max_sources=None)
        self.assertNotIn("kegg", {row["source_id"] for row in open_plan["sources"]})
        self.assertIn("kegg", {row["source_id"] for row in all_plan["sources"]})
        self.assertTrue(any("Restricted" in warning for warning in open_plan["warnings"]))

    def test_unknown_lane_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, "Unsupported research lane"):
            build_retrieval_plan(["astrology"])

    def test_cli_writes_machine_readable_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.json"
            main(
                [
                    "route-sources",
                    "--lanes",
                    "identity,pathway",
                    "--identifiers",
                    "CHEBI:17234",
                    "--out",
                    str(out),
                ]
            )
            payload = read_json(out)
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertIn("chemical_identity", payload["covered_lanes"])
            self.assertIn("pathways", payload["covered_lanes"])


if __name__ == "__main__":
    unittest.main()

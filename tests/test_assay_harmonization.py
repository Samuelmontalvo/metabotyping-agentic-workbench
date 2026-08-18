from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from metabotyping_agentic.harmonization.assay_harmonization import (
    APPROVED_TRANSFORM_REGISTRY,
    build_assay_harmonization_plan,
    evaluate_assay_pair,
    load_assay_harmonization_fixture,
    write_assay_harmonization_artifacts,
)
from metabotyping_agentic.harmonization.assay_models import MetaboliteAssayRecord
from metabotyping_agentic.io import read_json, to_plain
from metabotyping_agentic.schemas import project_schema_path, validate_against_schema


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/examples/mock_metabolite_assays.json"


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


class AssayHarmonizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records, cls.pairs = load_assay_harmonization_fixture(FIXTURE)
        cls.by_id = {item.feature_id: item for item in cls.records}

    def test_synthetic_records_and_plan_validate_against_new_schemas(self):
        raw_records = read_json(FIXTURE)["records"]
        record_schema = project_schema_path("metabolite_assay_record.schema.json")
        for record in raw_records:
            self.assertEqual(validate_against_schema(record, record_schema), [])

        plan = build_assay_harmonization_plan(self.records, self.pairs)
        plan_schema = project_schema_path("assay_harmonization_plan.schema.json")
        self.assertEqual(validate_against_schema(to_plain(plan), plan_schema), [])

    def test_compatible_absolute_assays_get_deterministic_unit_and_loq_plan(self):
        decision = evaluate_assay_pair(
            self.by_id["SYN-A:citrate"], self.by_id["SYN-B:citrate"]
        )

        self.assertEqual(_value(decision.status), "accepted")
        self.assertTrue(decision.raw_values_combinable)
        self.assertEqual(_value(decision.permitted_analysis), "pooled_individual_values")
        self.assertEqual(decision.common_unit, "umol/L")
        self.assertTrue(decision.canonical_identity.startswith("inchikey:"))
        transforms = {item.registry_key: item for item in decision.transforms}
        self.assertEqual(set(transforms) - APPROVED_TRANSFORM_REGISTRY, set())
        loq = transforms["censor_below_common_loq"].parameters
        self.assertEqual(loq, {"common_loq": 1.0, "unit": "umol/L"})
        multipliers = sorted(
            item.parameters["multiplier"]
            for item in decision.transforms
            if item.registry_key == "convert_compatible_concentration_unit"
        )
        self.assertEqual(multipliers, [1.0, 1000.0])

    def test_plan_is_order_independent_and_has_no_clock_timestamp(self):
        forward = build_assay_harmonization_plan(self.records, self.pairs)
        reverse = build_assay_harmonization_plan(
            list(reversed(self.records)), list(reversed(self.pairs))
        )
        forward_json = json.dumps(to_plain(forward), sort_keys=True)
        reverse_json = json.dumps(to_plain(reverse), sort_keys=True)
        self.assertEqual(forward_json, reverse_json)
        self.assertNotIn("generated_at", to_plain(forward))

    def test_name_only_match_never_establishes_identity(self):
        decision = evaluate_assay_pair(
            self.by_id["SYN-A:citrate"], self.by_id["SYN-C:citrate-name-only"]
        )
        self.assertNotEqual(_value(decision.status), "accepted")
        self.assertEqual(_value(decision.identity_status), "requires_human_review")
        self.assertFalse(decision.raw_values_combinable)
        codes = {item.code for item in decision.evidence}
        self.assertIn("reported_name_not_identity_evidence", codes)
        self.assertIn("no_shared_standard_identifier", codes)
        self.assertEqual(decision.transforms, [])

    def test_conflicting_exact_inchikey_is_explicitly_non_combinable(self):
        decision = evaluate_assay_pair(
            self.by_id["SYN-A:citrate"], self.by_id["SYN-D:different-structure"]
        )
        self.assertEqual(_value(decision.identity_status), "non_combinable")
        self.assertEqual(_value(decision.status), "non_combinable")
        self.assertIn("inchikey_structure_conflict", decision.blockers)
        self.assertEqual(decision.transforms, [])

    def test_msi_level_2_and_unresolved_isomer_cannot_auto_merge(self):
        payload = deepcopy(to_plain(self.by_id["SYN-B:citrate"]))
        payload["feature_id"] = "SYN-B:citrate-putative"
        payload["identity"]["identification_level"] = "msi_level_2"
        payload["identity"]["resolution"] = "stereochemistry_unresolved"
        for identifier in payload["identity"]["standard_identifiers"]:
            identifier["resolution"] = "stereochemistry_unresolved"
        putative = MetaboliteAssayRecord.model_validate(payload)

        decision = evaluate_assay_pair(self.by_id["SYN-A:citrate"], putative)
        self.assertEqual(_value(decision.identity_status), "requires_human_review")
        self.assertIn("isomer_or_stereochemistry_unresolved", decision.blockers)
        self.assertIn("msi_level_1_evidence_required", decision.blockers)
        self.assertFalse(decision.raw_values_combinable)

    def test_unbridged_nmr_and_lcms_are_review_gated_with_heterogeneity_plan(self):
        decision = evaluate_assay_pair(
            self.by_id["SYN-A:citrate"], self.by_id["SYN-E:citrate-nmr"]
        )
        self.assertEqual(_value(decision.identity_status), "accepted")
        self.assertEqual(_value(decision.status), "requires_human_review")
        self.assertIn("unbridged_assay_methods", decision.blockers)
        self.assertFalse(decision.raw_values_combinable)
        self.assertEqual(
            _value(decision.permitted_analysis), "study_specific_effects_meta_analysis"
        )
        self.assertIn(
            "platform_moderator_meta_regression",
            decision.heterogeneity_plan.required_diagnostics,
        )
        self.assertIn("leave_one_platform_out", decision.heterogeneity_plan.required_diagnostics)
        self.assertEqual(decision.transforms, [])

    def test_relative_abundance_and_feature_intensity_never_pool_with_concentration(self):
        relative = evaluate_assay_pair(
            self.by_id["SYN-A:citrate"], self.by_id["SYN-F:citrate-relative"]
        )
        self.assertEqual(_value(relative.quantitative_status), "non_combinable")
        self.assertFalse(relative.raw_values_combinable)
        self.assertEqual(
            _value(relative.permitted_analysis), "study_specific_effects_meta_analysis"
        )
        self.assertIn("quantitation_type_incompatible", relative.blockers)

    def test_irreversible_below_limit_imputation_blocks_even_effect_meta_analysis(self):
        payload = deepcopy(to_plain(self.by_id["SYN-B:citrate"]))
        payload["feature_id"] = "SYN-B:citrate-imputed"
        payload["quantitative"]["limits"]["censoring_policy"] = "half_limit_imputed"
        payload["quantitative"]["missingness"]["imputation_method"] = "half_loq"
        payload["quantitative"]["missingness"]["unimputed_values_available"] = False
        imputed = MetaboliteAssayRecord.model_validate(payload)

        decision = evaluate_assay_pair(self.by_id["SYN-A:citrate"], imputed)
        self.assertEqual(_value(decision.status), "non_combinable")
        self.assertIn("SYN-B:citrate-imputed:irreversible_imputation", decision.blockers)
        self.assertEqual(_value(decision.permitted_analysis), "none")
        self.assertEqual(decision.transforms, [])

    def test_cross_study_batch_correction_is_prohibited(self):
        payload = deepcopy(to_plain(self.by_id["SYN-B:citrate"]))
        payload["feature_id"] = "SYN-B:citrate-joint-batch"
        payload["assay"]["batch"]["batch_count"] = 2
        payload["assay"]["batch"]["batch_id_variable"] = "joint_batch"
        payload["assay"]["batch"]["correction_scope"] = "cross_study"
        joint = MetaboliteAssayRecord.model_validate(payload)

        decision = evaluate_assay_pair(self.by_id["SYN-A:citrate"], joint)
        self.assertEqual(_value(decision.qa_qc_status), "non_combinable")
        self.assertIn("SYN-B:citrate-joint-batch:cross_study_batch_correction", decision.blockers)
        self.assertEqual(_value(decision.permitted_analysis), "none")
        self.assertEqual(decision.transforms, [])

    def test_unknown_pair_and_duplicate_feature_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown candidate"):
            build_assay_harmonization_plan(self.records, [["SYN-A:citrate", "missing"]])
        with self.assertRaisesRegex(ValueError, "Duplicate feature_id"):
            build_assay_harmonization_plan([self.records[0], self.records[0]], [])

    def test_write_plan_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assay_plan.json"
            plan = build_assay_harmonization_plan(
                self.records, self.pairs, out_path=path
            )
            self.assertEqual(read_json(path), to_plain(plan))

    def test_artifact_writer_emits_review_gated_plan_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            first_paths = write_assay_harmonization_artifacts(FIXTURE, tmp)
            first = {key: read_json(path) for key, path in first_paths.items()}
            second_paths = write_assay_harmonization_artifacts(FIXTURE, tmp)
            second = {key: read_json(path) for key, path in second_paths.items()}

        self.assertEqual(first, second)
        self.assertEqual(len(first["accepted"]["decisions"]), 1)
        self.assertEqual(len(first["review"]["decisions"]), 1)
        self.assertEqual(len(first["non_combinable"]["decisions"]), 3)
        self.assertTrue(first["accepted"]["decisions"][0]["transforms"])
        self.assertTrue(
            all(not item["transforms"] for item in first["review"]["decisions"])
        )
        self.assertTrue(
            all(not item["transforms"] for item in first["non_combinable"]["decisions"])
        )
        self.assertEqual(len(first["audit"]["source_provenance"]), 6)
        self.assertNotIn("generated_at", first["audit"])


if __name__ == "__main__":
    unittest.main()

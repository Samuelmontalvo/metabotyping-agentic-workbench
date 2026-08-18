from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_metabolite_effect_search.py"
SPEC = importlib.util.spec_from_file_location("run_metabolite_effect_search", SCRIPT_PATH)
assert SPEC is not None
metabolite_effect_search = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = metabolite_effect_search
SPEC.loader.exec_module(metabolite_effect_search)


class MetaboliteEffectSearchTests(unittest.TestCase):
    def assert_output_contract(self, df):
        self.assertFalse(df.empty)
        for column in [
            "query_original",
            "query_type",
            "matched_term",
            "match_basis",
            "review_status",
            "decision_scope",
            "harmonization_eligibility",
            "source_system",
            "study_id",
            "accession_or_contrast",
            "sample_matrix",
            "species",
            "assay_panel",
            "analysis_stratum",
            "analysis_stratum_fields",
            "intervention_timing",
            "refmet_id",
            "refmet_annotation_match_basis",
            "refmet_annotation_source",
            "refmet_annotation_release",
            "refmet_annotation_provenance",
            "direction",
            "effect_interpretation",
            "provenance_file",
        ]:
            self.assertIn(column, df.columns)
            self.assertFalse(df[column].isna().any(), column)
            self.assertTrue(df[column].astype(str).str.len().gt(0).all(), column)

        self.assertTrue(df["provenance_file"].map(lambda p: Path(str(p)).exists()).all())
        self.assertFalse(df.loc[df["log2fc"].notna(), "direction"].eq("orientation_unknown").any())
        self.assertIn("identity_stable_identifier_supported", df.columns)
        self.assertFalse(df["identity_stable_identifier_supported"].isna().any())
        self.assertTrue(
            df["harmonization_eligibility"].eq("requires_assay_identity_review").all()
        )

    def test_leucine_metabolite_query_keeps_exact_and_review_hits_separate(self):
        df = metabolite_effect_search.run_search("Leucine", "metabolite")
        self.assert_output_contract(df)
        self.assertEqual(len(df), 35)
        self.assertEqual(df["match_basis"].value_counts().to_dict(), {
            "substring_name_match": 29,
            "exact_name_match": 6,
        })
        exact = df[df["match_basis"].eq("exact_name_match")]
        self.assertTrue(exact["review_status"].eq("requires_human_review").all())
        self.assertTrue(exact["match_confidence"].eq("exact_name_only").all())
        self.assertTrue(exact["identity_stable_identifier_supported"].eq(False).all())
        self.assertTrue(exact["refmet_id"].ne("not_available").all())
        self.assertTrue(exact["source_refmet_id"].eq("not_available").all())
        self.assertTrue(
            df.loc[df["match_basis"].eq("substring_name_match"), "review_status"]
            .eq("requires_human_review")
            .all()
        )
        self.assertTrue(
            df.loc[df["missing_evidence"].astype(str).str.contains("source_metabolite_name"), "matched_term"]
            .astype(str)
            .str.len()
            .gt(0)
            .all()
        )

    def test_leucine_metabolite_query_across_metabolomics_workbench(self):
        df = metabolite_effect_search.run_search("Leucine", "metabolite")
        mw = df[df["source_system"].eq("Metabolomics Workbench")]

        self.assertEqual(len(mw), 6)
        self.assertEqual(set(mw["study_id"]), {"ST004303"})
        self.assertEqual(mw["match_basis"].value_counts().to_dict(), {
            "substring_name_match": 5,
            "exact_name_match": 1,
        })
        self.assertEqual(mw["review_status"].value_counts().to_dict(), {
            "requires_human_review": 6,
        })
        self.assertEqual(
            int(mw["significance_call"].eq("significant_FDR<0.05").sum()),
            4,
        )

        exact = mw[mw["match_basis"].eq("exact_name_match")]
        self.assertEqual(exact["matched_term"].tolist(), ["Leucine"])
        self.assertEqual(exact["review_status"].tolist(), ["requires_human_review"])
        self.assertEqual(exact["refmet_id"].tolist(), ["RM0136379"])
        self.assertEqual(
            exact["refmet_annotation_release"].tolist(),
            [metabolite_effect_search.REFMET_ANNOT_RELEASE_FALLBACK],
        )
        self.assertIn("chemical_identity_not_identifier_supported", exact.iloc[0]["missing_evidence"])
        self.assertEqual(exact["direction"].tolist(), ["up_in_numerator"])

    def test_acylcarnitine_class_query_separates_curated_from_inferred_matches(self):
        df = metabolite_effect_search.run_search("acylcarnitine", "class")
        self.assert_output_contract(df)
        self.assertEqual(len(df), 224)
        self.assertEqual(df["match_basis"].value_counts().to_dict(), {
            "inferred_name_pattern": 179,
            "refmet_curated_class": 45,
        })
        self.assertTrue(
            df.loc[df["match_basis"].eq("refmet_curated_class"), "review_status"]
            .eq("requires_human_review")
            .all()
        )
        self.assertTrue(
            df.loc[df["match_basis"].eq("inferred_name_pattern"), "review_status"]
            .eq("requires_human_review")
            .all()
        )

    def test_unknown_metabolite_query_returns_empty_frame_without_error(self):
        df = metabolite_effect_search.run_search("zzzz_not_a_metabolite", "metabolite")
        self.assertTrue(df.empty)

    def test_source_refmet_id_can_support_identity_but_conflicts_fail_closed(self):
        leucine = metabolite_effect_search.annotate("Leucine")
        glucose = metabolite_effect_search.annotate("Glucose")
        self.assertTrue(leucine.get("refmet_id"))
        self.assertTrue(glucose.get("refmet_id"))

        base = {
            "metabolite": "Leucine",
            "refmet_name": "Leucine",
            "log2fc": 1.0,
            "p_value": 0.01,
            "fdr": 0.02,
        }
        supported = metabolite_effect_search.build_effect_record(
            r=metabolite_effect_search.pd.Series({**base, "refmet_id": leucine["refmet_id"]}),
            meta=metabolite_effect_search.EFFECT_TABLES[0],
            query="Leucine",
            qtype="metabolite",
            matched_term="Leucine",
            match_basis="exact_name_match",
            match_confidence="exact_name_only",
            review_status="requires_human_review",
        )
        self.assertEqual(supported["review_status"], "accepted_curated")
        self.assertEqual(supported["decision_scope"], "retrieval_and_annotation_match_only")
        self.assertEqual(
            supported["harmonization_eligibility"],
            "requires_assay_identity_review",
        )
        self.assertEqual(
            supported["identity_evidence_level"],
            "source_stable_identifier_assertion",
        )
        self.assertEqual(supported["match_confidence"], "curated_identifier_supported")
        self.assertTrue(supported["identity_stable_identifier_supported"])
        self.assertEqual(supported["refmet_annotation_match_basis"], "source_refmet_id")

        conflict = metabolite_effect_search.build_effect_record(
            r=metabolite_effect_search.pd.Series({**base, "refmet_id": glucose["refmet_id"]}),
            meta=metabolite_effect_search.EFFECT_TABLES[0],
            query="Leucine",
            qtype="metabolite",
            matched_term="Leucine",
            match_basis="exact_name_match",
            match_confidence="exact_name_only",
            review_status="requires_human_review",
        )
        self.assertEqual(conflict["review_status"], "requires_human_review")
        self.assertFalse(conflict["identity_stable_identifier_supported"])
        self.assertIn("source_refmet_id_name_conflict", conflict["missing_evidence"])

    def test_refmet_main_class_enrichment_uses_stratum_specific_backgrounds(self):
        df = metabolite_effect_search.run_refmet_enrichment(
            "Amino acids and peptides",
            "main_class",
        )

        self.assertGreaterEqual(len(df), 3)
        self.assertEqual(df["analysis_stratum"].nunique(), len(df))
        self.assertTrue(df["query_type"].eq("enrichment").all())
        self.assertTrue(df["refmet_level"].eq("main_class").all())
        self.assertTrue(df["refmet_label"].eq("Amino acids and peptides").all())
        self.assertTrue(df["match_basis"].eq("refmet_hierarchy_annotation").all())
        self.assertTrue(df["review_status"].eq("requires_human_review").all())
        self.assertEqual(set(df["species"]), {"Homo sapiens", "Rattus norvegicus"})
        self.assertEqual(
            set(df["study_id"]),
            {"ST004303", "human-precovid-sed-adu", "pass1b06"},
        )
        self.assertTrue(df["n_background_rows"].lt(1503).all())
        self.assertFalse(df["source_systems"].str.contains(";").any())
        self.assertFalse(df["study_ids"].str.contains(";").any())
        self.assertTrue(df["bh_test_count"].gt(1).all())
        self.assertTrue(df["fisher_exact_q"].between(0, 1).all())
        self.assertTrue(
            df["harmonization_eligibility"]
            .eq("not_applicable_do_not_harmonize_from_enrichment")
            .all()
        )
        self.assertTrue(
            df["identity_evidence_level"]
            .eq("contains_name_resolved_or_unresolved_rows")
            .all()
        )
        self.assertTrue((df["fisher_exact_q"] + 1e-15 >= df["fisher_exact_p"]).all())

    def test_refmet_all_main_class_enrichment_ranks_significant_classes(self):
        df = metabolite_effect_search.run_refmet_enrichment("all", "main_class")

        self.assertGreaterEqual(len(df), 100)
        self.assertGreaterEqual(df["analysis_stratum"].nunique(), 10)
        top = df.iloc[0]
        self.assertLess(float(top["fisher_exact_q"]), 0.05)
        self.assertEqual(top["multiple_testing_method"], "Benjamini-Hochberg")
        self.assertEqual(top["multiple_testing_scope"], "analysis_stratum")
        self.assertTrue(df["fisher_exact_q"].is_monotonic_increasing)

    def test_enrichment_never_pools_study_species_or_assay_and_adjusts_before_query_filter(self):
        rows = []
        specifications = [
            ("mw", "Metabolomics Workbench", "MW1", "Homo sapiens", "panel-mw", 4),
            ("human_motrpac", "MoTrPAC DataHub", "HUM1", "Homo sapiens", "panel-human", 6),
            ("rat_motrpac", "MoTrPAC DataHub", "RAT1", "Rattus norvegicus", "panel-rat", 8),
        ]
        for stratum, source, study, species, assay, size in specifications:
            for index in range(size):
                label = "Class A" if index < size // 2 else "Class B"
                significant = index < max(1, size // 3)
                rows.append({
                    "class": label,
                    "analysis_stratum": stratum,
                    "significance_call": "significant_FDR<0.05" if significant else "not_significant",
                    "identity_stable_identifier_supported": index % 2 == 0,
                    "direction": "up_in_numerator" if significant else "down_in_numerator",
                    "p_value": 0.001 + index / 100,
                    "matched_term": f"feature-{stratum}-{index}",
                    "refmet_id": f"RM-{stratum}-{index}",
                    "refmet_annotation_source": "RefMet",
                    "refmet_annotation_release": "synthetic-release",
                    "refmet_annotation_provenance": "synthetic-refmet.csv",
                    "source_system": source,
                    "study_id": study,
                    "species": species,
                    "sample_matrix": "plasma",
                    "assay_panel": assay,
                    "sex_or_subgroup": "all_or_not_reported",
                    "accession_or_contrast": f"contrast-{study}",
                    "provenance_file": f"{stratum}.csv",
                })
        universe = metabolite_effect_search.pd.DataFrame(rows)
        with mock.patch.object(
            metabolite_effect_search,
            "collect_effect_universe",
            return_value=universe,
        ):
            all_results = metabolite_effect_search.run_refmet_enrichment("all", "main_class")
            class_a = metabolite_effect_search.run_refmet_enrichment("Class A", "main_class")

        self.assertEqual(len(all_results), 6)
        self.assertEqual(len(class_a), 3)
        expected_backgrounds = {name: size for name, _, _, _, _, size in specifications}
        self.assertEqual(
            all_results.groupby("analysis_stratum")["n_background_rows"].first().to_dict(),
            expected_backgrounds,
        )
        self.assertTrue(all_results["bh_test_count"].eq(2).all())
        expected_q = (
            all_results[all_results["refmet_label"].eq("Class A")]
            .set_index("analysis_stratum")["fisher_exact_q"]
            .sort_index()
        )
        observed_q = class_a.set_index("analysis_stratum")["fisher_exact_q"].sort_index()
        metabolite_effect_search.pd.testing.assert_series_equal(expected_q, observed_q)

    def test_enrichment_report_states_stratum_and_bh_semantics(self):
        out = metabolite_effect_search.run_refmet_enrichment(
            "Amino acids and peptides",
            "main_class",
        ).head(2)
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                report_path = metabolite_effect_search.write_enrichment_report(
                    out,
                    "Amino acids and peptides",
                    "main_class",
                )
                report = report_path.read_text()
        finally:
            os.chdir(old_cwd)
        self.assertIn("never pooled as exchangeable observations", report)
        self.assertIn("Benjamini-Hochberg", report)
        self.assertIn("name-resolved RefMet annotation does not confirm", report)


if __name__ == "__main__":
    unittest.main()

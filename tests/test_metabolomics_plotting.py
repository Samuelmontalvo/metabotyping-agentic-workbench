import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.plotting import (
    AggregationRules,
    ContrastMetadata,
    PlotValidationError,
    TrajectoryMetadata,
    benjamini_hochberg,
    export_plot_bundle,
    prepare_all_hierarchy_views,
    prepare_effect_heatmap_data,
    prepare_hierarchy_aggregate_data,
    prepare_single_feature_effect_data,
    prepare_single_feature_trajectory_data,
    prepare_volcano_data,
    render_effect_heatmap,
    render_hierarchy_heatmap,
    render_single_feature_effect,
    render_single_feature_trajectory,
    render_volcano_plot,
    run_metabolomics_plot_workflow,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "plotting"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_contrasts() -> list[ContrastMetadata]:
    payload = json.loads((FIXTURES / "contrast_metadata.json").read_text(encoding="utf-8"))
    return [ContrastMetadata(**row) for row in payload]


class MetabolomicsPlottingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = read_csv(FIXTURES / "synthetic_effects.csv")
        cls.trajectory = read_csv(FIXTURES / "synthetic_trajectory.csv")
        cls.contrasts = load_contrasts()
        cls.by_id = {contrast.contrast_id: contrast for contrast in cls.contrasts}
        cls.expected = json.loads((FIXTURES / "expected_members.json").read_text(encoding="utf-8"))

    def test_bh_and_volcano_encode_direction_fdr_quality_and_stable_order(self):
        adjusted = benjamini_hochberg([0.01, 0.04, None, 0.03])
        rounded = [round(value, 3) if value is not None else None for value in adjusted]
        self.assertEqual(rounded, [0.03, 0.04, None, 0.04])

        contrast = self.contrasts[0]
        rows = [row for row in self.effects if row["contrast_id"] == contrast.contrast_id]
        prepared = prepare_volcano_data(rows, contrast)
        self.assertEqual(len(prepared), 6)
        self.assertEqual(prepared[0]["feature_label"], "Leucine")
        self.assertEqual(prepared[0]["selection_status"], "higher_in_numerator")
        self.assertIn("EE post 10 min higher", prepared[0]["direction_statement"])
        self.assertIn("Benjamini-Hochberg", prepared[0]["fdr_statement"])
        oleic = next(row for row in prepared if row["feature_label"] == "Oleic acid")
        self.assertIn("high_below_lod", oleic["quality_flags"])
        self.assertEqual(oleic["selection_status"], "fdr_significant_below_effect_threshold")
        self.assertEqual([row["display_order"] for row in prepared], list(range(1, 7)))

        without_fdr = [dict(row, fdr="") for row in rows]
        computed = prepare_volcano_data(without_fdr, contrast)
        self.assertTrue(
            all(row["fdr_source"] == "computed_bh_over_supplied_rows" for row in computed)
        )
        self.assertTrue(all(row["fdr_test_count"] == 6 for row in computed))

    def test_volcano_rejects_duplicate_feature_ids_within_contrast(self):
        contrast = self.contrasts[0]
        rows = [row for row in self.effects if row["contrast_id"] == contrast.contrast_id]
        with self.assertRaisesRegex(PlotValidationError, "Duplicate feature_id"):
            prepare_volcano_data(rows + [dict(rows[0])], contrast)

    def test_contrast_requires_complete_orientation_and_adjustment_scope(self):
        with self.assertRaises(PlotValidationError):
            ContrastMetadata(
                contrast_id="bad",
                numerator_label="post",
                denominator_label="post",
                effect_scale="log2 fold change",
                fdr_method="BH",
                fdr_scope="",
                source_study_id="S",
                source_dataset_id="D",
            )

    def test_cross_dataset_heatmap_gates_unreviewed_mapping_and_fills_grid(self):
        heatmap = prepare_effect_heatmap_data(self.effects, self.contrasts)
        self.assertEqual(len(heatmap), 12)
        self.assertEqual(
            [(row["feature_order"], row["contrast_order"]) for row in heatmap],
            sorted((row["feature_order"], row["contrast_order"]) for row in heatmap),
        )
        gated = next(
            row
            for row in heatmap
            if row["canonical_feature_id"] == "RM0149976"
            and row["contrast_id"] == "SYN_TRAINED_vs_BASE"
        )
        self.assertEqual(gated["cell_status"], "unreviewed_harmonization")
        self.assertIsNone(gated["heatmap_value"])
        self.assertTrue(gated["cross_dataset_view"])

        # A second source feature that resolves to the same canonical id and contrast
        # is a heatmap-cell collision; an identical feature_id is caught earlier by
        # the volcano guard, which is tested separately.
        same_canonical = dict(self.effects[0], feature_id=self.effects[0]["feature_id"] + "_alt")
        duplicate = self.effects + [same_canonical]
        with self.assertRaisesRegex(PlotValidationError, "Duplicate heatmap cell"):
            prepare_effect_heatmap_data(duplicate, self.contrasts)

        legacy_name_only = [dict(row) for row in self.effects]
        legacy_name_only[0]["mapping_status"] = "accepted_exact"
        legacy_heatmap = prepare_effect_heatmap_data(legacy_name_only, self.contrasts)
        legacy_cell = next(
            row
            for row in legacy_heatmap
            if row["canonical_feature_id"] == legacy_name_only[0]["canonical_feature_id"]
            and row["contrast_id"] == legacy_name_only[0]["contrast_id"]
        )
        self.assertEqual(legacy_cell["cell_status"], "unreviewed_harmonization")
        self.assertIsNone(legacy_cell["heatmap_value"])

    def test_heatmap_refuses_mixed_effect_scales(self):
        # Derived statements are not constructor fields.
        payload = self.contrasts[1].to_dict()
        payload.pop("direction_statement")
        payload.pop("fdr_statement")
        payload["effect_scale"] = "standardized mean difference"
        mixed = ContrastMetadata(**payload)
        with self.assertRaisesRegex(PlotValidationError, "mix effect scales"):
            prepare_effect_heatmap_data(self.effects, [self.contrasts[0], mixed])

    def test_single_feature_trajectory_has_explicit_missing_and_lod_denominators(self):
        metadata = TrajectoryMetadata(
            feature_id="RM0136379",
            value_scale="synthetic concentration (µmol/L)",
            timepoint_order=("pre_exercise", "post_10_min", "post_24_hr"),
            group_order=("EE", "RE"),
            source_study_id="SYN-MOTRPAC",
            source_dataset_id="SYN-MOTRPAC-A",
        )
        prepared = prepare_single_feature_trajectory_data(self.trajectory, metadata)
        self.assertEqual(len(prepared), 6)
        ee_24 = next(
            row
            for row in prepared
            if row["exercise_group"] == "EE" and row["timepoint"] == "post_24_hr"
        )
        self.assertEqual(ee_24["n_input_rows"], 3)
        self.assertEqual(ee_24["n_missing"], 1)
        self.assertAlmostEqual(ee_24["missing_fraction"], 1 / 3)
        self.assertIn("high_missingness", ee_24["quality_flags"])
        re_10 = next(
            row
            for row in prepared
            if row["exercise_group"] == "RE" and row["timepoint"] == "post_10_min"
        )
        self.assertEqual(re_10["n_below_lod"], 1)
        self.assertEqual(re_10["n_observed"], 2)
        self.assertAlmostEqual(re_10["mean"], 1.95)
        self.assertIn("high_below_lod", re_10["quality_flags"])
        self.assertIn("explicit input rows", re_10["missingness_denominator"])

        duplicate = self.trajectory + [dict(self.trajectory[0])]
        with self.assertRaisesRegex(PlotValidationError, "Duplicate participant"):
            prepare_single_feature_trajectory_data(duplicate, metadata)

    def test_hierarchy_views_use_refmet_names_coverage_and_descriptive_semantics(self):
        views = prepare_all_hierarchy_views(
            self.effects,
            self.contrasts,
            expected_members=self.expected,
            rules=AggregationRules(min_features=3, min_coverage=0.75),
        )
        self.assertEqual(set(views), {"pathway", "sub_class", "main_class", "super_class"})
        organic = next(
            row
            for row in views["super_class"]
            if row["category"] == "Organic acids"
            and row["contrast_id"] == "SYN_EE_POST10_vs_PRE"
        )
        self.assertEqual(organic["aggregate_status"], "eligible_descriptive_summary")
        self.assertEqual(organic["observed_feature_count"], 3)
        self.assertEqual(organic["expected_feature_count"], 3)
        self.assertEqual(organic["coverage_fraction"], 1.0)
        self.assertIn("not the RefMet over-representation", organic["aggregate_inference"])
        self.assertNotIn("aggregate_p_value", organic)

        fatty_training = next(
            row
            for row in views["super_class"]
            if row["category"] == "Fatty Acyls"
            and row["contrast_id"] == "SYN_TRAINED_vs_BASE"
        )
        self.assertEqual(fatty_training["aggregate_status"], "insufficient_feature_count")
        self.assertEqual(fatty_training["excluded_unreviewed_mapping_count"], 1)

        unknown_coverage = prepare_hierarchy_aggregate_data(
            self.effects,
            self.contrasts,
            "super_class",
            expected_members=None,
            rules=AggregationRules(min_features=2),
        )
        self.assertTrue(
            any(
                row["aggregate_status"] == "coverage_denominator_unknown"
                for row in unknown_coverage
            )
        )

    def test_conflicting_refmet_aliases_are_rejected(self):
        rows = [dict(row) for row in self.effects]
        rows[0]["superclass"] = "Conflicting label"
        with self.assertRaisesRegex(PlotValidationError, "Conflicting values"):
            prepare_hierarchy_aggregate_data(
                rows,
                self.contrasts,
                "super_class",
                expected_members=self.expected["super_class"],
            )

    def test_export_bundle_is_checksummed_and_deterministic(self):
        volcano = prepare_volcano_data(
            [row for row in self.effects if row["contrast_id"] == self.contrasts[0].contrast_id],
            self.contrasts[0],
        )
        heatmap = prepare_effect_heatmap_data(self.effects, self.contrasts)
        provenance = {
            "analysis_id": "synthetic-plot-contract-test",
            "input_artifacts": [
                {"path": "tests/fixtures/plotting/synthetic_effects.csv", "synthetic": True}
            ],
            "synthetic_data": True,
            "software_version": "0.1.0-test",
            "notes": ["No biological interpretation."],
        }
        with tempfile.TemporaryDirectory() as tmp:
            first = export_plot_bundle(
                {"volcano": volcano, "heatmap": heatmap}, Path(tmp) / "a", provenance
            )
            second = export_plot_bundle(
                {"volcano": volcano, "heatmap": heatmap}, Path(tmp) / "b", provenance
            )
            self.assertEqual(first["volcano"].read_bytes(), second["volcano"].read_bytes())
            self.assertEqual(first["manifest"].read_bytes(), second["manifest"].read_bytes())
            manifest = json.loads(first["manifest"].read_text(encoding="utf-8"))
            self.assertTrue(manifest["synthetic_data"])
            self.assertEqual(manifest["artifacts"]["volcano"]["row_count"], 6)
            self.assertEqual(len(manifest["artifacts"]["volcano"]["sha256"]), 64)
            self.assertNotIn("generated_at", manifest)

    def test_complete_workflow_exports_all_plot_ready_views_without_renderer(self):
        provenance = {
            "analysis_id": "synthetic-complete-workflow",
            "input_artifacts": [
                {"path": "tests/fixtures/plotting/synthetic_effects.csv", "synthetic": True}
            ],
            "synthetic_data": True,
            "software_version": "0.1.0-test",
        }
        trajectory_metadata = TrajectoryMetadata(
            feature_id="RM0136379",
            value_scale="synthetic concentration (µmol/L)",
            timepoint_order=("pre_exercise", "post_10_min", "post_24_hr"),
            group_order=("EE", "RE"),
            source_study_id="SYN-MOTRPAC",
            source_dataset_id="SYN-MOTRPAC-A",
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = run_metabolomics_plot_workflow(
                self.effects,
                self.contrasts,
                tmp,
                provenance,
                expected_members=self.expected,
                single_feature_id="RM0136379",
                trajectory_observations=self.trajectory,
                trajectory_metadata=trajectory_metadata,
                render=False,
            )
            expected_names = {
                "effect_heatmap",
                "hierarchy_pathway",
                "hierarchy_sub_class",
                "hierarchy_main_class",
                "hierarchy_super_class",
                "single_effect_rm0136379",
                "trajectory_rm0136379",
                "manifest",
            }
            self.assertTrue(expected_names.issubset(paths))
            self.assertTrue(all(paths[name].stat().st_size > 0 for name in expected_names))

    @unittest.skipUnless(
        importlib.util.find_spec("matplotlib") and importlib.util.find_spec("numpy"),
        "optional matplotlib/numpy rendering stack is unavailable",
    )
    def test_all_renderers_produce_nonempty_synthetic_smoke_outputs(self):
        volcano = prepare_volcano_data(
            [row for row in self.effects if row["contrast_id"] == self.contrasts[0].contrast_id],
            self.contrasts[0],
        )
        heatmap = prepare_effect_heatmap_data(self.effects, self.contrasts)
        single_effect = prepare_single_feature_effect_data(
            self.effects, self.contrasts, "RM0136379"
        )
        trajectory_metadata = TrajectoryMetadata(
            feature_id="RM0136379",
            value_scale="synthetic concentration (µmol/L)",
            timepoint_order=("pre_exercise", "post_10_min", "post_24_hr"),
            group_order=("EE", "RE"),
            source_study_id="SYN-MOTRPAC",
            source_dataset_id="SYN-MOTRPAC-A",
        )
        trajectory = prepare_single_feature_trajectory_data(self.trajectory, trajectory_metadata)
        hierarchy = prepare_hierarchy_aggregate_data(
            self.effects,
            self.contrasts,
            "super_class",
            expected_members=self.expected["super_class"],
            rules=AggregationRules(min_features=3, min_coverage=0.75),
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            outputs = [
                render_volcano_plot(volcano, self.contrasts[0], tmp_path / "volcano.png"),
                render_effect_heatmap(heatmap, tmp_path / "heatmap.png"),
                render_single_feature_effect(single_effect, tmp_path / "single_effect.png"),
                render_single_feature_trajectory(trajectory, tmp_path / "trajectory.png"),
                render_hierarchy_heatmap(hierarchy, tmp_path / "super_class.png"),
            ]
            self.assertTrue(all(path.exists() and path.stat().st_size > 1000 for path in outputs))


if __name__ == "__main__":
    unittest.main()

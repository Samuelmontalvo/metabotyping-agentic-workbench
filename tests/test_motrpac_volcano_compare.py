import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.cli import main
from metabotyping_agentic.live_sources.motrpac_volcano_compare import (
    ambiguous_feature_key_count,
    bh_adjust,
    classify_mw_timepoint,
    compute_mw_volcano_stats,
    derive_motrpac_between_group_contrasts,
    discover_motrpac_da_objects_from_bundle,
    fetch_motrpac_volcano_stats,
    is_motrpac_acute_pre_contrast,
    normalize_motrpac_omics_assay_filter,
    normalize_motrpac_scope,
    parse_motrpac_contrast_plot_metadata,
    parse_motrpac_da_tsv,
    parse_motrpac_group_contrast_filter,
    parse_motrpac_object_metadata,
    parse_mw_factor_plot_metadata,
    prepare_motrpac_plot_rows,
    rank_similarity,
)

FEATURES = ["Alanine", "Citrulline", "Glucose", "Lactate", "Succinate", "Fumarate"]


def fixture_factors():
    rows = {}
    index = 1
    for participant in ["P1", "P2", "P3"]:
        for suffix, factor in [("B", "Group:Pre"), ("R2", "Group:Time 0"), ("R3", "Group:Time 60")]:
            rows[str(index)] = {
                "local_sample_id": f"{participant}_{suffix}",
                "sample_source": "Blood (plasma)",
                "factors": factor,
            }
            index += 1
    return rows


def fixture_mw_data():
    rows = {}
    for index, feature in enumerate(FEATURES, start=1):
        base = 100.0 + index * 10.0
        rows[str(index)] = {
            "study_id": "ST001789",
            "analysis_id": "AN1",
            "analysis_summary": "Test LC-MS",
            "metabolite_name": feature,
            "metabolite_id": f"ME{index}",
            "refmet_name": feature,
            "units": "peak area",
            "DATA": {
                "P1_B": str(base),
                "P1_R2": str(base * (1.2 + index * 0.01)),
                "P1_R3": str(base * (1.1 + index * 0.01)),
                "P2_B": str(base + 10),
                "P2_R2": str((base + 10) * (1.2 + index * 0.01)),
                "P2_R3": str((base + 10) * (1.1 + index * 0.01)),
                "P3_B": str(base + 20),
                "P3_R2": str((base + 20) * (1.2 + index * 0.01)),
                "P3_R3": None if feature == "Fumarate" else str((base + 20) * (1.1 + index * 0.01)),
            },
        }
    return rows


def fixture_mw_time_factor_records():
    rows = {}
    index = 1
    for subject in ["S1", "S2", "S3"]:
        for sample_number, timepoint in [("01", "1P"), ("02", "2P"), ("03", "4P")]:
            rows[str(index)] = {
                "local_sample_id": f"sample_{subject}_{sample_number}",
                "sample_source": "Blood",
                "factors": f"Sample source:Blood | Treatment:MIE | Time:{timepoint} | Subject:{subject}",
            }
            index += 1
    return rows


def fixture_mw_time_factor_data():
    rows = {}
    for index, feature in enumerate(FEATURES, start=1):
        base = 50.0 + index
        data = {}
        for subject_i, subject in enumerate(["S1", "S2", "S3"], start=1):
            pre = base + subject_i
            data[f"sample_{subject}_01"] = str(pre)
            data[f"sample_{subject}_02"] = str(pre * (1.05 + index * 0.01))
            data[f"sample_{subject}_03"] = str(pre * (1.12 + index * 0.01))
        rows[str(index)] = {
            "study_id": "ST004303",
            "analysis_id": "AN1",
            "analysis_summary": "Test LC-MS",
            "metabolite_name": feature,
            "metabolite_id": f"ME{index}",
            "refmet_name": feature,
            "DATA": data,
        }
    return rows


def fixture_da_text():
    lines = [
        "assay\tfeature_id\tlogFC\tp_value\tadj_p_value\tcontrast",
    ]
    for index, feature in enumerate(FEATURES, start=1):
        lines.append(
            "\t".join(
                [
                    "metab-t-amines",
                    feature,
                    str(0.12 + index * 0.01),
                    str(0.001 * index),
                    str(0.01 * index),
                    "group_timepointADUResist.post_10_min - group_timepointADUResist.pre_exercise",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def fixture_da_text_all_groups(row_assay: str = "metab-t-amines"):
    lines = [
        "assay\tfeature_id\tlogFC\tp_value\tadj_p_value\tcontrast",
    ]
    group_terms = {
        "EE": ("ADUEndur", 0.30),
        "RE": ("ADUResist", 0.20),
        "CON": ("ADUControl", 0.05),
    }
    for group_index, (_group_token, (motrpac_token, base_logfc)) in enumerate(group_terms.items(), start=1):
        for feature_index, feature in enumerate(FEATURES, start=1):
            lines.append(
                "\t".join(
                    [
                        row_assay,
                        feature,
                        str(base_logfc + feature_index * 0.01),
                        str(0.001 * feature_index * group_index),
                        str(0.01 * feature_index * group_index),
                        f"group_timepoint{motrpac_token}.post_10_min - group_timepoint{motrpac_token}.pre_exercise",
                    ]
                )
            )
    return "\n".join(lines) + "\n"


class MotrpacVolcanoCompareTests(unittest.TestCase):
    TARGETED_OBJECT = (
        "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/"
        "human-precovid-sed-adu_t02-plasma_metab-t-amines_da_dream-acute_v1.3.txt"
    )
    UNTARGETED_OBJECT = (
        "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/"
        "human-precovid-sed-adu_t02-plasma_metab-u-lrppos_da_dream-acute_v1.3.txt"
    )
    MUSCLE_OBJECT = (
        "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/"
        "human-precovid-sed-adu_t10-muscle_metab-t-tca_da_dream-acute_v1.3.txt"
    )

    def test_plot_metadata_parsing_is_explicit_and_conservative(self):
        motrpac_metadata = parse_motrpac_contrast_plot_metadata(
            "group_timepointADUResist.post_10_min - group_timepointADUResist.pre_exercise"
        )
        self.assertEqual(motrpac_metadata["exercise_group"], "RE")
        self.assertEqual(motrpac_metadata["timepoint"], "post_10_min")
        self.assertEqual(motrpac_metadata["palette_source"], "motrpac-contrast")

        during_metadata = parse_motrpac_contrast_plot_metadata(
            "group_timepointADUEndur.during_20_min - group_timepointADUEndur.pre_exercise"
        )
        self.assertEqual(during_metadata["exercise_group"], "EE")
        self.assertEqual(during_metadata["timepoint"], "during_20_min")
        self.assertTrue(
            is_motrpac_acute_pre_contrast(
                "group_timepointADUEndur.during_20_min - group_timepointADUEndur.pre_exercise"
            )
        )
        self.assertFalse(is_motrpac_acute_pre_contrast("group_timepointADUEndur.post_10_min - unrelated"))

        mw_metadata = parse_mw_factor_plot_metadata(
            {"factors": "Treatment:Endurance | Sex:Female | Group:Time 60"}
        )
        self.assertEqual(mw_metadata["exercise_group"], "EE")
        self.assertEqual(mw_metadata["sex"], "female")
        self.assertEqual(mw_metadata["palette_source"], "mw-explicit-factors")

        neutral_mw = parse_mw_factor_plot_metadata({"factors": "Group:Time 60"})
        self.assertEqual(neutral_mw["exercise_group"], "")
        self.assertEqual(neutral_mw["sex"], "")
        self.assertEqual(neutral_mw["palette_source"], "")

    def test_r_helper_declares_motrpac_palette_aliases(self):
        helper_path = (
            Path(__file__).resolve().parents[1]
            / "src/metabotyping_agentic/plotting/motrpac_plot_helpers.R"
        )
        helper_text = helper_path.read_text(encoding="utf-8")
        for expected in [
            'EE = "#d95f02"',
            'ADUEndur = "#d95f02"',
            'RE = "#1b9e77"',
            'ADUResist = "#1b9e77"',
            'CON = "#7570b3"',
            'ADUControl = "#7570b3"',
            'male = "#5555ff"',
            'female = "#f95c6f"',
        ]:
            self.assertIn(expected, helper_text)

    def test_r_helper_palette_function_when_rscript_is_available(self):
        rscript = shutil.which("Rscript")
        if not rscript:
            self.skipTest("Rscript is not available")
        helper_path = (
            Path(__file__).resolve().parents[1]
            / "src/metabotyping_agentic/plotting/motrpac_plot_helpers.R"
        )
        command = (
            f"source({str(helper_path)!r}); "
            "cat(motrpac_palette_color('exercise_group', 'EE'), "
            "motrpac_palette_color('exercise_group', 'RE'), "
            "motrpac_palette_color('exercise_group', 'CON'), "
            "motrpac_palette_color('sex', 'male'), "
            "motrpac_palette_color('sex', 'female'))"
        )
        output = subprocess.check_output([rscript, "-e", command], text=True)
        self.assertEqual(output.strip().split(), ["#d95f02", "#1b9e77", "#7570b3", "#5555ff", "#f95c6f"])

    def test_mw_timepoint_fallback_tokens_respect_boundaries(self):
        # An explicit Time factor is authoritative.
        self.assertEqual(classify_mw_timepoint("Sample source:Blood | Time:1P"), "pre")
        self.assertEqual(classify_mw_timepoint("Time:4P"), "time_4p")
        # Documented fallback conventions (ST001789-style factors and sample IDs).
        self.assertEqual(classify_mw_timepoint("Group:Pre"), "pre")
        self.assertEqual(classify_mw_timepoint("Group:Time 0"), "time_0")
        self.assertEqual(classify_mw_timepoint("Group:Time 60"), "time_60")
        self.assertEqual(classify_mw_timepoint("Collection:pre_exercise"), "pre")
        self.assertEqual(classify_mw_timepoint("P1_B"), "pre")
        self.assertEqual(classify_mw_timepoint("P1_R2"), "time_0")
        self.assertEqual(classify_mw_timepoint("P1_R3"), "time_60")
        # Substrings that previously produced a timepoint the study never declared.
        for text in [
            "Diagnosis:prediabetes",
            "Treatment:prednisone",
            "Sample source:Blood | Group:Control",
            "Pressure:high",
            "CTR2_01",
            "Group:R30",
            "Time 05 min",
            "",
        ]:
            with self.subTest(text=text):
                self.assertEqual(classify_mw_timepoint(text), "unknown")

    def test_mw_paired_stats_and_bh_adjustment(self):
        rows = compute_mw_volcano_stats(_records(fixture_mw_data()), _records(fixture_factors()))
        self.assertEqual({row["contrast_key"] for row in rows}, {"MW_Time_0_vs_Pre", "MW_Time_60_vs_Pre"})
        self.assertEqual(len(rows), 12)
        self.assertTrue(all("exercise_group" in row for row in rows))
        self.assertTrue(all("sex" in row for row in rows))
        self.assertTrue(all("timepoint" in row for row in rows))
        self.assertTrue(all("palette_source" in row for row in rows))
        fumarate_time_60 = [
            row for row in rows if row["feature_label"] == "Fumarate" and row["contrast_key"] == "MW_Time_60_vs_Pre"
        ][0]
        self.assertEqual(fumarate_time_60["n_pairs"], 2)
        self.assertTrue(0 < float(fumarate_time_60["adj_p_value"]) <= 1)

        adjusted = bh_adjust([0.01, 0.04, 0.03])
        self.assertEqual([round(value, 3) for value in adjusted], [0.03, 0.04, 0.04])

    def test_mw_time_factor_pairs_generate_all_post_vs_pre_contrasts(self):
        rows = compute_mw_volcano_stats(
            _records(fixture_mw_time_factor_data()),
            _records(fixture_mw_time_factor_records()),
        )

        self.assertEqual({row["contrast_key"] for row in rows}, {"MW_2P_vs_Pre", "MW_4P_vs_Pre"})
        self.assertEqual({row["timepoint"] for row in rows}, {"time_2p", "time_4p"})
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row["n_pairs"] == 3 for row in rows))

    def test_motrpac_bundle_discovery_requires_external_release(self):
        bundle = (
            'const key="AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE";'
            f'{{object_size:123,external_release:!0,object:"{self.TARGETED_OBJECT}",phase:"HUMAN"}},'
            f'{{object_size:456,external_release:!1,object:"{self.MUSCLE_OBJECT}",phase:"HUMAN"}}'
        )
        objects = discover_motrpac_da_objects_from_bundle(bundle)
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]["tissue"], "t02-plasma")
        self.assertEqual(objects[0]["assay"], "metab-t-amines")

    def test_motrpac_scope_defaults_to_blood_plasma_and_can_include_all_tissues(self):
        self.assertEqual(normalize_motrpac_scope("plasma"), "blood-plasma")
        self.assertEqual(normalize_motrpac_scope("all_tissues"), "all-tissues")
        with tempfile.TemporaryDirectory() as tmp:
            da_dir = Path(tmp)
            (da_dir / "human-precovid-sed-adu_t02-plasma_metab-t-amines_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text(),
                encoding="utf-8",
            )
            (da_dir / "human-precovid-sed-adu_t10-muscle_metab-t-tca_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text(),
                encoding="utf-8",
            )

            default_rows, default_objects = fetch_motrpac_volcano_stats(local_da_dir=da_dir)
            self.assertEqual({item["tissue"] for item in default_objects}, {"t02-plasma"})
            self.assertEqual({row["tissue"] for row in default_rows}, {"t02-plasma"})

            all_rows, all_objects = fetch_motrpac_volcano_stats(local_da_dir=da_dir, scope="all-tissues")
            self.assertEqual({item["tissue"] for item in all_objects}, {"t02-plasma", "t10-muscle"})
            self.assertEqual({row["tissue"] for row in all_rows}, {"t02-plasma", "t10-muscle"})

    def test_motrpac_omics_assay_and_group_contrast_filters(self):
        self.assertEqual(normalize_motrpac_omics_assay_filter("metabolomics_untargeted"), "untargeted")
        self.assertEqual(parse_motrpac_group_contrast_filter("EE-CON,RE-CON"), ("EE-CON", "RE-CON"))
        with tempfile.TemporaryDirectory() as tmp:
            da_dir = Path(tmp)
            (da_dir / "human-precovid-sed-adu_t02-plasma_metab-t-amines_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text_all_groups(),
                encoding="utf-8",
            )
            (da_dir / "human-precovid-sed-adu_t02-plasma_metab-u-lrppos_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text_all_groups("metab-u-lrppos"),
                encoding="utf-8",
            )

            rows, objects = fetch_motrpac_volcano_stats(local_da_dir=da_dir, omics_assay_filter="untargeted")
            self.assertEqual({item["omics_assay"] for item in objects}, {"untargeted"})
            self.assertEqual({row["omics_assay"] for row in rows}, {"untargeted"})
            derived_rows = prepare_motrpac_plot_rows(rows)
            filtered = [row for row in derived_rows if row["group_contrast"] in {"EE-CON", "RE-CON"}]
            self.assertEqual({row["group_contrast"] for row in filtered}, {"EE-CON", "RE-CON"})
            self.assertNotIn("EE-RE", {row["group_contrast"] for row in filtered})

    def test_motrpac_object_metadata_normalizes_metabolomics_assay_layer(self):
        metadata = parse_motrpac_object_metadata(self.TARGETED_OBJECT)
        self.assertEqual(metadata["omics"], "metabolomics")
        self.assertEqual(metadata["omics_assay"], "targeted")
        self.assertEqual(metadata["raw_omics"], "metabolomics-targeted")
        self.assertEqual(metadata["assay_label"], "metabolomics-metab-t-amines")

        untargeted_metadata = parse_motrpac_object_metadata(self.UNTARGETED_OBJECT)
        self.assertEqual(untargeted_metadata["omics"], "metabolomics")
        self.assertEqual(untargeted_metadata["omics_assay"], "untargeted")
        self.assertEqual(untargeted_metadata["assay_label"], "metabolomics-metab-u-lrppos")

    def test_motrpac_da_parser_and_similarity_ranking(self):
        metadata = {
            "object": self.TARGETED_OBJECT,
            "release": "human-precovid-sed-adu",
            "omics": "metabolomics",
            "omics_assay": "targeted",
            "raw_omics": "metabolomics-targeted",
            "tissue": "t02-plasma",
            "assay": "metab-t-amines",
            "assay_label": "metabolomics-metab-t-amines",
            "method": "dream",
        }
        motrpac_rows = parse_motrpac_da_tsv(fixture_da_text(), metadata)
        self.assertEqual(len(motrpac_rows), 6)
        self.assertEqual({row["omics"] for row in motrpac_rows}, {"metabolomics"})
        self.assertEqual({row["omics_assay"] for row in motrpac_rows}, {"targeted"})
        self.assertEqual({row["exercise_group"] for row in motrpac_rows}, {"RE"})
        self.assertEqual({row["timepoint"] for row in motrpac_rows}, {"post_10_min"})
        self.assertEqual({row["palette_source"] for row in motrpac_rows}, {"motrpac-contrast"})

        mw_rows = compute_mw_volcano_stats(_records(fixture_mw_data()), _records(fixture_factors()))
        comparisons = rank_similarity(mw_rows, motrpac_rows)
        self.assertGreaterEqual(len(comparisons), 1)
        self.assertGreaterEqual(int(comparisons[0]["overlap_n"]), 5)

    def test_similarity_excludes_duplicate_normalized_feature_keys(self):
        mw_rows = [
            {
                "contrast_key": "mw-contrast",
                "contrast": "Post - Pre",
                "feature_key": "shared",
                "logFC": 1.0,
            },
            {
                "contrast_key": "mw-contrast",
                "contrast": "Post - Pre",
                "feature_key": "ambiguous",
                "logFC": 100.0,
            },
            {
                "contrast_key": "mw-contrast",
                "contrast": "Post - Pre",
                "feature_key": "ambiguous",
                "logFC": -100.0,
            },
        ]
        motrpac_rows = [
            {
                "contrast_key": "motrpac-contrast",
                "contrast": "EE post - pre",
                "feature_key": "shared",
                "logFC": 1.0,
                "tissue": "t02-plasma",
                "assay": "metab-t-amines",
                "omics": "metabolomics",
            },
            {
                "contrast_key": "motrpac-contrast",
                "contrast": "EE post - pre",
                "feature_key": "ambiguous",
                "logFC": 1.0,
                "tissue": "t02-plasma",
                "assay": "metab-t-amines",
                "omics": "metabolomics",
            },
        ]

        self.assertEqual(ambiguous_feature_key_count(mw_rows), 1)
        comparisons = rank_similarity(mw_rows, motrpac_rows, min_overlap=1)

        self.assertEqual(len(comparisons), 1)
        comparison = comparisons[0]
        self.assertEqual(comparison["overlap_n"], 1)
        self.assertEqual(comparison["overlap_feature_keys"], "shared")
        self.assertEqual(comparison["mw_ambiguous_feature_key_n"], 1)
        self.assertEqual(comparison["motrpac_ambiguous_feature_key_n"], 0)
        self.assertEqual(comparison["excluded_ambiguous_overlap_n"], 1)
        self.assertEqual(comparison["excluded_ambiguous_overlap_feature_keys"], "ambiguous")

        only_ambiguous = rank_similarity(mw_rows[1:], motrpac_rows[1:], min_overlap=1)
        self.assertEqual(only_ambiguous, [])

    def test_motrpac_between_group_contrast_derivation(self):
        metadata = parse_motrpac_object_metadata(self.TARGETED_OBJECT)
        metadata["object"] = self.TARGETED_OBJECT
        source_rows = parse_motrpac_da_tsv(fixture_da_text_all_groups(), metadata)
        derived_rows = derive_motrpac_between_group_contrasts(source_rows)

        self.assertEqual(len(source_rows), 18)
        self.assertEqual(len(derived_rows), 18)
        self.assertEqual({row["group_contrast"] for row in derived_rows}, {"EE-CON", "RE-CON", "EE-RE"})
        self.assertTrue(
            all(row["contrast_family"] == "derived_between_group_from_pre_exercise_logFC" for row in derived_rows)
        )
        self.assertTrue(all(row["exercise_group"] == "" for row in derived_rows))
        self.assertTrue(all(row["omics"] == "metabolomics" for row in derived_rows))

        alanine_ee_con = [
            row for row in derived_rows if row["feature_label"] == "Alanine" and row["group_contrast"] == "EE-CON"
        ][0]
        self.assertAlmostEqual(float(alanine_ee_con["logFC"]), 0.25)
        self.assertEqual(
            alanine_ee_con["p_value_source"],
            "max_component_pre_exercise_summary_p_value_not_between_group_inference",
        )
        self.assertEqual(prepare_motrpac_plot_rows(source_rows)[0]["contrast_family"], "derived_between_group_from_pre_exercise_logFC")
        self.assertEqual(prepare_motrpac_plot_rows(source_rows, "acute-pre")[0]["contrast_family"], "acute_pre_exercise")

    def test_cli_smoke_with_local_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mw_data_path = tmp_path / "mw_data.json"
            mw_factors_path = tmp_path / "mw_factors.json"
            da_dir = tmp_path / "motrpac_da"
            out_dir = tmp_path / "out"
            da_dir.mkdir()
            mw_data_path.write_text(json.dumps(fixture_mw_data()), encoding="utf-8")
            mw_factors_path.write_text(json.dumps(fixture_factors()), encoding="utf-8")
            (da_dir / "human-precovid-sed-adu_t02-plasma_metab-t-amines_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text(),
                encoding="utf-8",
            )
            (da_dir / "human-precovid-sed-adu_t10-muscle_metab-t-tca_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text(),
                encoding="utf-8",
            )

            main(
                [
                    "live-compare-mw-motrpac-volcano",
                    "--mw-data-json",
                    str(mw_data_path),
                    "--mw-factors-json",
                    str(mw_factors_path),
                    "--motrpac-da-dir",
                    str(da_dir),
                    "--out",
                    str(out_dir),
                    "--skip-plots",
                ]
            )

            self.assertTrue((out_dir / "normalized/mw_volcano_stats.csv").exists())
            self.assertTrue((out_dir / "normalized/motrpac_volcano_stats.csv").exists())
            self.assertTrue((out_dir / "normalized/comparison_similarity.csv").exists())
            self.assertTrue((out_dir / "comparison_report.md").exists())
            report = (out_dir / "comparison_report.md").read_text(encoding="utf-8")
            self.assertIn("ambiguous normalized feature keys excluded from similarity", report)
            mw_header = (out_dir / "normalized/mw_volcano_stats.csv").read_text(encoding="utf-8").splitlines()[0]
            motrpac_header = (
                out_dir / "normalized/motrpac_volcano_stats.csv"
            ).read_text(encoding="utf-8").splitlines()[0]
            motrpac_rows = (out_dir / "normalized/motrpac_volcano_stats.csv").read_text(encoding="utf-8")
            for column in ["timepoint", "exercise_group", "sex", "palette_source"]:
                self.assertIn(column, mw_header)
                self.assertIn(column, motrpac_header)
            for column in ["omics_assay", "assay_label", "contrast_family", "group_contrast", "p_value_source"]:
                self.assertIn(column, motrpac_header)
            self.assertTrue((out_dir / "normalized/motrpac_pre_exercise_volcano_stats.csv").exists())
            self.assertIn("t02-plasma", motrpac_rows)
            self.assertNotIn("t10-muscle", motrpac_rows)

    def test_cli_fixture_plot_rendering_when_rscript_is_available(self):
        if not shutil.which("Rscript"):
            self.skipTest("Rscript is not available")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mw_data_path = tmp_path / "mw_data.json"
            mw_factors_path = tmp_path / "mw_factors.json"
            da_dir = tmp_path / "motrpac_da"
            out_dir = tmp_path / "out"
            da_dir.mkdir()
            mw_data_path.write_text(json.dumps(fixture_mw_data()), encoding="utf-8")
            mw_factors_path.write_text(json.dumps(fixture_factors()), encoding="utf-8")
            (da_dir / "human-precovid-sed-adu_t02-plasma_metab-t-amines_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text(),
                encoding="utf-8",
            )
            (da_dir / "human-precovid-sed-adu_t02-plasma_metab-u-lrppos_da_dream-acute_v1.3.txt").write_text(
                fixture_da_text_all_groups("metab-u-lrppos"),
                encoding="utf-8",
            )

            main(
                [
                    "live-compare-mw-motrpac-volcano",
                    "--mw-data-json",
                    str(mw_data_path),
                    "--mw-factors-json",
                    str(mw_factors_path),
                    "--motrpac-da-dir",
                    str(da_dir),
                    "--out",
                    str(out_dir),
                    "--top-n",
                    "1",
                    "--motrpac-omics-assay",
                    "untargeted",
                    "--motrpac-group-contrasts",
                    "EE-CON,RE-CON",
                ]
            )

            self.assertTrue((out_dir / "plots/mw_all_acute_overview.png").exists())
            self.assertTrue((out_dir / "plots/motrpac_blood_plasma_overview.png").exists())
            self.assertTrue((out_dir / "plots/motrpac_all_tissues_overview.png").exists())
            self.assertTrue((out_dir / "plots/motrpac_all_timepoints_heatmap.png").exists())
            self.assertTrue((out_dir / "plots/mw_reference_vs_motrpac_EE_CON_all_timepoints_volcano.png").exists())
            self.assertTrue((out_dir / "plots/mw_reference_vs_motrpac_RE_CON_all_timepoints_volcano.png").exists())
            self.assertTrue((out_dir / "plots/side_by_side_top_01.png").exists())
            self.assertTrue((out_dir / "plots/side_by_side_top_01_heatmap.png").exists())


def _records(payload):
    return list(payload.values())


if __name__ == "__main__":
    unittest.main()

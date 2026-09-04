"""Render RefMet-super_class-colored volcano plots for exercise studies from cached live tables.

Uses ``metabotyping_agentic.plotting.metabolomics.prepare_volcano_data`` for the reviewable
FDR/direction preparation and validation, then draws a custom scatter colored by RefMet
super_class (a chemical-identity dimension, not the direction/significance palette that
``render_volcano_plot`` draws).

Rules this renderer enforces:

- One figure is one contrast in one multiple-testing family. The MoTrPAC rat table is
  sex-stratified at the source (each sex is its own timewise DA family), so it renders as two
  figures, never one. The MoTrPAC human table concatenates eleven platform DA tables whose
  ``adj_p_value`` was computed per platform, so its FDR scope is recorded as per-platform and
  the figure is labeled as an overlay of eleven families, not one study-wide adjustment.
- ``feature_id`` is the unique source feature label, never the RefMet name. Isomers, repeat
  features, and multi-platform measurements legitimately share a RefMet name; plotting them
  under one id double-counts the feature, and ``prepare_volcano_data`` now rejects it.
- Internal-standard rows (``[iSTD]``/``internal standard``) are QC features, not analytes; they
  are excluded from the biological volcano and counted in the manifest.
- RefMet super_class comes only from exact casefolded name matches in
  ``data/live/refmet_annotations.csv``; an unmatched feature is labeled
  ``unclassified_no_refmet_match``, never guessed. That file records no RefMet release.
- ST003807 is a registered repository record with no fetched statistics table in ``data/live/``;
  it is reported as a coverage gap, not plotted.

Every caveat a reader needs (arm pooling in ST004303, unverified timing interpretation, missing
retrieval provenance for the rat table) is written to ``manifest.json`` next to the figures.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from metabotyping_agentic.plotting.metabolomics import (
    ContrastMetadata,
    _load_matplotlib,
    _save_figure,
    prepare_volcano_data,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = REPO_ROOT / "data" / "live"
OUT_DIR = REPO_ROOT / "reports_live" / "exercise_studies"

REFMET_SOURCE = LIVE_DIR / "refmet_annotations.csv"
REFMET_PROVENANCE = LIVE_DIR / "refmet_annotations_provenance.json"
UNCLASSIFIED = "unclassified_no_refmet_match"
MISSING_LABELS = {"", "na", "nan", "none", "null"}

SUPER_CLASS_PALETTE_SOURCE = (
    "Matplotlib 'tab20' categorical palette assigned in stable sorted-super_class order "
    "(fixed here at render time; not a repo-wide RefMet palette object)."
)
INTERNAL_STANDARD_PATTERN = re.compile(r"internal\s*standard|\[istd\]|(?:^|_)istd(?:_|$)", re.IGNORECASE)


@dataclass(frozen=True)
class FigureSpec:
    slug: str
    source_csv: Path
    title: str
    metadata: ContrastMetadata
    stratum_column: str | None = None
    stratum_value: str | None = None
    provenance: dict = field(default_factory=dict)
    caveats: tuple[str, ...] = ()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_refmet_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    with REFMET_SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("name") or "").strip().casefold()
            super_class = (row.get("super_class") or "").strip()
            if name and super_class:
                lookup.setdefault(name, super_class)
    return lookup


def attach_super_class(rows: list[dict], refmet_lookup: dict[str, str]) -> list[dict]:
    out = []
    for row in rows:
        super_class = None
        for candidate in (row.get("refmet_name"), row.get("metabolite")):
            if not candidate or str(candidate).strip().casefold() in MISSING_LABELS:
                continue
            super_class = refmet_lookup.get(str(candidate).strip().casefold())
            if super_class:
                break
        row = dict(row)
        row["refmet_super_class"] = super_class or UNCLASSIFIED
        out.append(row)
    return out


def is_internal_standard(row: dict) -> bool:
    return any(
        INTERNAL_STANDARD_PATTERN.search(str(row.get(key) or ""))
        for key in ("metabolite", "refmet_name")
    )


def source_feature_id(row: dict) -> str:
    """Unique source identity for one row: the source label plus its RefMet name.

    Neither column alone is unique. RefMet names are shared by isomers and repeat
    features, and the MoTrPAC rat table reports one source label (for example
    ``pi(38:3)>pi(18:0_20:3)_feature2``) under two RefMet lipid names within one sex.
    The pair is unique per stratum in every cached table, and keeping both parts
    visible in the id means a reviewer can see exactly which row a point is.
    """

    metabolite = str(row.get("metabolite") or "").strip()
    refmet_name = str(row.get("refmet_name") or "").strip()
    if metabolite.casefold() in MISSING_LABELS:
        return f"{refmet_name} [source metabolite label {metabolite or 'blank'}]"
    if refmet_name and refmet_name.casefold() != metabolite.casefold():
        return f"{metabolite} [refmet: {refmet_name}]"
    return metabolite


def build_palette(super_classes: list[str]) -> dict[str, str]:
    plt, _, _ = _load_matplotlib()
    ordered = sorted(set(super_classes))
    cmap = plt.get_cmap("tab20")
    palette = {}
    for index, label in enumerate(ordered):
        if label == UNCLASSIFIED:
            palette[label] = "#999999"
        else:
            r, g, b, _ = cmap(index % 20)
            palette[label] = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
    return palette


def render(prepared: list[dict], palette: dict[str, str], title: str, footer: str, out_path: Path) -> None:
    plt, _, _ = _load_matplotlib()
    fig, axis = plt.subplots(figsize=(8.2, 6.0))
    ordered_classes = sorted(
        {row["refmet_super_class"] for row in prepared},
        key=lambda label: (label == UNCLASSIFIED, label),
    )
    for super_class in ordered_classes:
        subset = [
            row
            for row in prepared
            if row["refmet_super_class"] == super_class
            and row.get("effect") is not None
            and row.get("neg_log10_fdr") is not None
        ]
        if not subset:
            continue
        axis.scatter(
            [row["effect"] for row in subset],
            [row["neg_log10_fdr"] for row in subset],
            c=palette[super_class],
            s=26,
            alpha=0.85,
            linewidths=0.3,
            edgecolors="white",
            label=f"{super_class} (n={len(subset)})",
        )
    alpha = prepared[0]["alpha"]
    axis.axhline(-math.log10(alpha), color="#444444", linestyle="--", linewidth=0.9)
    axis.axvline(0, color="#777777", linewidth=0.7)
    axis.set_xlabel(prepared[0]["effect_scale"])
    axis.set_ylabel("-log10 FDR (as scoped in caption)")
    axis.set_title(title, fontsize=10)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E5E5", linewidth=0.6)
    axis.legend(frameon=False, fontsize=6.5, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.text(
        0.01,
        0.005,
        f"{prepared[0]['direction_statement']}. {prepared[0]['fdr_statement']}. {footer} "
        "Color = RefMet super_class by exact name match (chemical identity inference), not "
        f"FDR/direction selection. Palette: {SUPER_CLASS_PALETTE_SOURCE}",
        ha="left",
        va="bottom",
        fontsize=5.8,
        color="#333333",
        wrap=True,
    )
    fig.subplots_adjust(right=0.72, bottom=0.2)
    _save_figure(fig, out_path)
    plt.close(fig)


def write_backing_csv(prepared: list[dict], out_path: Path) -> None:
    fieldnames = [
        "feature_id",
        "refmet_name",
        "refmet_super_class",
        "effect",
        "effect_scale",
        "p_value",
        "fdr",
        "fdr_method",
        "fdr_scope",
        "fdr_source",
        "selection_status",
        "source_study_id",
        "source_dataset_id",
        "contrast_id",
        "platform",
        "sex",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in prepared:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def run_one(spec: FigureSpec, refmet_lookup: dict[str, str]) -> dict:
    with spec.source_csv.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = source_rows
    if spec.stratum_column is not None:
        rows = [row for row in rows if row.get(spec.stratum_column) == spec.stratum_value]
    internal_standards = [row for row in rows if is_internal_standard(row)]
    rows = [row for row in rows if not is_internal_standard(row)]
    for row in rows:
        row["feature_id"] = source_feature_id(row)
        row["feature_label"] = row.get("refmet_name") or row["feature_id"]

    prepared = attach_super_class(prepare_volcano_data(rows, spec.metadata), refmet_lookup)
    palette = build_palette([row["refmet_super_class"] for row in prepared])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_path = OUT_DIR / f"{spec.slug}_volcano_refmet_superclass.png"
    csv_out = OUT_DIR / f"{spec.slug}_volcano_refmet_superclass.csv"
    footer = " ".join(spec.caveats)
    render(prepared, palette, spec.title, footer, fig_path)
    write_backing_csv(prepared, csv_out)

    unmatched = sum(1 for row in prepared if row["refmet_super_class"] == UNCLASSIFIED)
    platforms = sorted({str(row.get("platform") or "") for row in prepared} - {""})
    fdr_sources = sorted({row["fdr_source"] for row in prepared})
    return {
        "slug": spec.slug,
        "source_csv": str(spec.source_csv.relative_to(REPO_ROOT)),
        "source_csv_sha256": sha256_of(spec.source_csv),
        "figure": str(fig_path.relative_to(REPO_ROOT)),
        "backing_csv": str(csv_out.relative_to(REPO_ROOT)),
        "contrast": spec.metadata.to_dict(),
        "stratum": (
            {"column": spec.stratum_column, "value": spec.stratum_value}
            if spec.stratum_column
            else None
        ),
        "n_source_rows_in_table": len(source_rows),
        "n_rows_in_stratum": len(rows) + len(internal_standards),
        "n_internal_standard_rows_excluded": len(internal_standards),
        "n_features_plotted": len(prepared),
        "n_unclassified_no_refmet_match": unmatched,
        "n_platforms_overlaid": len(platforms) if platforms else None,
        "platforms": platforms or None,
        "fdr_source": fdr_sources,
        "feature_id_rule": (
            "source label ('metabolite' column, with platform suffix where the source carries "
            "one) plus ' [refmet: <name>]' when the RefMet name differs; rows whose source label "
            "is NA use the RefMet name with an explicit '[source metabolite label NA]' tag. The "
            "(source label, RefMet name) pair is the unique per-stratum identity in every cached "
            "table; neither column alone is."
        ),
        "refmet_match_method": (
            "exact casefolded match of refmet_name, then metabolite, against the 'name' column "
            "of data/live/refmet_annotations.csv; no synonym or structure resolution"
        ),
        "provenance": spec.provenance,
        "caveats": list(spec.caveats),
    }


def figure_specs() -> list[FigureSpec]:
    st004303 = FigureSpec(
        slug="ST004303_human",
        source_csv=LIVE_DIR / "volcano_human_ST004303.csv",
        title="ST004303 human plasma — 4P vs 1P, paired on log2 abundance (MIE+SIE arms pooled)",
        metadata=ContrastMetadata(
            contrast_id="ST004303_4P_vs_1P_paired_arms_pooled",
            numerator_label="4P (later timepoint; read as post-exercise)",
            denominator_label="1P (first timepoint; read as pre-exercise)",
            effect_scale="log2fc",
            effect_column="log2fc",
            fdr_method="benjamini_hochberg",
            fdr_scope="within_study_all_266_paired_tested_features_scan_lane_bh",
            source_study_id="ST004303",
            source_dataset_id="ST004303_human_plasma_paired_ttest",
            tissue="blood",
            omics="metabolomics",
            assay="paired t-test on log2 abundance (scripts/volcano_compare.py)",
        ),
        provenance={
            "status": "recorded",
            "record": "data/live/volcano_provenance.json (human_mw block, requests list)",
            "release_date": "2025-11-12",
            "license": "CC BY 4.0",
        },
        caveats=(
            "The paired contrast pools the MIE and SIE exercise-intensity arms as retrieved; no "
            "arm-stratified estimate is shown.",
            "1P/4P are read as pre/post from the MW 'Time' factor; the timing interpretation "
            "is not verified against the study protocol.",
            "Features with fewer than three complete pairs were dropped upstream and the per-"
            "feature pair count is not carried in the cached table.",
        ),
    )
    motrpac_human = FigureSpec(
        slug="motrpac_human_endur_post",
        source_csv=LIVE_DIR / "volcano_motrpac_human_plasma_endur_post.csv",
        title="MoTrPAC human plasma — endurance post (3.5-4 h) vs pre; 11 platform DA tables overlaid",
        metadata=ContrastMetadata(
            contrast_id="motrpac_human_precovid_endur_post_3.5_4hr_vs_pre",
            numerator_label="ADU endurance post-exercise 3.5-4 h",
            denominator_label="ADU endurance pre-exercise",
            effect_scale="log2fc",
            effect_column="log2fc",
            fdr_method="benjamini_hochberg",
            fdr_scope="within_each_platform_da_table_as_released_by_motrpac_v1.3_dream_acute",
            source_study_id="MoTrPAC_human_precovid_sed_adu",
            source_dataset_id="motrpac_human_plasma_endur_post",
            tissue="blood",
            omics="metabolomics",
            platform="11 targeted and untargeted platform DA tables overlaid; see manifest",
            exercise_group="EE",
        ),
        provenance={
            "status": "recorded",
            "record": "data/live/volcano_provenance.json (motrpac block, 11 signed-url requests)",
            "release": "human-precovid-sed-adu v1.3 dream-acute DA tables",
        },
        caveats=(
            "Eleven platform DA tables are overlaid; each carries its own per-platform BH "
            "adjustment, so the y-axis is not one study-wide FDR family.",
            "The same RefMet name measured on several platforms appears once per platform "
            "(feature_id carries the platform suffix); these are separate measurements, not "
            "replicates of one identity.",
        ),
    )
    rat_specs = []
    for sex in ("female", "male"):
        rat_specs.append(
            FigureSpec(
                slug=f"motrpac_pass1b06_8w_{sex}",
                source_csv=LIVE_DIR / "volcano_motrpac_pass1b06_plasma_8w.csv",
                title=f"MoTrPAC rat pass1b-06 plasma — 8-week trained vs sedentary control, {sex}",
                metadata=ContrastMetadata(
                    contrast_id=f"motrpac_pass1b06_plasma_8w_trained_vs_sedentary_{sex}",
                    numerator_label=f"8-week endurance-trained ({sex})",
                    denominator_label=f"sex-matched sedentary control ({sex})",
                    effect_scale="log2fc",
                    effect_column="log2fc",
                    fdr_method="benjamini_hochberg",
                    fdr_scope=f"within_{sex}_stratum_pass1b06_plasma_8w_timewise_da_as_released",
                    source_study_id="MoTrPAC_pass1b06_rat",
                    source_dataset_id="motrpac_pass1b06_plasma_8w",
                    tissue="blood",
                    omics="metabolomics",
                    sex=sex,
                ),
                stratum_column="sex",
                stratum_value=sex,
                provenance={
                    "status": "retrieval_provenance_not_recorded",
                    "detail": (
                        "data/live/volcano_provenance.json covers the human mode only; the rat "
                        "table was committed in afb5eb9 (2026-08-18) with no request log. The "
                        "producing code path is scripts/volcano_compare.py::fetch_motrpac_rat_volcano "
                        "(search_public metabolomics_timewise, study pass1b06, tissue plasma, "
                        "comparison_group 8w)."
                    ),
                },
                caveats=(
                    "Rat training adaptation (8 weeks) versus sedentary control is not an acute "
                    "exercise bout and is not comparable to the human post-versus-pre contrasts.",
                    "Retrieval provenance for this table is not recorded; treat the release "
                    "version as unverified.",
                ),
            )
        )
    return [st004303, motrpac_human, *rat_specs]


def main() -> None:
    refmet_lookup = load_refmet_lookup()
    manifest = {
        "renderer": "scripts/render_exercise_studies_refmet_volcanoes.py",
        "refmet_source": {
            "path": str(REFMET_SOURCE.relative_to(REPO_ROOT)),
            "sha256": sha256_of(REFMET_SOURCE),
            "provenance_record": str(REFMET_PROVENANCE.relative_to(REPO_ROOT)),
            "release": "not_recorded",
        },
        "figure_rule": (
            "one figure = one contrast in one multiple-testing family; sex strata and platform "
            "families are never pooled into a single feature set"
        ),
        "figures": [run_one(spec, refmet_lookup) for spec in figure_specs()],
        "coverage_gaps": [
            {
                "study_id": "ST003807",
                "status": "registered_repository_record_no_fetched_stats_table",
                "note": (
                    "data/live/repository_records.csv lists ST003807 as a public exercise study "
                    "with data files present, but no volcano/differential-abundance table has been "
                    "fetched into data/live/ for it. No plot was generated; this is an availability "
                    "gap in what has been retrieved, not evidence the study lacks data."
                ),
            }
        ],
        "study_list_screening": (
            "mw_exercise_studies.csv is a keyword-retrieved candidate list with no recorded query; "
            "see mw_exercise_studies_screening.json from scripts/screen_mw_exercise_study_titles.py"
        ),
    }
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "figures"}, indent=2))
    for figure in manifest["figures"]:
        print(
            f"{figure['slug']}: plotted={figure['n_features_plotted']} "
            f"istd_excluded={figure['n_internal_standard_rows_excluded']} "
            f"unclassified={figure['n_unclassified_no_refmet_match']} fdr_source={figure['fdr_source']}"
        )


if __name__ == "__main__":
    main()

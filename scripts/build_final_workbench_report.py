#!/usr/bin/env python3
"""Build the evidence tables and compact figures for the final workbench report.

This renderer is offline. It consumes the frozen Metabolomics Workbench bulk
indexes, the local RefMet vocabulary snapshot, current workbench audit outputs,
and the cached Lac-Phe/MoTrPAC demonstrations. It never treats a reference
vocabulary entry, a feature row, or a normalized name overlap as an exact
chemical identity.
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SNAPSHOT_DIR = ROOT / "data/live/mw_corpus_snapshot"
REFMET_PATH = ROOT / "data/live/refmet_annotations.csv"
MW_EFFECT_PATH = ROOT / "data/live/volcano_human_ST004303.csv"
MOTRPAC_HUMAN_PATH = ROOT / "data/live/volcano_motrpac_human_plasma_endur_post.csv"
MOTRPAC_RAT_PATH = ROOT / "data/live/volcano_motrpac_pass1b06_plasma_8w.csv"
LACPHE_SEARCH_PATH = ROOT / "data/live/metabolite_search_lacphe/metstat_metabolite_study_hits.csv"
LACPHE_EFFECT_PATH = (
    ROOT
    / "data/live/metabolite_scan/n_lactoyl_phenylalanine/mw_queried_metabolite_effects.csv"
)
LACPHE_SAMPLE_PATH = (
    ROOT
    / "data/live/metabolite_scan/n_lactoyl_phenylalanine/mw_ST003662_queried_sample_level.csv"
)
LACPHE_FAMILY_PATH = ROOT / "reports_live/lacphe/figure_tables/f5_class_coverage.csv"
SKILL_AUDIT_PATH = ROOT / "docs/skill_evaluation_results.json"
READINESS_PATH = ROOT / "docs/scientific_readiness_results.json"
BENCHMARK_PATH = ROOT / "reports/benchmark_results.json"

OUT_DIR = ROOT / "reports_live/final_workbench_report"
DATA_DIR = OUT_DIR / "data"
FIGURE_DIR = OUT_DIR / "figures"

# Neutral report palette plus the repository's MoTrPAC metabolomics color from
# src/metabotyping_agentic/plotting/motrpac_plot_helpers.R.
SURFACE = "#fcfcfb"
INK = "#171717"
MUTED = "#5d5b57"
GRID = "#dedbd5"
MW_BLUE = "#2a78d6"
MOTRPAC_METABOLOMICS = "#6D4B08"
ACCENT = "#b2182b"
WARNING = "#d18b00"
UNCLASSIFIED = "#aaa7a1"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": GRID,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "font.size": 9.5,
    }
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def registry_context():
    from metabotyping_agentic.knowledge.source_registry import SOURCE_REGISTRY, supported_lanes

    return SOURCE_REGISTRY, supported_lanes()


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_space_case(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def normalize_comparator_key(value) -> str:
    """Match the conservative punctuation-insensitive comparator key."""

    text = normalize_space_case(value)
    if text in {"", "unknown", "not_reported", "na", "nan"}:
        return ""
    text = text.replace("α", "alpha").replace("β", "beta").replace("γ", "gamma")
    text = text.replace("Δ", "delta").replace("δ", "delta")
    key = re.sub(r"[^a-z0-9]+", "", text)
    return key if len(key) >= 3 else ""


def distribution(frame: pd.DataFrame, column: str, label: str) -> pd.DataFrame:
    counts = frame.groupby(column, dropna=False).size().sort_values(ascending=False)
    output = counts.rename("count").reset_index().rename(columns={column: label})
    output["percent"] = 100 * output["count"] / len(frame)
    return output


def style_axis(ax, grid_axis: str | None = "x") -> None:
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)


def annotate_horizontal_bars(ax, bars, values, *, suffix: str = "") -> None:
    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_width() * 1.04,
            bar.get_y() + bar.get_height() / 2,
            f"{int(value):,}{suffix}",
            va="center",
            fontsize=8,
            color=INK,
        )


def save_figure(fig, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=220, bbox_inches="tight")
    fig.savefig(FIGURE_DIR / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def build_corpus_figure(
    species: pd.DataFrame,
    assay_counts: pd.DataFrame,
    refmet_super: pd.DataFrame,
    metabolite_counts: pd.Series,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.4), constrained_layout=True)

    top_species = species.head(10).iloc[::-1]
    ax = axes[0, 0]
    bars = ax.barh(top_species["latin_name"], top_species["study_count"], color=MW_BLUE)
    annotate_horizontal_bars(ax, bars, top_species["study_count"])
    ax.set_title("A. Studies per organism label (top 10)", loc="left", fontweight="bold")
    ax.set_xlabel("unique studies carrying the label")
    ax.set_xlim(0, top_species["study_count"].max() * 1.18)
    style_axis(ax)

    assay_order = ["unclassified_or_other", "explicit_untargeted", "explicit_targeted"]
    assay_labels = {
        "unclassified_or_other": "unclassified / other",
        "explicit_untargeted": "untargeted (official index)",
        "explicit_targeted": "targeted (assay-text lower bound)",
    }
    assay_colors = [UNCLASSIFIED, MW_BLUE, WARNING]
    ordered = assay_counts.set_index("assay_scope").reindex(assay_order).fillna(0)
    ax = axes[0, 1]
    bars = ax.barh(
        [assay_labels[value] for value in assay_order],
        ordered["analysis_count"],
        color=assay_colors,
    )
    ax.set_xscale("log")
    for bar, value in zip(bars, ordered["analysis_count"], strict=True):
        ax.text(
            max(float(value) * 1.10, 1.2),
            bar.get_y() + bar.get_height() / 2,
            f"{int(value):,}",
            va="center",
            fontsize=8,
        )
    ax.set_title("B. Assay-scope evidence (log count)", loc="left", fontweight="bold")
    ax.set_xlabel("analyses; categories are evidence labels, not a forced binary")
    ax.set_xlim(1, max(ordered["analysis_count"]) * 2.1)
    style_axis(ax)

    top_super = refmet_super.head(6).copy()
    other_count = int(refmet_super.iloc[6:]["count"].sum())
    other = pd.DataFrame(
        [{"super_class": "Other 17 superclasses", "count": other_count, "percent": 0.0}]
    )
    super_plot = pd.concat([top_super, other], ignore_index=True)
    super_plot["percent"] = 100 * super_plot["count"] / super_plot["count"].sum()
    super_plot = super_plot.iloc[::-1]
    ax = axes[1, 0]
    bars = ax.barh(super_plot["super_class"], super_plot["percent"], color=MOTRPAC_METABOLOMICS)
    for bar, value in zip(bars, super_plot["percent"], strict=True):
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}%",
            va="center",
            fontsize=8,
        )
    ax.set_title("C. RefMet reference hierarchy", loc="left", fontweight="bold")
    ax.set_xlabel("share of 205,948 reference entries")
    ax.set_xlim(0, max(super_plot["percent"]) * 1.22)
    style_axis(ax)

    ax = axes[1, 1]
    positive = metabolite_counts[metabolite_counts > 0]
    bins = np.logspace(0, np.log10(max(positive.max(), 10)), 30)
    ax.hist(positive, bins=bins, color=MW_BLUE, alpha=0.9, edgecolor=SURFACE)
    ax.set_xscale("log")
    median = float(positive.median())
    ax.axvline(median, color=ACCENT, ls="--", lw=1.5)
    ax.text(median * 1.15, ax.get_ylim()[1] * 0.82, f"median {median:,.0f}", color=ACCENT)
    ax.set_title(
        "D. Reported features per analysis\nwith numeric count (n=5,420)",
        loc="left",
        fontweight="bold",
    )
    ax.set_xlabel("analysis-level feature count (log scale)")
    ax.set_ylabel("analyses")
    style_axis(ax, "y")

    fig.suptitle(
        "Metabolomics Workbench corpus and RefMet reference landscape",
        x=0.01,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.01,
        -0.018,
        textwrap.fill(
            "Counts are frozen from the public MW bulk REST indexes on 2026-08-24 UTC. "
            "RefMet entries are nomenclature records, not study-observed or MSI level-1 identities.",
            width=145,
        ),
        ha="left",
        va="top",
        fontsize=8,
        color=MUTED,
    )
    save_figure(fig, "corpus_landscape")


def build_demonstration_figure(
    overlap: dict,
    lacphe_search: pd.DataFrame,
    family: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.0), constrained_layout=True)

    ax = axes[0]
    labels = ["MoTrPAC effect rows", "normalized labels", "candidate overlaps", "unique-key gate"]
    values = [
        overlap["motrpac_effect_rows"],
        overlap["motrpac_unique_normalized_labels"],
        overlap["candidate_comparator_key_overlaps"],
        overlap["unambiguous_both_sides_overlaps"],
    ]
    bars = ax.barh(labels[::-1], values[::-1], color=[ACCENT, WARNING, MOTRPAC_METABOLOMICS, MW_BLUE])
    ax.set_xscale("log")
    for bar, value in zip(bars, values[::-1], strict=True):
        ax.text(value * 1.08, bar.get_y() + bar.get_height() / 2, f"{value:,}", va="center")
    ax.set_title("A. MW-MoTrPAC screening funnel", loc="left", fontweight="bold")
    ax.set_xlabel("counts (log scale)")
    ax.set_xlim(1, max(values) * 2.0)
    style_axis(ax)

    ax = axes[1]
    species_counts = lacphe_search.groupby("species", dropna=False).size().sort_values(ascending=False)
    top = species_counts.head(5)
    other = int(species_counts.iloc[5:].sum())
    labels = [str(value) if str(value) != "nan" else "not reported" for value in top.index]
    values = list(top.astype(int))
    if other:
        labels.append("other field values")
        values.append(other)
    bars = ax.barh(labels[::-1], values[::-1], color=MW_BLUE)
    annotate_horizontal_bars(ax, bars, values[::-1])
    ax.set_title("B. Lac-Phe search hits by species field", loc="left", fontweight="bold")
    ax.set_xlabel("study-analysis pairs (n=60)")
    ax.set_xlim(0, max(values) * 1.35)
    style_axis(ax)

    ax = axes[2]
    values = [len(family), int((family["mw_analyses_any_species"] > 0).sum()), 1, 0]
    labels = ["N-lactoyl entries", "reported in MW", "in ST003662", "in public MoTrPAC tables"]
    bars = ax.barh(labels[::-1], values[::-1], color=[UNCLASSIFIED, ACCENT, WARNING, MW_BLUE])
    for bar, value in zip(bars, values[::-1], strict=True):
        ax.text(
            max(value + 0.35, 0.35),
            bar.get_y() + bar.get_height() / 2,
            f"{value}",
            va="center",
        )
    ax.set_title("C. N-lactoyl family coverage", loc="left", fontweight="bold")
    ax.set_xlabel("RefMet labels / coverage counts")
    ax.set_xlim(0, max(values) * 1.22)
    style_axis(ax)

    fig.suptitle(
        "Demonstrations: candidate overlap narrows under review gates",
        x=0.01,
        ha="left",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.01,
        -0.025,
        textwrap.fill(
            "Overlap is normalized-label screening only. Duplicate feature keys, assay identity, matrix, "
            "scale, timing and estimand remain review gates; a missing Lac-Phe label is a coverage gap.",
            width=155,
        ),
        ha="left",
        va="top",
        fontsize=8,
        color=MUTED,
    )
    save_figure(fig, "demonstration_summary")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    corpus = read_json(SNAPSHOT_DIR / "corpus_summary.json")
    species = pd.read_csv(SNAPSHOT_DIR / "species_distribution.csv")
    analyses = pd.read_csv(SNAPSHOT_DIR / "analyses.csv")
    analysis_feature_counts = pd.read_csv(SNAPSHOT_DIR / "analysis_metabolite_counts.csv")
    refmet = pd.read_csv(REFMET_PATH, low_memory=False)
    mw = pd.read_csv(MW_EFFECT_PATH)
    motrpac_human = pd.read_csv(MOTRPAC_HUMAN_PATH)
    motrpac_rat = pd.read_csv(MOTRPAC_RAT_PATH)
    lacphe_search = pd.read_csv(LACPHE_SEARCH_PATH)
    lacphe_effects = pd.read_csv(LACPHE_EFFECT_PATH)
    lacphe_samples = pd.read_csv(LACPHE_SAMPLE_PATH)
    lacphe_family = pd.read_csv(LACPHE_FAMILY_PATH)
    skill_audit = read_json(SKILL_AUDIT_PATH)
    readiness = read_json(READINESS_PATH)
    benchmark = read_json(BENCHMARK_PATH)
    source_registry, registry_lanes = registry_context()

    if len(refmet) != refmet["refmet_id"].nunique() or len(refmet) != refmet["name"].nunique():
        raise RuntimeError("RefMet rows, IDs, and names are not one-to-one in this snapshot")
    if sum(corpus["analysis_scope_counts"].values()) != corpus["analysis_count"]:
        raise RuntimeError("Assay-scope categories do not exhaust the analysis denominator")

    refmet_super = distribution(refmet, "super_class", "super_class")
    refmet_main = distribution(refmet, "main_class", "main_class")
    refmet_sub = distribution(refmet, "sub_class", "sub_class")
    refmet_super.to_csv(DATA_DIR / "refmet_superclass_distribution.csv", index=False)
    refmet_main.to_csv(DATA_DIR / "refmet_main_class_distribution.csv", index=False)
    refmet_sub.to_csv(DATA_DIR / "refmet_subclass_distribution.csv", index=False)
    species.to_csv(DATA_DIR / "species_distribution.csv", index=False)

    assay_counts = (
        analyses.groupby("assay_scope").size().rename("analysis_count").reset_index()
    )
    assay_counts["percent_of_analyses"] = 100 * assay_counts["analysis_count"] / len(analyses)
    assay_counts.to_csv(DATA_DIR / "assay_scope_distribution.csv", index=False)

    mw_exact = {normalize_space_case(value) for value in mw["refmet_name"].dropna()}
    motrpac_exact = {
        normalize_space_case(value) for value in motrpac_human["refmet_name"].dropna()
    }
    mw_keys = [normalize_comparator_key(value) for value in mw["refmet_name"]]
    motrpac_keys = [normalize_comparator_key(value) for value in motrpac_human["refmet_name"]]
    mw_key_counts = Counter(value for value in mw_keys if value)
    motrpac_key_counts = Counter(value for value in motrpac_keys if value)
    candidate_keys = set(mw_key_counts) & set(motrpac_key_counts)
    unique_keys = {
        key
        for key in candidate_keys
        if mw_key_counts[key] == 1 and motrpac_key_counts[key] == 1
    }
    overlap = {
        "mw_effect_rows": len(mw),
        "mw_unique_normalized_labels": len(mw_exact),
        "motrpac_effect_rows": len(motrpac_human),
        "motrpac_unique_normalized_labels": len(motrpac_exact),
        "exact_case_space_label_overlaps": len(mw_exact & motrpac_exact),
        "candidate_comparator_key_overlaps": len(candidate_keys),
        "unambiguous_both_sides_overlaps": len(unique_keys),
        "ambiguous_candidate_overlaps": len(candidate_keys - unique_keys),
        "interpretation": (
            "Candidate name-key overlap only; neither effect table carries source RefMet IDs, "
            "so every overlap requires assay-identity review before harmonization or pooling."
        ),
    }
    pd.DataFrame([overlap]).to_csv(DATA_DIR / "mw_motrpac_overlap_summary.csv", index=False)

    all_effect = lacphe_effects[lacphe_effects["stratum"] == "all"].iloc[0]
    complete = lacphe_samples.dropna(subset=["value_pre", "value_post"])
    complete = complete[(complete["value_pre"] > 0) & (complete["value_post"] > 0)]
    lacphe_summary = {
        "mw_search_studies": int(lacphe_search["study_id"].nunique()),
        "mw_search_analyses": int(len(lacphe_search)),
        "mw_search_human_studies": int(
            lacphe_search.loc[lacphe_search["species"] == "Human", "study_id"].nunique()
        ),
        "mw_search_human_analyses": int((lacphe_search["species"] == "Human").sum()),
        "complete_pairs": int(all_effect["n_pairs"]),
        "participant_rows": int(len(lacphe_samples)),
        "participants_increased": int((complete["value_post"] > complete["value_pre"]).sum()),
        "log2fc": float(all_effect["log2fc"]),
        "geometric_fold": float(2 ** float(all_effect["log2fc"])),
        "mean_pre": float(all_effect["mean_pre"]),
        "mean_post": float(all_effect["mean_post"]),
        "arithmetic_mean_ratio": float(all_effect["mean_post"] / all_effect["mean_pre"]),
        "p_value": float(all_effect["p_value"]),
        "fdr": float(all_effect["fdr"]),
        "rank_of_165": 4,
        "n_lactoyl_refmet_entries": int(len(lacphe_family)),
        "n_lactoyl_entries_with_mw_hit": int(
            (lacphe_family["mw_analyses_any_species"] > 0).sum()
        ),
        "n_lactoyl_labels_in_public_motrpac_human": int(
            lacphe_family["in_motrpac_human_public_plasma"].sum()
        ),
        "n_lactoyl_labels_in_public_motrpac_rat": int(
            lacphe_family["in_motrpac_rat_pass1b06"].sum()
        ),
    }
    pd.DataFrame([lacphe_summary]).to_csv(DATA_DIR / "lacphe_summary.csv", index=False)

    benchmark_by_name = {row["metric_name"]: row for row in benchmark}
    registry_status = Counter(row.implementation_status for row in source_registry)
    capability = {
        "canonical_agent_roles": skill_audit["summary"]["paired_agent_names"],
        "logical_project_skills": skill_audit["summary"]["paired_skill_names"],
        "deprecated_agent_aliases": skill_audit["summary"][
            "paired_deprecated_agent_alias_names"
        ],
        "registry_sources": len(source_registry),
        "registry_lanes": len(registry_lanes),
        "registry_implementation_status_counts": dict(sorted(registry_status.items())),
        "synthetic_release_gate": readiness["strict_release_gate_status"],
        "synthetic_tests_passed": readiness["counts"]["passed"],
        "synthetic_tests_run": readiness["tests_run"],
        "benchmark_candidate_precision": benchmark_by_name["candidate_precision"]["value"],
        "benchmark_unsafe_auto_accept_rate": benchmark_by_name[
            "unsafe_auto_accept_rate"
        ]["value"],
        "benchmark_review_capture_rate": benchmark_by_name["review_capture_rate"]["value"],
        "benchmark_quality_score_agreement": benchmark_by_name[
            "quality_score_agreement_within_0.15"
        ]["value"],
        "validation_scope": "offline synthetic/local; not independent external validation",
    }

    refmet_metrics = {
        "reference_entries": int(len(refmet)),
        "superclasses": int(refmet["super_class"].nunique()),
        "main_classes": int(refmet["main_class"].nunique()),
        "subclasses": int(refmet["sub_class"].nunique()),
        "distinct_nonblank_formulas": int(refmet["formula"].dropna().nunique()),
        "rows_with_blank_formula": int(refmet["formula"].isna().sum()),
        "snapshot_release": "not recorded in local snapshot",
        "interpretation": "Reference nomenclature entries, not MW-observed or identity-confirmed analytes.",
    }

    rat_names = {
        normalize_space_case(value)
        for value in motrpac_rat["refmet_name"].dropna()
        if normalize_space_case(value)
    }
    human_names = {
        normalize_space_case(value)
        for value in motrpac_human["refmet_name"].dropna()
        if normalize_space_case(value)
    }
    metrics = {
        "corpus": corpus,
        "refmet": refmet_metrics,
        "mw_motrpac_overlap": overlap,
        "lacphe": lacphe_summary,
        "motrpac_cached_feature_spaces": {
            "human_effect_rows": len(motrpac_human),
            "human_unique_normalized_labels": len(human_names),
            "rat_effect_rows": len(motrpac_rat),
            "rat_unique_normalized_labels": len(rat_names),
        },
        "capability": capability,
    }
    write_json(DATA_DIR / "report_metrics.json", metrics)

    build_corpus_figure(
        species,
        assay_counts,
        refmet_super,
        pd.to_numeric(analysis_feature_counts["num_metabolites"], errors="coerce").dropna(),
    )
    build_demonstration_figure(overlap, lacphe_search, lacphe_family)
    print(f"[ok] report evidence bundle -> {OUT_DIR}")


if __name__ == "__main__":
    main()

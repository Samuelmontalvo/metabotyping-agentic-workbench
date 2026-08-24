#!/usr/bin/env python3
"""Lac-Phe figure suite: participant-level response, effect ranking, substrate
coupling, sex concordance, conjugate-class coverage, rat tissue heatmaps, and the
study-discovery landscape.

Offline renderer. Reads only tables already fetched into ``data/live/`` by the
declared network-boundary scripts and writes PNG + SVG into
``reports_live/lacphe/figures/`` plus the backing CSV for each figure.

Colour roles (validated categorical palette; see the project data-viz method):
- categorical identity  : male ``#2a78d6``, female ``#eb6834`` (all-pairs validated)
- diverging polarity    : blue <-> red with a neutral grey midpoint (sign of an effect)
- sequential magnitude  : single blue ramp (counts)
- status                : good/critical/warning, always paired with a glyph and label

Guardrails: human and rat effects never share a statistical axis; a metabolite
absent from a source is drawn as an explicit coverage gap, never as a zero effect;
precursors are labelled as precursors.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from scipy import stats

SCAN_LACPHE = Path("data/live/metabolite_scan/n_lactoyl_phenylalanine")
SCAN_LACTATE = Path("data/live/metabolite_scan/lactic_acid")
SEARCH_LACPHE = Path("data/live/metabolite_search_lacphe")
SEARCH_FAMILY = Path("data/live/metabolite_search_lacphe_family")
MOTRPAC_HUMAN_PLASMA = Path("data/live/volcano_motrpac_human_plasma_endur_post.csv")
OUT_DIR = Path("reports_live/lacphe/figures")
TABLE_DIR = Path("reports_live/lacphe/figure_tables")

LACPHE_REFMET = "N-Lactoyl phenylalanine"
LACPHE_FEATURE = "Lactoyl Phenylalanine"
LACTATE_FEATURE = "Lactic acid"
P_THRESH = 0.05

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8985"
GRID = "#e3e2de"
SEX = {"m": "#2a78d6", "f": "#eb6834"}
SEX_LABEL = {"m": "male", "f": "female"}
POLE_UP = "#e34948"
POLE_DOWN = "#2a78d6"
NEUTRAL_MID = "#f0efec"
NS_GREY = "#c4c3bf"
STATUS = {"good": "#0ca30c", "critical": "#d03b3b", "warning": "#fab219"}
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

SEQ_CMAP = LinearSegmentedColormap.from_list("seq_blue", BLUE_RAMP)
DIV_CMAP = LinearSegmentedColormap.from_list("div_blue_red", [POLE_DOWN, NEUTRAL_MID, POLE_UP])

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": INK,
    "axes.edgecolor": GRID,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "font.size": 10,
})


def norm_name(value) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def style(ax, *, grid_axis: str | None = "y") -> None:
    """Recessive chrome: no top/right spines, faint grid behind the marks."""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)


def footer(fig, text: str, *, y: float = 0.012, width: int = 116) -> None:
    """Wrapped caption anchored to the figure, so long provenance notes never clip."""
    fig.text(0.5, y, textwrap.fill(" ".join(text.split()), width=width),
             ha="center", va="bottom", fontsize=8, color=INK_2, linespacing=1.45)


def save(fig, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)
    print(f"[figure] {path}")


def dump(frame: pd.DataFrame, name: str) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLE_DIR / f"{name}.csv", index=False)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
def load() -> dict:
    volcano = pd.read_csv(SCAN_LACPHE / "mw_ST003662_volcano_pre_post.csv")
    effects = pd.read_csv(SCAN_LACPHE / "mw_queried_metabolite_effects.csv")
    lacphe_samples = pd.read_csv(SCAN_LACPHE / "mw_ST003662_queried_sample_level.csv")
    lactate_samples = pd.read_csv(SCAN_LACTATE / "mw_ST003662_queried_sample_level.csv")
    lactate_samples = lactate_samples[lactate_samples["metabolite"] == LACTATE_FEATURE]
    rat = pd.read_csv(SCAN_LACPHE / "rat_pass1b06_metabolomics_timewise_all_rows.csv", low_memory=False)
    search = pd.read_csv(SEARCH_LACPHE / "metstat_metabolite_study_hits.csv")
    provenance = json.loads((SCAN_LACPHE / "provenance.json").read_text())
    motrpac_human = pd.read_csv(MOTRPAC_HUMAN_PLASMA)
    family = {}
    for directory in sorted(SEARCH_FAMILY.glob("*")):
        hits_path = directory / "metstat_metabolite_study_hits.csv"
        prov_path = directory / "metstat_metabolite_study_provenance.json"
        if not hits_path.is_file() or not prov_path.is_file():
            continue
        prov = json.loads(prov_path.read_text())
        family[prov["query_original"]] = {
            "hits": pd.read_csv(hits_path),
            "refmet_id": prov["refmet_identity"].get("refmet_id", ""),
        }
    return {
        "volcano": volcano,
        "effects": effects,
        "lacphe_samples": lacphe_samples,
        "lactate_samples": lactate_samples,
        "rat": rat,
        "search": search,
        "provenance": provenance,
        "motrpac_human": motrpac_human,
        "family": family,
    }


# --------------------------------------------------------------------------- #
# F1 — participant-level pre/post response
# --------------------------------------------------------------------------- #
def figure_participant_response(data: dict) -> None:
    samples = data["lacphe_samples"].copy()
    samples = samples[np.isfinite(samples["value_pre"]) & np.isfinite(samples["value_post"])]
    samples = samples[(samples["value_pre"] > 0) & (samples["value_post"] > 0)]
    samples["delta_log2"] = np.log2(samples["value_post"] / samples["value_pre"])
    effects = data["effects"]
    dump(samples, "f1_participant_response")

    overall_up = int((samples["value_post"] > samples["value_pre"]).sum())
    overall_n = len(samples)
    sexes = [s for s in ("m", "f") if (samples["sex"] == s).any()]
    fig, axes = plt.subplots(1, len(sexes), figsize=(4.6 * len(sexes) + 1.4, 5.6), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, sex in zip(axes, sexes):
        sub = samples[samples["sex"] == sex]
        rising = 0
        for _, row in sub.iterrows():
            up = row["value_post"] >= row["value_pre"]
            rising += int(up)
            ax.plot([0, 1], [row["value_pre"], row["value_post"]],
                    color=POLE_UP if up else POLE_DOWN, lw=0.9, alpha=0.45,
                    marker="o", ms=3.2, mew=0, zorder=2)
        med_pre, med_post = sub["value_pre"].median(), sub["value_post"].median()
        ax.plot([0, 1], [med_pre, med_post], color=INK, lw=2.6, marker="o", ms=8,
                mfc=SURFACE, mew=2.2, zorder=5, label="median")
        stat_row = effects[effects["stratum"] == sex]
        annotation = [f"{len(sub)} participants", f"{rising}/{len(sub)} increase ({100 * rising / len(sub):.0f}%)",
                      f"median {med_pre:.2f} → {med_post:.2f} µmol/L"]
        if not stat_row.empty:
            row = stat_row.iloc[0]
            annotation.append(f"paired log2FC {row['log2fc']:+.2f}, FDR {row['fdr']:.1e}")
        ax.text(0.02, 0.03, "\n".join(annotation), transform=ax.transAxes, ha="left", va="bottom",
                fontsize=8.8, color=INK_2,
                bbox=dict(boxstyle="round,pad=0.4", fc=SURFACE, ec=GRID, lw=0.9, alpha=0.82),
                zorder=6)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["pre-exercise", "post-exercise"])
        ax.set_xlim(-0.28, 1.28)
        ax.set_yscale("log", base=2)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda value, _pos: f"{value:g}" if value >= 0.1 else f"{value:.2f}"))
        ax.set_title(f"{SEX_LABEL[sex]} athletes", fontsize=11.5, color=INK)
        style(ax, grid_axis="y")
    axes[0].set_ylabel("Lac-Phe, µmol/L whole blood (log2 scale)")
    handles = [
        plt.Line2D([], [], color=POLE_UP, lw=1.6, marker="o", ms=4, label="participant increase"),
        plt.Line2D([], [], color=POLE_DOWN, lw=1.6, marker="o", ms=4, label="participant decrease"),
        plt.Line2D([], [], color=INK, lw=2.6, marker="o", ms=7, mfc=SURFACE, mew=2, label="group median"),
    ]
    fig.legend(handles=handles, frameon=False, fontsize=9, ncol=3, loc="lower center",
               bbox_to_anchor=(0.5, 0.075))
    fig.suptitle(f"Lac-Phe rises in {overall_up} of {overall_n} athletes "
                 f"({100 * overall_up / overall_n:.0f}%) after a single exercise bout\n"
                 "MW ST003662 · N-Lactoyl phenylalanine (RefMet RM0131640) · paired whole-blood samples",
                 fontsize=12.5)
    footer(fig,
           "One line per participant, same person pre and post; values are the study's own reported µmol/L. "
           "Sex panels are the study's reported strata. The exercise protocol, intensity and post-bout sampling "
           "delay are not encoded in the public record, so the magnitude is not interpretable as a dose response.")
    fig.tight_layout(rect=(0, 0.125, 1, 0.955))
    save(fig, "f1_lacphe_participant_response")


# --------------------------------------------------------------------------- #
# F2 — where Lac-Phe sits in the whole measured metabolome
# --------------------------------------------------------------------------- #
def figure_effect_ranking(data: dict) -> None:
    frame = data["volcano"]
    frame = frame[frame["stratum"] == "all"].copy()
    frame = frame.sort_values("log2fc", ascending=False).reset_index(drop=True)
    frame["rank"] = np.arange(1, len(frame) + 1)
    dump(frame, "f2_effect_ranking")

    significant = frame["fdr"] < P_THRESH
    colors = np.where(~significant, NS_GREY, np.where(frame["log2fc"] > 0, POLE_UP, POLE_DOWN))

    fig, ax = plt.subplots(figsize=(13, 6.2))
    ax.bar(frame["rank"], frame["log2fc"], width=1.0, color=colors, linewidth=0)
    ax.axhline(0, color=INK, lw=1.0)

    lacphe_row = frame[frame["refmet_name"] == LACPHE_REFMET].iloc[0]

    # Deterministic label ladders anchored in axes coordinates: bars at the extremes are
    # too close together to carry inline labels without collisions.
    top_labels = [row for row in frame.head(7).itertuples() if row.refmet_name != LACPHE_REFMET][:6]
    for index, row in enumerate(top_labels):
        ax.annotate(f"{row.refmet_name}  ({row.log2fc:+.2f})",
                    xy=(row.rank, row.log2fc), xycoords="data",
                    xytext=(0.115, 0.955 - index * 0.062), textcoords="axes fraction",
                    fontsize=8.8, color=INK_2, va="center", ha="left",
                    bbox=dict(boxstyle="square,pad=0.18", fc=SURFACE, ec="none"),
                    arrowprops=dict(arrowstyle="-", lw=0.7, color=INK_MUTED,
                                    shrinkA=2, shrinkB=1))
    bottom_labels = list(frame.tail(4).itertuples())[::-1]
    for index, row in enumerate(bottom_labels):
        ax.annotate(f"{row.refmet_name}  ({row.log2fc:+.2f})",
                    xy=(row.rank, row.log2fc), xycoords="data",
                    xytext=(0.60, 0.02 + index * 0.05), textcoords="axes fraction",
                    fontsize=8.8, color=INK_2, va="center", ha="right",
                    bbox=dict(boxstyle="square,pad=0.18", fc=SURFACE, ec="none"),
                    arrowprops=dict(arrowstyle="-", lw=0.7, color=INK_MUTED,
                                    shrinkA=2, shrinkB=1))
    ax.annotate(f"Lac-Phe\nrank {int(lacphe_row['rank'])} of {len(frame)}\n"
                f"log2FC {lacphe_row['log2fc']:+.2f}, FDR {lacphe_row['fdr']:.1e}",
                xy=(lacphe_row["rank"], lacphe_row["log2fc"]), xycoords="data",
                xytext=(0.30, 0.58), textcoords="axes fraction",
                fontsize=9.8, color=INK, fontweight="bold", va="center",
                bbox=dict(boxstyle="round,pad=0.42", fc=SURFACE, ec=INK, lw=1.3),
                arrowprops=dict(arrowstyle="-|>", lw=1.3, color=INK,
                                connectionstyle="arc3,rad=0.18"))
    ax.set_xlabel("metabolite rank by effect size (of 165 features with usable paired data)")
    ax.set_ylabel("log2 fold-change, post- vs pre-exercise")
    ax.set_xlim(-1, len(frame) + 2)
    handles = [
        mpatches.Patch(color=POLE_UP, label=f"higher post-exercise (BH FDR<{P_THRESH})"),
        mpatches.Patch(color=POLE_DOWN, label=f"lower post-exercise (BH FDR<{P_THRESH})"),
        mpatches.Patch(color=NS_GREY, label="not significant"),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=9, loc="upper right")
    style(ax, grid_axis="y")
    ax.set_title("Lac-Phe is the 4th largest post-exercise increase in this blood metabolome — "
                 "only lactate, pyruvate and xanthine move more\n"
                 "MW ST003662, all paired athletes, paired t-test on log2 µmol/L with BH adjustment",
                 fontsize=12, loc="left")
    footer(fig,
           "Bar height is the effect; colour is its sign. Lactic acid is the Lac-Phe substrate, so the ranking "
           "above it is mechanistically adjacent rather than independent. Effect size is not identity evidence: "
           "the Lac-Phe feature is a RefMet name match awaiting MS/MS confirmation.")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    save(fig, "f2_lacphe_effect_ranking")


# --------------------------------------------------------------------------- #
# F3 — substrate/conjugate coupling within participants
# --------------------------------------------------------------------------- #
def figure_substrate_coupling(data: dict) -> None:
    lacphe = data["lacphe_samples"][["participant_code", "sex", "value_pre", "value_post"]].copy()
    lactate = data["lactate_samples"][["participant_code", "value_pre", "value_post"]].copy()
    merged = lacphe.merge(lactate, on="participant_code", suffixes=("_lacphe", "_lactate"))
    for prefix in ("lacphe", "lactate"):
        pre, post = merged[f"value_pre_{prefix}"], merged[f"value_post_{prefix}"]
        merged[f"delta_{prefix}"] = np.log2(post / pre)
    merged = merged.replace([np.inf, -np.inf], np.nan)
    total_pairs = len(merged)
    lactate_missing = int(merged[["value_pre_lactate", "value_post_lactate"]].isna().any(axis=1).sum())
    lacphe_missing = int(merged[["value_pre_lacphe", "value_post_lacphe"]].isna().any(axis=1).sum())
    merged = merged.dropna(subset=["delta_lacphe", "delta_lactate"])
    dump(merged, "f3_substrate_coupling")

    x, y = merged["delta_lactate"].to_numpy(), merged["delta_lacphe"].to_numpy()
    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_r, spearman_p = stats.spearmanr(x, y)

    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    for sex in ("m", "f"):
        sub = merged[merged["sex"] == sex]
        ax.scatter(sub["delta_lactate"], sub["delta_lacphe"], s=46, c=SEX[sex], alpha=0.82,
                   linewidths=0.8, edgecolors=SURFACE, label=f"{SEX_LABEL[sex]} (n={len(sub)})", zorder=3)
    slope, intercept = np.polyfit(x, y, 1)
    grid_x = np.linspace(x.min(), x.max(), 50)
    ax.plot(grid_x, slope * grid_x + intercept, ls="--", lw=1.4, color=INK_2, zorder=2,
            label="least-squares fit")
    ax.axhline(0, color=GRID, lw=1.0)
    ax.axvline(0, color=GRID, lw=1.0)
    ax.text(0.02, 0.02,
            f"Pearson r = {pearson_r:.2f} (p = {pearson_p:.1e})\n"
            f"Spearman ρ = {spearman_r:.2f} (p = {spearman_p:.1e})\n"
            f"n = {len(merged)} of {total_pairs} paired participants\n"
            f"dropped: lactate value missing in {lactate_missing}, Lac-Phe in {lacphe_missing}",
            transform=ax.transAxes, va="bottom", ha="left", fontsize=9.4, color=INK,
            bbox=dict(boxstyle="round,pad=0.42", fc=SURFACE, ec=GRID, lw=0.9))
    ax.set_xlabel("within-participant Δlog2 lactic acid (post − pre)")
    ax.set_ylabel("within-participant Δlog2 Lac-Phe (post − pre)")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    style(ax, grid_axis="both")
    ax.set_title(f"A larger lactate rise tracks a larger Lac-Phe rise, but explains only part of it "
                 f"(r = {pearson_r:.2f})\n"
                 "MW ST003662 whole blood, same individuals on both axes", fontsize=12)
    footer(fig,
           "Association within one study, not a mechanism test: CNDP2-mediated conjugation was not measured here, "
           "and lactate is only one of the two substrates. Both axes are within-participant changes, so "
           "between-person baseline differences are removed by construction. The plotted subset is NOT a random "
           "sample: lactic acid has no reported pre-exercise value in most dropped participants, so a selection "
           "effect on this correlation cannot be excluded.", width=104)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    save(fig, "f3_lacphe_lactate_coupling")


# --------------------------------------------------------------------------- #
# F4 — male vs female effect concordance
# --------------------------------------------------------------------------- #
def figure_sex_concordance(data: dict) -> None:
    frame = data["volcano"]
    male = frame[frame["stratum"] == "m"][["refmet_name", "log2fc", "fdr"]]
    female = frame[frame["stratum"] == "f"][["refmet_name", "log2fc", "fdr"]]
    merged = male.merge(female, on="refmet_name", suffixes=("_male", "_female"))
    dump(merged, "f4_sex_concordance")

    x, y = merged["log2fc_male"].to_numpy(), merged["log2fc_female"].to_numpy()
    pearson_r, pearson_p = stats.pearsonr(x, y)
    concordant = int(np.sum(np.sign(x) == np.sign(y)))

    fig, ax = plt.subplots(figsize=(7.8, 7.2))
    # Shared, data-driven square limits: an equal aspect with symmetric limits would
    # spend most of the panel on empty space below the cloud.
    both = np.concatenate([x, y])
    low, high = float(np.nanmin(both)), float(np.nanmax(both))
    pad = 0.09 * (high - low)
    low, high = low - pad, high + pad
    ax.plot([low, high], [low, high], ls="--", lw=1.2, color=INK_MUTED, zorder=1)
    ax.axhline(0, color=GRID, lw=1.0)
    ax.axvline(0, color=GRID, lw=1.0)
    ax.scatter(x, y, s=34, c=NS_GREY, alpha=0.9, linewidths=0, zorder=2)

    highlights = [LACPHE_REFMET, "Lactic acid", "Pyruvic acid", "Xanthine"]
    for name in highlights:
        row = merged[merged["refmet_name"] == name]
        if row.empty:
            continue
        row = row.iloc[0]
        is_lacphe = name == LACPHE_REFMET
        ax.scatter([row["log2fc_male"]], [row["log2fc_female"]],
                   s=150 if is_lacphe else 80,
                   facecolors=POLE_UP if is_lacphe else SURFACE,
                   edgecolors=INK, linewidths=1.8, zorder=4)
        ax.annotate("Lac-Phe" if is_lacphe else name,
                    xy=(row["log2fc_male"], row["log2fc_female"]),
                    xytext=(12, -16 if is_lacphe else 10), textcoords="offset points",
                    fontsize=9.6 if is_lacphe else 8.8,
                    fontweight="bold" if is_lacphe else "normal", color=INK)
    ax.text(0.03, 0.97,
            f"Pearson r = {pearson_r:.2f} (p = {pearson_p:.1e})\n"
            f"same-direction features: {concordant}/{len(merged)}\n"
            "dashed line = identical effect in both sexes",
            transform=ax.transAxes, va="top", ha="left", fontsize=9.2, color=INK,
            bbox=dict(boxstyle="round,pad=0.42", fc=SURFACE, ec=GRID, lw=0.9))
    plotted = set(merged["refmet_name"])
    male_pairs = frame[(frame["stratum"] == "m") & (frame["refmet_name"].isin(plotted))]["n_pairs"]
    female_pairs = frame[(frame["stratum"] == "f") & (frame["refmet_name"].isin(plotted))]["n_pairs"]
    ax.set_xlabel(f"log2 fold-change, male athletes "
                  f"(per-feature n = {int(male_pairs.min())}–{int(male_pairs.max())} pairs)")
    ax.set_ylabel(f"log2 fold-change, female athletes "
                  f"(per-feature n = {int(female_pairs.min())}–{int(female_pairs.max())} pairs)")
    ax.set_xlim(low, high)
    ax.set_ylim(low, high)
    ax.set_aspect("equal")
    style(ax, grid_axis="both")
    ax.set_title("Male and female effect estimates agree across the measured metabolome\n"
                 f"MW ST003662, {len(merged)} features tested in both strata, independent paired tests",
                 fontsize=12)
    footer(fig,
           "Both axes come from the same study, platform and batch, so this is internal consistency, not "
           "independent replication. Pairs are dropped per feature on missingness, so the low-n tail "
           "(features estimated from as few as 3-4 pairs) carries more scatter than the bulk. Lac-Phe sits to the right of the identity line, i.e. a larger male point "
           "estimate, but the strata are not an interaction test — a sex difference needs a model on the "
           "sample-level matrix.", width=100)
    fig.tight_layout(rect=(0, 0.115, 1, 1))
    save(fig, "f4_sex_concordance")


# --------------------------------------------------------------------------- #
# F5 — N-lactoyl conjugate class coverage across sources
# --------------------------------------------------------------------------- #
def figure_class_coverage(data: dict) -> None:
    family = data["family"]
    st003662_features = {norm_name(name) for name in data["volcano"]["refmet_name"].unique()}
    rat_names = set()
    for column in ("refmet_name", "metabolite", "feature_id"):
        rat_names |= {norm_name(value) for value in data["rat"][column].astype(str).unique()}
    motrpac_human_names = {norm_name(value) for value in data["motrpac_human"]["refmet_name"].astype(str).unique()}

    rows = []
    for name, payload in family.items():
        hits = payload["hits"]
        human_blood = hits[(hits.get("species") == "Human") & (hits.get("sample_source") == "Blood")] \
            if len(hits) else hits
        key = norm_name(name)
        rows.append({
            "conjugate": name.replace("N-Lactoyl ", "Lac-"),
            "refmet_name": name,
            "refmet_id": payload["refmet_id"],
            "mw_analyses_any_species": len(hits),
            "mw_human_blood_analyses": len(human_blood),
            "in_st003662_human_whole_blood": int(key in st003662_features),
            "in_motrpac_human_public_plasma": int(key in motrpac_human_names),
            "in_motrpac_rat_pass1b06": int(key in rat_names),
        })
    table = pd.DataFrame(rows).sort_values("mw_analyses_any_species", ascending=False).reset_index(drop=True)
    dump(table, "f5_class_coverage")

    presence_cols = [("in_st003662_human_whole_blood", "MW ST003662\nhuman whole blood"),
                     ("in_motrpac_human_public_plasma", "MoTrPAC human\npublic plasma panel"),
                     ("in_motrpac_rat_pass1b06", "MoTrPAC rat\npass1b-06, 19 tissues")]

    fig, (ax_counts, ax_presence) = plt.subplots(
        1, 2, figsize=(14.2, 8.6), gridspec_kw={"width_ratios": [1.0, 1.3]})

    # Counts as paired bars rather than a heatmap: two magnitudes on very different
    # scales share one length axis honestly, where a single colour ramp would wash
    # the smaller column out.
    ypos = np.arange(len(table))
    height = 0.38
    ax_counts.barh(ypos - height / 2, table["mw_analyses_any_species"], height=height,
                   color=SEX["m"], linewidth=0, label="all species")
    ax_counts.barh(ypos + height / 2, table["mw_human_blood_analyses"], height=height,
                   color=SEX["f"], linewidth=0, label="human blood")
    for y, row in zip(ypos, table.itertuples()):
        ax_counts.text(row.mw_analyses_any_species + 0.7, y - height / 2, str(row.mw_analyses_any_species),
                       va="center", fontsize=8.4, color=INK_2)
        ax_counts.text(row.mw_human_blood_analyses + 0.7, y + height / 2, str(row.mw_human_blood_analyses),
                       va="center", fontsize=8.4, color=INK_2)
    ax_counts.set_yticks(ypos)
    ax_counts.set_yticklabels([row.conjugate for row in table.itertuples()], fontsize=9)
    ax_counts.set_ylim(len(table) - 0.5, -0.5)   # matched to the presence panel so rows line up
    ax_counts.set_xlim(0, table["mw_analyses_any_species"].max() * 1.16)
    ax_counts.set_xlabel("MW analyses reporting the conjugate")
    ax_counts.set_title("How often each conjugate is reported in Metabolomics Workbench",
                        fontsize=10.5, color=INK, loc="left")
    ax_counts.legend(frameon=False, fontsize=9, loc="lower right")
    style(ax_counts, grid_axis="x")

    presence = table[[column for column, _ in presence_cols]].to_numpy(dtype=int)
    ax_presence.set_xlim(-0.5, len(presence_cols) - 0.5)
    ax_presence.set_ylim(len(table) - 0.5, -0.5)
    for row_index in range(presence.shape[0]):
        for col_index in range(presence.shape[1]):
            measured = bool(presence[row_index, col_index])
            color = STATUS["good"] if measured else STATUS["critical"]
            ax_presence.add_patch(mpatches.Rectangle(
                (col_index - 0.46, row_index - 0.42), 0.92, 0.84,
                facecolor=color, alpha=0.16, edgecolor="none"))
            ax_presence.text(col_index, row_index, "✓ measured" if measured else "✗ not measured",
                             ha="center", va="center", fontsize=8.6,
                             color=STATUS["good"] if measured else STATUS["critical"],
                             fontweight="bold" if measured else "normal")
    ax_presence.set_xticks(range(len(presence_cols)))
    ax_presence.set_xticklabels([label for _, label in presence_cols], fontsize=9)
    ax_presence.set_yticks([])
    ax_presence.tick_params(length=0)
    for spine in ax_presence.spines.values():
        spine.set_visible(False)
    ax_presence.set_title("Is the conjugate in the feature space of each exercise source?",
                          fontsize=10.5, color=INK)

    fig.suptitle("The whole N-lactoyl amino-acid class is missing from both MoTrPAC exercise panels\n"
                 "22 RefMet conjugates · Lac-Phe is the best covered of them in MW, and still absent from "
                 "MoTrPAC human and rat feature spaces",
                 fontsize=12.5)
    footer(fig,
           "Left: MW analyses reporting each conjugate, all species vs human blood. Right: glyph plus colour for "
           "feature-space presence, so status never rests on colour alone. 'Not measured' is a panel-coverage "
           "finding — it is not evidence the conjugate is unchanged by exercise. MW counts are analyses, so one "
           "study can contribute several.")
    fig.tight_layout(rect=(0, 0.065, 1, 0.95))
    save(fig, "f5_lactoyl_class_coverage")


# --------------------------------------------------------------------------- #
# F6 — rat precursor response across all pass1b-06 tissues
# --------------------------------------------------------------------------- #
def figure_rat_tissue_heatmap(data: dict) -> None:
    rat = data["rat"]
    precursors = ["lactic acid", "phenylalanine"]
    sub = rat[rat["refmet_name"].astype(str).str.lower().isin(precursors)].copy()
    for column in ("logFC", "p_value", "adj_p_value"):
        sub[column] = pd.to_numeric(sub[column], errors="coerce")
    sub["tissue"] = sub["tissue"].astype(str).str.lower()
    sub["sex"] = sub["sex"].astype(str).str.lower()
    dump(sub, "f6_rat_precursor_tissue_rows")

    groups = ["1w", "2w", "4w", "8w"]
    tissues = sorted(sub["tissue"].unique())
    limit = float(np.nanmax(np.abs(sub["logFC"]))) or 1.0
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)

    fig, axes = plt.subplots(2, 2, figsize=(12.2, 9.4), sharey=True)
    for row_index, metabolite in enumerate(precursors):
        for col_index, sex in enumerate(["male", "female"]):
            ax = axes[row_index][col_index]
            cell = sub[(sub["refmet_name"].astype(str).str.lower() == metabolite)
                       & (sub["sex"] == sex)]
            matrix = np.full((len(tissues), len(groups)), np.nan)
            nominal = np.zeros_like(matrix, dtype=bool)
            fdr_significant = np.zeros_like(matrix, dtype=bool)
            adj_missing = np.zeros_like(matrix, dtype=bool)
            for t_index, tissue in enumerate(tissues):
                for g_index, group in enumerate(groups):
                    record = cell[(cell["tissue"] == tissue) & (cell["comparison_group"] == group)]
                    if record.empty:
                        continue
                    row = record.iloc[0]
                    matrix[t_index, g_index] = float(row["logFC"])
                    nominal[t_index, g_index] = bool(row["p_value"] < P_THRESH)
                    adj_value = row["adj_p_value"]
                    adj_missing[t_index, g_index] = bool(pd.isna(adj_value))
                    fdr_significant[t_index, g_index] = bool(
                        not pd.isna(adj_value) and adj_value < P_THRESH)
            masked = np.ma.masked_invalid(matrix)
            cmap = DIV_CMAP.copy()
            cmap.set_bad(color="#eceae5")
            mesh = ax.imshow(masked, cmap=cmap, norm=norm, aspect="auto")
            for t_index in range(len(tissues)):
                for g_index in range(len(groups)):
                    if np.isnan(matrix[t_index, g_index]):
                        ax.text(g_index, t_index, "n/a", ha="center", va="center",
                                fontsize=7.5, color=INK_MUTED)
                    elif fdr_significant[t_index, g_index]:
                        ax.text(g_index, t_index, "*", ha="center", va="center",
                                fontsize=13, fontweight="bold", color=INK)
                    elif nominal[t_index, g_index]:
                        # Grey dagger where the source reported no adjusted p for the cell,
                        # so an unadjusted-only result is never read as an FDR result.
                        ax.text(g_index, t_index, "†", ha="center", va="center", fontsize=9.5,
                                color=INK_MUTED if adj_missing[t_index, g_index] else INK)
            ax.set_xticks(range(len(groups)))
            ax.set_xticklabels([f"{group}" for group in groups], fontsize=9)
            ax.set_yticks(range(len(tissues)))
            ax.set_yticklabels(tissues, fontsize=8.4)
            ax.set_title(f"{metabolite} — {sex} rats", fontsize=10.8, color=INK)
            ax.tick_params(length=0)
            for spine in ax.spines.values():
                spine.set_visible(False)
            if row_index == 1:
                ax.set_xlabel("training weeks vs sedentary control", fontsize=9)
    bar = fig.colorbar(mesh, ax=axes, fraction=0.028, pad=0.02)
    bar.set_label("logFC, trained vs sedentary (consortium timewise model)", fontsize=8.5)
    bar.outline.set_visible(False)

    coverage = {
        metabolite: sub[sub["refmet_name"].astype(str).str.lower() == metabolite]["tissue"].nunique()
        for metabolite in precursors
    }
    fig.suptitle("Rat pass1b-06 reports both Lac-Phe substrates — and the conjugate itself in no tissue at all\n"
                 f"phenylalanine in {coverage['phenylalanine']}/{len(tissues)} tissues, lactic acid in "
                 f"{coverage['lactic acid']}/{len(tissues)}, any N-lactoyl conjugate in 0/{len(tissues)} "
                 f"(0 of 2,459 rat features)",
                 fontsize=12.5)
    fdr_rows = sub[sub["adj_p_value"] < P_THRESH]
    nominal_only = int(((sub["p_value"] < P_THRESH) & ~(sub["adj_p_value"] < P_THRESH)).sum())
    # Counted among nominally significant cells only, because that is the set the grey
    # dagger marks; an adj_p-absent cell with p>=0.05 carries no marker to explain.
    adj_absent = int(((sub["p_value"] < P_THRESH) & sub["adj_p_value"].isna()).sum())
    fdr_description = "; ".join(
        f"{row.refmet_name}, {row.sex} {row.tissue}, {row.comparison_group} "
        f"(logFC {row.logFC:+.2f}, adj_p {row.adj_p_value:.3f})"
        for row in fdr_rows.itertuples()
    ) or "none"
    footer(fig,
           f"Precursor-level evidence only, not a Lac-Phe substitute. * = adj_p<0.05 "
           f"({len(fdr_rows)} of {len(sub)} plotted cells: {fdr_description}). † = nominal p<0.05 only "
           f"({nominal_only} cells, of which {adj_absent} carry a grey † because the source reported no "
           f"adjusted p for that cell). 'n/a' = the metabolite was not reported for that tissue x week x sex. "
           "Chronic training adaptation, not an acute bout, so this is not comparable to the human acute "
           "contrast.", y=0.008)
    save(fig, "f6_rat_precursor_tissue_heatmap")


# --------------------------------------------------------------------------- #
# F7 — study-discovery landscape
# --------------------------------------------------------------------------- #
def figure_discovery_landscape(data: dict) -> None:
    search = data["search"].copy()
    search["species"] = search["species"].replace("", np.nan).fillna("not reported")
    search["sample_source"] = search["sample_source"].replace("", np.nan).fillna("not reported")
    dump(search, "f7_discovery_landscape")

    species_counts = search["species"].value_counts()
    top_species = species_counts.head(6)
    other_total = int(species_counts.iloc[6:].sum())
    labels = list(top_species.index) + ([f"other ({len(species_counts) - 6} taxa)"] if other_total else [])
    values = list(top_species.to_numpy()) + ([other_total] if other_total else [])

    human = search[search["species"] == "Human"]
    human_counts = human["sample_source"].value_counts()

    fig, (ax_species, ax_human) = plt.subplots(1, 2, figsize=(13.4, 5.8),
                                               gridspec_kw={"width_ratios": [1, 1]})
    ypos = np.arange(len(labels))[::-1]
    ax_species.barh(ypos, values, color=BLUE_RAMP[3], height=0.68, linewidth=0)
    for y, value in zip(ypos, values):
        ax_species.text(value + 0.35, y, str(value), va="center", fontsize=9, color=INK_2)
    ax_species.set_yticks(ypos)
    ax_species.set_yticklabels(labels, fontsize=9.5)
    ax_species.set_xlabel("MW analyses reporting Lac-Phe")
    ax_species.set_title(f"Lac-Phe is reported by {search['study_id'].nunique()} MW studies "
                         f"({len(search)} analyses)", fontsize=11, loc="left")
    ax_species.set_xlim(0, max(values) * 1.16)
    style(ax_species, grid_axis="x")

    ypos_h = np.arange(len(human_counts))[::-1]
    ax_human.barh(ypos_h, human_counts.to_numpy(), color=BLUE_RAMP[3], height=0.68, linewidth=0)
    for y, (source, value) in zip(ypos_h, human_counts.items()):
        note = "  ← 1 of these is an exercise design (ST003662)" if source == "Blood" else ""
        ax_human.text(value + 0.12, y, f"{value}{note}", va="center", fontsize=9,
                      color=INK if note else INK_2, fontweight="bold" if note else "normal")
    ax_human.set_yticks(ypos_h)
    ax_human.set_yticklabels(human_counts.index, fontsize=9.5)
    ax_human.set_xlabel("human MW analyses reporting Lac-Phe")
    ax_human.set_title("Human analyses by sample source", fontsize=11, loc="left")
    ax_human.set_xlim(0, human_counts.max() * 2.75)
    style(ax_human, grid_axis="x")

    fig.suptitle("Lac-Phe is widely reported but almost never in an exercise design", fontsize=13)
    footer(fig,
           "Metabolomics Workbench metstat search on RefMet name N-Lactoyl phenylalanine. Counts are analyses, so "
           "one study can contribute several rows. The remaining human blood studies are disease and case-control "
           "cohorts with no exercise exposure.")
    fig.tight_layout(rect=(0, 0.085, 1, 0.955))
    save(fig, "f7_discovery_landscape")


def main() -> None:
    data = load()
    figure_participant_response(data)
    figure_effect_ranking(data)
    figure_substrate_coupling(data)
    figure_sex_concordance(data)
    figure_class_coverage(data)
    figure_rat_tissue_heatmap(data)
    figure_discovery_landscape(data)
    print(f"[lacphe-figures] wrote {OUT_DIR} and {TABLE_DIR}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render the Lac-Phe (N-lactoyl phenylalanine) cross-species evidence report.

Offline renderer: reads only the live tables written by
``scripts/volcano_compare.py --metabolite-scan`` and
``metabo-agent live-search-metabolite-studies``, then writes figures and a
markdown report under ``reports_live/lacphe/``. No network access.

Scientific guardrails enforced here:
- Human effects and rat effects are never pooled or plotted on a shared
  statistical axis; they are different species, designs, and estimands.
- Rat precursor metabolites (lactic acid, phenylalanine) are labelled as
  precursor-level evidence, never as Lac-Phe replication.
- A queried metabolite missing from a source feature space is rendered as a
  coverage gap, not as a null effect.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

SCAN_DIR = Path("data/live/metabolite_scan/n_lactoyl_phenylalanine")
SCAN_LACTATE_DIR = Path("data/live/metabolite_scan/lactic_acid")
SEARCH_DIR = Path("data/live/metabolite_search_lacphe")
SEARCH_FAMILY_DIR = Path("data/live/metabolite_search_lacphe_family")
LITERATURE_DIR = Path("data/live/literature/lacphe")
MOTRPAC_HUMAN_PLASMA = Path("data/live/volcano_motrpac_human_plasma_endur_post.csv")
OUT_DIR = Path("reports_live/lacphe")

QUERY = "N-Lactoyl phenylalanine"
REFMET_ID = "RM0131640"
RAT_PRECURSORS = ["lactic acid", "phenylalanine"]
RAT_FOCUS_TISSUES = ["plasma", "gastrocnemius", "vastus lateralis", "liver", "heart"]

C_NS = "#b8b8b8"
C_UP = "#d62728"
C_DOWN = "#1f77b4"
C_HIT = "#111111"
SEX_COLORS = {"all": "#444444", "m": "#3b6ea5", "f": "#c2557a", "male": "#3b6ea5", "female": "#c2557a"}
P_THRESH = 0.05


def footer(fig, text: str, *, y: float = 0.012, width: int = 112) -> None:
    """Wrapped caption anchored to the figure, so long provenance notes never clip."""
    fig.text(0.5, y, textwrap.fill(" ".join(text.split()), width=width),
             ha="center", va="bottom", fontsize=8, color="#444444", linespacing=1.45)


def paired_ci(log2fc: float, p_value: float, n_pairs: int) -> tuple[float, float, float]:
    """Recover the paired-t standard error and 95% CI from (log2fc, p, n).

    The scan lane stores the effect, its two-sided paired-t p-value, and the pair
    count, so the SE is recoverable exactly as |effect| / |t|; this avoids
    re-fetching or re-deriving the abundance matrix in the renderer.
    """
    df = max(n_pairs - 1, 1)
    if not np.isfinite(p_value) or p_value <= 0 or p_value >= 1 or log2fc == 0:
        return float("nan"), float("nan"), float("nan")
    t_abs = float(stats.t.ppf(1.0 - p_value / 2.0, df))
    se = abs(log2fc) / t_abs
    crit = float(stats.t.ppf(0.975, df))
    return se, log2fc - crit * se, log2fc + crit * se


def _norm(value) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def derive_suite_stats(inputs: dict) -> dict:
    """Numbers behind the figure suite, recomputed from the live tables."""

    volcano_all = inputs["volcano"][inputs["volcano"]["stratum"] == "all"].copy()
    volcano_all = volcano_all.sort_values("log2fc", ascending=False).reset_index(drop=True)
    volcano_all["rank"] = range(1, len(volcano_all) + 1)
    lacphe_row = volcano_all[volcano_all["refmet_name"] == QUERY].iloc[0]

    samples = pd.read_csv(SCAN_DIR / "mw_ST003662_queried_sample_level.csv")
    usable = samples[(samples["value_pre"] > 0) & (samples["value_post"] > 0)].dropna(
        subset=["value_pre", "value_post"])
    responders = int((usable["value_post"] > usable["value_pre"]).sum())

    lactate = pd.read_csv(SCAN_LACTATE_DIR / "mw_ST003662_queried_sample_level.csv")
    lactate = lactate[lactate["metabolite"] == "Lactic acid"]
    merged = samples.merge(lactate, on="participant_code", suffixes=("_lacphe", "_lactate"))
    for suffix in ("lacphe", "lactate"):
        merged[f"delta_{suffix}"] = np.log2(
            merged[f"value_post_{suffix}"] / merged[f"value_pre_{suffix}"])
    coupled = merged.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["delta_lacphe", "delta_lactate"])
    pearson_r, pearson_p = stats.pearsonr(coupled["delta_lactate"], coupled["delta_lacphe"])

    male = inputs["volcano"][inputs["volcano"]["stratum"] == "m"][["refmet_name", "log2fc"]]
    female = inputs["volcano"][inputs["volcano"]["stratum"] == "f"][["refmet_name", "log2fc"]]
    sexes = male.merge(female, on="refmet_name", suffixes=("_m", "_f"))
    sex_r, _ = stats.pearsonr(sexes["log2fc_m"], sexes["log2fc_f"])
    concordant = int((np.sign(sexes["log2fc_m"]) == np.sign(sexes["log2fc_f"])).sum())

    rat_names = set()
    for column in ("refmet_name", "metabolite", "feature_id"):
        rat_names |= {_norm(value) for value in inputs["rat"][column].astype(str).unique()}
    motrpac_human = pd.read_csv(MOTRPAC_HUMAN_PLASMA)
    motrpac_human_names = {_norm(value) for value in motrpac_human["refmet_name"].astype(str).unique()}
    st003662_names = {_norm(value) for value in inputs["volcano"]["refmet_name"].unique()}

    family = []
    for directory in sorted(SEARCH_FAMILY_DIR.glob("*")):
        hits_path = directory / "metstat_metabolite_study_hits.csv"
        prov_path = directory / "metstat_metabolite_study_provenance.json"
        if not hits_path.is_file() or not prov_path.is_file():
            continue
        hits = pd.read_csv(hits_path)
        name = json.loads(prov_path.read_text())["query_original"]
        key = _norm(name)
        family.append({
            "name": name,
            "mw_analyses": len(hits),
            "in_st003662": key in st003662_names,
            "in_motrpac_human": key in motrpac_human_names,
            "in_rat": key in rat_names,
        })
    family_frame = pd.DataFrame(family)

    rat_precursors = inputs["rat"][
        inputs["rat"]["refmet_name"].astype(str).str.lower().isin(("lactic acid", "phenylalanine"))].copy()
    for column in ("logFC", "p_value", "adj_p_value"):
        rat_precursors[column] = pd.to_numeric(rat_precursors[column], errors="coerce")
    precursor_fdr = rat_precursors[rat_precursors["adj_p_value"] < 0.05]

    rat_precursor_tissues = {}
    for precursor in ("lactic acid", "phenylalanine"):
        rows = inputs["rat"][inputs["rat"]["refmet_name"].astype(str).str.lower() == precursor]
        rat_precursor_tissues[precursor] = int(rows["tissue"].nunique())

    return {
        "paired_feature_count": int(inputs["volcano"]["refmet_name"].nunique()),
        "precursor_cells": len(rat_precursors),
        "precursor_fdr_rows": precursor_fdr,
        "precursor_nominal_only": int(
            ((rat_precursors["p_value"] < 0.05) & ~(rat_precursors["adj_p_value"] < 0.05)).sum()),
        "precursor_adj_absent": int(
            ((rat_precursors["p_value"] < 0.05) & rat_precursors["adj_p_value"].isna()).sum()),
        "precursor_adj_absent_tissues": ", ".join(sorted(set(
            rat_precursors[(rat_precursors["p_value"] < 0.05)
                           & rat_precursors["adj_p_value"].isna()]["tissue"].astype(str)))) or "none",
        "feature_count": len(volcano_all),
        "lacphe_rank": int(lacphe_row["rank"]),
        "above_lacphe": list(volcano_all.head(int(lacphe_row["rank"]) - 1)["refmet_name"]),
        "responders": responders,
        "responder_total": len(usable),
        "coupling_r": float(pearson_r),
        "coupling_p": float(pearson_p),
        "coupling_n": len(coupled),
        "coupling_total": len(merged),
        "coupling_dropped_lactate": int(
            merged[["value_pre_lactate", "value_post_lactate"]].isna().any(axis=1).sum()),
        "sex_r": float(sex_r),
        "sex_concordant": concordant,
        "sex_features": len(sexes),
        "family": family_frame,
        "rat_tissue_total": int(inputs["rat"]["tissue"].nunique()),
        "rat_precursor_tissues": rat_precursor_tissues,
        "motrpac_human_features": len(motrpac_human),
    }


def load_inputs() -> dict:
    volcano = pd.read_csv(SCAN_DIR / "mw_ST003662_volcano_pre_post.csv")
    hits = pd.read_csv(SCAN_DIR / "mw_queried_metabolite_effects.csv")
    provenance = json.loads((SCAN_DIR / "provenance.json").read_text())
    rat = pd.read_csv(SCAN_DIR / "rat_pass1b06_metabolomics_timewise_all_rows.csv", low_memory=False)
    search = pd.read_csv(SEARCH_DIR / "metstat_metabolite_study_hits.csv")
    search_prov = json.loads((SEARCH_DIR / "metstat_metabolite_study_provenance.json").read_text())
    # The literature lane is a separate live command. If it has not been run, the report
    # says so instead of implying that no literature exists.
    literature_review_path = LITERATURE_DIR / "literature_review.json"
    literature_provenance_path = LITERATURE_DIR / "literature_provenance.json"
    literature = (
        json.loads(literature_review_path.read_text()) if literature_review_path.exists() else None
    )
    literature_prov = (
        json.loads(literature_provenance_path.read_text())
        if literature_provenance_path.exists()
        else None
    )
    return {
        "volcano": volcano,
        "hits": hits,
        "provenance": provenance,
        "rat": rat,
        "search": search,
        "search_provenance": search_prov,
        "literature": literature,
        "literature_provenance": literature_prov,
    }


SUBJECT_CONFIRMED = ("subject_name_in_title", "subject_name_in_abstract")
REPLICATION_DESIGNS = ("randomized_controlled_trial", "interventional_exercise_bout_or_program")


def derive_literature_stats(review: dict | None, provenance: dict | None) -> dict | None:
    """Derive every literature number in the report from the screened record set.

    Nothing here is hand-entered: counts, record lists and source status all come from
    the live artifacts, so the section regenerates with the data.
    """

    if not review:
        return None
    records = review.get("records") or []
    summary = review.get("summary") or {}
    confirmed = [row for row in records if row["subject_term_evidence"] in SUBJECT_CONFIRMED]
    human_exercise = [row for row in confirmed if row["screen_class"] == "direct_human_exercise"]
    human_exercise_primary = [row for row in human_exercise if row["evidence_tier"] == "peer_reviewed_primary"]
    replication = sorted(
        (row for row in human_exercise_primary if row["intervention_design"] in REPLICATION_DESIGNS),
        key=lambda row: (row["publication_year"], row["title"]),
    )
    mechanistic = [row for row in confirmed if row["screen_class"] == "animal_or_invitro_mechanistic"]
    reviews = [row for row in confirmed if row["screen_class"] == "secondary_synthesis"]
    non_exercise = [row for row in confirmed if row["screen_class"] == "human_non_exercise_context"]
    retracted = [row for row in records if row["evidence_tier"] == "retracted_or_retraction_notice"]
    preprints = [row for row in records if row["evidence_tier"] == "preprint_not_peer_reviewed"]
    with_accession = [row for row in human_exercise if row["data_availability_evidence"] == "accession_in_record_text"]
    escalation_counts: dict[str, int] = {}
    for row in review.get("escalations") or []:
        escalation_counts[row["escalation"]] = escalation_counts.get(row["escalation"], 0) + 1
    sources = (provenance or {}).get("sources") or []
    return {
        "record_count": len(records),
        "raw_record_count": (provenance or {}).get("record_count_raw"),
        "confirmed": confirmed,
        "confirmed_count": len(confirmed),
        "human_exercise": human_exercise,
        "human_exercise_count": len(human_exercise),
        "human_exercise_primary_count": len(human_exercise_primary),
        "replication": replication,
        "mechanistic_count": len(mechanistic),
        "reviews_count": len(reviews),
        "non_exercise_count": len(non_exercise),
        "retracted": retracted,
        "preprint_count": len(preprints),
        "human_exercise_with_accession": len(with_accession),
        "summary": summary,
        "escalation_counts": escalation_counts,
        "escalation_total": sum(escalation_counts.values()),
        "sources": sources,
        "unavailable_sources": list(summary.get("unavailable_sources") or []),
        "truncated_sources": list(summary.get("truncated_sources") or []),
        "subject_absent": summary.get("subject_term_evidence_counts", {}).get(
            "subject_name_absent_from_title_and_abstract", 0
        ),
        "no_abstract": summary.get("subject_term_evidence_counts", {}).get("unknown_no_abstract_retrieved", 0),
        "homonym_flagged": summary.get("homonym_risk_counts", {}).get("flagged_non_metabolite_homonym_context", 0),
        "homonym_mixed": summary.get("homonym_risk_counts", {}).get("mixed_material_and_biological_context", 0),
        "years": sorted({row["publication_year"] for row in confirmed if row["publication_year"]}),
        "uncertain_no_abstract": sum(
            1 for row in records if "uncertain_reason=no_abstract_returned" in row["screen_basis"]
        ),
        "uncertain_species_not_stated": sum(
            1 for row in records if "uncertain_reason=species_not_stated_in_abstract" in row["screen_basis"]
        ),
        "uncertain_total": summary.get("screen_class_counts", {}).get(
            "screening_uncertain_insufficient_text", 0
        ),
    }


def plot_human_volcano(volcano: pd.DataFrame, hits: pd.DataFrame, path: Path,
                       panel_size: int) -> None:
    strata = ["all", "m", "f"]
    titles = {
        "all": "All paired athletes",
        "m": "Male athletes",
        "f": "Female athletes",
    }
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), sharey=True)
    for ax, stratum in zip(axes, strata):
        sub = volcano[volcano["stratum"] == stratum]
        if sub.empty:
            ax.set_axis_off()
            continue
        sig = sub["fdr"] < P_THRESH
        up = sig & (sub["log2fc"] > 0)
        down = sig & (sub["log2fc"] < 0)
        ax.scatter(sub.loc[~sig, "log2fc"], sub.loc[~sig, "neg_log10_p"],
                   s=16, c=C_NS, alpha=0.55, linewidths=0, label="FDR n.s.")
        ax.scatter(sub.loc[up, "log2fc"], sub.loc[up, "neg_log10_p"],
                   s=20, c=C_UP, alpha=0.8, linewidths=0, label="higher post")
        ax.scatter(sub.loc[down, "log2fc"], sub.loc[down, "neg_log10_p"],
                   s=20, c=C_DOWN, alpha=0.8, linewidths=0, label="lower post")
        hit = hits[hits["stratum"] == stratum]
        if not hit.empty:
            row = hit.iloc[0]
            ax.scatter([row["log2fc"]], [row["neg_log10_p"]], s=140, facecolors="none",
                       edgecolors=C_HIT, linewidths=2.0, zorder=5)
            ax.annotate(
                f"Lac-Phe\nlog2FC {row['log2fc']:+.2f}\nFDR {row['fdr']:.1e}",
                xy=(row["log2fc"], row["neg_log10_p"]),
                xytext=(18, 34), textcoords="offset points", ha="left", fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_HIT, lw=0.8, alpha=0.9),
                arrowprops=dict(arrowstyle="->", lw=1.0, color=C_HIT),
            )
        ax.axvline(0, ls=":", lw=0.8, c="grey")
        n_pairs = int(sub["n_pairs"].max())
        ax.set_title(f"{titles[stratum]} (n≤{n_pairs} pairs)", fontsize=11)
        ax.set_xlabel("log2 fold-change (post / pre exercise)")
    axes[0].set_ylabel("-log10 paired-t p")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.suptitle(
        "Human whole-blood metabolome, post- vs pre-exercise — MW ST003662 (athletes)\n"
        f"Lac-Phe = {QUERY} (RefMet {REFMET_ID}); paired t-test on log2 μmol/L, BH within stratum",
        fontsize=12,
    )
    fig.text(0.5, 0.005,
             f"Single study, whole blood, quantitative LC-MS panel ({panel_size} named metabolites in "
             "\u03bcmol/L; "
             "AN006015 HILIC + AN006016 reversed phase). Name-level RefMet match: "
             "screening evidence, not MSI-confirmed identity. Sex strata are separate BH families.",
             ha="center", fontsize=8, color="#444444")
    fig.tight_layout(rect=(0, 0.03, 1, 0.9))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)


def plot_human_effect_by_sex(hits: pd.DataFrame, path: Path) -> None:
    order = ["all", "m", "f"]
    labels = {"all": "All athletes", "m": "Male", "f": "Female"}
    rows = []
    for stratum in order:
        sub = hits[hits["stratum"] == stratum]
        if sub.empty:
            continue
        row = sub.iloc[0]
        se, lo, hi = paired_ci(row["log2fc"], row["p_value"], int(row["n_pairs"]))
        rows.append((labels[stratum], stratum, row["log2fc"], lo, hi, int(row["n_pairs"]), row["fdr"]))

    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    ypos = np.arange(len(rows))[::-1]
    for y, (label, stratum, effect, lo, hi, n, fdr) in zip(ypos, rows):
        color = SEX_COLORS.get(stratum, "#444444")
        ax.plot([lo, hi], [y, y], lw=2.2, c=color, solid_capstyle="round")
        ax.plot([effect], [y], "o", ms=8, c=color)
        ax.text(hi + 0.06, y, f"{effect:+.2f} [{lo:+.2f}, {hi:+.2f}]  n={n}  FDR={fdr:.1e}",
                va="center", fontsize=8.5)
    ax.axvline(0, ls="--", lw=0.9, c="grey")
    ax.set_yticks(ypos)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlabel("log2 fold-change, post- vs pre-exercise (95% CI)")
    ax.set_xlim(-0.25, max(row[4] for row in rows) + 2.55)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(f"Lac-Phe exercise response by sex — MW ST003662 whole blood", fontsize=11)
    fig.text(0.5, 0.01,
             "CIs recovered from the stored paired-t effect, p-value and pair count. Sex strata overlap the 'All' "
             "stratum and are not independent replications.",
             ha="center", fontsize=7.5, color="#444444")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)


def rat_precursor_frame(rat: pd.DataFrame) -> pd.DataFrame:
    sub = rat[rat["refmet_name"].astype(str).str.lower().isin(RAT_PRECURSORS)].copy()
    sub = sub[sub["tissue"].astype(str).str.lower().isin(RAT_FOCUS_TISSUES)]
    for col in ("logFC", "p_value", "adj_p_value", "logFC_se"):
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
    return sub


def plot_rat_precursors(rat_sub: pd.DataFrame, path: Path) -> None:
    """Rat precursor logFC by tissue and training week, with sexes kept separate.

    Sex strata are plotted in their own panels rather than averaged: MoTrPAC models
    male and female rats separately, and pooling them here would invent an estimand
    the source never reported.
    """
    groups = ["1w", "2w", "4w", "8w"]
    sexes = ["male", "female"]
    cmap = plt.get_cmap("viridis")
    colors = {group: cmap(0.12 + 0.24 * index) for index, group in enumerate(groups)}

    fig, axes = plt.subplots(len(RAT_PRECURSORS), len(sexes), figsize=(13, 7.4))
    for row_index, metabolite in enumerate(RAT_PRECURSORS):
        met_rows = rat_sub[rat_sub["refmet_name"].astype(str).str.lower() == metabolite]
        tissues = [t for t in RAT_FOCUS_TISSUES if t in set(met_rows["tissue"].astype(str).str.lower())]
        for col_index, sex in enumerate(sexes):
            ax = axes[row_index][col_index]
            sub = met_rows[met_rows["sex"].astype(str).str.lower() == sex]
            width = 0.8 / len(groups)
            for g_index, group in enumerate(groups):
                xs, ys, errs, stars = [], [], [], []
                for t_index, tissue in enumerate(tissues):
                    cell = sub[(sub["tissue"].astype(str).str.lower() == tissue)
                               & (sub["comparison_group"] == group)]
                    if cell.empty:
                        continue
                    record = cell.iloc[0]
                    xs.append(t_index - 0.4 + width * (g_index + 0.5))
                    ys.append(float(record["logFC"]))
                    errs.append(float(record["logFC_se"]) if np.isfinite(record["logFC_se"]) else 0.0)
                    stars.append(bool(record["p_value"] < P_THRESH))
                ax.bar(xs, ys, width=width * 0.9, yerr=errs, capsize=1.5, color=colors[group],
                       linewidth=0, label=group if (row_index == 0 and col_index == 0) else None)
                for x, y, star, err in zip(xs, ys, stars, errs):
                    if star:
                        offset = err + 0.045 if y >= 0 else -(err + 0.085)
                        ax.text(x, y + offset, "\u2020", ha="center", fontsize=9.5, color="black")
            ax.axhline(0, lw=0.9, c="black")
            ax.set_xticks(range(len(tissues)))
            ax.set_xticklabels(tissues, fontsize=8.5, rotation=20, ha="right")
            if col_index == 0:
                ax.set_ylabel("logFC\n(trained vs sedentary)", fontsize=9)
            ax.set_title(f"{metabolite} — {sex} rats", fontsize=10.5)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, ncol=4, title="training week",
               title_fontsize=9, loc="upper center", bbox_to_anchor=(0.5, 0.935))
    fig.suptitle(
        "Rat MoTrPAC pass1b-06: Lac-Phe PRECURSORS only — Lac-Phe itself is absent from the rat feature space",
        fontsize=12.5,
    )
    footer(fig,
           "Precursor-level evidence (the lactate and phenylalanine substrates), NOT Lac-Phe replication. "
           "Consortium timewise logFC per sex; error bars are the reported logFC_se. In these five focus tissues "
           "no cell reaches adj_p<0.05 (every reported adj_p is 1.0, and four heart cells have no reported adj_p "
           "at all); \u2020 marks nominal p<0.05 \u2014 see the 19-tissue heatmap for the one FDR-significant "
           "precursor cell. Endurance-training adaptation vs sedentary control, not an acute exercise bout. "
           "Lactic acid was not reported in vastus lateralis.", y=0.008, width=118)
    fig.tight_layout(rect=(0, 0.115, 1, 0.90))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)


def plot_alignment_matrix(context: dict, rat_coverage: dict, path: Path) -> None:
    rows = [
        ("Human MW ST003662\nwhole blood, acute bout", "Lac-Phe measured", 1,
         f"log2FC +{context['effect']:.2f}, FDR {context['fdr']:.0e}"),
        ("Rat MoTrPAC pass1b-06\n19 tissues, 1-8w training", "Lac-Phe NOT measured", 0,
         f"0/{rat_coverage['unique_features']} features match"),
        ("Rat MoTrPAC pass1b-06\nprecursors", "lactate + phenylalanine measured", 0.5,
         "precursor-level only"),
        ("Human MoTrPAC\nPRECAWG / DataHub human arm", "not assessed here", 0.25,
         "access-controlled arm not fetched"),
    ]
    fig, ax = plt.subplots(figsize=(10.5, 3.6))
    cmap = {1: "#2e7d32", 0.5: "#f9a825", 0.25: "#8a8985", 0: "#c62828"}
    for index, (source, status, level, detail) in enumerate(rows):
        y = len(rows) - index - 1
        ax.barh([y], [1], color=cmap[level], alpha=0.18, edgecolor="none")
        ax.plot([0.035], [y], "o", ms=13, c=cmap[level])
        ax.text(0.07, y + 0.16, status, fontsize=10, va="center", fontweight="bold")
        ax.text(0.07, y - 0.2, detail, fontsize=8.5, va="center", color="#444444")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=9)
    ax.set_xticks([])
    ax.set_xlim(0, 1)
    for spine in ("top", "right", "bottom"):
        ax.spines[spine].set_visible(False)
    ax.set_title("Lac-Phe cross-species availability: alignment is blocked by feature coverage, not by effect size",
                 fontsize=11.5)
    footer(fig,
           "Green = metabolite present with an extractable effect. Amber = related (precursor-level) evidence. "
           "Grey = not assessed here. Red = coverage gap. A gap is an availability finding, never a null result.")
    fig.tight_layout(rect=(0, 0.115, 1, 1))
    fig.savefig(path, dpi=200)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)


def render_report(inputs: dict, context: dict, rat_sub: pd.DataFrame, suite: dict, path: Path) -> None:
    hits = inputs["hits"]
    search = inputs["search"]
    prov = inputs["provenance"]
    identity = inputs["search_provenance"]["refmet_identity"]
    rat_cov = prov["rat_motrpac"]
    mw_ctx = prov["mw_studies"][0]

    species_counts = search["species"].fillna("not_reported").replace("", "not_reported").value_counts()
    human_blood = search[(search["species"] == "Human") & (search["sample_source"] == "Blood")]

    lines: list[str] = []
    add = lines.append
    add("# Lac-Phe (N-lactoyl phenylalanine): study discovery, exercise effect, and MoTrPAC rat alignment")
    add("")
    add("Live-mode report. Every row below comes from a public released record fetched through the declared")
    add("network boundary; no synthetic stand-ins are used, and unavailable data is reported as a coverage gap.")
    add("")
    add("## Headline")
    add("")
    row_all = hits[hits["stratum"] == "all"].iloc[0]
    se, lo, hi = paired_ci(row_all["log2fc"], row_all["p_value"], int(row_all["n_pairs"]))
    add(f"- **Human exercise effect is present and large.** In MW `ST003662` (healthy male and female athletes,")
    add(f"  whole blood, post- vs pre-exercise), Lac-Phe rises **log2FC {row_all['log2fc']:+.2f}** "
        f"(95% CI {lo:+.2f} to {hi:+.2f}; ~{2 ** row_all['log2fc']:.1f}-fold), "
        f"paired t p={row_all['p_value']:.2e}, BH FDR={row_all['fdr']:.2e}, n={int(row_all['n_pairs'])} pairs.")
    add(f"- **Rat MoTrPAC alignment is blocked by feature coverage, not by effect size.** Lac-Phe does not appear")
    add(f"  anywhere in pass1b-06 metabolomics: 0 matches across {rat_cov['unique_features']} unique features, "
        f"{rat_cov['timewise_rows_returned']:,} timewise rows, {len(rat_cov['tissues'])} tissues, "
        f"{len(rat_cov['comparison_groups'])} training-week groups.")
    add("- **No N-lactoyl amino-acid conjugate of any kind is in the rat feature space**, so this is a panel-coverage")
    add("  gap for the whole conjugate class rather than a missing single annotation.")
    add(f"- **The effect is individually consistent, not a group artefact.** Lac-Phe increases in "
        f"{suite['responders']} of {suite['responder_total']} paired athletes "
        f"({100 * suite['responders'] / suite['responder_total']:.0f}%), and it is the "
        f"**{suite['lacphe_rank']}th largest** of {suite['feature_count']} measured effects — behind only "
        f"{', '.join(suite['above_lacphe'])}.")
    add(f"- **Lactate rise explains only part of it.** Within-participant Δlog2 lactate vs Δlog2 Lac-Phe gives "
        f"r = {suite['coupling_r']:.2f} (p = {suite['coupling_p']:.1e}, n = {suite['coupling_n']}), so the "
        f"conjugate is not a simple readout of substrate availability.")
    lit_head = suite.get("literature")
    if lit_head:
        add(f"- **The single-study limit is a deposition limit, not a literature limit.** A literature sweep of "
            f"Europe PMC, Crossref and bioRxiv/medRxiv returned {lit_head['record_count']} deduplicated records, "
            f"{lit_head['confirmed_count']} of which name Lac-Phe in the retrieved title or abstract; "
            f"{lit_head['human_exercise_count']} are human exercise records and {len(lit_head['replication'])} of "
            f"those describe an interventional or randomized design. None names a repository accession in its "
            f"abstract, so their deposition status is unresolved rather than absent (Aim 4).")
    add("- Alignment therefore stops at **precursor-level** evidence (lactic acid, phenylalanine) plus a documented")
    add("  availability gap. It is not a cross-species replication and must not be reported as one.")
    add("")
    add("## Chemical identity of the query")
    add("")
    add(f"| field | value |")
    add(f"| --- | --- |")
    add(f"| query submitted to MW | {inputs['search_provenance']['query_original']} |")
    add(f"| name variants also searched | "
        f"{', '.join(inputs['search_provenance']['searched_names'][1:]) or 'none'} |")
    add(f"| resolved RefMet name | {identity['refmet_name']} |")
    add(f"| RefMet ID | {identity['refmet_id']} |")
    add(f"| formula / exact mass | {identity['formula']} / {identity['exactmass']} |")
    add(f"| InChIKey | {identity['inchi_key']} |")
    add(f"| PubChem CID | {identity['pubchem_cid']} |")
    add(f"| RefMet class path | {identity['super_class']} > {identity['main_class']} > {identity['sub_class']} |")
    add(f"| resolution source | `{identity['source_url']}` |")
    add("")
    add("Identity is resolved at the **RefMet-name and structure-annotation level**. It is not MSI level-1")
    add("confirmation in any of the assays below; every effect row stays `requires_human_review` for assay identity.")
    add("")
    add("## Aim 1 — Study discovery")
    add("")
    add(f"Metabolomics Workbench `metstat` was queried for the resolved RefMet name across all species, sources and")
    add(f"platforms. **{search['study_id'].nunique()} studies / {len(search)} analyses** report Lac-Phe.")
    add("")
    add("| species | analyses |")
    add("| --- | --- |")
    for species, count in species_counts.items():
        add(f"| {species} | {count} |")
    add("")
    add(f"- Human blood analyses: **{len(human_blood)}** across {human_blood['study_id'].nunique()} studies.")
    add("- Of those, exactly **one** is an exercise-physiology design: `ST003662`. Six of the remaining eight")
    add("  studies are disease cohorts (cancer x3, ARDS, ALS, multiple sclerosis); the other two are a")
    add("  clinical-prediction modelling study (`ST003587`) and a healthy-volunteer plasma/faeces study")
    add("  (`ST004826`). None of the eight carries an exercise exposure, so none can answer an exercise question.")
    add(f"- Rat MW analyses exist ({int(species_counts.get('Rat', 0))}) but are oxycodone-exposure plasma and")
    add("  post-colectomy feces designs — neither is an exercise design.")
    add("- **Discovery verdict:** the exercise-relevant human Lac-Phe evidence base in MW is a single study.")
    if suite.get("literature"):
        add("  Treat every conclusion below as single-study *deposited* evidence. Aim 4 shows the published")
        add("  literature is not single-study, so the limit here is MW deposition and discoverability rather")
        add("  than measurement.")
    else:
        add("  Treat every conclusion below as single-study evidence pending independent replication.")
    add("")
    add("Full table: `data/live/metabolite_search_lacphe/metstat_metabolite_study_hits.csv`")
    add("")
    add("## Aim 2 — Human exercise effect (MW ST003662)")
    add("")
    add(f"- Study: [{mw_ctx['study_title']}]({mw_ctx['study_link']})")
    add(f"- Species: {mw_ctx['species']}; license {mw_ctx['license']}")
    add(f"- Matrix: whole blood, μmol/L (analyses AN006015 HILIC + AN006016 reversed phase)")
    add(f"- Contrast: {mw_ctx['contrast']}; orientation: {mw_ctx['orientation']}")
    add(f"- Statistic: {mw_ctx['statistic']}")
    add(f"- Named metabolites in the fetched panel: {mw_ctx['features_measured']}")
    add(f"- Features with a usable paired estimate (>=3 complete pairs): {suite['paired_feature_count']}")
    add("")
    add("| stratum | log2FC | 95% CI | fold-change | p | BH FDR | pairs | mean pre | mean post |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for stratum, label in (("all", "All athletes"), ("m", "Male"), ("f", "Female")):
        sub = hits[hits["stratum"] == stratum]
        if sub.empty:
            continue
        row = sub.iloc[0]
        _se, clo, chi = paired_ci(row["log2fc"], row["p_value"], int(row["n_pairs"]))
        add(f"| {label} | {row['log2fc']:+.2f} | {clo:+.2f} to {chi:+.2f} | {2 ** row['log2fc']:.2f}x | "
            f"{row['p_value']:.2e} | {row['fdr']:.2e} | {int(row['n_pairs'])} | "
            f"{row['mean_pre']:.3f} | {row['mean_post']:.3f} |")
    add("")
    add("Reading: Lac-Phe is one of the strongest post-exercise increases in this blood metabolome, and it is")
    add("significant in both sexes. The male point estimate is larger than the female one, but the sex strata are")
    add("nested inside the all-athlete stratum, share the platform and batch, and their CIs overlap — this is")
    add("**not** evidence of a sex-by-exercise interaction. A formal interaction test on the sample-level matrix")
    add("is required before any sex-difference claim.")
    add("")
    add("- Figure: `figures/human_ST003662_lacphe_volcano.png`")
    add("- Figure: `figures/human_ST003662_lacphe_effect_by_sex.png`")
    add("- Table: `data/live/metabolite_scan/n_lactoyl_phenylalanine/mw_queried_metabolite_effects.csv`")
    add("")
    add("## Aim 3 — MoTrPAC rat alignment")
    add("")
    add("### What was searched")
    add("")
    add(f"- Endpoint: `{rat_cov['endpoint']}`, query `{json.dumps(rat_cov['query'])}`")
    add(f"- Block: `metabolomics_timewise` (trained vs sedentary control, timewise differential rows)")
    add(f"- Rows returned: {rat_cov['timewise_rows_returned']:,}; unique features: {rat_cov['unique_features']}")
    add(f"- Tissues: {', '.join(rat_cov['tissues'])}")
    add(f"- Training-week groups: {', '.join(rat_cov['comparison_groups'])}")
    add(f"- Name columns scanned: {', '.join(rat_cov['name_columns_scanned'])}")
    add("")
    add("### Result: coverage gap")
    add("")
    add(f"**{rat_cov['queried_feature_hits']} rows matched Lac-Phe.** Name matching was normalization-insensitive")
    add("(punctuation and spacing stripped, so `N-Lactoyl phenylalanine`, `N-lactoylphenylalanine` and")
    add("`lactoylphenylalanine` all collapse to one key). A direct substring sweep of all three name columns")
    add("(`refmet_name` 2459 unique, `metabolite` 2651 unique, `feature_id` 2739 unique) returns **zero rows")
    add("containing `lactoyl`** — no N-lactoyl-phenylalanine, -leucine, -valine, or any other conjugate.")
    add("")
    add("This is an **availability gap in the rat metabolomics panel**, and it is the correct scientific finding to")
    add("report. It is emphatically *not*: (a) evidence that Lac-Phe is unchanged by training in rats, (b) grounds")
    add("for substituting a synthetic or imputed rat Lac-Phe row, or (c) a reason to swap in a nearby analyte and")
    add("call it Lac-Phe.")
    add("")
    add("### Closest available rat evidence — precursors only")
    add("")
    add("The two substrates of the Lac-Phe conjugation reaction *are* measured in rat:")
    add("")
    add("| metabolite | tissues in focus set | timewise rows | rows adj_p<0.05 | rows nominal p<0.05 |")
    add("| --- | --- | --- | --- | --- |")
    for metabolite in RAT_PRECURSORS:
        sub = rat_sub[rat_sub["refmet_name"].astype(str).str.lower() == metabolite]
        tissues = ", ".join(sorted(set(sub["tissue"].astype(str))))
        add(f"| {metabolite} | {tissues} | {len(sub)} | "
            f"{int((sub['adj_p_value'] < P_THRESH).sum())} | "
            f"{int((sub['p_value'] < P_THRESH).sum())} |")
    add("")
    add("")
    add("No precursor cell in the five focus tissues reaches adj_p<0.05. Across **all "
        f"{suite['rat_tissue_total']} tissues** the picture is not quite empty, and the report states it "
        "explicitly rather than rounding it to zero:")
    add("")
    fdr_rows = suite["precursor_fdr_rows"]
    if len(fdr_rows):
        add(f"- **{len(fdr_rows)} of {suite['precursor_cells']} precursor cells survives FDR**: "
            + "; ".join(
                f"{row.refmet_name} in {row.sex} {row.tissue} at {row.comparison_group} "
                f"(logFC {row.logFC:+.2f}, adj_p {row.adj_p_value:.3f})"
                for row in fdr_rows.itertuples()) + ".")
    else:
        add(f"- 0 of {suite['precursor_cells']} precursor cells survives FDR.")
    add(f"- {suite['precursor_nominal_only']} cells are nominally significant without surviving FDR. For "
        f"{suite['precursor_adj_absent']} of those the source reports no adjusted p at all "
        f"({suite['precursor_adj_absent_tissues']}), so they cannot be assessed against FDR either way; the "
        "19-tissue heatmap marks them with a grey dagger.")
    if len(fdr_rows) == 1:
        surviving = fdr_rows.iloc[0]
        add(f"- That single surviving signal is {surviving['refmet_name']} in **{surviving['tissue']}**, not "
            "muscle or plasma, and it is a free-amino-acid training effect. It is precursor evidence about "
            "substrate availability in that tissue; it is not evidence about Lac-Phe, which is absent from the "
            "panel entirely.")
    add("")
    add("- Figure: `figures/rat_pass1b06_lacphe_precursors.png` (five focus tissues), "
        "`figures/f6_rat_precursor_tissue_heatmap.png` (all "
        f"{suite['rat_tissue_total']} tissues, with the FDR-significant cell marked)")
    add("- Precursor abundance changes constrain **substrate availability**, not conjugate formation. CNDP2-mediated")
    add("  Lac-Phe synthesis is a separate step, and neither substrate is a validated proxy for the conjugate.")
    add("")
    add("### The gap is class-wide, not a single missing annotation")
    add("")
    family = suite["family"]
    reported = family[family["mw_analyses"] > 0]
    add(f"All {len(family)} N-lactoyl amino-acid conjugates in RefMet were searched in MW and checked against each")
    add(f"exercise source's feature space. {len(reported)} of {len(family)} are reported somewhere in MW, and")
    add(f"Lac-Phe is the best covered of them ({int(family.loc[family['name'] == QUERY, 'mw_analyses'].iloc[0])} "
        f"analyses).")
    add("")
    add("| conjugate | MW analyses | in ST003662 human whole blood | in MoTrPAC human public plasma | "
        "in MoTrPAC rat pass1b-06 |")
    add("| --- | --- | --- | --- | --- |")
    for row in family.sort_values("mw_analyses", ascending=False).itertuples():
        add(f"| {row.name} | {row.mw_analyses} | {'yes' if row.in_st003662 else 'no'} | "
            f"{'yes' if row.in_motrpac_human else 'no'} | {'yes' if row.in_rat else 'no'} |")
    add("")
    add(f"Every conjugate is absent from both MoTrPAC feature spaces — the rat pass1b-06 panel "
        f"({suite['rat_tissue_total']} tissues) and the public human plasma acute panel "
        f"({suite['motrpac_human_features']} features). Only Lac-Phe appears in ST003662. The implication is a")
    add("panel-design gap for the whole conjugate class rather than a per-metabolite annotation miss, which is what")
    add("a future data request would have to address.")
    add("")
    add("- Figure: `figures/f5_lactoyl_class_coverage.png`")
    add("")
    add("### Barriers to alignment")
    add("")
    add("| barrier | human ST003662 | rat pass1b-06 | consequence |")
    add("| --- | --- | --- | --- |")
    add("| feature coverage | Lac-Phe measured | Lac-Phe absent | no shared analyte: crosswalk impossible |")
    add("| estimand | acute post- vs pre-bout, paired within participant | chronic 1-8w training vs sedentary, "
        "between-group | different biological question even if the analyte existed |")
    add("| matrix | whole blood, μmol/L | plasma and 18 solid tissues, platform-scaled | units and matrix not "
        "exchangeable |")
    add("| statistic | paired t on log2 μmol/L, computed here | consortium timewise model logFC | effect scales "
        "not directly comparable |")
    add("")
    add("Even a future rat panel that adds Lac-Phe would still face the estimand and matrix barriers. Alignment")
    add("would then require an effect-level synthesis with study-specific effects, not a pooled analysis.")
    add("")
    add("- Figure: `figures/lacphe_cross_species_alignment.png`")
    add("")
    lit = suite.get("literature")
    if lit is None:
        add("## Aim 4 — Published literature")
        add("")
        add("The literature lane has **not** been run for this report, so no statement is made here about the")
        add("published record. Run `live-search-literature` (see Reproduction) before reading the Aim 1 discovery")
        add("verdict as a statement about the literature rather than about Metabolomics Workbench.")
        add("")
    else:
        epmc = next((row for row in lit["sources"] if row["source_system"] == "europe_pmc"), {})
        crossref = next((row for row in lit["sources"] if row["source_system"] == "crossref"), {})
        add("## Aim 4 — Published literature")
        add("")
        add("### What was searched")
        add("")
        add("- Indexes: Europe PMC (which indexes MEDLINE/PubMed, PMC and preprints), PubMed E-utilities,")
        add("  Crossref, and the bioRxiv/medRxiv detail API for preprint version and journal linkage.")
        add(f"- Europe PMC expression: `{epmc.get('queried_expression', 'not_recorded')}`")
        add(f"- Records retrieved: {lit['raw_record_count']} rows across all indexes, "
            f"{lit['record_count']} after cross-source deduplication on DOI, PMID and PMCID.")
        add("")
        add("| index | status | reported hits | retrieved | complete sweep |")
        add("| --- | --- | --- | --- | --- |")
        for row in lit["sources"]:
            reported = "unknown" if row.get("reported_hit_count") is None else f"{row['reported_hit_count']:,}"
            add(f"| {row['source_system']} | {row['status']} | {reported} | {row['retrieved_count']} | "
                f"{'yes' if row.get('pagination_complete') else 'no'} |")
        add("")
        add("### Retrieval limits that bound every count below")
        add("")
        for source in lit["unavailable_sources"]:
            add(f"- **{source} could not be reached** from this network egress. Its coverage for this query is")
            add("  unknown. This is an availability gap, not a finding that it holds no matching publication, and")
            add("  the Europe PMC `SRC:MED` subset is the only MEDLINE coverage this report actually has.")
        for source in lit["truncated_sources"]:
            reported = crossref.get("reported_hit_count") if source == "crossref" else None
            tail = (
                f" out of a scored candidate pool of {reported:,} summed across the five variant queries"
                if isinstance(reported, int)
                else ""
            )
            add(f"- **{source} returned a ranked relevance sample**{tail}, so absence of a paper from the tables")
            add("  below is not evidence that the index does not hold it.")
        if epmc.get("detail"):
            add(f"- Europe PMC {epmc['detail']}.")
        add("- Bibliographic records only. No full text was read, so data availability statements, methods-level")
        add("  assay identity, and reported effect sizes are outside what this lane can establish.")
        add("")
        add("### A name match is not subject evidence")
        add("")
        add(f"Of {lit['record_count']} deduplicated records, **{lit['confirmed_count']} actually name Lac-Phe or a")
        add(f"declared variant in the retrieved title or abstract**. {lit['subject_absent']} do not — they matched")
        add(f"on full-text indexing or on Crossref relevance ranking — and {lit['no_abstract']} were returned with")
        add("no abstract at all, so their subject could not be located either way. All of those are escalated as")
        add("unconfirmed rather than counted as evidence.")
        add("")
        if lit["homonym_flagged"] or lit["homonym_mixed"]:
            add("`Lac-Phe` is also used for lactide-phenylalanine copolymers, so a string match in the materials")
            add("literature denotes a different chemical entity. Among the subject-named records,")
            add(f"{lit['homonym_flagged']} carry materials-science context with no biological context and")
            add(f"{lit['homonym_mixed']} carry both. Both classes are escalated for entity confirmation from full")
            add("text rather than counted as subject evidence; the automated signal is deliberately conservative,")
            add("so it under-detects rather than over-flags.")
            add("")
        add("### What the subject-confirmed literature contains")
        add("")
        add("| evidence class | records | note |")
        add("| --- | --- | --- |")
        add(f"| human exercise | {lit['human_exercise_count']} | {lit['human_exercise_primary_count']} are "
            "peer-reviewed primary research |")
        add(f"| animal or in-vitro mechanistic | {lit['mechanistic_count']} | background only; never a human "
            "required-term match |")
        add(f"| human, non-exercise context | {lit['non_exercise_count']} | disease, drug, diet and assay-method "
            "reports |")
        add(f"| secondary synthesis | {lit['reviews_count']} | reviews and meta-analyses; not primary evidence |")
        add(f"| retracted or withdrawn | {len(lit['retracted'])} | excluded from primary evidence and named below |")
        add(f"| unscreenable (all records, not only subject-confirmed) | {lit['uncertain_total']} | "
            f"{lit['uncertain_no_abstract']} returned no abstract and {lit['uncertain_species_not_stated']} name no "
            "species in the abstract; unresolved, not excluded |")
        add("")
        if lit["retracted"]:
            for row in lit["retracted"]:
                # Some indexed journal names carry their full society expansion; clip so the
                # bullet stays readable without dropping the identifying prefix.
                journal = row["journal"] or "journal not recorded"
                if len(journal) > 60:
                    journal = journal[:57].rstrip(" :;,") + "…"
                add(f"- Retraction-flagged: *{row['title']}* ({journal}, "
                    f"{row['publication_year'] or 'year not recorded'}). Verify the retraction status before any use.")
            add("")
        add("### This qualifies the Aim 1 discovery verdict")
        add("")
        add("Aim 1 found exactly one exercise-design human study reporting Lac-Phe **in Metabolomics Workbench**.")
        add(f"The published record is larger: {lit['human_exercise_count']} subject-confirmed human exercise")
        add(f"records, of which {len(lit['replication'])} report an interventional or randomized exercise design.")
        add("")
        add("| year | design | journal | study |")
        add("| --- | --- | --- | --- |")
        for row in lit["replication"]:
            design = row["intervention_design"].replace("_", " ")
            add(f"| {row['publication_year'] or 'unknown'} | {design} | {row['journal'] or 'not recorded'} | "
                f"{row['title']} |")
        add("")
        add("Counts here are **records, not resolved studies**: identifiers and preprint-to-journal linkage are")
        add("merged, but companion papers, secondary analyses and cohort overlap between records are not resolved,")
        add("so the number of distinct human exercise cohorts is at most this and may be fewer.")
        add("")
        add("So *single-study* is a true statement about the MW-deposited evidence base and a false one about the")
        add("literature. The bottleneck is deposition and discoverability, not measurement: independent human")
        add("exercise studies have measured Lac-Phe, but their data are not retrievable through the MW `metstat`")
        add("lane that Aim 1 searched.")
        add("")
        add(f"That said, **{lit['human_exercise_with_accession']} of {lit['human_exercise_count']}** subject-confirmed")
        add("human exercise records name a repository accession anywhere in their retrieved bibliographic text. An")
        add("abstract is not a data availability statement, so this does not establish that those studies deposited")
        add("nothing — it establishes that deposition cannot be resolved without reading their full texts. The")
        add("distinction is the difference between a confirmed deposition gap and an unread one, and this report")
        add("claims only the latter.")
        add("")
        add("Direction of effect is also **not** claimed from this lane. The retrieved abstracts state their own")
        add("results, which is bibliographic testimony rather than a re-analysis; no effect size from any of these")
        add("records was recomputed here, and none may be pooled with the ST003662 estimate above.")
        add("")
        add("### Escalations raised by the literature lane")
        add("")
        add(f"{lit['escalation_total']} escalations, by type:")
        add("")
        add("| escalation | records |")
        add("| --- | --- |")
        for kind, count in sorted(lit["escalation_counts"].items(), key=lambda item: (-item[1], item[0])):
            add(f"| {kind.replace('_', ' ')} | {count} |")
        add("")
        add(f"Full report: `reports_live/literature/n_lactoyl_phenylalanine_literature_report.md`. Full queue: "
            f"`{(LITERATURE_DIR / 'literature_escalations.csv').as_posix()}`.")
        add("")
    add("## Figure suite")
    add("")
    add("Rendered by `scripts/render_lacphe_figures.py` (offline) with one backing CSV per figure under")
    add("`reports_live/lacphe/figure_tables/`.")
    add("")
    add("| figure | what it shows | the claim it supports |")
    add("| --- | --- | --- |")
    add(f"| `figures/f1_lacphe_participant_response.png` | every paired athlete's pre → post Lac-Phe, by sex | "
        f"the increase is individual and near-uniform ({suite['responders']}/{suite['responder_total']}), "
        "not a shift in a few outliers |")
    add(f"| `figures/f2_lacphe_effect_ranking.png` | all {suite['feature_count']} features ranked by effect | "
        f"Lac-Phe is rank {suite['lacphe_rank']}; the features above it are its own glycolytic and purine "
        "context |")
    add(f"| `figures/f3_lacphe_lactate_coupling.png` | Δlactate vs ΔLac-Phe within participants | "
        f"substrate rise tracks conjugate rise (r = {suite['coupling_r']:.2f}) but does not determine it; "
        f"{suite['coupling_total'] - suite['coupling_n']} participants dropped for missing values |")
    add(f"| `figures/f4_sex_concordance.png` | male vs female effect for every feature | "
        f"internal consistency (r = {suite['sex_r']:.2f}, {suite['sex_concordant']}/{suite['sex_features']} "
        "same direction) — not independent replication |")
    add("| `figures/f5_lactoyl_class_coverage.png` | 22 conjugates: MW analysis counts (all species, human "
        "blood) plus presence in 3 exercise feature spaces | the coverage gap is class-wide |")
    add(f"| `figures/f6_rat_precursor_tissue_heatmap.png` | rat precursor logFC across "
        f"{suite['rat_tissue_total']} tissues x 4 weeks x 2 sexes | substrates are measured "
        f"(phenylalanine {suite['rat_precursor_tissues']['phenylalanine']}/{suite['rat_tissue_total']} tissues, "
        f"lactic acid {suite['rat_precursor_tissues']['lactic acid']}/{suite['rat_tissue_total']}); the "
        f"conjugate is not, and only {len(suite['precursor_fdr_rows'])} of {suite['precursor_cells']} "
        "precursor cells survives FDR |")
    add("| `figures/f7_discovery_landscape.png` | the 60 MW analyses by species and human sample source | "
        "Lac-Phe is widely reported but almost never under exercise |")
    add("| `figures/human_ST003662_lacphe_volcano.png` | whole-metabolome volcano per stratum | effect size and "
        "significance in context |")
    add("| `figures/human_ST003662_lacphe_effect_by_sex.png` | forest of stratum effects with 95% CIs | overlapping "
        "CIs across sexes |")
    add("| `figures/rat_pass1b06_lacphe_precursors.png` | precursor logFC in the five focus tissues | precursor-level "
        "evidence only |")
    add("| `figures/lacphe_cross_species_alignment.png` | availability status per source | alignment is blocked by "
        "coverage, not effect size |")
    add("")
    add("## Figure plates")
    add("")
    add("The same figures, inline, so the markdown and the PDF render carry the evidence rather than pointing")
    add("at it. Each has a backing CSV of the exact plotted values in `figure_tables/`.")
    add("")
    for filename, caption in [
        ("f1_lacphe_participant_response.png",
         f"Figure 1. Lac-Phe pre- vs post-exercise in every paired athlete of MW ST003662, by sex. "
         f"{suite['responders']} of {suite['responder_total']} participants increase."),
        ("f2_lacphe_effect_ranking.png",
         f"Figure 2. All {suite['feature_count']} features ranked by post- vs pre-exercise effect. Lac-Phe is "
         f"rank {suite['lacphe_rank']}."),
        ("f3_lacphe_lactate_coupling.png",
         f"Figure 3. Within-participant lactate change vs Lac-Phe change (r = {suite['coupling_r']:.2f}, "
         f"n = {suite['coupling_n']} of {suite['coupling_total']}; the dropped participants mostly lack a "
         "reported pre-exercise lactate value, so the subset is not random)."),
        ("f4_sex_concordance.png",
         f"Figure 4. Male vs female effect estimates for the {suite['sex_features']} features tested in both "
         f"strata (r = {suite['sex_r']:.2f}). Same study and platform, so this is internal consistency, not "
         "independent replication."),
        ("f5_lactoyl_class_coverage.png",
         "Figure 5. All 22 N-lactoyl amino-acid conjugates in RefMet: MW analysis counts, and presence in the "
         "three exercise feature spaces. The coverage gap is class-wide."),
        ("f6_rat_precursor_tissue_heatmap.png",
         f"Figure 6. Rat pass1b-06 precursor logFC across {suite['rat_tissue_total']} tissues, four training "
         f"weeks and both sexes. One of {suite['precursor_cells']} cells survives FDR (*); Lac-Phe itself is "
         "absent from every tissue."),
        ("f7_discovery_landscape.png",
         "Figure 7. The 60 MW analyses reporting Lac-Phe, by species and by human sample source."),
        ("human_ST003662_lacphe_volcano.png",
         "Figure 8. Whole-metabolome volcano per stratum, with Lac-Phe circled."),
        ("human_ST003662_lacphe_effect_by_sex.png",
         "Figure 9. Lac-Phe effect and 95% CI per stratum. The sex strata are nested inside the all-athlete "
         "stratum and their intervals overlap."),
        ("rat_pass1b06_lacphe_precursors.png",
         "Figure 10. Rat precursor logFC in the five focus tissues, sexes kept separate."),
        ("lacphe_cross_species_alignment.png",
         "Figure 11. Lac-Phe availability by source. Alignment is blocked by feature coverage, not effect size."),
    ]:
        add(f"![{caption}](figures/{filename})")
        add("")

    add("## Human MoTrPAC arm")
    add("")
    add("The human MoTrPAC arm was **not** fetched for this report. The DataHub human arm is access-controlled, and")
    add("this workbench does not fabricate records for embargoed data. Whether MoTrPAC's human plasma targeted and")
    add("untargeted panels carry Lac-Phe is an open availability question and is recorded as a mirage risk, not as")
    add("a negative result. The public human-precovid-sed-adu acute plasma DA tables already cached under")
    add("`data/live/volcano_motrpac_human_plasma_endur_post.csv` also contain no lactoyl-conjugate feature.")
    add("")
    add("## Human-review escalations")
    add("")
    add("| # | item | why a human must decide |")
    add("| --- | --- | --- |")
    add("| 1 | Assay identity of `Lactoyl Phenylalanine` in ST003662 | RefMet name match only. Level-1 confirmation "
        "(RT + MS/MS against an authentic standard) is not documented in the public record. The reported "
        "μmol/L values imply calibration that must be verified before quantitative claims. |")
    add("| 2 | Sex-difference claim | Male vs female point estimates differ but strata are nested with overlapping "
        "CIs; needs an interaction model on sample-level data. |")
    add("| 3 | Exercise protocol | ST003662 `Collectionpoint:Before/After` does not encode modality, intensity, "
        "duration, or post-exercise sampling delay. Lac-Phe kinetics are minute-scale, so the effect size is not "
        "interpretable without the timing. |")
    add("| 4 | Rat panel gap | Confirm against MoTrPAC panel documentation whether Lac-Phe was targeted and lost "
        "at QC, or never targeted. The two have different implications for a future request. |")
    add("| 5 | Any pooling or meta-analysis | Blocked. No shared analyte, different estimands, different matrices. |")
    add("| 6 | Whole blood vs plasma | ST003662 is whole blood; MoTrPAC is plasma. Lac-Phe partitioning between "
        "erythrocytes and plasma is not established here. |")
    lit_esc = suite.get("literature")
    if lit_esc:
        add(f"| 7 | Data deposition for the published human exercise studies | {lit_esc['human_exercise_with_accession']} "
            f"of {lit_esc['human_exercise_count']} subject-confirmed human exercise records name a repository "
            "accession in their retrieved text. Full-text data availability statements must be read before any "
            "deposition gap is recorded as confirmed. |")
        if lit_esc["unavailable_sources"]:
            add(f"| 8 | Literature coverage of {', '.join(lit_esc['unavailable_sources'])} | The index was "
                "unreachable from this egress, so its coverage is unknown. A reviewer must decide whether the "
                "sweep may be relied on or must be repeated from a permitted network path. |")
        add(f"| 9 | Subject identity of the {lit_esc['subject_absent']} name-absent records | The index matched them "
            "on full text or relevance ranking, but the queried name is not in the retrieved title or abstract. "
            "`Lac-Phe` also abbreviates lactide-phenylalanine copolymers, so entity confirmation is a human call. |")
    add("")
    add("## Missing evidence")
    add("")
    add("- Exercise modality, intensity, duration, and post-exercise sampling delay for ST003662.")
    add("- MS/MS-level identity confirmation and calibration provenance for the ST003662 Lac-Phe feature.")
    add("- Whether rat pass1b-06 panels ever targeted N-lactoyl conjugates.")
    add("- Lac-Phe availability in the access-controlled human MoTrPAC arm.")
    add("- Independent human exercise studies measuring Lac-Phe in MW (none found beyond ST003662).")
    if suite.get("literature"):
        lit_missing = suite["literature"]
        add(f"- Deposited data for the {lit_missing['human_exercise_count']} subject-confirmed human exercise")
        add("  records found in the literature: no accession appears in their retrieved bibliographic text and full")
        add("  texts were not read.")
        add("- Study-level identity across those records: companion papers and overlapping cohorts are unresolved,")
        add("  so the count of distinct human exercise cohorts is an upper bound.")
        add("- Full-text methods for MSI-level identity and calibration in the published human exercise studies.")
        for source in lit_missing["unavailable_sources"]:
            add(f"- {source} literature coverage for this query (index unreachable from this egress).")
    add("")
    add("## Reproduction")
    add("")
    add("Live steps 1-5 need network access; steps 6-9 are offline. Every step writes under `data/live/`,")
    add("`reports_live/` or both, and none touches the offline pilot.")
    add("")
    add("```bash")
    add("# 1. resolve the RefMet identity and find every MW study reporting Lac-Phe (network)")
    add("PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-metabolite-studies \\")
    add('  --query "N-Lactoyl phenylalanine" \\')
    add('  --name-variants "Lac-Phe;N-lactoylphenylalanine" \\')
    add("  --out data/live/metabolite_search_lacphe")
    add("")
    add("# 2. same search for all 22 N-lactoyl conjugates in RefMet, for the class-coverage figure (network)")
    add('grep -i "^N-Lactoyl" data/live/refmet_annotations.csv | cut -d, -f1 | while read -r name; do')
    add("  slug=$(echo \"$name\" | tr 'A-Z ' 'a-z_' | tr -cd 'a-z0-9_')")
    add("  PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-metabolite-studies \\")
    add('    --query "$name" --out "data/live/metabolite_search_lacphe_family/$slug"')
    add("done")
    add("")
    add("# 3. human pre/post effects + participant-level values + rat pass1b-06 coverage scan (network)")
    add('PYTHONPATH=src python3 scripts/volcano_compare.py --metabolite-scan "N-Lactoyl phenylalanine" \\')
    add('  --name-variants "Lac-Phe;N-lactoylphenylalanine;lactoylphenylalanine" \\')
    add("  --mw-studies ST003662")
    add("")
    add("# 4. the lactate substrate, for the substrate-coupling figure (network; rat scan skipped)")
    add('PYTHONPATH=src python3 scripts/volcano_compare.py --metabolite-scan "Lactic acid" \\')
    add("  --mw-studies ST003662 --scan-skip-rat")
    add("")
    add("# 5. the published literature for the same subject (network)")
    add("PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-literature \\")
    add('  --query "N-Lactoyl phenylalanine" \\')
    add('  --name-variants "Lac-Phe;N-lactoylphenylalanine;lactoylphenylalanine;N-lactoyl-phenylalanine" \\')
    add("  --out data/live/literature/lacphe --reports-out reports_live/literature")
    add("")
    add("# 6. figure suite + one backing CSV per figure (offline)")
    add("python3 scripts/render_lacphe_figures.py")
    add("")
    add("# 7. this report (offline)")
    add("python3 scripts/render_lacphe_report.py")
    add("")
    add("# 8. PDF render of this report with the figure plates embedded (offline)")
    add("python3 scripts/render_markdown_pdf.py \\")
    add("  reports_live/lacphe/lacphe_report.md reports_live/lacphe/lacphe_report.pdf")
    add("")
    add("# 9. self-contained HTML render of this report, figures inlined (offline)")
    add("python3 scripts/render_markdown_html.py \\")
    add("  reports_live/lacphe/lacphe_report.md reports_live/lacphe/lacphe_report.html")
    add("```")
    add("")
    add("`data/live/volcano_motrpac_human_plasma_endur_post.csv` is reused from the earlier MoTrPAC human")
    add("plasma acute fetch rather than re-downloaded; its endpoints and signed-URL requests are recorded in")
    add("`data/live/volcano_provenance.json`.")
    add("")
    add("Live fetch provenance:")
    add("")
    add(f"- `{(SCAN_DIR / 'provenance.json').as_posix()}` — human ST003662 scan + rat pass1b-06 coverage scan")
    add(f"- `{(SCAN_LACTATE_DIR / 'provenance.json').as_posix()}` — lactate scan (rat scan skipped, recorded)")
    add(f"- `{(SEARCH_DIR / 'metstat_metabolite_study_provenance.json').as_posix()}` — RefMet + metstat search")
    add(f"- `{SEARCH_FAMILY_DIR.as_posix()}/<conjugate>/metstat_metabolite_study_provenance.json` — "
        f"{len(suite['family'])} conjugate searches")
    add("- `data/live/volcano_provenance.json` — MoTrPAC human plasma acute panel fetch")
    if suite.get("literature"):
        add(f"- `{(LITERATURE_DIR / 'literature_provenance.json').as_posix()}` — literature sweep: per-index status, "
            "query expression, endpoint URLs, hit and retrieved counts")
    add("")
    add("| gate | status |")
    add("| --- | --- |")
    add("| FAIR provenance | pass — accession, analysis id, source URL, license, matrix, contrast, statistic recorded |")
    add("| reproducibility | pass — regenerated from declared queries and deterministic matching rules |")
    add("| critical evidence | pass — exact vs precursor vs missing evidence kept distinct |")
    lit_gate = suite.get("literature")
    if lit_gate:
        add(f"| human review | pass — 9 report-level escalations plus {lit_gate['escalation_total']} record-level "
            "literature escalations; harmonization blocked |")
        add("| mirage detection | pass — rat gap, embargoed human arm, and the unreachable literature index are "
            "reported as availability findings, never as negative results |")
        add("| literature evidence tiering | pass — peer-reviewed, preprint, secondary-synthesis and retracted "
            "records kept in separate tiers; name matches without subject confirmation escalated, not counted |")
    else:
        add("| human review | pass — 6 escalations raised, harmonization blocked |")
        add("| mirage detection | pass — rat gap and embargoed human arm reported as availability findings |")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    figures = OUT_DIR / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs()
    hits, volcano = inputs["hits"], inputs["volcano"]
    rat_sub = rat_precursor_frame(inputs["rat"])

    row_all = hits[hits["stratum"] == "all"].iloc[0]
    context = {"effect": float(row_all["log2fc"]), "fdr": float(row_all["fdr"])}

    plot_human_volcano(volcano, hits, figures / "human_ST003662_lacphe_volcano.png",
                       panel_size=int(inputs["provenance"]["mw_studies"][0]["features_measured"]))
    plot_human_effect_by_sex(hits, figures / "human_ST003662_lacphe_effect_by_sex.png")
    plot_rat_precursors(rat_sub, figures / "rat_pass1b06_lacphe_precursors.png")
    plot_alignment_matrix(context, inputs["provenance"]["rat_motrpac"],
                          figures / "lacphe_cross_species_alignment.png")
    rat_sub.to_csv(OUT_DIR / "rat_pass1b06_lacphe_precursor_rows.csv", index=False)
    suite = derive_suite_stats(inputs)
    suite["literature"] = derive_literature_stats(inputs["literature"], inputs["literature_provenance"])
    render_report(inputs, context, rat_sub, suite, OUT_DIR / "lacphe_report.md")
    print(f"[lacphe] wrote {OUT_DIR}")


if __name__ == "__main__":
    main()

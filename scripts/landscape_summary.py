#!/usr/bin/env python3
"""Summary-landscape figure: 338 human Metabolomics Workbench exercise/activity
candidate studies vs MoTrPAC.

Reads data/live/mw_human_candidates.csv (study summaries fetched from MW REST for
the candidate pool surfaced by exercise/activity/cohort title sweeps) and renders a
4-panel overview to reports_live/. The central finding the figure communicates:
accelerometry is essentially absent from MW deposits, while MoTrPAC collects it but
holds it in the access-controlled human arm.

No network here — operates on the cached CSV. Outputs to reports_live/.

Usage:
    .venv/bin/python scripts/landscape_summary.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CSV = Path("data/live/mw_human_candidates.csv")
OUT = Path("reports_live/landscape_mw_vs_motrpac.png")

# Reference studies to annotate
ST_VOLCANO = "ST004303"            # human acute exercise (our volcano study)
MOTRPAC_HUMAN_N = 2380             # approx human-precovid-sed-adu participants (protocol target)
ACCEL_HITS = 0                     # verified accelerometry studies among the 338
ACCEL_FALSE_POS = 2                # "actical" matched "practical" — excluded


def main():
    df = pd.read_csv(CSV)
    df["n"] = pd.to_numeric(df["number_of_samples"], errors="coerce")
    df["year"] = pd.to_datetime(df["release_date"], errors="coerce").dt.year

    # collapse platform labels
    def plat(a):
        a = str(a)
        if "/" in a:
            return "multi-platform"
        return a
    df["platform"] = df["analysis_type"].map(plat)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Human exercise/activity metabolomics landscape: 338 Metabolomics Workbench studies vs MoTrPAC",
                 fontsize=13, fontweight="bold")

    # ---- A: platform distribution ----
    ax = axes[0, 0]
    vc = df["platform"].value_counts().head(8)[::-1]
    ax.barh(vc.index, vc.values, color="#4c78a8")
    for i, v in enumerate(vc.values):
        ax.text(v + 2, i, str(v), va="center", fontsize=8)
    ax.set_title("A. Assay platform (n=338)", fontsize=10)
    ax.set_xlabel("studies")

    # ---- B: sample-size distribution ----
    ax = axes[0, 1]
    n = df["n"].dropna()
    bins = np.logspace(np.log10(max(n.min(), 1)), np.log10(n.max()), 30)
    ax.hist(n, bins=bins, color="#72b7b2", edgecolor="white")
    ax.set_xscale("log")
    med = n.median()
    ax.axvline(med, color="#333", ls="--", lw=1)
    ax.text(med * 1.1, ax.get_ylim()[1] * 0.9, f"median {int(med)}", fontsize=8)
    st = df.loc[df["study_id"] == ST_VOLCANO, "n"]
    if len(st):
        ax.axvline(float(st.iloc[0]), color="#e45756", lw=1.5)
        ax.text(float(st.iloc[0]) * 1.1, ax.get_ylim()[1] * 0.7,
                f"{ST_VOLCANO}\n(n={int(st.iloc[0])})", fontsize=7, color="#e45756")
    ax.set_title("B. Sample size per study (log scale)", fontsize=10)
    ax.set_xlabel("samples"); ax.set_ylabel("studies")

    # ---- C: studies by release year ----
    ax = axes[1, 0]
    yc = df["year"].value_counts().sort_index()
    ax.bar(yc.index.astype(int), yc.values, color="#54a24b")
    ax.set_title("C. Public release year", fontsize=10)
    ax.set_xlabel("year"); ax.set_ylabel("studies")

    # ---- D: accelerometry availability ----
    ax = axes[1, 1]
    ax.set_title("D. Accelerometry / actigraphy availability", fontsize=10)
    # single stacked bar (left side of the panel)
    ax.bar([0], [338 - ACCEL_HITS], width=0.6, color="#bab0ac", label="no accelerometry")
    ax.bar([0], [ACCEL_HITS], width=0.6, bottom=[338 - ACCEL_HITS], color="#e45756",
           label="has accelerometry")
    ax.set_xlim(-0.6, 4.2)
    ax.set_ylim(0, 360)
    ax.set_xticks([0]); ax.set_xticklabels(["MW\n(n=338)"], fontsize=8)
    ax.set_ylabel("studies")
    ax.text(0, 345, f"{ACCEL_HITS} with\naccelerometry", ha="center", fontsize=7.5, color="#e45756")
    txt = (
        "Searched all 338 mwTab metadata\n"
        "records for accelerometry, actigraphy,\n"
        "Actiwatch, MVPA, step count, wrist/\n"
        "hip-worn, Fitbit, free-living activity,\n"
        "objectively-measured PA.\n\n"
        f"VERIFIED HITS: {ACCEL_HITS} / 338\n"
        "(2 'Actical' = 'prACTICAL' false pos.)\n\n"
        "=> Accelerometry effectively ABSENT\n"
        "   from MW: a missing-modality gap.\n\n"
        "MoTrPAC human collects free-living\n"
        "accelerometry+VO2max+DXA, but those\n"
        "live in the ACCESS-CONTROLLED arm,\n"
        "not the public omics release."
    )
    ax.text(0.30, 0.97, txt, va="top", ha="left", fontsize=7.6, family="monospace",
            transform=ax.transAxes)

    fig.text(0.5, 0.005,
             "Candidate pool: human MW studies surfaced by exercise/activity/fitness/sleep/circadian/obesity/diabetes/aging/cohort/lifestyle "
             "title sweeps (MW REST). Accelerometry verified against full mwTab metadata. MoTrPAC = molecular transducers of physical activity consortium.",
             ha="center", fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(OUT, dpi=150)
    fig.savefig(OUT.with_suffix(".svg"))
    print(f"[done] wrote {OUT} (+ .svg)")
    print(f"studies={len(df)} | platforms={df['platform'].nunique()} | "
          f"median n={int(df['n'].median())} | accel hits={ACCEL_HITS}")


if __name__ == "__main__":
    main()

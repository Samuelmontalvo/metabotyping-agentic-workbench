#!/usr/bin/env python3
"""Render the manuscript's evidence-flow architecture figure."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK = "#24313D"
MUTED = "#5B6670"
INPUT_FILL = "#F3F4F6"
MODEL_FILL = "#E8F1F8"
MODULE_FILL = "#E8F3EF"
OUTPUT_FILL = "#EEF5E9"
REVIEW_FILL = "#FFF0D8"
ACCENT = "#2F6F8F"
REVIEW = "#A96016"


def add_box(ax, x, y, width, height, title, lines, fill, border=INK):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.3,
        edgecolor=border,
        facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.018,
        y + height - 0.045,
        title,
        ha="left",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        x + 0.018,
        y + height - 0.105,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=10.5,
        color=INK,
        linespacing=1.45,
    )


def add_arrow(ax, start, end, color=ACCENT, linewidth=1.8):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=linewidth,
            color=color,
            connectionstyle="arc3,rad=0",
        )
    )


def render(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.2, 7.4), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.03,
        0.95,
        "Evidence flow and review boundaries",
        ha="left",
        va="top",
        fontsize=21,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        0.03,
        0.895,
        "Purpose: determine which datasets can be reused, what evidence is missing, and which decisions require expert review.",
        ha="left",
        va="top",
        fontsize=11.5,
        color=MUTED,
    )

    x_positions = [0.03, 0.275, 0.52, 0.765]
    width = 0.205
    y = 0.33
    height = 0.49

    add_box(
        ax,
        x_positions[0],
        y,
        width,
        height,
        "Inputs",
        [
            "Research question",
            "Publication records",
            "Repository records",
            "Variable dictionaries",
            "Assay and effect tables",
        ],
        INPUT_FILL,
    )
    add_box(
        ax,
        x_positions[1],
        y,
        width,
        height,
        "Evidence models",
        [
            "Inclusion criteria",
            "Source retrieval plan",
            "Study and dataset cards",
            "Chemical identifiers",
            "Assay and QA/QC fields",
        ],
        MODEL_FILL,
    )
    add_box(
        ax,
        x_positions[2],
        y,
        width,
        height,
        "Decision modules",
        [
            "Eligibility and evidence gaps",
            "Variable crosswalks",
            "Metabolite identity",
            "Assay compatibility",
            "Feasibility screening",
            "Plot-table validation",
        ],
        MODULE_FILL,
    )
    add_box(
        ax,
        x_positions[3],
        y,
        width,
        height,
        "Outputs",
        [
            "Ranked candidates",
            "Provenance-bearing cards",
            "Approved transforms",
            "Human-review queue",
            "Plot tables and manifest",
        ],
        OUTPUT_FILL,
    )

    for index in range(3):
        add_arrow(
            ax,
            (x_positions[index] + width + 0.008, y + height / 2),
            (x_positions[index + 1] - 0.008, y + height / 2),
        )

    review_box = FancyBboxPatch(
        (0.275, 0.205),
        0.695,
        0.075,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.3,
        edgecolor=REVIEW,
        facecolor=REVIEW_FILL,
    )
    ax.add_patch(review_box)
    ax.text(
        0.294,
        0.244,
        "Review states",
        ha="left",
        va="center",
        fontsize=11.5,
        fontweight="bold",
        color=REVIEW,
    )
    ax.text(
        0.445,
        0.244,
        "accepted   |   requires human review   |   non-combinable",
        ha="left",
        va="center",
        fontsize=11.5,
        color=INK,
    )
    add_arrow(ax, (0.622, 0.33), (0.622, 0.285), color=REVIEW, linewidth=1.5)

    provenance_box = FancyBboxPatch(
        (0.03, 0.11),
        0.94,
        0.055,
        boxstyle="round,pad=0.006,rounding_size=0.01",
        linewidth=1.0,
        edgecolor="#8A949C",
        facecolor="white",
    )
    ax.add_patch(provenance_box)
    ax.text(
        0.5,
        0.138,
        "Every artifact records source location, rule version, decision rationale, and unresolved evidence.",
        ha="center",
        va="center",
        fontsize=10.5,
        color=INK,
    )

    ax.text(
        0.5,
        0.055,
        "Agent and skill contracts invoke these modules; the evaluated offline workflow does not call a language model.",
        ha="center",
        va="center",
        fontsize=10.5,
        fontweight="bold",
        color=INK,
    )

    png_path = output_dir / "metabotyping_agentic_workbench_architecture.png"
    pdf_path = output_dir / "metabotyping_agentic_workbench_architecture.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/manuscript/figures"),
        help="Output directory for PNG and PDF files.",
    )
    args = parser.parse_args()
    render(args.out)


if __name__ == "__main__":
    main()

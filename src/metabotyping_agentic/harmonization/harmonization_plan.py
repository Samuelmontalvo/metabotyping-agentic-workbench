"""Render review-gated harmonization plans."""

from __future__ import annotations

from pathlib import Path

from ..io import read_csv_rows, write_csv_rows, write_text
from .skeptic import human_review_reason
from .transforms import is_transform_approved


def review_crosswalk(crosswalk_path: str | Path, out_dir: str | Path) -> dict[str, list[dict[str, str]]]:
    rows = read_csv_rows(crosswalk_path)
    buckets = {
        "accepted": [row for row in rows if row["review_status"] == "accepted"],
        "requires_human_review": [row for row in rows if row["review_status"] == "requires_human_review"],
        "rejected": [row for row in rows if row["review_status"] == "rejected"],
    }
    out_dir = Path(out_dir)
    for name, bucket in buckets.items():
        if bucket:
            write_csv_rows(out_dir / f"{name}_crosswalk.csv", bucket)
    review_rows = []
    for row in buckets["requires_human_review"] + buckets["rejected"]:
        review_row = dict(row)
        review_row["human_review_reason"] = human_review_reason(row)
        review_rows.append(review_row)
    if review_rows:
        write_csv_rows(out_dir / "human_review_queue.csv", review_rows)
    return buckets


def _markdown_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        return "_None._\n"
    header = "| " + " | ".join(columns) + " |\n"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |\n"
    body = ""
    for row in rows:
        body += "| " + " | ".join(str(row.get(col, "")).replace("|", "/") for col in columns) + " |\n"
    return header + sep + body


def build_harmonization_plan(crosswalk_path: str | Path, out_dir: str | Path) -> Path:
    rows = read_csv_rows(crosswalk_path)
    accepted = [
        row for row in rows if row["review_status"] == "accepted" and is_transform_approved(row["transform"])
    ]
    review = [row for row in rows if row["review_status"] == "requires_human_review"]
    rejected = [row for row in rows if row["review_status"] == "rejected"]
    missing_metadata = [
        row
        for row in rows
        if row["source_unit"] in {"unknown", "not_reported", ""}
        or row["source_timing"] in {"unknown", "not_reported", ""}
    ]
    impossible = [
        row
        for row in rows
        if row["review_status"] == "rejected" or row["transform"] == "unit_conversion_requires_review"
    ]

    text = f"""# Aim 2 Harmonization Plan

## Inputs

- Crosswalk: `{crosswalk_path}`
- Synthetic source variable dictionary: `data/examples/mock_variable_dictionary.csv`

## Outputs

- Harmonized analysis table: `data/harmonized/harmonized_variables.csv`
- Human review queue: `data/review/human_review_queue.csv`
- Audit log: `data/harmonized/harmonization_audit.json`

## Approved Transformations

{_markdown_table(accepted, ["source_study", "source_variable", "proposed_common_variable", "transform", "confidence"])}

## Proposed Mappings Requiring Review

{_markdown_table(review, ["source_study", "source_variable", "proposed_common_variable", "confidence", "evidence"])}

## Rejected Mappings

{_markdown_table(rejected, ["source_study", "source_variable", "proposed_common_variable", "confidence", "evidence"])}

## Missing Metadata

{_markdown_table(missing_metadata, ["source_study", "source_variable", "source_unit", "source_timing", "source_modality"])}

## Impossible Harmonizations

{_markdown_table(impossible, ["source_study", "source_variable", "proposed_common_variable", "transform", "review_status"])}

## Validation Checks

- Confirm each approved source variable exists in the input dictionary.
- Confirm units match the proposed common unit or an approved transform exists.
- Confirm timing is present for longitudinal or exercise-response variables.
- Confirm no rejected or review-required mappings enter deterministic ETL.

## Failure Conditions

- Missing source files.
- Missing source variable during ETL.
- Unapproved transform.
- Human-review mapping appears in approved ETL input.
- VO₂max/VO₂peak endpoint cannot be documented.

## Human Decisions Required

{_markdown_table([
    {**row, "human_review_reason": human_review_reason(row)} for row in review
], ["source_study", "source_variable", "proposed_common_variable", "human_review_reason"])}
"""
    return write_text(Path(out_dir) / "aim2_harmonization_report.md", text)


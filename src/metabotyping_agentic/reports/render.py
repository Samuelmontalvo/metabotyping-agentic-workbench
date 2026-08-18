"""Markdown report renderers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io import read_csv_rows, read_json, to_plain, write_text
from ..models import BenchmarkResult, MoTrPACAlignment, QualityScore, Recommendation


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_None._\n"
    header = "| " + " | ".join(columns) + " |\n"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |\n"
    body = ""
    for row in rows:
        body += "| " + " | ".join(str(row.get(col, "")).replace("|", "/") for col in columns) + " |\n"
    return header + sep + body


def _first_present(*values: Any) -> Any:
    """Return the first value that is not an empty missing-value sentinel."""

    for value in values:
        if value is not None and value != "":
            return value
    return "missing"


def render_catalog_report(
    recommendations: list[Recommendation],
    out_dir: str | Path,
) -> Path:
    rows = [to_plain(item) for item in recommendations]
    top_rows = rows[:12]
    mirages = [
        {
            "study_id": row["study_id"],
            "score": row["score"],
            "mirage_flags": ", ".join(row["mirage_flags"]),
        }
        for row in rows
        if row["mirage_flags"]
    ]
    text = f"""# Aim 1 Catalog Report

## Candidate Study Ranking

{markdown_table(top_rows, ["study_id", "recommendation_class", "match_class", "score", "rationale"])}

## Mirage Risks

{markdown_table(mirages, ["study_id", "score", "mirage_flags"])}

## Decision Rationale

Ranking rewards required human metabolomics criteria, direct exercise/activity matches, genetics, CPET, body composition, diet, repository accessions, metadata, codebooks, sample size, assay platform, biospecimen timing, and MoTrPAC-like modality coverage.
"""
    return write_text(Path(out_dir) / "aim1_catalog_report.md", text)


def render_human_review_packet(review_dir: str | Path, out_dir: str | Path) -> Path:
    queue_path = Path(review_dir) / "human_review_queue.csv"
    rows = read_csv_rows(queue_path) if queue_path.exists() else []
    text = f"""# Human Review Packet

## Queue

{markdown_table(rows, ["source_study", "source_variable", "proposed_common_variable", "confidence", "human_review_reason"])}

## Reviewer Instructions

- Accept only when biological meaning, unit, modality, timing, and protocol are sufficiently documented.
- Reject mappings that rely only on superficial name similarity.
- Require protocol confirmation before treating VO₂max and VO₂peak as equivalent.
- Approved decisions may be converted into deterministic ETL; review-required decisions may not.
"""
    return write_text(Path(out_dir) / "human_review_packet.md", text)


def render_evaluation_report(scores: list[QualityScore], out_dir: str | Path) -> Path:
    rows = [to_plain(score) for score in scores]
    text = f"""# Aim 3 Evaluation Report

## Dataset-Readiness Scores

{markdown_table(rows, ["study_id", "overall_score", "study_design_rigor", "metadata_completeness", "metabolomics_quality", "harmonization_feasibility"])}

## Interpretation

Scores are transparent, metadata-backed rule-based subscores from 0 to 1. They are curation and harmonization triage signals, not validated judgments of overall study quality, risk of bias, assay validity, or biological evidence strength.
"""
    return write_text(Path(out_dir) / "aim3_evaluation_report.md", text)


def render_motrpac_alignment_report(alignments: list[MoTrPACAlignment], out_dir: str | Path) -> Path:
    rows = [to_plain(item) for item in alignments]
    compact_rows = [
        {
            "study_id": row["study_id"],
            "score": row["score"],
            "tier": row["tier"],
            "missing_elements": ", ".join(row["missing_elements"]),
        }
        for row in rows
    ]
    text = f"""# MoTrPAC Alignment Report

## Metadata Readiness

{markdown_table(compact_rows, ["study_id", "score", "tier", "missing_elements"])}

## Notes

The alignment score records whether candidate metadata contain prerequisites for planning MoTrPAC-style comparisons: human participants, metabolomics, activity/exercise phenotypes, biospecimen timing, sample matrix, assay platform, genetics documentation, CPET/cardiorespiratory fitness, body composition, diet metadata, and variable dictionaries. A metadata-readiness tier does not establish protocol equivalence or biological replication feasibility.
"""
    return write_text(Path(out_dir) / "motrpac_alignment_report.md", text)


def render_benchmark_report(
    results: list[BenchmarkResult],
    out_dir: str | Path,
    *,
    run_bundle: Any | None = None,
) -> Path:
    out_dir = Path(out_dir)
    report_path = out_dir / "benchmark_report.md"
    # ``benchmark()`` renders from its in-memory run bundle before the manifest is
    # written. Preserve an already complete report if a downstream API caller invokes
    # this renderer later without the bundle's provenance.
    if run_bundle is None and report_path.exists():
        return report_path

    rows = [to_plain(result) for result in results]
    metric_rows = []
    denominator_rows = []
    for row in rows:
        details = row.get("details", {})
        interval = details.get("wilson_95_interval")
        interval_text = (
            f"[{interval['lower']}, {interval['upper']}]" if interval else "not applicable"
        )
        value = row.get("value")
        metric_rows.append(
            {
                "metric_name": row["metric_name"],
                "value": value if value is not None else "not applicable",
                "numerator": details.get("numerator"),
                "denominator": (
                    details.get("denominator")
                    if details.get("denominator") is not None
                    else "not applicable"
                ),
                "applicability": details.get("applicability", ""),
                "wilson_95_interval": interval_text,
            }
        )
        denominator_rows.append(
            {
                "metric_name": row["metric_name"],
                "definition": details.get("definition", ""),
                "undefined_reason": details.get("undefined_reason") or "",
            }
        )

    if run_bundle is not None:
        disagreements = run_bundle.disagreement_rows
        input_artifacts = [
            to_plain(artifact) for artifact in run_bundle.input_artifacts
        ]
        metadata = run_bundle.manifest_metadata
    else:
        disagreements_path = out_dir / "benchmark_disagreements.csv"
        disagreements = (
            read_csv_rows(disagreements_path) if disagreements_path.exists() else []
        )
        input_artifacts = []
        metadata = {}
    disagreement_rows = [
        {
            "case_type": row.get("case_type", ""),
            "source_study": row.get("source_study", ""),
            "source_variable": row.get("source_variable", ""),
            "reason_codes": row.get("reason_codes", ""),
            "gold": _first_present(
                row.get("gold_common_variable"),
                row.get("gold_overall_score"),
            ),
            "predicted": _first_present(
                row.get("predicted_common_variable"),
                row.get("predicted_overall_score"),
            ),
            "gold_review_status": row.get("gold_review_status", ""),
            "predicted_review_status": row.get(
                "predicted_review_status",
                "",
            ),
        }
        for row in disagreements
    ]

    provenance_rows = [
        {
            "role": item.get("role", ""),
            "path": item.get("path", ""),
            "state": item.get("state", ""),
            "row_count": (
                item.get("row_count")
                if item.get("row_count") is not None
                else ""
            ),
            "columns": ", ".join(item.get("columns", [])),
            "sha256": item.get("sha256") or "",
        }
        for item in input_artifacts
    ]

    text = f"""# Benchmark Report

## Metrics

{markdown_table(metric_rows, ["metric_name", "value", "numerator", "denominator", "applicability", "wilson_95_interval"])}

Wilson score intervals are 95% intervals for direct proportions. Candidate F1 is derived from candidate error counts rather than a binomial proportion and therefore has no Wilson interval.

## Denominators

{markdown_table(denominator_rows, ["metric_name", "definition", "undefined_reason"])}

## Disagreements

{markdown_table(disagreement_rows, ["case_type", "source_study", "source_variable", "reason_codes", "gold", "predicted", "gold_review_status", "predicted_review_status"])}

Disagreements are review artifacts rather than automatic scientific adjudications. A case's `outcome` is its first reason under the manifest's fixed precedence; `reason_codes` retains every applicable classification. The complete flattened evidence is in `benchmark_disagreements.csv`; the full mapping and quality unions are in `benchmark_case_results.json`.

## Provenance

- Manifest version: {metadata.get("manifest_version", "not available")}
- Benchmark rule-set version: {metadata.get("benchmark_rule_set_version", "not available")}
- Software version: {metadata.get("software_version", "not available")}
- Quality-score tolerance: {metadata.get("quality_score_tolerance", "not available")} (inclusive)

### Inputs

{markdown_table(provenance_rows, ["role", "path", "state", "row_count", "columns", "sha256"])}

The manifest is written after this report is finalized and records SHA-256 hashes for the metrics, full case union, flattened disagreements, and this report.

## Scope

The benchmark compares deterministic MVP outputs against synthetic expert fixtures for exact variable mappings, automatic-accept safety, review routing, exact review statuses, and quality-score agreement. Missing predictions and unexpected predictions remain visible in the full case union. Aggregate metrics are regression evidence, not ground truth.
"""
    return write_text(report_path, text)


def render_harmonization_summary(crosswalk_path: str | Path, out_dir: str | Path) -> Path:
    rows = read_csv_rows(crosswalk_path)
    accepted = [row for row in rows if row["review_status"] == "accepted"]
    review = [row for row in rows if row["review_status"] == "requires_human_review"]
    rejected = [row for row in rows if row["review_status"] == "rejected"]
    text = f"""# Aim 2 Harmonization Report

## Accepted Mappings

{markdown_table(accepted, ["source_study", "source_variable", "proposed_common_variable", "transform", "confidence"])}

## Human Review Queue

{markdown_table(review, ["source_study", "source_variable", "proposed_common_variable", "confidence", "evidence"])}

## Rejected Mappings

{markdown_table(rejected, ["source_study", "source_variable", "proposed_common_variable", "confidence", "evidence"])}
"""
    return write_text(Path(out_dir) / "aim2_harmonization_report.md", text)


def load_json_rows(path: str | Path) -> list[dict[str, Any]]:
    value = read_json(path)
    if isinstance(value, list):
        return value
    return [value]

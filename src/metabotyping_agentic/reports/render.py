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


def render_literature_report(
    review: dict[str, Any],
    out_dir: str | Path,
    *,
    retrieval_provenance: dict[str, Any] | None = None,
    filename: str = "literature_report.md",
    title: str = "Literature Evidence Report",
    top_n: int = 25,
) -> Path:
    """Render the literature screening and appraisal report.

    The report keeps three things visible that a bare citation list hides: which
    indexes were actually reachable, which records could not be screened at all, and
    which publications carry a repository accession that bridges back to retrievable
    data.
    """

    screened = list(review.get("screened") or [])
    summary = review.get("summary") or {}
    escalations = list(review.get("escalations") or [])
    provenance = retrieval_provenance or {}

    def _reported(value: Any) -> str:
        return "unknown" if value is None else f"{value:,}" if isinstance(value, int) else str(value)

    def _clip(value: Any, limit: int = 200) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    source_rows = [
        {
            "source": source.get("source_system", ""),
            "status": source.get("status", ""),
            "reported hits": _reported(source.get("reported_hit_count")),
            "retrieved": source.get("retrieved_count", 0),
            "complete sweep": "yes" if source.get("pagination_complete") else "no",
            "detail": _clip(source.get("detail")),
        }
        for source in provenance.get("sources", []) or []
    ]

    def class_rows(screen_class: str) -> list[dict[str, Any]]:
        return [
            {
                "year": row.get("publication_year") or "unknown",
                "title": row.get("title", ""),
                "journal": row.get("journal") or "unknown",
                "tier": row.get("evidence_tier", ""),
                "species": row.get("species_scope", ""),
                "design": row.get("intervention_design", ""),
                "accessions": row.get("accessions_in_record_text") or "none in retrieved text",
                "review": row.get("review_status", ""),
                "url": row.get("record_url", ""),
            }
            for row in screened
            if row.get("screen_class") == screen_class
        ][:top_n]

    def count_table(counts: dict[str, Any], key_label: str) -> str:
        return markdown_table(
            [{key_label: key, "records": value} for key, value in (counts or {}).items()],
            [key_label, "records"],
        )

    homonym_rows = [
        {
            "homonym risk": row.get("homonym_risk", ""),
            "year": row.get("publication_year") or "unknown",
            "title": row.get("title", ""),
            "journal": row.get("journal") or "unknown",
            "url": row.get("record_url", ""),
        }
        for row in screened
        if row.get("homonym_risk")
        in {"flagged_non_metabolite_homonym_context", "mixed_material_and_biological_context"}
    ][:top_n]
    homonym_absent_note = "_No record carries a materials-science reading of the queried name._\n"

    accession_rows = [
        {
            "accessions": row.get("accessions_in_record_text", ""),
            "screen class": row.get("screen_class", ""),
            "year": row.get("publication_year") or "unknown",
            "title": row.get("title", ""),
            "url": row.get("record_url", ""),
        }
        for row in screened
        if row.get("data_availability_evidence") == "accession_in_record_text"
    ][:top_n]

    escalation_counts: dict[str, int] = {}
    escalation_decisions: dict[str, str] = {}
    for row in escalations:
        kind = row.get("escalation", "")
        escalation_counts[kind] = escalation_counts.get(kind, 0) + 1
        escalation_decisions.setdefault(kind, row.get("decision_needed", ""))
    escalation_summary = [
        {"escalation": kind, "records": count, "decision_needed": escalation_decisions.get(kind, "")}
        for kind, count in sorted(escalation_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    escalations_path = str(review.get("escalations_path") or "the escalations CSV beside this review")

    accession_count = summary.get("records_with_accession_in_text", 0)
    if accession_count:
        accession_section = (
            f"{accession_count} of {summary.get('record_count', 0)} records name a repository accession in "
            "the retrieved text. Namespace counts:\n"
            + count_table(summary.get("accession_namespace_counts"), "namespace")
            + "\n"
            + markdown_table(accession_rows, ["accessions", "screen class", "year", "title", "url"])
        )
    else:
        accession_section = (
            f"No accession appears in the retrieved text of any of the {summary.get('record_count', 0)} "
            "records. Abstracts rarely carry accessions, so this says nothing about whether these studies "
            "deposited data; it says the bridge to retrievable data cannot be built from bibliographic "
            "records alone."
        )

    unavailable = list(summary.get("unavailable_sources") or [])
    truncated = list(summary.get("truncated_sources") or [])
    gap_lines = []
    for source in unavailable:
        gap_lines.append(
            f"- **{source} was unreachable.** Its coverage for this query is unknown. This is an availability "
            "gap, not a finding that no matching publication exists."
        )
    for source in truncated:
        gap_lines.append(
            f"- **{source} returned a ranked sample, not a complete sweep.** Absence of a paper from the "
            "table below is not evidence that it does not exist."
        )
    if not gap_lines:
        gap_lines.append("- Every queried index answered, and each reported result set was retrieved in full.")

    columns = ["year", "title", "journal", "tier", "species", "design", "accessions", "review", "url"]
    text = f"""# {title}

Screening and appraisal of retrieved bibliographic records. Retrieval provenance is preserved per
source; screening flags state whether they came from a structured field or from title/abstract text.
No relevance, quality, or replication claim is made from a bibliographic hit alone.

## Query

- Query: `{review.get("query") or provenance.get("query_original") or "not_recorded"}`
- Name variants searched: {", ".join(provenance.get("name_variants_searched", []) or []) or "none"}
- Context terms: {", ".join(provenance.get("context_terms", []) or []) or "none"}
- Records after cross-source deduplication: {summary.get("record_count", 0)}
- Records requiring human review: {summary.get("review_required_count", 0)}

## Retrieval provenance

{markdown_table(source_rows, ["source", "status", "reported hits", "retrieved", "complete sweep", "detail"])}

### Retrieval gaps

{chr(10).join(gap_lines)}

## Screening classes

{count_table(summary.get("screen_class_counts"), "screen class")}

## Evidence tiers

{count_table(summary.get("evidence_tier_counts"), "evidence tier")}

## Species scope of the retrieved evidence

{count_table(summary.get("species_scope_counts"), "species scope")}

Species scope is inferred from retrieved title and abstract text unless the basis column says
`structured_field`. `not_stated_in_retrieved_text` means the text carried no species term; it does not
mean the study had no species.

## Subject-name evidence and homonym risk

Declared subject terms: {", ".join(review.get("subject_terms", []) or []) or "none declared"}

{count_table(summary.get("subject_term_evidence_counts"), "subject-name evidence")}
{count_table(summary.get("homonym_risk_counts"), "homonym risk")}

A record matched by a full-text index whose retrieved title and abstract never name the queried subject
cannot be confirmed as subject evidence from the record alone. Where the name appears only alongside
materials-science context terms, the string may denote a different chemical entity that shares the
abbreviation; those records are escalated rather than counted as subject evidence.

{markdown_table(homonym_rows, ["homonym risk", "year", "title", "journal", "url"]) if homonym_rows else homonym_absent_note}

## Direct human exercise records

{markdown_table(class_rows("direct_human_exercise"), columns)}

## Human, non-exercise context

{markdown_table(class_rows("human_non_exercise_context"), columns)}

## Animal or in-vitro mechanistic background

Retained as mechanistic background. These records never satisfy a human required term.

{markdown_table(class_rows("animal_or_invitro_mechanistic"), columns)}

## Secondary synthesis (reviews, meta-analyses)

{markdown_table(class_rows("secondary_synthesis"), columns)}

## Unscreenable records

Retrieved records that could not be screened: either no abstract was returned, or the abstract names no
species and carries no decisive modality signal. The `screen_basis` column in the screened CSV gives the
reason per record. These are unresolved, not excluded.

{markdown_table(class_rows("screening_uncertain_insufficient_text"), columns)}

## Accession bridge to retrievable data

{accession_section}

A record with no accession in its retrieved text is an open question about deposition, not a confirmed
deposition gap: bibliographic text is not a data availability statement.

## Human-review escalations

{len(escalations)} escalation(s) raised. The full queue is in `{escalations_path}`; the counts below are
the queue by type, followed by the first {top_n} rows.

{markdown_table(escalation_summary, ["escalation", "records", "decision_needed"])}

{markdown_table(escalations[:top_n], ["escalation", "reason", "decision_needed", "title", "record_url"])}

## Evaluation gates

| gate | status |
| --- | --- |
| FAIR provenance | {"pass" if source_rows or screened else "fail"} — every record keeps source system, source URL, and identifiers |
| reproducibility | pass — screening is regenerated offline from the declared record set with deterministic rules |
| critical evidence | pass — structured evidence, text inference, and unknown-for-lack-of-text are distinct values |
| human review | pass — {len(escalations)} escalation(s) raised |
| mirage detection | pass — unreachable and truncated sources are reported as availability gaps, never as zero hits |
"""
    return write_text(Path(out_dir) / filename, text)


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

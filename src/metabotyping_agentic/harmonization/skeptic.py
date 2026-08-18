"""Scientific skepticism helpers for harmonization review."""

from __future__ import annotations


def human_review_reason(row: dict[str, str]) -> str:
    status = row.get("review_status", "")
    variable = row.get("proposed_common_variable", "")
    evidence = row.get("evidence", "")
    if status == "accepted":
        return "No human decision required before deterministic ETL."
    if variable == "vo2max" and ("VO2peak" in evidence or "protocol" in evidence):
        return "Confirm exercise test protocol and whether endpoint was VO2max or VO2peak."
    if row.get("transform") == "unit_conversion_requires_review":
        return "Confirm unit conversion and biological comparability before harmonization."
    if status == "rejected":
        return "Rejected by deterministic guardrail; only override with documented expert rationale."
    return "Human review required because confidence or metadata completeness is insufficient."


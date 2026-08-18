"""Query parsing into deterministic inclusion criteria."""

from __future__ import annotations

from ..models import InclusionCriteria

PREFERRED_TERMS = [
    "exercise",
    "actigraphy",
    "physical activity",
    "genetics",
    "cpet",
    "body composition",
    "diet",
]

COMPLEMENTARY_TERMS = [
    "omics phenotype overlap",
    "non-exercise metabolomics with genetics",
    "activity/body-composition/diet enrichment metadata",
]


def define_inclusion_criteria(query: str) -> InclusionCriteria:
    query_lower = query.lower()
    preferred = [term for term in PREFERRED_TERMS if term in query_lower]
    if "physical activity" not in preferred and "activity" in query_lower:
        preferred.append("physical activity")
    if "vo2" in query_lower and "cpet" not in preferred:
        preferred.append("cpet")
    if not preferred:
        preferred = ["exercise", "actigraphy", "genetics", "cpet", "body composition", "diet"]

    notes = [
        "Required terms are intentionally strict: human and metabolomics.",
        "Complementary datasets may lack exercise but must improve omics/phenotype enrichment.",
        "Animal-only, cell-only, and no-metabolomics studies are exclusions.",
    ]
    if "motrpac" in query_lower:
        notes.append(
            "Query explicitly requests MoTrPAC-style metadata-readiness relevance."
        )

    return InclusionCriteria(
        query=query,
        preferred_terms=preferred,
        complementary_terms=COMPLEMENTARY_TERMS,
        notes=notes,
    )

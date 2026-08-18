"""Sample matrix predicates shared across discovery and live-source adapters."""

from __future__ import annotations

import re

BLOOD_DERIVED_SAMPLE_MATRIX_TERMS = ("blood", "plasma", "serum")


def has_blood_derived_sample_matrix(sample_matrix: str | None) -> bool:
    """Return true when a sample matrix names a blood-derived biospecimen."""

    text = (sample_matrix or "").strip().lower()
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in BLOOD_DERIVED_SAMPLE_MATRIX_TERMS)


def is_metabolomics_workbench_repository(repository_name: str | None) -> bool:
    """Identify Metabolomics Workbench repository labels from normalized records."""

    text = (repository_name or "").strip().lower()
    return text in {"metabolomics workbench", "metabolomicsworkbench", "mw", "mwb"}


def looks_like_metabolomics_workbench_accession(accession: str | None) -> bool:
    """Identify common Metabolomics Workbench study/accession identifiers."""

    text = (accession or "").strip().upper()
    return bool(text.startswith("MWB-") or re.fullmatch(r"ST\d{6}", text))

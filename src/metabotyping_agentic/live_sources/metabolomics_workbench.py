"""Metabolomics Workbench live metadata intake.

The adapter is intentionally metadata-first. It does not persist sample-level
factor rows or quantitative data matrices; it writes normalized CSV inputs that
the existing deterministic workbench can ingest.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..evaluation.motrpac_alignment import align_motrpac
from ..evaluation.quality_scoring import score_quality
from ..extraction.metadata_cards import extract_metadata_cards
from ..extraction.variable_inventory import extract_variable_inventory
from ..io import ensure_dir, parse_int, write_csv_rows, write_json
from ..reports.render import render_evaluation_report, render_motrpac_alignment_report
from ..sample_matrix import has_blood_derived_sample_matrix

BASE_URL = "https://www.metabolomicsworkbench.org/rest"
DEFAULT_TIMEOUT_SECONDS = 30
USER_AGENT = "metabotyping-agentic-workbench/0.1"


@dataclass(frozen=True)
class LiveIntakeResult:
    """Paths and counts from a live metadata intake run."""

    study_id: str
    out_dir: Path
    repository_records_path: Path
    publications_path: Path
    variable_dictionary_path: Path | None
    extracted_dir: Path
    reports_dir: Path
    metabolite_count: int
    sample_count: int | None
    data_endpoint_checked: bool
    data_endpoint_available: bool


Fetcher = Callable[[str], Any]
AvailabilityChecker = Callable[[str], bool]


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """Fetch JSON from a public URL using only the Python standard library."""

    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit public data adapter
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"Metabolomics Workbench request failed with HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Metabolomics Workbench request failed: {url}") from exc
    if not body.strip():
        raise RuntimeError(f"Metabolomics Workbench returned an empty response: {url}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        snippet = body[:160].replace("\n", " ")
        raise RuntimeError(f"Metabolomics Workbench returned non-JSON content: {snippet}") from exc


def endpoint_has_content(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bool:
    """Check whether an endpoint returns a non-empty successful response without storing it."""

    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit public data adapter
            return 200 <= response.status < 300 and bool(response.read(1))
    except (HTTPError, URLError, TimeoutError):
        return False


def _study_url(study_id: str, output: str) -> str:
    return f"{BASE_URL}/study/study_id/{study_id}/{output}"


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    values = list(payload.values())
    if values and all(isinstance(item, dict) for item in values):
        return values
    return [payload]


def _text_blob(*parts: Any) -> str:
    text_parts: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text_parts.extend(str(value) for value in part.values())
        elif isinstance(part, list):
            text_parts.extend(_text_blob(item) for item in part)
        else:
            text_parts.append(str(part))
    return " ".join(text_parts).lower()


def _contains_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _infer_publication_flags(summary: dict[str, Any], factor_summary: dict[str, Any]) -> dict[str, bool]:
    text = _text_blob(summary, factor_summary)
    human = _contains_any(text, [r"\bhomo sapiens\b", r"\bhuman\b"])
    exercise = _contains_any(
        text,
        [
            r"\bexercise\b",
            r"\bendurance\b",
            r"\bresistance\b",
            r"\btraining\b",
            r"\btreadmill\b",
            r"\brun\b",
            r"\brunning\b",
        ],
    )
    return {
        "human": human,
        "exercise": exercise,
        "actigraphy": _contains_any(text, [r"\bactigraphy\b", r"\bacceleromet"]),
        "metabolomics": True,
        "genetics": _contains_any(text, [r"\bgenetic", r"\bgenomic", r"\bgenotype"]),
        "cpet": _contains_any(text, [r"\bcpet\b", r"cardiopulmonary", r"\bvo2", r"oxygen consumption"]),
        "body_composition": _contains_any(text, [r"body composition", r"\bdxa\b", r"\bfat mass\b", r"\blean mass\b"]),
        "diet": _contains_any(text, [r"\bdiet\b", r"\bnutrition\b", r"\bfood\b"]),
    }


def _modalities(flags: dict[str, bool]) -> str:
    names = [
        "metabolomics",
        "exercise",
        "actigraphy",
        "genetics",
        "cpet",
        "body_composition",
        "diet",
    ]
    values = [name for name in names if flags.get(name)]
    return ";".join(values or ["unknown"])


def _analysis_records_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("analysis_id")): record for record in records if record.get("analysis_id")}


def _summarize_assay_platform(analysis_records: list[dict[str, Any]]) -> str:
    if not analysis_records:
        return "unknown"
    platform_parts: list[str] = []
    for record in analysis_records:
        parts = [
            record.get("analysis_type"),
            record.get("chromatography_type"),
            record.get("ms_instrument_type") or record.get("nmr_instrument_type"),
        ]
        platform = " ".join(str(part).strip() for part in parts if str(part or "").strip())
        if platform:
            platform_parts.append(platform)
    unique = sorted(set(platform_parts))
    return "; ".join(unique) if unique else "unknown"


def _summarize_factors(factor_records: list[dict[str, Any]]) -> dict[str, Any]:
    sample_sources = sorted(
        {str(record.get("sample_source", "")).strip() for record in factor_records if record.get("sample_source")}
    )
    factor_values: set[str] = set()
    for record in factor_records:
        factors = str(record.get("factors", "")).strip()
        if not factors:
            continue
        for part in re.split(r"\s*\|\s*", factors):
            if part:
                factor_values.add(part)
    return {
        "sample_count": len(factor_records) or None,
        "sample_matrix": "; ".join(sample_sources) if sample_sources else "unknown",
        "biospecimen_timing": "; ".join(sorted(factor_values)) if factor_values else "unknown",
        "factor_value_count": len(factor_values),
    }


def _publication_row(
    study_id: str,
    summary: dict[str, Any],
    factor_summary: dict[str, Any],
    flags: dict[str, bool],
) -> dict[str, Any]:
    title = summary.get("study_title") or f"Metabolomics Workbench study {study_id}"
    notes = [
        "Live metadata imported from the Metabolomics Workbench REST API.",
        "Sample-level factors and quantitative data matrices were not persisted by this adapter.",
    ]
    if summary.get("license"):
        notes.append(f"License: {summary['license']}.")
    if factor_summary.get("factor_value_count"):
        notes.append(f"Unique factor labels summarized: {factor_summary['factor_value_count']}.")
    return {
        "study_id": study_id,
        "title": title,
        "doi": "not_reported",
        "pmid": "not_reported",
        "human": flags["human"],
        "exercise": flags["exercise"],
        "actigraphy": flags["actigraphy"],
        "metabolomics": flags["metabolomics"],
        "genetics": flags["genetics"],
        "cpet": flags["cpet"],
        "body_composition": flags["body_composition"],
        "diet": flags["diet"],
        "repository_accession": study_id,
        "notes": " ".join(notes),
    }


def _repository_row(
    study_id: str,
    summary: dict[str, Any],
    analysis_records: list[dict[str, Any]],
    factor_summary: dict[str, Any],
    metabolite_count: int,
    data_endpoint_available: bool,
    flags: dict[str, bool],
) -> dict[str, Any]:
    sample_count = parse_int(summary.get("number_of_samples")) or factor_summary.get("sample_count")
    return {
        "study_id": study_id,
        "repository": "Metabolomics Workbench",
        "accession": study_id,
        "public_status": "public",
        "has_metadata": bool(summary and analysis_records),
        "has_codebook": metabolite_count > 0,
        "has_data_files": data_endpoint_available,
        "assay_platform": _summarize_assay_platform(analysis_records),
        "sample_matrix": factor_summary.get("sample_matrix") or "unknown",
        "biospecimen_timing": factor_summary.get("biospecimen_timing") or "unknown",
        "sample_size": sample_count,
        "modalities": _modalities(flags),
    }


def _variable_rows(
    study_id: str,
    metabolite_records: list[dict[str, Any]],
    analysis_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, record in enumerate(metabolite_records, start=1):
        analysis_id = str(record.get("analysis_id") or "analysis_not_reported")
        metabolite_name = str(record.get("metabolite_name") or "").strip()
        refmet_name = str(record.get("refmet_name") or "").strip()
        label = refmet_name or metabolite_name or f"metabolite_{index}"
        key = (analysis_id, label)
        if key in seen:
            continue
        seen.add(key)
        analysis = analysis_by_id.get(analysis_id, {})
        rows.append(
            {
                "study_id": study_id,
                "source_variable": f"{analysis_id}::{label}",
                "label": label,
                "unit": analysis.get("units") or "unknown",
                "timing": "not_reported",
                "modality": "metabolomics",
                "description": (
                    f"Metabolomics Workbench named metabolite. "
                    f"Reported name: {metabolite_name or 'not_reported'}; "
                    f"RefMet: {refmet_name or 'not_reported'}."
                ),
            }
        )
    return rows


def ingest_metabolomics_workbench_study(
    study_id: str,
    out_dir: str | Path,
    *,
    fetcher: Fetcher = fetch_json,
    availability_checker: AvailabilityChecker = endpoint_has_content,
    check_data_endpoint: bool = True,
    require_blood_derived_sample_matrix: bool = True,
) -> LiveIntakeResult:
    """Fetch a public Metabolomics Workbench study and run local review artifacts."""

    study_id = study_id.strip().upper()
    out_dir = ensure_dir(out_dir)
    raw_dir = ensure_dir(out_dir / "source_summaries")
    normalized_dir = ensure_dir(out_dir / "normalized")
    extracted_dir = ensure_dir(out_dir / "extracted")
    reports_dir = ensure_dir(out_dir / "reports")

    summary = fetcher(_study_url(study_id, "summary"))
    analysis_records = _records(fetcher(_study_url(study_id, "analysis")))
    factor_records = _records(fetcher(_study_url(study_id, "factors")))
    metabolite_records = _records(fetcher(_study_url(study_id, "metabolites")))
    factor_summary = _summarize_factors(factor_records)
    if require_blood_derived_sample_matrix and not has_blood_derived_sample_matrix(
        factor_summary.get("sample_matrix")
    ):
        sample_matrix = factor_summary.get("sample_matrix") or "unknown"
        raise ValueError(
            f"Metabolomics Workbench study {study_id} has sample_matrix={sample_matrix!r}; "
            "default live intake only accepts blood-derived matrices containing blood, plasma, or serum."
        )
    data_url = _study_url(study_id, "data")
    data_endpoint_available = availability_checker(data_url) if check_data_endpoint else False

    flags = _infer_publication_flags(summary, factor_summary)
    analysis_by_id = _analysis_records_by_id(analysis_records)
    variable_rows = _variable_rows(study_id, metabolite_records, analysis_by_id)
    publication_rows = [_publication_row(study_id, summary, factor_summary, flags)]
    repository_rows = [
        _repository_row(
            study_id,
            summary,
            analysis_records,
            factor_summary,
            len(variable_rows),
            data_endpoint_available,
            flags,
        )
    ]

    repository_records_path = write_csv_rows(
        normalized_dir / "repository_records.csv",
        repository_rows,
        [
            "study_id",
            "repository",
            "accession",
            "public_status",
            "has_metadata",
            "has_codebook",
            "has_data_files",
            "assay_platform",
            "sample_matrix",
            "biospecimen_timing",
            "sample_size",
            "modalities",
        ],
    )
    publications_path = write_csv_rows(
        normalized_dir / "publications.csv",
        publication_rows,
        [
            "study_id",
            "title",
            "doi",
            "pmid",
            "human",
            "exercise",
            "actigraphy",
            "metabolomics",
            "genetics",
            "cpet",
            "body_composition",
            "diet",
            "repository_accession",
            "notes",
        ],
    )
    variable_dictionary_path: Path | None = None
    if variable_rows:
        variable_dictionary_path = write_csv_rows(
            normalized_dir / "variable_dictionary.csv",
            variable_rows,
            ["study_id", "source_variable", "label", "unit", "timing", "modality", "description"],
        )
        extract_variable_inventory(variable_dictionary_path, extracted_dir)

    write_json(
        raw_dir / "metabolomics_workbench_summary.json",
        {
            "study_id": study_id,
            "source_urls": {
                "summary": _study_url(study_id, "summary"),
                "analysis": _study_url(study_id, "analysis"),
                "factors": _study_url(study_id, "factors"),
                "metabolites": _study_url(study_id, "metabolites"),
                "data": data_url,
            },
            "summary": summary,
            "analysis_count": len(analysis_records),
            "sample_count": factor_summary.get("sample_count"),
            "sample_matrix": factor_summary.get("sample_matrix"),
            "biospecimen_timing": factor_summary.get("biospecimen_timing"),
            "metabolite_count": len(variable_rows),
            "data_endpoint_checked": check_data_endpoint,
            "data_endpoint_available": data_endpoint_available,
            "note": "Sample-level factors and quantitative data matrices were not persisted.",
        },
    )

    extract_metadata_cards(repository_records_path, extracted_dir, publications_path)
    scores = score_quality(extracted_dir, extracted_dir)
    alignments = align_motrpac(extracted_dir, reports_dir)
    render_evaluation_report(scores, reports_dir)
    render_motrpac_alignment_report(alignments, reports_dir)

    return LiveIntakeResult(
        study_id=study_id,
        out_dir=out_dir,
        repository_records_path=repository_records_path,
        publications_path=publications_path,
        variable_dictionary_path=variable_dictionary_path,
        extracted_dir=extracted_dir,
        reports_dir=reports_dir,
        metabolite_count=len(variable_rows),
        sample_count=factor_summary.get("sample_count"),
        data_endpoint_checked=check_data_endpoint,
        data_endpoint_available=data_endpoint_available,
    )


# ---------------------------------------------------------------------------
# Metabolite -> study discovery lane (RefMet name search)
# ---------------------------------------------------------------------------

METSTAT_FIELDS = (
    "analysis_type",
    "polarity",
    "chromatography",
    "species",
    "sample_source",
    "disease",
    "kegg_id",
    "refmet_name",
)


def _refmet_url(name: str, output: str) -> str:
    return f"{BASE_URL}/refmet/name/{quote(name)}/{output}"


def _metstat_url(refmet_name: str) -> str:
    # metstat takes a fixed positional filter string; empty slots mean "no filter".
    # metstat parses literal semicolons as slot separators, so only the slot
    # values are percent-encoded.
    filters = ["", "", "", "", "", "", "", refmet_name]
    encoded = ";".join(quote(value, safe="") for value in filters)
    return f"{BASE_URL}/metstat/{encoded}"


def resolve_refmet_entry(name: str, *, fetcher: Fetcher = fetch_json) -> dict[str, Any]:
    """Resolve a user-supplied metabolite name to a RefMet entry, preserving the query."""

    url = _refmet_url(name, "all")
    try:
        payload = fetcher(url)
    except RuntimeError as exc:
        return {
            "query_original": name,
            "resolved": False,
            "source_url": url,
            "error": str(exc),
        }
    records = _records(payload)
    record = records[0] if records else {}
    refmet_name = str(record.get("refmet_name") or record.get("name") or "").strip()
    return {
        "query_original": name,
        "resolved": bool(refmet_name),
        "refmet_name": refmet_name,
        "refmet_id": str(record.get("refmet_id") or "").strip(),
        "formula": str(record.get("formula") or "").strip(),
        "exactmass": str(record.get("exactmass") or "").strip(),
        "super_class": str(record.get("super_class") or "").strip(),
        "main_class": str(record.get("main_class") or "").strip(),
        "sub_class": str(record.get("sub_class") or "").strip(),
        "inchi_key": str(record.get("inchi_key") or "").strip(),
        "pubchem_cid": str(record.get("pubchem_cid") or "").strip(),
        "source_url": url,
    }


def search_studies_by_refmet_name(
    refmet_name: str,
    *,
    fetcher: Fetcher = fetch_json,
) -> dict[str, Any]:
    """Return MW study/analysis rows that report a named RefMet metabolite."""

    url = _metstat_url(refmet_name)
    try:
        payload = fetcher(url)
    except RuntimeError as exc:
        return {"refmet_name": refmet_name, "source_url": url, "rows": [], "error": str(exc)}
    def field(record: dict[str, Any], *names: str) -> str:
        # metstat labels differ from the study endpoints ("study"/"analysis"/"source"),
        # so accept both spellings rather than dropping the value.
        for name in names:
            value = str(record.get(name) or "").strip()
            if value:
                return value
        return ""

    rows: list[dict[str, Any]] = []
    for record in _records(payload):
        study_id = field(record, "study_id", "study")
        if not study_id:
            continue
        rows.append(
            {
                "query_refmet_name": refmet_name,
                "study_id": study_id,
                "analysis_id": field(record, "analysis_id", "analysis"),
                "study_title": field(record, "study_title"),
                "species": field(record, "species"),
                "sample_source": field(record, "sample_source", "source"),
                "analysis_type": field(record, "analysis_type"),
                "polarity": field(record, "polarity"),
                "chromatography": field(record, "chromatography", "chromatography_type"),
                "disease": field(record, "disease"),
                "refmet_name": field(record, "refmet_name") or refmet_name,
                "refmet_id": field(record, "refmet_id"),
                "inchi_key": field(record, "inchi_key"),
                "pubchem_cid": field(record, "pubchem_cid"),
                "super_class": field(record, "super_class"),
                "main_class": field(record, "main_class"),
                "sub_class": field(record, "sub_class"),
                "study_link": f"https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID={study_id}",
                "source_system": "metabolomics_workbench_metstat",
                "provenance_url": url,
            }
        )
    return {"refmet_name": refmet_name, "source_url": url, "rows": rows}


def search_metabolite_studies(
    query: str,
    out_dir: str | Path,
    *,
    name_variants: list[str] | None = None,
    fetcher: Fetcher = fetch_json,
) -> dict[str, Any]:
    """Discover MW studies reporting a metabolite and record full search provenance.

    Name resolution and retrieval only: every returned row stays review-required for
    MSI-level assay identity, and absent rows are reported as coverage gaps rather
    than inferred measurements.
    """

    out_dir = ensure_dir(out_dir)
    identity = resolve_refmet_entry(query, fetcher=fetcher)
    candidates: list[str] = []
    for candidate in [identity.get("refmet_name") or "", query, *(name_variants or [])]:
        candidate = candidate.strip()
        if candidate and candidate.lower() not in {item.lower() for item in candidates}:
            candidates.append(candidate)

    searches: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        result = search_studies_by_refmet_name(candidate, fetcher=fetcher)
        searches.append(
            {
                "queried_name": candidate,
                "source_url": result["source_url"],
                "row_count": len(result["rows"]),
                "error": result.get("error", ""),
            }
        )
        for row in result["rows"]:
            key = (row["study_id"], row["analysis_id"])
            if key in seen:
                continue
            seen.add(key)
            row["match_basis"] = (
                "refmet_name_exact"
                if candidate.lower() == (identity.get("refmet_name") or "").lower()
                else "refmet_name_variant"
            )
            row["review_status"] = "requires_human_review"
            row["decision_scope"] = "retrieval_only"
            row["harmonization_eligibility"] = "requires_assay_identity_review"
            rows.append(row)

    rows.sort(key=lambda row: (row["species"].lower(), row["study_id"]))
    fieldnames = [
        "query_refmet_name",
        "match_basis",
        "review_status",
        "decision_scope",
        "harmonization_eligibility",
        "study_id",
        "analysis_id",
        "study_title",
        "species",
        "sample_source",
        "analysis_type",
        "polarity",
        "chromatography",
        "disease",
        "refmet_name",
        "refmet_id",
        "inchi_key",
        "pubchem_cid",
        "super_class",
        "main_class",
        "sub_class",
        "study_link",
        "source_system",
        "provenance_url",
    ]
    hits_path = write_csv_rows(out_dir / "metstat_metabolite_study_hits.csv", rows, fieldnames)
    provenance_path = write_json(
        out_dir / "metstat_metabolite_study_provenance.json",
        {
            "query_original": query,
            "refmet_identity": identity,
            "searched_names": candidates,
            "searches": searches,
            "study_count": len({row["study_id"] for row in rows}),
            "analysis_row_count": len(rows),
            "metstat_filter_fields": list(METSTAT_FIELDS),
            "note": (
                "Retrieval evidence only. A metstat hit shows the study reported this RefMet "
                "name; it does not confirm MSI-level identity, comparable quantitation, or "
                "harmonization eligibility. Absence of a study is a coverage gap, not evidence "
                "the metabolite is unchanged."
            ),
        },
    )
    return {
        "query": query,
        "identity": identity,
        "rows": rows,
        "hits_path": hits_path,
        "provenance_path": provenance_path,
        "searches": searches,
    }

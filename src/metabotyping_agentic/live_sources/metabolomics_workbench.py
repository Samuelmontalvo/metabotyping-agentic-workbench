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


# ---------------------------------------------------------------------------
# Compound, gene/protein (MGP), and mass-search contexts
#
# These share the base URL, host, and terms of the study/refmet/metstat contexts
# above, so they widen the declared network boundary by zero modules. They do not
# share an error taxonomy: every application error is returned as HTTP 200 with a
# ``text/html`` body, so status codes cannot be used to detect failure.
# ---------------------------------------------------------------------------

MW_TERMS_URL = "https://www.metabolomicsworkbench.org/about/termsofuse.php"
MW_REST_DOC_URL = "https://www.metabolomicsworkbench.org/tools/mw_rest.php"
# The doc page carries the only version string the service publishes; there is no
# version endpoint, so the string is recorded rather than queried.
MW_REST_API_VERSION = "MW REST API v1.2, 07/22/2025"

COMPOUND_INPUT_ITEMS = (
    "regno",
    "formula",
    "inchi_key",
    "lm_id",
    "pubchem_cid",
    "hmdb_id",
    "kegg_id",
    "smiles",
)
# Accepted by the live service but absent from every published input list, so a
# query using one is flagged rather than presented as a supported contract.
COMPOUND_UNDOCUMENTED_INPUT_ITEMS = ("chebi_id", "metacyc_id")
# molfile, sdf, and png are deliberately out of scope: png redirects out of /rest/
# into a display page, and structure files are not evidence this lane needs.
COMPOUND_OUTPUT_ITEMS = (
    "all",
    "classification",
    "regno",
    "formula",
    "exactmass",
    "inchi_key",
    "name",
    "sys_name",
    "smiles",
    "lm_id",
    "pubchem_cid",
    "hmdb_id",
    "kegg_id",
    "chebi_id",
    "metacyc_id",
)

GENE_INPUT_ITEMS = ("mgp_id", "gene_id", "gene_name", "gene_symbol", "taxid")
PROTEIN_INPUT_ITEMS = GENE_INPUT_ITEMS + (
    "mrna_id",
    "refseq_id",
    "uniprot_id",
    "protein_entry",
    "protein_name",
)
# The MGP tables hold human records only; every other taxid answers with an empty
# list, which would otherwise be recorded as a coverage gap for that species.
MW_MGP_SUPPORTED_TAXIDS = ("9606",)

MOVERZ_DATABASES = ("MB", "LIPIDS", "REFMET")
# Documented but broken upstream: the service accepts it and answers with the
# neutral mass, so it is refused here rather than silently mis-recorded.
MOVERZ_REFUSED_ION_TYPES = ("M.KFormate-H",)


@dataclass(frozen=True)
class MwRawResponse:
    """A Metabolomics Workbench response before interpretation."""

    url: str
    http_status: int | None
    content_type: str
    body: str
    transport_error: str = ""


MwRawFetcher = Callable[[str], MwRawResponse]


def fetch_mw_raw(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> MwRawResponse:
    """Fetch a Metabolomics Workbench URL without interpreting the body.

    Required for moverz and exactmass, which never return JSON, and for detecting
    the HTML error bodies the JSON contexts return under HTTP 200.
    """

    request = Request(url, headers={"Accept": "*/*", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit public data adapter
            body = response.read().decode("utf-8", "replace")
            content_type = str(response.headers.get("Content-Type") or "")
            return MwRawResponse(url, int(response.status), content_type, body)
    except HTTPError as exc:
        content_type = str(exc.headers.get("Content-Type") or "") if exc.headers else ""
        return MwRawResponse(url, int(exc.code), content_type, "")
    except (URLError, TimeoutError) as exc:
        return MwRawResponse(url, None, "", "", transport_error=str(exc))


def classify_mw_response(response: MwRawResponse) -> tuple[str, Any, str]:
    """Return ``(status, payload_or_None, detail)`` for a JSON-context response.

    Status codes carry almost no information here: a bad input item, a bad output
    item, and a genuine miss all answer HTTP 200. Classification therefore reads
    the content type and the body prefix.
    """

    if response.transport_error:
        return "unavailable", None, f"transport error: {response.transport_error}"
    if response.http_status is not None and response.http_status >= 400:
        return "unavailable", None, f"HTTP {response.http_status}"
    body = response.body.strip()
    if not body:
        return "unavailable", None, "empty response body"
    if "text/html" in response.content_type.lower() or body.startswith("<"):
        detail = " ".join(re.sub(r"<[^>]+>", " ", body)[:200].split())
        return "request_rejected", None, detail
    if body == "[]":
        return "no_hits", [], ""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "unavailable", None, "non-JSON body: " + " ".join(body[:200].split())
    rows = mw_rows(payload)
    if not rows:
        return "no_hits", payload, ""
    return "ok", payload, ""


def mw_rows(payload: Any) -> list[dict[str, Any]]:
    """Normalize the flat, ``Row1..RowN``, and integer-keyed response shapes."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict) or not payload:
        # An empty object carries no record; emitting it as a row would fabricate a
        # compound whose every field reads "not_reported".
        return []
    values = list(payload.values())
    if values and all(isinstance(item, dict) for item in values):
        return values
    return [payload]


def normalize_compound_identifier(input_item: str, value: str) -> tuple[str, str]:
    """Return ``(normalized_value, normalization_applied)``.

    An unnormalized identifier answers with an empty list, which would otherwise
    be written as a coverage gap for a compound the database actually holds. Every
    normalization is reported so a formatting fix is never mistaken for a finding.
    """

    text = str(value).strip()
    if input_item == "hmdb_id":
        match = re.fullmatch(r"HMDB0*(\d+)", text, flags=re.IGNORECASE)
        if match:
            padded = f"HMDB{int(match.group(1)):07d}"
            return padded, ("none" if padded == text else f"zero_padded_hmdb_id:{text}->{padded}")
    if input_item == "chebi_id":
        match = re.fullmatch(r"CHEBI:\s*(\d+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1), f"stripped_chebi_prefix:{text}->{match.group(1)}"
    if input_item in {"inchi_key", "kegg_id"}:
        upper = text.upper()
        return upper, ("none" if upper == text else f"upper_cased_{input_item}:{text}->{upper}")
    return text, "none"


def _mw_context_url(context: str, input_item: str, value: str, output_item: str) -> str:
    # A forward slash inside a value is untransmittable: raw it splits the path and
    # percent-encoded it is rejected by the front end before the handler runs.
    if "/" in value:
        raise ValueError(
            f"A forward slash in a {context} query value is not transmittable to the "
            f"Metabolomics Workbench REST API: {value!r}"
        )
    return f"{BASE_URL}/{context}/{input_item}/{quote(value, safe='()')}/{output_item}"


COMPOUND_FIELDNAMES = [
    "query_input_item",
    "query_value",
    "query_value_normalized",
    "identifier_normalization_applied",
    "input_item_support",
    "regno",
    "name",
    "sys_name",
    "formula",
    "exactmass",
    "inchi_key",
    "smiles",
    "pubchem_cid",
    "hmdb_id",
    "kegg_id",
    "chebi_id",
    "lm_id",
    "metacyc_id",
    "record_index",
    "candidate_set_size",
    "identity_status",
    "evidence_type",
    "measurement_established",
    "review_status",
    "decision_scope",
    "source_system",
    "source_url",
]

COMPOUND_RECORD_FIELDS = (
    "regno",
    "name",
    "sys_name",
    "formula",
    "exactmass",
    "inchi_key",
    "smiles",
    "pubchem_cid",
    "hmdb_id",
    "kegg_id",
    "chebi_id",
    "lm_id",
    "metacyc_id",
)


def lookup_compound(
    value: str,
    out_dir: str | Path,
    *,
    input_item: str = "pubchem_cid",
    output_item: str = "all",
    fetcher: MwRawFetcher = fetch_mw_raw,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Retrieve Metabolomics Workbench compound records for one identifier.

    Identifier crosswalk retrieval only. Two identifiers that resolve to different
    registry numbers are emitted as a candidate set for human review, never merged:
    KEGG ``C00031`` and ``HMDB0000122`` both read as "glucose" and resolve to
    different registry numbers with different stereochemistry.
    """

    supported = COMPOUND_INPUT_ITEMS + COMPOUND_UNDOCUMENTED_INPUT_ITEMS
    if input_item not in supported:
        raise ValueError(
            f"Unsupported compound input item {input_item!r}. Supported: " + ", ".join(supported)
        )
    if output_item not in COMPOUND_OUTPUT_ITEMS:
        raise ValueError(
            f"Unsupported compound output item {output_item!r}. Supported: "
            + ", ".join(COMPOUND_OUTPUT_ITEMS)
        )
    out_dir = ensure_dir(out_dir)
    normalized, normalization = normalize_compound_identifier(input_item, value)
    url = _mw_context_url("compound", input_item, normalized, output_item)
    status, payload, detail = classify_mw_response(fetcher(url))
    records = mw_rows(payload) if status == "ok" else []
    support = (
        "undocumented_may_be_withdrawn"
        if input_item in COMPOUND_UNDOCUMENTED_INPUT_ITEMS
        else "documented"
    )

    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        rows.append(
            {
                "query_input_item": input_item,
                "query_value": value,
                "query_value_normalized": normalized,
                "identifier_normalization_applied": normalization,
                "input_item_support": support,
                # ``all`` is sparse: an absent cross-reference is a dropped key, so
                # every field is read with a default rather than indexed.
                **{
                    field: str(record.get(field, "") or "not_reported")
                    for field in COMPOUND_RECORD_FIELDS
                },
                "record_index": index,
                "candidate_set_size": len(records),
                "identity_status": (
                    "single_candidate_requires_human_review"
                    if len(records) == 1
                    else "multiple_candidates_requires_human_review"
                ),
                "evidence_type": "compound_registry_record",
                "measurement_established": "not_established",
                "review_status": "requires_human_review",
                "decision_scope": "identifier_crosswalk_retrieval_only",
                "source_system": "metabolomics_workbench_compound",
                "source_url": url,
            }
        )

    records_path = write_csv_rows(out_dir / "mw_compound_records.csv", rows, COMPOUND_FIELDNAMES)
    provenance_path = write_json(
        out_dir / "mw_compound_provenance.json",
        {
            "generated_utc": generated_utc or "",
            "context": "compound",
            "query_input_item": input_item,
            "input_item_support": support,
            "query_value": value,
            "query_value_normalized": normalized,
            "identifier_normalization_applied": normalization,
            "output_item": output_item,
            "source_url": url,
            "status": status,
            "detail": detail,
            "record_count": len(rows),
            "registered_source_ids": ["mw_compound_database"],
            "api_version_string": MW_REST_API_VERSION,
            "api_documentation_url": MW_REST_DOC_URL,
            "terms_url": MW_TERMS_URL,
            "decision_scope": "identifier_crosswalk_retrieval_only",
            "review_status": "requires_human_review",
            "coverage_gap_semantics": (
                "status=unavailable means the service could not be reached and coverage is "
                "unknown. status=request_rejected means the input or output item was refused and "
                "nothing was searched, which is a query defect and not a coverage fact. "
                "status=no_hits means the service answered and holds no record for the normalized "
                "identifier."
            ),
            "note": (
                "Identifier crosswalk retrieval only. A shared name or a shared formula across "
                "records is not identity: distinct registry numbers with distinct InChIKeys are "
                "emitted as a candidate set for human review and are never merged."
            ),
        },
    )
    return {
        "status": status,
        "detail": detail,
        "rows": rows,
        "records_path": records_path,
        "provenance_path": provenance_path,
        "source_url": url,
    }


MGP_FIELDNAMES = [
    "query_context",
    "query_input_item",
    "query_value",
    "mgp_id",
    "gene_id",
    "gene_symbol",
    "gene_name",
    "gene_synonyms",
    "taxid",
    "species",
    "mrna_id",
    "refseq_id",
    "uniprot_id",
    "protein_entry",
    "record_index",
    "match_basis",
    "evidence_type",
    "measurement_established",
    "metabolite_link_established",
    "annotation_currency",
    "upstream_provenance",
    "species_coverage",
    "review_status",
    "decision_scope",
    "source_system",
    "source_url",
]

MGP_RECORD_FIELDS = (
    "mgp_id",
    "gene_id",
    "gene_symbol",
    "gene_name",
    "gene_synonyms",
    "taxid",
    "species",
    "mrna_id",
    "refseq_id",
    "uniprot_id",
    "protein_entry",
)


def lookup_mgp_gene_protein(
    value: str,
    out_dir: str | Path,
    *,
    context: str = "gene",
    input_item: str = "gene_symbol",
    fetcher: MwRawFetcher = fetch_mw_raw,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Retrieve Human Metabolome Gene/Protein annotation records.

    Annotation retrieval only. These contexts carry no compound, pathway, or study
    field, so they cannot link a gene to a metabolite; that bridge is MetGENE's,
    and it is an annotation bridge rather than a measurement.
    """

    if context not in {"gene", "protein"}:
        raise ValueError(f"Unsupported MGP context {context!r}. Supported: gene, protein")
    allowed = GENE_INPUT_ITEMS if context == "gene" else PROTEIN_INPUT_ITEMS
    if input_item not in allowed:
        raise ValueError(
            f"Unsupported {context} input item {input_item!r}. Supported: " + ", ".join(allowed)
        )
    text = str(value).strip()
    if input_item == "taxid" and text not in MW_MGP_SUPPORTED_TAXIDS:
        raise ValueError(
            "The Metabolomics Workbench gene/protein tables hold records for taxid "
            + ", ".join(MW_MGP_SUPPORTED_TAXIDS)
            + f" only; taxid {text!r} is species_not_covered_by_source and is not queried, "
            "because an empty answer would otherwise be recorded as a coverage gap for that "
            "species."
        )

    out_dir = ensure_dir(out_dir)
    # The gene context rejects ``gene_id`` as an output item, so the full record is
    # always requested and projected locally.
    url = _mw_context_url(context, input_item, text, "all")
    status, payload, detail = classify_mw_response(fetcher(url))
    records = mw_rows(payload) if status == "ok" else []
    match_basis = (
        "unanchored_substring_match"
        if input_item in {"gene_name", "protein_name"}
        else "exact_identifier_match"
    )

    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        rows.append(
            {
                "query_context": context,
                "query_input_item": input_item,
                "query_value": text,
                **{
                    field: str(record.get(field, "") or "not_reported")
                    for field in MGP_RECORD_FIELDS
                },
                "record_index": index,
                "match_basis": match_basis,
                "evidence_type": f"{context}_annotation_record",
                "measurement_established": "not_established",
                "metabolite_link_established": "not_established_no_compound_field_in_source",
                "annotation_currency": "unknown_no_build_date",
                "upstream_provenance": "ncbi_refseq_and_uniprot",
                "species_coverage": "human_only_taxid_9606",
                "review_status": "requires_human_review",
                "decision_scope": "annotation_retrieval_only",
                "source_system": f"metabolomics_workbench_{context}",
                "source_url": url,
            }
        )

    records_path = write_csv_rows(out_dir / "mw_mgp_records.csv", rows, MGP_FIELDNAMES)
    provenance_path = write_json(
        out_dir / "mw_mgp_provenance.json",
        {
            "generated_utc": generated_utc or "",
            "context": context,
            "query_input_item": input_item,
            "query_value": text,
            "match_basis": match_basis,
            "source_url": url,
            "status": status,
            "detail": detail,
            "record_count": len(rows),
            "registered_source_ids": ["mw_metabolome_gene_protein"],
            "api_version_string": MW_REST_API_VERSION,
            "api_documentation_url": MW_REST_DOC_URL,
            "terms_url": MW_TERMS_URL,
            "species_coverage": "human_only_taxid_9606",
            "decision_scope": "annotation_retrieval_only",
            "review_status": "requires_human_review",
            "note": (
                "These contexts hold gene and protein annotation only. They contain no compound, "
                "pathway, or study field, so a record here never establishes that a gene is "
                "linked to a metabolite, and a substring name match is never identifier "
                "resolution."
            ),
        },
    )
    return {
        "status": status,
        "detail": detail,
        "rows": rows,
        "records_path": records_path,
        "provenance_path": provenance_path,
        "source_url": url,
    }


MOVERZ_FIELDNAMES = [
    "query_mz",
    "query_adduct",
    "echoed_adduct",
    "adduct_verified",
    "query_tolerance_da",
    "query_database",
    "matched_mz",
    "delta",
    "name",
    "systematic_name",
    "formula",
    "category",
    "main_class",
    "sub_class",
    "column_recovery_applied",
    "evidence_type",
    "identification_status",
    "measurement_established",
    "review_status",
    "decision_scope",
    "source_system",
    "source_url",
]


def _adducts_match(requested: str, echoed: str) -> bool:
    """Compare a requested adduct with the ion label the service echoed back.

    The service rewrites a path-safe '.' to '+', wraps the adduct in brackets, and
    appends the charge state: ``M.Cl`` comes back as ``[M+Cl]-`` and ``M-2H`` as
    ``[M-2H]2-``. The charge is stripped by unwrapping the brackets rather than by
    trimming trailing characters, because a trailing trim also eats the digit in a
    formula such as ``M+NH4`` and would discard every genuine ammonium match.
    """

    def canon(value: str) -> str:
        text = re.sub(r"\s", "", str(value).strip().upper()).replace(".", "+")
        bracketed = re.fullmatch(r"\[(.+?)\]\d*[+-]*", text)
        if bracketed:
            return bracketed.group(1)
        return text

    return bool(str(echoed).strip()) and canon(requested) == canon(echoed)


def _split_matched_and_delta(input_mz: str, merged: str) -> tuple[str, str] | None:
    """Recover the concatenated ``Matched m/z`` and ``Delta`` fields of a LIPIDS row.

    Splitting on the second decimal point alone is wrong once the delta reaches one
    dalton, because the greedy match then borrows a digit from the delta's integer
    part. Every candidate split point is therefore checked against the row's own
    input m/z, and the recovery is reported as unapplied when none is consistent.
    """

    try:
        target = float(input_mz)
    except (TypeError, ValueError):
        return None
    best: tuple[float, str, str] | None = None
    # The two values are concatenated with no separator, so the boundary is not
    # necessarily at a decimal point: a delta of one dalton or more puts its integer
    # digits immediately after the matched m/z. Every split is tried and scored.
    for position in range(1, len(merged)):
        matched, delta = merged[:position], merged[position:]
        try:
            matched_value = float(matched)
            delta_value = abs(float(delta))
        except ValueError:
            continue
        residual = abs(abs(matched_value - target) - delta_value)
        if residual > 1e-4:
            continue
        if best is None or residual < best[0]:
            best = (residual, matched, delta)
    return (best[1], best[2]) if best else None


def _parse_moverz_table(body: str, database: str) -> tuple[list[dict[str, str]], bool]:
    """Parse the tab-delimited moverz body.

    The LIPIDS table declares six columns but emits five fields per row: the tab
    between the matched m/z and the delta is missing and a spurious trailing tab
    follows the ion. The two values are recovered by splitting at the second
    decimal point, and the recovery is reported rather than applied silently.
    """

    lines = [line for line in body.splitlines() if line.strip()]
    if not lines:
        return [], False
    header = [cell.strip() for cell in lines[0].split("\t")]
    recovery_applied = False
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split("\t")]
        while cells and not cells[-1]:
            # The LIPIDS rows carry a spurious trailing tab, so the row can look
            # correctly sized while being one field short.
            cells.pop()
        if database == "LIPIDS" and len(cells) >= 2 and len(cells) < len(header):
            split = _split_matched_and_delta(cells[0], cells[1])
            if split:
                cells = [cells[0], split[0], split[1], *cells[2:]]
                recovery_applied = True
        rows.append({header[index]: cells[index] for index in range(min(len(header), len(cells)))})
    return rows, recovery_applied


def search_moverz(
    mz: float | str,
    out_dir: str | Path,
    *,
    adduct: str = "M+H",
    tolerance_da: float | str = 0.02,
    database: str = "REFMET",
    fetcher: MwRawFetcher = fetch_mw_raw,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Search a precursor m/z against a Metabolomics Workbench mass database.

    A mass match is a candidate, never an identification. An unrecognised adduct
    is silently computed as neutral by the service, so every emitted row has its
    echoed ion label verified against the requested adduct.
    """

    database = str(database).strip().upper()
    if database not in MOVERZ_DATABASES:
        raise ValueError(
            f"Unsupported moverz database {database!r}. Supported: " + ", ".join(MOVERZ_DATABASES)
        )
    if str(adduct).strip() in MOVERZ_REFUSED_ION_TYPES:
        raise ValueError(
            f"Ion type {adduct!r} is documented but returns the neutral mass, so it is refused "
            "rather than recorded as a match."
        )
    try:
        mz_value = float(str(mz).strip())
        tolerance_value = float(str(tolerance_da).strip())
    except ValueError as exc:
        raise ValueError("m/z and tolerance must be numeric.") from exc
    if tolerance_value <= 0:
        # An empty or zero tolerance returns a header-only body that is
        # indistinguishable from a genuine zero-match.
        raise ValueError("Mass tolerance must be a positive number of daltons.")

    out_dir = ensure_dir(out_dir)
    path_adduct = str(adduct).strip()
    url = (
        f"{BASE_URL}/moverz/{database}/{mz_value}"
        f"/{quote(path_adduct, safe='+-.')}/{tolerance_value}"
    )
    response = fetcher(url)
    table: list[dict[str, str]] = []
    recovery = False
    body = response.body
    if response.transport_error or (response.http_status or 200) >= 400:
        status = "unavailable"
        detail = response.transport_error or f"HTTP {response.http_status}"
    elif not body.strip():
        # A zero-length body is not a zero-match: the expected zero-match shape is a
        # header row with no data rows.
        status = "unavailable"
        detail = "empty response body; the zero-match shape is a header row with no data rows"
    elif "does not exist" in body or "not allowed" in body or "Internal error" in body:
        status = "request_rejected"
        detail = " ".join(re.sub(r"<[^>]+>", " ", body)[:200].split())
    elif body.lstrip().startswith("<"):
        # The service returns application errors as HTTP 200 HTML, so an HTML body is
        # a rejected request rather than an absent match.
        status = "request_rejected"
        detail = "HTML body returned in place of the tab-delimited table: " + " ".join(
            re.sub(r"<[^>]+>", " ", body)[:200].split()
        )
    elif "\t" not in body.splitlines()[0]:
        status = "unavailable"
        detail = "response is not the expected tab-delimited table: " + " ".join(body[:200].split())
    else:
        table, recovery = _parse_moverz_table(body, database)
        status = "ok" if table else "no_hits"
        detail = "" if table else "header row returned with no data rows"

    rows: list[dict[str, Any]] = []
    unverified = 0
    for record in table:
        echoed = record.get("Ion", "")
        if not _adducts_match(path_adduct, echoed):
            unverified += 1
            continue
        rows.append(
            {
                "query_mz": mz_value,
                "query_adduct": adduct,
                "echoed_adduct": echoed,
                "adduct_verified": True,
                "query_tolerance_da": tolerance_value,
                "query_database": database,
                "matched_mz": record.get("Matched m/z", "not_reported"),
                "delta": record.get("Delta", "not_reported"),
                "name": record.get("Name", "not_reported"),
                "systematic_name": record.get("Systematic name", "not_reported"),
                "formula": record.get("Formula", "not_reported"),
                "category": record.get("Category", "not_reported"),
                "main_class": record.get("Main class", "not_reported"),
                "sub_class": record.get("Sub class", "not_reported"),
                "column_recovery_applied": recovery,
                "evidence_type": "precursor_ion_mass_match",
                "identification_status": "candidate_not_an_identification",
                "measurement_established": "not_established",
                "review_status": "requires_human_review",
                "decision_scope": "mass_search_retrieval_only",
                "source_system": f"metabolomics_workbench_moverz_{database.lower()}",
                "source_url": url,
            }
        )
    if unverified and not rows:
        status = "adduct_not_supported_silent_neutral_fallback"
        detail = (
            f"{unverified} row(s) echoed an ion label that does not match the requested adduct "
            f"{adduct!r}; the service computes an unrecognised adduct as neutral, so the result "
            "was discarded rather than reported as a match."
        )

    records_path = write_csv_rows(out_dir / "mw_moverz_matches.csv", rows, MOVERZ_FIELDNAMES)
    provenance_path = write_json(
        out_dir / "mw_mass_provenance.json",
        {
            "generated_utc": generated_utc or "",
            "context": "moverz",
            "query_mz": mz_value,
            "requested_adduct": adduct,
            "echoed_adducts": sorted({str(record.get("Ion", "")) for record in table}),
            "adduct_verified": bool(rows),
            "discarded_unverified_adduct_rows": unverified,
            "query_tolerance_da": tolerance_value,
            "query_database": database,
            "databases_available": list(MOVERZ_DATABASES),
            "column_recovery_applied": recovery,
            "source_url": url,
            "status": status,
            "detail": detail,
            "match_count": len(rows),
            "registered_source_ids": ["mw_compound_database"],
            "api_version_string": MW_REST_API_VERSION,
            "api_documentation_url": MW_REST_DOC_URL,
            "terms_url": MW_TERMS_URL,
            "decision_scope": "mass_search_retrieval_only",
            "review_status": "requires_human_review",
            "note": (
                "A precursor-ion mass match is a candidate, not an identification. Confirming an "
                "identity requires orthogonal evidence such as retention time, fragmentation "
                "spectra, or an authentic standard analysed in the same run."
            ),
        },
    )
    return {
        "status": status,
        "detail": detail,
        "rows": rows,
        "records_path": records_path,
        "provenance_path": provenance_path,
        "source_url": url,
    }


EXACTMASS_FIELDNAMES = [
    "query_abbreviation",
    "query_abbreviation_normalized",
    "notation_rewrite_applied",
    "resolved_name",
    "resolved_bulk_composition",
    "requested_adduct",
    "echoed_adduct",
    "adduct_verified",
    "exact_mz",
    "ion_formula",
    "evidence_type",
    "identification_status",
    "measurement_established",
    "review_status",
    "decision_scope",
    "source_system",
    "source_url",
]


def compute_exact_mass(
    abbreviation: str,
    out_dir: str | Path,
    *,
    adduct: str = "M+H",
    fetcher: MwRawFetcher = fetch_mw_raw,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Compute the exact m/z and ion formula for a lipid abbreviation.

    ``PC(16:0/18:1)`` is rewritten to the underscore form because a slash cannot be
    transmitted in a path value; ``PC(16:0-18:1)`` is refused, because the hyphen
    yields a chemically unrelated answer with HTTP 200.
    """

    text = str(abbreviation).strip()
    rewrite = "none"
    if re.search(r"\d\s*-\s*\d", text):
        raise ValueError(
            f"Lipid abbreviation {text!r} uses a hyphen chain separator, which the service "
            "resolves to a chemically unrelated species; use '/' or '_' instead."
        )
    if "/" in text:
        rewritten = text.replace("/", "_")
        rewrite = f"slash_to_underscore:{text}->{rewritten}"
        text = rewritten
    if str(adduct).strip() in MOVERZ_REFUSED_ION_TYPES:
        raise ValueError(
            f"Ion type {adduct!r} is documented but returns the neutral mass, so it is refused."
        )

    out_dir = ensure_dir(out_dir)
    path_adduct = str(adduct).strip()
    url = f"{BASE_URL}/moverz/exactmass/{quote(text, safe='()_:')}/{quote(path_adduct, safe='+-.')}"
    response = fetcher(url)

    record: dict[str, Any] = {}
    if response.transport_error or (response.http_status or 200) >= 400:
        status = "unavailable"
        detail = response.transport_error or f"HTTP {response.http_status}"
    elif not response.body.strip():
        # Nothing came back, which is not the same as the request being refused.
        status = "unavailable"
        detail = "empty response body"
    else:
        # The body is '</br>'-separated and its line count varies with the input
        # notation, so it is parsed from the end: formula, m/z, ion label.
        parts = [part.strip() for part in re.split(r"</br>", response.body) if part.strip()]
        if len(parts) < 3 or "does not exist" in response.body:
            status = "request_rejected"
            detail = " ".join(response.body[:200].split())
        elif not _adducts_match(path_adduct, parts[-3]):
            status = "adduct_not_supported_silent_neutral_fallback"
            detail = (
                f"echoed ion label {parts[-3]!r} does not match the requested adduct {adduct!r}; "
                "the service computes an unrecognised adduct as the neutral mass"
            )
        else:
            status = "ok"
            detail = ""
            record = {
                "query_abbreviation": abbreviation,
                "query_abbreviation_normalized": text,
                "notation_rewrite_applied": rewrite,
                "resolved_name": parts[0],
                # Bulk notation returns 4 parts and molecular-species notation 5; only
                # the 5-part form carries a separate resolved bulk composition line.
                "resolved_bulk_composition": parts[1] if len(parts) >= 5 else parts[0],
                "requested_adduct": adduct,
                "echoed_adduct": parts[-3],
                "adduct_verified": True,
                "exact_mz": parts[-2],
                "ion_formula": parts[-1],
                "evidence_type": "computed_exact_mass",
                "identification_status": "computed_value_not_a_measurement",
                "measurement_established": "not_established",
                "review_status": "requires_human_review",
                "decision_scope": "mass_calculation_only",
                "source_system": "metabolomics_workbench_exactmass",
                "source_url": url,
            }

    rows = [record] if record else []
    records_path = write_csv_rows(out_dir / "mw_exactmass.csv", rows, EXACTMASS_FIELDNAMES)
    provenance_path = write_json(
        out_dir / "mw_exactmass_provenance.json",
        {
            "generated_utc": generated_utc or "",
            "context": "exactmass",
            "query_abbreviation": abbreviation,
            "query_abbreviation_normalized": text,
            "notation_rewrite_applied": rewrite,
            "requested_adduct": adduct,
            "echoed_adduct": record.get("echoed_adduct", ""),
            "adduct_verified": bool(record),
            "source_url": url,
            "status": status,
            "detail": detail,
            "registered_source_ids": ["mw_compound_database"],
            "api_version_string": MW_REST_API_VERSION,
            "api_documentation_url": MW_REST_DOC_URL,
            "terms_url": MW_TERMS_URL,
            "decision_scope": "mass_calculation_only",
            "review_status": "requires_human_review",
            "note": (
                "A computed exact mass describes a formula, not a measured feature, and a bulk "
                "lipid abbreviation does not specify the acyl chain positions that a measurement "
                "would have to resolve."
            ),
        },
    )
    return {
        "status": status,
        "detail": detail,
        "rows": rows,
        "records_path": records_path,
        "provenance_path": provenance_path,
        "source_url": url,
    }

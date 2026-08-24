"""Live literature retrieval across Europe PMC, PubMed, Crossref, and bioRxiv/medRxiv.

Retrieval only. This module fetches and normalizes public bibliographic records; it
does not screen, rank, appraise, or synthesize them. Screening and appraisal live in
``metabotyping_agentic.discovery.literature_review``, which never touches the network.

Two properties matter more than coverage here:

1. A source that could not be reached is recorded as ``unavailable``, never as zero
   hits. An unreachable index and an index with no matching papers are different
   scientific facts, and collapsing them manufactures a false negative.
2. Retrieval breadth is declared. Every query string, endpoint URL, reported hit
   count, retrieved count, and pagination truncation is written to provenance so a
   reviewer can tell a complete sweep from a first-page sample.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..io import ensure_dir, write_csv_rows, write_json

EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF_BASE = "https://api.crossref.org"
BIORXIV_BASE = "https://api.biorxiv.org"

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_RECORDS_PER_SOURCE = 300
POLITE_DELAY_SECONDS = 0.34
TOOL_NAME = "metabotyping-agentic-workbench"
CONTACT_EMAIL_ENV = "METABOTYPING_CONTACT_EMAIL"
NCBI_API_KEY_ENV = "NCBI_API_KEY"

# Every retrieval lane declared here must also be registered in
# ``metabotyping_agentic.knowledge.source_registry``; the source-registry librarian
# treats an unregistered lane as a blocking escalation rather than a usable source.
LITERATURE_SOURCES = ("europe_pmc", "pubmed", "crossref", "biorxiv_medrxiv")

RECORD_FIELDNAMES = [
    "record_key",
    "source_system",
    "source_subset",
    "doi",
    "pmid",
    "pmcid",
    "preprint_server",
    "title",
    "authors",
    "journal",
    "publication_year",
    "publication_types",
    "is_preprint",
    "is_open_access",
    "cited_by_count",
    "linked_published_doi",
    "preprint_version_count",
    "record_url",
    "queried_expression",
    "source_url",
    "retrieved_via",
]

Fetcher = Callable[[str], Any]


@dataclass(frozen=True)
class SourceOutcome:
    """What one source actually returned, including the reason it returned nothing."""

    source_system: str
    status: str  # "ok" | "unavailable" | "no_hits"
    queried_expression: str
    endpoints: tuple[str, ...]
    reported_hit_count: int | None
    retrieved_count: int
    pagination_complete: bool
    detail: str = ""


def _contact_email() -> str:
    return os.environ.get(CONTACT_EMAIL_ENV, "").strip()


def _user_agent() -> str:
    email = _contact_email()
    return f"{TOOL_NAME}/0.1 (+https://github.com/; mailto:{email})" if email else f"{TOOL_NAME}/0.1"


RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """Fetch JSON from a public bibliographic API using only the standard library.

    Rate limiting and transient server errors are retried with linear backoff so a
    throttled request is not misrecorded as an unavailable source.
    """

    request = Request(url, headers={"Accept": "application/json", "User-Agent": _user_agent()})
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit public data adapter
                body = response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            last_error = exc
            if exc.code in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise RuntimeError(f"literature request failed with HTTP {exc.code}: {url}") from exc
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise RuntimeError(f"literature request failed: {url} ({exc})") from exc
        if not body.strip():
            raise RuntimeError(f"literature request returned an empty response: {url}")
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            snippet = " ".join(body[:200].split())
            raise RuntimeError(f"literature request returned non-JSON content: {url} :: {snippet}") from exc
    raise RuntimeError(f"literature request failed after {MAX_ATTEMPTS} attempts: {url} ({last_error})")


def _sleep() -> None:
    # Public APIs ask for polite request rates; a fixed delay keeps every lane inside
    # the documented limits without needing per-source bookkeeping.
    time.sleep(POLITE_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


def _phrase_terms(query: str, name_variants: Iterable[str]) -> list[str]:
    terms: list[str] = []
    for candidate in [query, *name_variants]:
        candidate = str(candidate).strip()
        if candidate and candidate.lower() not in {term.lower() for term in terms}:
            terms.append(candidate)
    return terms


def europe_pmc_expression(
    query: str,
    name_variants: Iterable[str] = (),
    context_terms: Iterable[str] = (),
) -> str:
    subject = " OR ".join(f'"{term}"' for term in _phrase_terms(query, name_variants))
    expression = f"({subject})"
    context = [str(term).strip() for term in context_terms if str(term).strip()]
    if context:
        expression += " AND (" + " OR ".join(f'"{term}"' for term in context) + ")"
    return expression


def pubmed_expression(
    query: str,
    name_variants: Iterable[str] = (),
    context_terms: Iterable[str] = (),
) -> str:
    subject = " OR ".join(f'"{term}"[All Fields]' for term in _phrase_terms(query, name_variants))
    expression = f"({subject})"
    context = [str(term).strip() for term in context_terms if str(term).strip()]
    if context:
        expression += " AND (" + " OR ".join(f'"{term}"[All Fields]' for term in context) + ")"
    return expression


# ---------------------------------------------------------------------------
# Europe PMC (indexes MEDLINE/PubMed as SRC:MED, PMC, and preprints as SRC:PPR)
# ---------------------------------------------------------------------------


def _europe_pmc_url(expression: str, *, page_size: int, cursor_mark: str) -> str:
    params = {
        "query": expression,
        "format": "json",
        "resultType": "core",
        "pageSize": str(page_size),
        "cursorMark": cursor_mark,
    }
    return f"{EUROPE_PMC_BASE}/search?{urlencode(params)}"


def _europe_pmc_record(result: dict[str, Any], expression: str, source_url: str) -> dict[str, Any]:
    journal_info = result.get("journalInfo") or {}
    journal = (journal_info.get("journal") or {}).get("title") or ""
    subset = str(result.get("source") or "").strip().upper()
    doi = str(result.get("doi") or "").strip().lower()
    pmid = str(result.get("pmid") or "").strip()
    pub_types = result.get("pubTypeList") or {}
    types = pub_types.get("pubType") if isinstance(pub_types, dict) else None
    if isinstance(types, str):
        types = [types]
    return {
        "source_system": "europe_pmc",
        "source_subset": subset,
        "doi": doi,
        "pmid": pmid,
        "pmcid": str(result.get("pmcid") or "").strip(),
        "preprint_server": "",
        "title": _plain_text(result.get("title")).rstrip("."),
        "authors": _plain_text(result.get("authorString")),
        "journal": _plain_text(journal),
        "publication_year": str(result.get("pubYear") or journal_info.get("yearOfPublication") or "").strip(),
        "publication_types": "; ".join(sorted({str(item).strip().lower() for item in (types or []) if str(item).strip()})),
        "is_preprint": "true" if subset == "PPR" else "false",
        "is_open_access": "true" if str(result.get("isOpenAccess") or "").upper() == "Y" else "false",
        "cited_by_count": str(result.get("citedByCount") or ""),
        "linked_published_doi": "",
        "preprint_version_count": "",
        "record_url": f"https://europepmc.org/article/{subset}/{result.get('id')}" if subset else "",
        "abstract": _plain_text(result.get("abstractText")),
        "queried_expression": expression,
        "source_url": source_url,
        "retrieved_via": "europe_pmc_rest_search",
    }


def search_europe_pmc(
    expression: str,
    *,
    max_records: int = DEFAULT_MAX_RECORDS_PER_SOURCE,
    page_size: int = DEFAULT_PAGE_SIZE,
    fetcher: Fetcher = fetch_json,
) -> tuple[list[dict[str, Any]], SourceOutcome]:
    records: list[dict[str, Any]] = []
    endpoints: list[str] = []
    cursor_mark = "*"
    hit_count: int | None = None
    while len(records) < max_records:
        url = _europe_pmc_url(expression, page_size=page_size, cursor_mark=cursor_mark)
        endpoints.append(url)
        try:
            payload = fetcher(url)
        except RuntimeError as exc:
            if records:
                # A mid-sweep failure is a truncated sweep, not an unavailable source.
                return records, SourceOutcome(
                    "europe_pmc", "ok", expression, tuple(endpoints), hit_count, len(records), False, str(exc)
                )
            return [], SourceOutcome(
                "europe_pmc", "unavailable", expression, tuple(endpoints), None, 0, False, str(exc)
            )
        if hit_count is None:
            hit_count = int(payload.get("hitCount") or 0)
        results = ((payload.get("resultList") or {}).get("result")) or []
        for result in results:
            if isinstance(result, dict):
                records.append(_europe_pmc_record(result, expression, url))
        next_cursor = str(payload.get("nextCursorMark") or "").strip()
        if not results or not next_cursor or next_cursor == cursor_mark:
            cursor_mark = ""
            break
        cursor_mark = next_cursor
        _sleep()
    exhausted_cursor = not cursor_mark
    complete = bool(hit_count is not None and len(records) >= hit_count) or exhausted_cursor
    detail = ""
    if exhausted_cursor and hit_count is not None and len(records) < hit_count:
        detail = (
            f"index reported {hit_count} hits but returned {len(records)} records across all pages; "
            "the difference is unexplained by the index and the shortfall is not a screening decision"
        )
    status = "ok" if records else "no_hits"
    return records, SourceOutcome(
        "europe_pmc", status, expression, tuple(endpoints), hit_count, len(records), complete, detail
    )


# ---------------------------------------------------------------------------
# PubMed E-utilities
# ---------------------------------------------------------------------------


def _eutils_params() -> dict[str, str]:
    params = {"tool": TOOL_NAME}
    email = _contact_email()
    if email:
        params["email"] = email
    api_key = os.environ.get(NCBI_API_KEY_ENV, "").strip()
    if api_key:
        params["api_key"] = api_key
    return params


def _pubmed_record(uid: str, summary: dict[str, Any], expression: str, source_url: str) -> dict[str, Any]:
    article_ids = summary.get("articleids") or []
    ids = {
        str(item.get("idtype") or "").lower(): str(item.get("value") or "").strip()
        for item in article_ids
        if isinstance(item, dict)
    }
    pub_types = summary.get("pubtype") or []
    if isinstance(pub_types, str):
        pub_types = [pub_types]
    authors = summary.get("authors") or []
    author_names = [
        str(item.get("name") or "").strip()
        for item in authors
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    pub_date = str(summary.get("pubdate") or summary.get("epubdate") or "").strip()
    return {
        "source_system": "pubmed",
        "source_subset": "MEDLINE",
        "doi": ids.get("doi", "").lower(),
        "pmid": uid,
        "pmcid": ids.get("pmc", ""),
        "preprint_server": "",
        "title": _plain_text(summary.get("title")).rstrip("."),
        "authors": ", ".join(author_names),
        "journal": _plain_text(summary.get("fulljournalname") or summary.get("source")),
        "publication_year": pub_date.split(" ")[0] if pub_date[:4].isdigit() else "",
        "publication_types": "; ".join(sorted({str(item).strip().lower() for item in pub_types if str(item).strip()})),
        "is_preprint": "true" if any("preprint" in str(item).lower() for item in pub_types) else "false",
        "is_open_access": "",
        "cited_by_count": "",
        "linked_published_doi": "",
        "preprint_version_count": "",
        "record_url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        "abstract": "",
        "queried_expression": expression,
        "source_url": source_url,
        "retrieved_via": "ncbi_eutils_esearch_esummary",
    }


def search_pubmed(
    expression: str,
    *,
    max_records: int = DEFAULT_MAX_RECORDS_PER_SOURCE,
    page_size: int = DEFAULT_PAGE_SIZE,
    fetcher: Fetcher = fetch_json,
) -> tuple[list[dict[str, Any]], SourceOutcome]:
    endpoints: list[str] = []
    search_params = {
        "db": "pubmed",
        "term": expression,
        "retmode": "json",
        "retmax": str(max_records),
        "sort": "relevance",
        **_eutils_params(),
    }
    search_url = f"{PUBMED_BASE}/esearch.fcgi?{urlencode(search_params)}"
    endpoints.append(search_url)
    try:
        payload = fetcher(search_url)
    except RuntimeError as exc:
        # NCBI blocks some shared egress IPs outright. That is an availability gap in
        # this environment, not evidence that PubMed has no matching papers.
        return [], SourceOutcome("pubmed", "unavailable", expression, tuple(endpoints), None, 0, False, str(exc))

    result = payload.get("esearchresult") or {}
    hit_count = int(str(result.get("count") or 0) or 0)
    uids = [str(item).strip() for item in (result.get("idlist") or []) if str(item).strip()]
    records: list[dict[str, Any]] = []
    for start in range(0, len(uids), page_size):
        batch = uids[start : start + page_size]
        summary_params = {"db": "pubmed", "id": ",".join(batch), "retmode": "json", **_eutils_params()}
        summary_url = f"{PUBMED_BASE}/esummary.fcgi?{urlencode(summary_params)}"
        endpoints.append(summary_url)
        try:
            summary_payload = fetcher(summary_url)
        except RuntimeError as exc:
            return records, SourceOutcome(
                "pubmed", "ok" if records else "unavailable", expression, tuple(endpoints),
                hit_count, len(records), False, str(exc),
            )
        summaries = (summary_payload.get("result") or {})
        for uid in batch:
            summary = summaries.get(uid)
            if isinstance(summary, dict):
                records.append(_pubmed_record(uid, summary, expression, summary_url))
        _sleep()
    complete = len(records) >= hit_count
    status = "ok" if records else "no_hits"
    return records, SourceOutcome(
        "pubmed", status, expression, tuple(endpoints), hit_count, len(records), complete
    )


# ---------------------------------------------------------------------------
# Crossref (DOI registration metadata; catches records absent from PubMed)
# ---------------------------------------------------------------------------

CROSSREF_NOTE = (
    "query.bibliographic is a ranked relevance query: reported_hit_count is the summed size of the "
    "candidate pools Crossref scored across the variant queries, not a count of publications about the "
    "subject, and the same work can be counted in more than one pool. The retrieved rows are the "
    "top-ranked sample of each query only."
)


def _plain_text(value: Any) -> str:
    """Strip JATS/HTML markup and unescape entities in indexed or deposited text.

    Entities are unescaped before the tag strip because indexes deposit escaped markup
    (``&lt;i&gt;``), and again afterwards so a doubly escaped ``&amp;amp;`` resolves.
    """

    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def _crossref_record(item: dict[str, Any], expression: str, source_url: str) -> dict[str, Any]:
    titles = item.get("title") or []
    container = item.get("container-title") or []
    issued_parts = ((item.get("issued") or {}).get("date-parts") or [[]])[0]
    authors = item.get("author") or []
    author_names = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        family = str(author.get("family") or "").strip()
        given = str(author.get("given") or "").strip()
        name = f"{family} {given[:1]}".strip() if family else str(author.get("name") or "").strip()
        if name:
            author_names.append(name)
    doi = str(item.get("DOI") or "").strip().lower()
    item_type = str(item.get("type") or "").strip().lower()
    is_preprint = item_type == "posted-content"
    return {
        "source_system": "crossref",
        "source_subset": item_type,
        "doi": doi,
        "pmid": "",
        "pmcid": "",
        "preprint_server": _plain_text((container[:1] or [""])[0]) if is_preprint else "",
        "title": _plain_text((titles[:1] or [""])[0]).rstrip("."),
        "authors": ", ".join(author_names),
        "journal": _plain_text((container[:1] or [""])[0]),
        "publication_year": str(issued_parts[0]) if issued_parts else "",
        "publication_types": item_type,
        "is_preprint": "true" if is_preprint else "false",
        "is_open_access": "",
        "cited_by_count": str(item.get("is-referenced-by-count") or ""),
        "linked_published_doi": "",
        "preprint_version_count": "",
        "record_url": str(item.get("URL") or (f"https://doi.org/{doi}" if doi else "")),
        "abstract": _plain_text(item.get("abstract")),
        "queried_expression": expression,
        "source_url": source_url,
        "retrieved_via": "crossref_rest_works",
    }


def search_crossref(
    query: str,
    *,
    name_variants: Iterable[str] = (),
    context_terms: Iterable[str] = (),
    max_records: int = DEFAULT_MAX_RECORDS_PER_SOURCE,
    page_size: int = 50,
    fetcher: Fetcher = fetch_json,
) -> tuple[list[dict[str, Any]], SourceOutcome]:
    # Crossref has no boolean phrase grammar, so each name variant is a separate
    # bibliographic query and the union is recorded with its per-query provenance.
    expressions = _phrase_terms(query, name_variants)
    context = " ".join(str(term).strip() for term in context_terms if str(term).strip())
    endpoints: list[str] = []
    records: list[dict[str, Any]] = []
    hit_total = 0
    failures: list[str] = []
    for expression in expressions:
        bibliographic = f"{expression} {context}".strip()
        # No ``select`` field list: Crossref rejects some documented combinations with
        # HTTP 400, and a silently dropped source is worse than a larger payload.
        params = {
            "query.bibliographic": bibliographic,
            "rows": str(min(page_size, max_records)),
            "sort": "relevance",
        }
        email = _contact_email()
        if email:
            params["mailto"] = email
        url = f"{CROSSREF_BASE}/works?{urlencode(params)}"
        endpoints.append(url)
        try:
            payload = fetcher(url)
        except RuntimeError as exc:
            failures.append(f"{expression}: {exc}")
            continue
        message = payload.get("message") or {}
        hit_total += int(message.get("total-results") or 0)
        for item in message.get("items") or []:
            if isinstance(item, dict):
                records.append(_crossref_record(item, bibliographic, url))
        _sleep()
    if not records and failures:
        return [], SourceOutcome(
            "crossref", "unavailable", "; ".join(expressions), tuple(endpoints), None, 0, False, " | ".join(failures)
        )
    status = "ok" if records else "no_hits"
    return records, SourceOutcome(
        "crossref",
        status,
        "; ".join(expressions),
        tuple(endpoints),
        hit_total,
        len(records),
        # Crossref relevance search is a ranked sample, never a declared-complete sweep.
        False,
        " | ".join([CROSSREF_NOTE, *failures]),
    )


# ---------------------------------------------------------------------------
# bioRxiv / medRxiv detail API (preprint version and journal-publication linkage)
# ---------------------------------------------------------------------------

PREPRINT_DOI_PREFIX = "10.1101/"


def enrich_preprint_records(
    records: Iterable[dict[str, Any]],
    *,
    max_lookups: int = 60,
    fetcher: Fetcher = fetch_json,
) -> tuple[list[dict[str, Any]], SourceOutcome]:
    """Resolve bioRxiv/medRxiv server, version count, and published-journal DOI.

    The linkage matters for appraisal: a preprint that later appeared in a journal is
    different evidence from one that never did, and the difference is only visible in
    the preprint server's own record.
    """

    candidates: list[str] = []
    for record in records:
        doi = str(record.get("doi") or "").strip().lower()
        if doi.startswith(PREPRINT_DOI_PREFIX) and doi not in candidates:
            candidates.append(doi)
    candidates = sorted(candidates)[:max_lookups]

    endpoints: list[str] = []
    resolved: list[dict[str, Any]] = []
    failures: list[str] = []
    for doi in candidates:
        for server in ("biorxiv", "medrxiv"):
            url = f"{BIORXIV_BASE}/details/{server}/{quote(doi, safe='/')}"
            endpoints.append(url)
            try:
                payload = fetcher(url)
            except RuntimeError as exc:
                failures.append(f"{doi} ({server}): {exc}")
                continue
            collection = payload.get("collection") or []
            if not collection:
                _sleep()
                continue
            latest = collection[-1] if isinstance(collection[-1], dict) else {}
            published = str(latest.get("published") or "").strip()
            resolved.append(
                {
                    "doi": doi,
                    "preprint_server": server,
                    "preprint_version_count": str(len(collection)),
                    "linked_published_doi": "" if published.upper() in {"", "NA"} else published.lower(),
                    "preprint_category": str(latest.get("category") or "").strip(),
                    "source_url": url,
                }
            )
            _sleep()
            break
        else:
            _sleep()
    if candidates and not resolved and failures:
        return [], SourceOutcome(
            "biorxiv_medrxiv", "unavailable", f"{len(candidates)} preprint DOIs",
            tuple(endpoints), None, 0, False, " | ".join(failures),
        )
    status = "ok" if resolved else "no_hits"
    return resolved, SourceOutcome(
        "biorxiv_medrxiv",
        status,
        f"{len(candidates)} preprint DOIs from the retrieved set",
        tuple(endpoints),
        len(candidates),
        len(resolved),
        len(candidates) <= max_lookups,
        " | ".join(failures),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _record_key(record: dict[str, Any]) -> str:
    doi = str(record.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    pmid = str(record.get("pmid") or "").strip()
    if pmid:
        return f"pmid:{pmid}"
    pmcid = str(record.get("pmcid") or "").strip()
    if pmcid:
        return f"pmcid:{pmcid}"
    title = " ".join(str(record.get("title") or "").lower().split())
    year = str(record.get("publication_year") or "").strip()
    return f"title:{title}|{year}"


def search_literature(
    query: str,
    out_dir: str | Path,
    *,
    name_variants: Iterable[str] = (),
    context_terms: Iterable[str] = (),
    sources: Iterable[str] = LITERATURE_SOURCES,
    max_records_per_source: int = DEFAULT_MAX_RECORDS_PER_SOURCE,
    fetcher: Fetcher = fetch_json,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Retrieve bibliographic records for one topic across the declared literature lane.

    Returns normalized records plus per-source outcomes. No screening decision, quality
    judgement, or relevance claim is made here.
    """

    out_dir = ensure_dir(out_dir)
    requested = [str(source).strip().lower() for source in sources if str(source).strip()]
    unknown = sorted(set(requested) - set(LITERATURE_SOURCES))
    if unknown:
        raise ValueError(
            "Unregistered literature source(s): "
            + ", ".join(unknown)
            + ". Registered sources: "
            + ", ".join(LITERATURE_SOURCES)
        )

    name_variants = list(name_variants)
    context_terms = list(context_terms)
    records: list[dict[str, Any]] = []
    outcomes: list[SourceOutcome] = []

    if "europe_pmc" in requested:
        expression = europe_pmc_expression(query, name_variants, context_terms)
        found, outcome = search_europe_pmc(
            expression, max_records=max_records_per_source, fetcher=fetcher
        )
        records.extend(found)
        outcomes.append(outcome)

    if "pubmed" in requested:
        expression = pubmed_expression(query, name_variants, context_terms)
        found, outcome = search_pubmed(
            expression, max_records=max_records_per_source, fetcher=fetcher
        )
        records.extend(found)
        outcomes.append(outcome)

    if "crossref" in requested:
        found, outcome = search_crossref(
            query,
            name_variants=name_variants,
            context_terms=context_terms,
            max_records=max_records_per_source,
            fetcher=fetcher,
        )
        records.extend(found)
        outcomes.append(outcome)

    preprint_links: list[dict[str, Any]] = []
    if "biorxiv_medrxiv" in requested:
        preprint_links, outcome = enrich_preprint_records(records, fetcher=fetcher)
        outcomes.append(outcome)
        by_doi = {link["doi"]: link for link in preprint_links}
        for record in records:
            link = by_doi.get(str(record.get("doi") or "").strip().lower())
            if not link:
                continue
            record["preprint_server"] = link["preprint_server"]
            record["preprint_version_count"] = link["preprint_version_count"]
            record["linked_published_doi"] = link["linked_published_doi"]
            record["is_preprint"] = "true"
            record["preprint_linkage_source_url"] = link["source_url"]

    for record in records:
        record["record_key"] = _record_key(record)
    records.sort(key=lambda row: (row["record_key"], row["source_system"]))

    records_path = write_csv_rows(
        out_dir / "literature_records.csv",
        [{field: record.get(field, "") for field in RECORD_FIELDNAMES} for record in records],
        RECORD_FIELDNAMES,
    )
    records_json_path = write_json(out_dir / "literature_records.json", records)
    unavailable = sorted(item.source_system for item in outcomes if item.status == "unavailable")
    truncated = sorted(
        item.source_system for item in outcomes if item.status == "ok" and not item.pagination_complete
    )
    provenance = {
        "generated_utc": generated_utc or "",
        "query_original": query,
        "name_variants_searched": name_variants,
        "context_terms": context_terms,
        "requested_sources": requested,
        "registered_sources": list(LITERATURE_SOURCES),
        "decision_scope": "retrieval_only",
        "review_status": "requires_human_review",
        "record_count_raw": len(records),
        "distinct_record_keys": len({record["record_key"] for record in records}),
        "unavailable_sources": unavailable,
        "truncated_sources": truncated,
        "preprint_linkage_lookups": len(preprint_links),
        "sources": [
            {
                "source_system": item.source_system,
                "status": item.status,
                "queried_expression": item.queried_expression,
                "reported_hit_count": item.reported_hit_count,
                "retrieved_count": item.retrieved_count,
                "pagination_complete": item.pagination_complete,
                "detail": item.detail,
                "endpoints": list(item.endpoints),
            }
            for item in outcomes
        ],
        "coverage_gap_semantics": (
            "status=unavailable means the index could not be reached and its coverage is unknown; it is "
            "not evidence that no matching publication exists. status=no_hits means the index answered "
            "and reported no match for the declared expression. pagination_complete=false means the "
            "retrieved set is a ranked sample, not the full result set."
        ),
        "note": (
            "Retrieval evidence only. A bibliographic hit does not establish that the publication "
            "measured the queried metabolite, that its species or design match the question, or that "
            "underlying data are deposited. Screening and appraisal run offline in "
            "metabotyping_agentic.discovery.literature_review."
        ),
    }
    provenance_path = write_json(out_dir / "literature_provenance.json", provenance)
    return {
        "query": query,
        "records": records,
        "outcomes": outcomes,
        "records_path": records_path,
        "records_json_path": records_json_path,
        "provenance_path": provenance_path,
        "provenance": provenance,
    }

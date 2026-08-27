"""MetGENE gene-centric annotation intake (live, opt-in).

MetGENE is the Metabolomics Workbench gene-centric tool hosted at ``bdcw.org``. It
answers "which compounds, reactions, and Metabolomics Workbench studies are
*annotated* to this gene", which is a different scientific claim from "this
metabolite was measured". Every row this module writes is annotation evidence and
carries ``measurement_established=not_established``.

The module lives outside ``metabolomics_workbench.py`` on purpose: it is a
different host, a different licence posture (KEGG-derived content under
personal/non-commercial terms), and a contradictory wire contract. MetGENE returns
HTML under ``application/json``, zero-length bodies with HTTP 200, and HTTP 500
for an unrecognised gene symbol, so it cannot share the strict JSON fetcher.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..io import ensure_dir, write_csv_rows, write_json

BASE_URL = "https://bdcw.org/MetGENE/rest"
HOMEPAGE = "https://bdcw.org/MetGENE/"
TERMS_URL = "https://bdcw.org/MetGENE/termsofuse.php"
KEGG_TERMS_URL = "https://www.kegg.jp/kegg/legal.html"
CITATION = (
    "Srinivasan S, et al. MetGENE: gene-centric metabolomics information retrieval. "
    "GigaScience 2023;12:giad089. doi:10.1093/gigascience/giad089. RRID:SCR_023402"
)

# The studies and metabolites contexts call KEGG behind an R subprocess, so the
# first request for a gene is slow; a short timeout would be recorded as an
# unavailable source rather than as latency.
DEFAULT_TIMEOUT_SECONDS = 60
POLITE_DELAY_SECONDS = 1.0
USER_AGENT = "metabotyping-agentic-workbench/0.1"

# Every retrieval lane declared here must also be registered in
# ``metabotyping_agentic.knowledge.source_registry``; the source-registry librarian
# treats an unregistered lane as a blocking escalation rather than a usable source.
METGENE_SOURCE_ID = "metgene"

# Verified against the service's own validator error strings, which enumerate the
# accepted values. There is no ``pathways`` context and no aggregate ``all``.
METGENE_CONTEXTS = ("summary", "metabolites", "reactions", "studies")
METGENE_SPECIES = ("human", "hsa", "mouse", "mmu", "rat", "rno")
METGENE_GENE_ID_TYPES = (
    "SYMBOL",
    "SYMBOL_OR_ALIAS",
    "ALIAS",
    "ENTREZID",
    "GENENAME",
    "ENSEMBL",
    "REFSEQ",
    "UNIPROT",
    "HGNC",
)
# metabolites/reactions answer ``[[{...}]]``; studies/summary answer ``[{...}]``.
# Branch on the context, never on the observed shape: the empty forms differ too
# (``[[]]`` versus ``[]``).
DOUBLE_NESTED_CONTEXTS = frozenset({"metabolites", "reactions"})

CONTEXT_STATUSES = (
    "ok",
    "no_hits",
    "gene_not_annotated",
    "gene_unresolved_or_source_error",
    "unavailable",
    "indeterminate_empty_body",
)

PATHWAY_LISTING_STATUS = "not_retrievable_by_api"
PATHWAY_LISTING_DETAIL = (
    "MetGENE exposes no REST pathways context (HTTP 400 'Invalid function: pathways'), and "
    "pathways.php reads gene identifiers from server session state rather than from query "
    "parameters. Only the precomputed integer pathway count in the summary context is retrievable."
)

COVERAGE_GAP_SEMANTICS = (
    "status=unavailable means MetGENE could not be reached and its coverage is unknown. "
    "status=no_hits means MetGENE answered and this gene product has no annotated rows for the "
    "context. status=gene_not_annotated means the identifier resolved but MetGENE holds no record "
    "for it. status=gene_unresolved_or_source_error means HTTP 500, which MetGENE returns both for "
    "an unrecognised or wrong-case gene symbol and for a genuine outage; the two are not "
    "distinguishable from the response and must be resolved by a reviewer. "
    "status=indeterminate_empty_body means a zero-length HTTP 200, which an unrecognised anatomy "
    "term also produces, so it is not evidence of absence."
)

INFERENCE_SEMANTICS = (
    "Every row is a gene-product annotation, not a measurement. A KEGG reaction linking a gene "
    "product to a compound is not evidence that the compound was measured, quantified, or changed "
    "in any study, tissue, or species. A MetGENE study accession is an annotation-derived "
    "candidate reached by RefMet name, and the study must be re-fetched from Metabolomics "
    "Workbench before anything is said about what it reported."
)

LICENCE_ENCUMBRANCE = "kegg_derived_noncommercial"
LICENCE_UNACKNOWLEDGED = "unacknowledged_kegg_and_noncommercial_terms"
LICENCE_ACKNOWLEDGED = "acknowledged_by_operator_for_non_commercial_research_use"


@dataclass(frozen=True)
class RawResponse:
    """A MetGENE response before any interpretation.

    ``http_status`` is ``None`` only for a transport failure. An HTTP error status
    is data here, not an exception, because MetGENE encodes distinct scientific
    facts in 403, 500, and a zero-length 200.
    """

    url: str
    http_status: int | None
    content_type: str
    body: str
    transport_error: str = ""


@dataclass(frozen=True)
class ContextOutcome:
    """What one MetGENE context actually returned, including why it returned nothing."""

    context: str
    status: str
    url: str
    http_status: int | None
    row_count: int
    detail: str = ""


RawFetcher = Callable[[str], RawResponse]


def fetch_raw(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> RawResponse:
    """Fetch a MetGENE URL without interpreting the body.

    Never raises for an HTTP error status: the status code is part of the answer.
    """

    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit public data adapter
            body = response.read().decode("utf-8", "replace")
            content_type = str(response.headers.get("Content-Type") or "")
            return RawResponse(url, int(response.status), content_type, body)
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # pragma: no cover - body is optional diagnostic detail
            body = ""
        content_type = str(exc.headers.get("Content-Type") or "") if exc.headers else ""
        return RawResponse(url, int(exc.code), content_type, body)
    except (URLError, TimeoutError) as exc:
        return RawResponse(url, None, "", "", transport_error=str(exc))


def _sleep() -> None:
    # Sequential requests only. Each call runs an R subprocess and live KEGG lookups
    # server-side, so parallelism is both slow and impolite.
    time.sleep(POLITE_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


# Characters that would silently break the mandatory nine-slot path grammar or be
# rejected by the site front end before the application sees the request.
_PATH_HOSTILE = re.compile(r"[/?#%&;\\]")


def metgene_encode(value: str) -> str:
    """Encode one MetGENE path segment: spaces become ``+``, never ``%20``.

    A percent-encoded space is rejected by the server front end with HTTP 403
    before the application sees it, which reads as an access-control failure
    rather than an encoding failure. Standard path-joining helpers emit ``%20``,
    so the substitution is made explicitly here and the path is not percent-encoded.

    A value carrying a path metacharacter is refused rather than encoded: escaping
    it would be rejected upstream, and passing it through would shift every later
    keyword out of position and turn a malformed request into a plausible answer.
    """

    text = str(value).strip()
    if _PATH_HOSTILE.search(text):
        raise ValueError(
            f"MetGENE path segment {text!r} contains a character that cannot be transmitted "
            "in this API's path grammar (one of / ? # % & ; \\)."
        )
    return re.sub(r"\s+", "+", text)


def metgene_url(
    context: str,
    species: str,
    gene_id_type: str,
    gene: str,
    *,
    anatomy: str = "NA",
    disease: str = "NA",
    phenotype: str = "NA",
    view_type: str = "json",
) -> str:
    """Build a MetGENE REST URL.

    All nine path slots are mandatory; an unused filter is the literal string
    ``NA``, not an empty segment. The context must be lowercase and the species,
    gene id type, and view type are case sensitive.
    """

    if context not in METGENE_CONTEXTS:
        raise ValueError(
            f"Unsupported MetGENE context {context!r}. Supported: " + ", ".join(METGENE_CONTEXTS)
        )
    if species not in METGENE_SPECIES:
        raise ValueError(
            f"Unsupported MetGENE species {species!r}. Supported: " + ", ".join(METGENE_SPECIES)
        )
    if gene_id_type not in METGENE_GENE_ID_TYPES:
        raise ValueError(
            f"Unsupported MetGENE gene id type {gene_id_type!r}. Supported: "
            + ", ".join(METGENE_GENE_ID_TYPES)
        )
    gene = str(gene).strip()
    if not gene:
        raise ValueError("A gene identifier is required.")
    # A partial multi-gene match prepends an unparseable HTML fragment to otherwise
    # valid JSON, so genes are fanned out one request each. Every separator the API
    # accepts is refused here, including whitespace and '+', which the encoder would
    # otherwise turn into a silent two-gene query.
    # A single underscore is legitimate (a RefSeq accession such as NM_005502); a
    # double underscore is one of the API's own multi-gene separators.
    if "__" in gene or not re.fullmatch(r"[A-Za-z0-9._:-]+", gene):
        raise ValueError(
            f"MetGENE is queried one gene per request and {gene!r} is not a single identifier; "
            "pass genes separately rather than as a comma, underscore, plus, semicolon, or "
            "whitespace separated list."
        )
    return (
        f"{BASE_URL}/{context}"
        f"/species/{metgene_encode(species)}"
        f"/GeneIDType/{metgene_encode(gene_id_type)}"
        f"/GeneInfoStr/{metgene_encode(gene)}"
        f"/anatomy/{metgene_encode(anatomy) or 'NA'}"
        f"/disease/{metgene_encode(disease) or 'NA'}"
        f"/phenotype/{metgene_encode(phenotype) or 'NA'}"
        f"/viewType/{view_type}"
    )


# ---------------------------------------------------------------------------
# Response classification and parsing (pure, offline-testable)
# ---------------------------------------------------------------------------


def _has_json_tail(body: str) -> bool:
    """True when an HTML-prefixed body still carries a parseable JSON value.

    This is the partial multi-gene response shape: the fragment names the genes that
    were not found and is followed by valid JSON for the ones that were.
    """

    for index, char in enumerate(body):
        if char not in "[{":
            continue
        try:
            json.loads(body[index:])
        except json.JSONDecodeError:
            continue
        return True
    return False


def classify_metgene_response(response: RawResponse, context: str) -> tuple[str, Any, str]:
    """Return ``(status, payload_or_None, detail)`` for one MetGENE response.

    A Content-Type of ``application/json`` does not guarantee a JSON body: valid
    JSON, HTML-only bodies, HTML-prefixed JSON, and zero-length bodies were all
    observed under it, and the three most informative failure states return 200.
    """

    if response.transport_error:
        return "unavailable", None, f"transport error: {response.transport_error}"
    status_code = response.http_status
    if status_code == 403:
        return (
            "unavailable",
            None,
            "HTTP 403 from the site front end; check for a percent-encoded space in the path",
        )
    if status_code == 500:
        return (
            "gene_unresolved_or_source_error",
            None,
            "HTTP 500; MetGENE returns this both for an unrecognised or wrong-case gene "
            "identifier and for a source outage",
        )
    if status_code is not None and status_code >= 400:
        snippet = " ".join(response.body[:200].split())
        return "unavailable", None, f"HTTP {status_code}: {snippet}"

    body = response.body
    if not body.strip():
        return (
            "indeterminate_empty_body",
            None,
            "zero-length HTTP 200; an unrecognised anatomy, disease, or phenotype term produces "
            "the same response as a genuine miss",
        )
    stripped = body.lstrip()
    if stripped.startswith("<"):
        text = " ".join(re.sub(r"<[^>]+>", " ", body)[:200].split())
        # A partial multi-gene match prepends an HTML fragment to otherwise valid
        # JSON. The client refuses multi-gene requests, so reaching this branch means
        # the response is mixed and the JSON tail must not be read as a whole answer.
        if _has_json_tail(body):
            return (
                "unavailable",
                None,
                "HTML fragment prepended to JSON, which the source returns for a partial "
                "multi-gene match; the JSON tail is not a complete answer: " + text,
            )
        if "no summaries found" in body.lower():
            return "gene_not_annotated", None, text
        return "unavailable", None, "HTML body returned in place of JSON: " + text
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "unavailable", None, "non-JSON body: " + " ".join(body[:200].split())

    rows = metgene_rows(context, payload)
    if not rows:
        return "no_hits", payload, ""
    return "ok", payload, ""


def metgene_rows(context: str, payload: Any) -> list[dict[str, Any]]:
    """Unwrap a MetGENE payload by context.

    ``metabolites`` and ``reactions`` are double nested; ``studies`` and
    ``summary`` are single nested.
    """

    if payload is None:
        return []
    items = payload
    if context in DOUBLE_NESTED_CONTEXTS and isinstance(items, list):
        flattened: list[Any] = []
        for item in items:
            if isinstance(item, list):
                flattened.extend(item)
            else:
                flattened.append(item)
        items = flattened
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def strip_kegg_anchor(value: Any) -> str:
    """Return the bare accession from a ``studies`` row.

    The studies context returns KEGG_COMPOUND_ID as an HTML anchor even under
    ``viewType/json``.
    """

    text = str(value or "")
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def split_study_ids(value: Any) -> list[str]:
    """Split the space-delimited STUDY_ID string a ``studies`` row returns."""

    return [token for token in str(value or "").split() if token]


def _first(record: dict[str, Any], *names: str) -> str:
    for name in names:
        value = record.get(name)
        if isinstance(value, list):
            # A null inside an array must not become the literal string "None".
            value = "; ".join(
                str(item).strip() for item in value if item is not None and str(item).strip()
            )
        text = str(value if value is not None else "").strip()
        if text:
            return text
    return ""


def _echo_status(echoed: str, queried: str) -> str:
    """Three states, because "no identifier came back" is not "the echo matched".

    MetGENE normalizes identifiers to Entrez internally and echoes them back that
    way, so a mismatch is expected for a SYMBOL query and is not by itself an error.
    A row with no echo at all leaves the entity question open.
    """

    if not echoed or echoed == "not_reported":
        return "no_echo_returned"
    return "echo_matches_query" if echoed == queried else "echo_differs_from_query"


def _parse_count(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def fetch_metgene_context(
    context: str,
    species: str,
    gene_id_type: str,
    gene: str,
    *,
    anatomy: str = "NA",
    disease: str = "NA",
    phenotype: str = "NA",
    fetcher: RawFetcher = fetch_raw,
) -> tuple[list[dict[str, Any]], ContextOutcome]:
    """Retrieve one MetGENE context for one gene. Retrieval only, no labeling."""

    url = metgene_url(
        context,
        species,
        gene_id_type,
        gene,
        anatomy=anatomy,
        disease=disease,
        phenotype=phenotype,
    )
    response = fetcher(url)
    status, payload, detail = classify_metgene_response(response, context)
    rows = metgene_rows(context, payload) if status == "ok" else []
    return rows, ContextOutcome(
        context=context,
        status=status,
        url=url,
        http_status=response.http_status,
        row_count=len(rows),
        detail=detail,
    )


def fetch_metgene_gene(
    gene: str,
    *,
    species: str = "human",
    gene_id_type: str = "SYMBOL",
    contexts: Iterable[str] = METGENE_CONTEXTS,
    anatomy: str = "NA",
    disease: str = "NA",
    phenotype: str = "NA",
    fetcher: RawFetcher = fetch_raw,
    delay: Callable[[], None] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[ContextOutcome]]:
    """Retrieve the requested MetGENE contexts for a single gene, sequentially."""

    requested = [str(item).strip().lower() for item in contexts if str(item).strip()]
    unknown = sorted(set(requested) - set(METGENE_CONTEXTS))
    if unknown:
        raise ValueError(
            "Unsupported MetGENE context(s): "
            + ", ".join(unknown)
            + ". Supported contexts: "
            + ", ".join(METGENE_CONTEXTS)
        )
    # The polite delay is the default for every caller. Identity-checking the fetcher
    # would drop it for any wrapped live fetcher, so an offline caller opts out
    # explicitly by passing a no-op delay instead.
    sleeper = _sleep if delay is None else delay

    rows_by_context: dict[str, list[dict[str, Any]]] = {}
    outcomes: list[ContextOutcome] = []
    issued = 0
    for context in METGENE_CONTEXTS:
        if context not in requested:
            continue
        # Sleep between requests, not before the first one, whichever contexts were asked for.
        if issued:
            sleeper()
        issued += 1
        rows, outcome = fetch_metgene_context(
            context,
            species,
            gene_id_type,
            gene,
            anatomy=anatomy,
            disease=disease,
            phenotype=phenotype,
            fetcher=fetcher,
        )
        rows_by_context[context] = rows
        outcomes.append(outcome)
    return rows_by_context, outcomes


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

SUMMARY_FIELDNAMES = [
    "queried_gene",
    "queried_gene_id_type",
    "queried_species",
    "echoed_gene_identifier",
    "identifier_echo_status",
    "pathway_count",
    "reaction_count",
    "metabolite_count",
    "study_count",
    "count_basis",
    "pathway_listing_status",
    "evidence_type",
    "measurement_established",
    "review_status",
    "decision_scope",
    "licence_encumbrance",
    "source_url",
    "retrieved_via",
]

METABOLITE_FIELDNAMES = [
    "queried_gene",
    "queried_gene_id_type",
    "queried_species",
    "echoed_gene_identifier",
    "identifier_echo_status",
    "kegg_compound_id",
    "refmet_name",
    "refmet_mapping_status",
    "kegg_reaction_id",
    "evidence_type",
    "inference_basis",
    "measurement_established",
    "species_of_annotation",
    "species_inference",
    "metstat_link",
    "link_protocol_downgrade",
    "review_status",
    "decision_scope",
    "licence_encumbrance",
    "source_url",
    "retrieved_via",
]

REACTION_FIELDNAMES = [
    "queried_gene",
    "queried_gene_id_type",
    "queried_species",
    "echoed_gene_identifier",
    "identifier_echo_status",
    "kegg_reaction_id",
    "kegg_reaction_name",
    "kegg_reaction_equation",
    "evidence_type",
    "inference_basis",
    "measurement_established",
    "species_of_annotation",
    "species_inference",
    "review_status",
    "decision_scope",
    "licence_encumbrance",
    "source_url",
    "retrieved_via",
]

STUDY_CANDIDATE_FIELDNAMES = [
    "queried_gene",
    "queried_gene_id_type",
    "queried_species",
    "kegg_compound_id",
    "refmet_name",
    "refmet_mapping_status",
    "study_id",
    "study_link",
    "evidence_type",
    "inference_basis",
    "measurement_established",
    "repository_refetch_required",
    "species_of_annotation",
    "species_inference",
    "review_status",
    "decision_scope",
    "licence_encumbrance",
    "source_url",
    "retrieved_via",
]

ESCALATION_FIELDNAMES = [
    "queried_gene",
    "queried_species",
    "context",
    "status",
    "escalation_reason",
    "reviewer_question",
    "evidence_needed",
    "source_url",
]

# A species value the caller supplied maps to exactly one annotation species; a
# result is never carried across species without a reviewer decision.
_SPECIES_LABELS = {
    "human": "Homo sapiens",
    "hsa": "Homo sapiens",
    "mouse": "Mus musculus",
    "mmu": "Mus musculus",
    "rat": "Rattus norvegicus",
    "rno": "Rattus norvegicus",
}

_ESCALATION_QUESTIONS = {
    "unavailable": (
        "MetGENE could not be reached for this context; is the gene uncovered or was the source down?",
        "a successful retrieval of the same context, or a recorded outage window",
    ),
    "gene_unresolved_or_source_error": (
        "HTTP 500: is the queried identifier wrong or wrongly cased, or was the source failing?",
        "confirmation of the canonical species-specific symbol casing, then a repeat retrieval",
    ),
    "indeterminate_empty_body": (
        "A zero-length response: is the filter term outside the source vocabulary, or is the result genuinely empty?",
        "the source filter vocabulary, or the same query with the filter set to NA",
    ),
    "gene_not_annotated": (
        "The identifier resolved but MetGENE holds no record; should another identifier type be tried?",
        "the same gene queried by ENTREZID or ENSEMBL, and confirmation the gene is in scope",
    ),
    "no_hits": (
        "MetGENE answered with zero rows; is this a real annotation gap for this gene product?",
        "an independent annotation source for the same gene, recorded as a separate lane",
    ),
}


def _summary_rows(
    rows: list[dict[str, Any]],
    *,
    gene: str,
    gene_id_type: str,
    species: str,
    url: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in rows:
        echoed = _first(record, "Genes", "_row")
        out.append(
            {
                "queried_gene": gene,
                "queried_gene_id_type": gene_id_type,
                "queried_species": species,
                "echoed_gene_identifier": echoed or "not_reported",
                "identifier_echo_status": _echo_status(echoed, gene),
                "pathway_count": _parse_count(record.get("Pathways")),
                "reaction_count": _parse_count(record.get("Reactions")),
                "metabolite_count": _parse_count(record.get("Metabolites")),
                "study_count": _parse_count(record.get("Studies")),
                "count_basis": "precomputed_count",
                "pathway_listing_status": PATHWAY_LISTING_STATUS,
                "evidence_type": "precomputed_annotation_count",
                "measurement_established": "not_established",
                "review_status": "requires_human_review",
                "decision_scope": "annotation_retrieval_only",
                "licence_encumbrance": LICENCE_ENCUMBRANCE,
                "source_url": url,
                "retrieved_via": "metgene_summary",
            }
        )
    return out


def _metabolite_rows(
    rows: list[dict[str, Any]],
    *,
    gene: str,
    gene_id_type: str,
    species: str,
    url: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in rows:
        echoed = _first(record, "Gene")
        refmet_name = _first(record, "REFMET_NAME")
        out.append(
            {
                "queried_gene": gene,
                "queried_gene_id_type": gene_id_type,
                "queried_species": species,
                "echoed_gene_identifier": echoed or "not_reported",
                "identifier_echo_status": _echo_status(echoed, gene),
                "kegg_compound_id": _first(record, "KEGG_COMPOUND_ID") or "not_reported",
                "refmet_name": refmet_name or "not_reported",
                "refmet_mapping_status": "mapped" if refmet_name else "absent_no_refmet_mapping",
                "kegg_reaction_id": _first(record, "KEGG_REACTION_ID") or "not_reported",
                "evidence_type": "gene_product_reaction_annotation",
                "inference_basis": "kegg_gene_reaction_annotation",
                "measurement_established": "not_established",
                "species_of_annotation": _SPECIES_LABELS.get(species, species),
                "species_inference": "direct_species_query",
                "metstat_link": _first(record, "METSTAT_LINK") or "not_reported",
                "link_protocol_downgrade": "http"
                if _first(record, "METSTAT_LINK").startswith("http://")
                else "none",
                "review_status": "requires_human_review",
                "decision_scope": "annotation_retrieval_only",
                "licence_encumbrance": LICENCE_ENCUMBRANCE,
                "source_url": url,
                "retrieved_via": "metgene_metabolites",
            }
        )
    return out


def _reaction_rows(
    rows: list[dict[str, Any]],
    *,
    gene: str,
    gene_id_type: str,
    species: str,
    url: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in rows:
        echoed = _first(record, "Gene")
        out.append(
            {
                "queried_gene": gene,
                "queried_gene_id_type": gene_id_type,
                "queried_species": species,
                "echoed_gene_identifier": echoed or "not_reported",
                "identifier_echo_status": _echo_status(echoed, gene),
                "kegg_reaction_id": _first(record, "KEGG_REACTION_ID", "_row") or "not_reported",
                "kegg_reaction_name": _first(record, "KEGG_REACTION_NAME") or "not_reported",
                "kegg_reaction_equation": _first(record, "KEGG_REACTION_EQN") or "not_reported",
                "evidence_type": "gene_product_reaction_annotation",
                "inference_basis": "kegg_gene_reaction_annotation",
                "measurement_established": "not_established",
                "species_of_annotation": _SPECIES_LABELS.get(species, species),
                "species_inference": "direct_species_query",
                "review_status": "requires_human_review",
                "decision_scope": "annotation_retrieval_only",
                "licence_encumbrance": LICENCE_ENCUMBRANCE,
                "source_url": url,
                "retrieved_via": "metgene_reactions",
            }
        )
    return out


def _study_candidate_rows(
    rows: list[dict[str, Any]],
    *,
    gene: str,
    gene_id_type: str,
    species: str,
    url: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in rows:
        compound = strip_kegg_anchor(record.get("KEGG_COMPOUND_ID"))
        refmet_name = _first(record, "REFMET_NAME")
        for study_id in split_study_ids(record.get("STUDY_ID")):
            out.append(
                {
                    "queried_gene": gene,
                    "queried_gene_id_type": gene_id_type,
                    "queried_species": species,
                    "kegg_compound_id": compound or "not_reported",
                    "refmet_name": refmet_name or "not_reported",
                    "refmet_mapping_status": "mapped" if refmet_name else "absent_no_refmet_mapping",
                    "study_id": study_id,
                    "study_link": (
                        "https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID="
                        f"{study_id}"
                    ),
                    "evidence_type": "annotation_derived_study_candidate",
                    "inference_basis": "kegg_compound_to_refmet_name_then_metstat_index",
                    "measurement_established": "not_established",
                    "repository_refetch_required": True,
                    "species_of_annotation": _SPECIES_LABELS.get(species, species),
                    "species_inference": "direct_species_query",
                    "review_status": "requires_human_review",
                    "decision_scope": "annotation_retrieval_only",
                    "licence_encumbrance": LICENCE_ENCUMBRANCE,
                    "source_url": url,
                    "retrieved_via": "metgene_studies",
                }
            )
    return out


def build_escalations(
    outcomes: Iterable[ContextOutcome],
    *,
    gene: str,
    species: str,
) -> list[dict[str, Any]]:
    """Turn every non-``ok`` context outcome into an explicit reviewer question."""

    escalations: list[dict[str, Any]] = []
    for outcome in outcomes:
        if outcome.status == "ok":
            continue
        question, evidence = _ESCALATION_QUESTIONS.get(
            outcome.status,
            ("An unclassified retrieval state was recorded.", "a repeat retrieval and manual inspection"),
        )
        escalations.append(
            {
                "queried_gene": gene,
                "queried_species": species,
                "context": outcome.context,
                "status": outcome.status,
                "escalation_reason": outcome.detail or outcome.status,
                "reviewer_question": question,
                "evidence_needed": evidence,
                "source_url": outcome.url,
            }
        )
    return escalations


def lookup_gene_metabolite_annotations(
    gene: str,
    out_dir: str | Path,
    *,
    species: str = "human",
    gene_id_type: str = "SYMBOL",
    contexts: Iterable[str] = METGENE_CONTEXTS,
    anatomy: str = "NA",
    disease: str = "NA",
    phenotype: str = "NA",
    acknowledge_licence_review: bool = False,
    fetcher: RawFetcher = fetch_raw,
    generated_utc: str | None = None,
    delay: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Retrieve MetGENE annotation evidence for one gene and write it with provenance.

    Retrieval and labeling only. No identity resolution, no scoring, and no claim
    that any metabolite was measured.

    MetGENE output is KEGG-derived and its terms of use permit personal,
    non-commercial use only. Unless ``acknowledge_licence_review`` is set, the
    KEGG-derived rows are not written to disk: only the provenance record and the
    escalation queue are, and the licence question is recorded as open.
    """

    if phenotype.strip().upper() not in {"", "NA"}:
        # A byte-identical response was observed for a phenotype value versus NA,
        # so a phenotype-filtered result may not actually be phenotype filtered.
        phenotype_effect = "unverified_suspected_noop"
    else:
        phenotype = "NA"
        phenotype_effect = "not_requested"

    out_dir = ensure_dir(out_dir)
    rows_by_context, outcomes = fetch_metgene_gene(
        gene,
        species=species,
        gene_id_type=gene_id_type,
        contexts=contexts,
        anatomy=anatomy,
        disease=disease,
        phenotype=phenotype,
        fetcher=fetcher,
        delay=delay,
    )
    url_by_context = {outcome.context: outcome.url for outcome in outcomes}

    summary_rows = _summary_rows(
        rows_by_context.get("summary", []),
        gene=gene,
        gene_id_type=gene_id_type,
        species=species,
        url=url_by_context.get("summary", ""),
    )
    metabolite_rows = _metabolite_rows(
        rows_by_context.get("metabolites", []),
        gene=gene,
        gene_id_type=gene_id_type,
        species=species,
        url=url_by_context.get("metabolites", ""),
    )
    reaction_rows = _reaction_rows(
        rows_by_context.get("reactions", []),
        gene=gene,
        gene_id_type=gene_id_type,
        species=species,
        url=url_by_context.get("reactions", ""),
    )
    study_rows = _study_candidate_rows(
        rows_by_context.get("studies", []),
        gene=gene,
        gene_id_type=gene_id_type,
        species=species,
        url=url_by_context.get("studies", ""),
    )
    escalations = build_escalations(outcomes, gene=gene, species=species)
    if not acknowledge_licence_review:
        escalations.append(
            {
                "queried_gene": gene,
                "queried_species": species,
                "context": "licence",
                "status": LICENCE_UNACKNOWLEDGED,
                "escalation_reason": (
                    "MetGENE output is KEGG-derived and its terms permit personal, non-commercial "
                    "use only, so the retrieved rows were not written to disk."
                ),
                "reviewer_question": (
                    "May KEGG-derived MetGENE rows be persisted and redistributed for this project?"
                ),
                "evidence_needed": f"a reviewed licensing decision against {TERMS_URL} and {KEGG_TERMS_URL}",
                "source_url": TERMS_URL,
            }
        )

    # A context that was never queried must not be written as a zero-row table:
    # "never asked" and "the source answered and holds nothing" are different facts,
    # and an empty CSV on disk reads as the second one.
    queried = {outcome.context for outcome in outcomes}
    not_requested = [context for context in METGENE_CONTEXTS if context not in queried]
    for context in not_requested:
        escalations.append(
            {
                "queried_gene": gene,
                "queried_species": species,
                "context": context,
                "status": "not_requested",
                "escalation_reason": (
                    "This context was excluded from the request, so nothing is known about it. "
                    "Its absence from the outputs is not a source answer."
                ),
                "reviewer_question": (
                    f"Is the {context} context needed for this question, and should it be retrieved?"
                ),
                "evidence_needed": f"a retrieval run that includes the {context} context",
                "source_url": "",
            }
        )

    tables = {
        "summary": (summary_rows, SUMMARY_FIELDNAMES, "metgene_summary.csv"),
        "metabolites": (metabolite_rows, METABOLITE_FIELDNAMES, "metgene_metabolites.csv"),
        "reactions": (reaction_rows, REACTION_FIELDNAMES, "metgene_reactions.csv"),
        "studies": (study_rows, STUDY_CANDIDATE_FIELDNAMES, "metgene_study_candidates.csv"),
    }
    written: dict[str, str] = {}
    if acknowledge_licence_review:
        for context, (rows, fieldnames, filename) in tables.items():
            if context not in queried:
                # Remove a stale table from an earlier, wider run rather than leaving
                # it beside provenance that no longer covers it.
                stale = out_dir / filename
                if stale.exists():
                    stale.unlink()
                continue
            written[context] = str(write_csv_rows(out_dir / filename, rows, fieldnames))
    escalations_path = write_csv_rows(
        out_dir / "metgene_escalations.csv", escalations, ESCALATION_FIELDNAMES
    )

    summary_record = summary_rows[0] if summary_rows else {}
    provenance = {
        "generated_utc": generated_utc or "",
        "queried_gene": gene,
        "queried_gene_id_type": gene_id_type,
        "queried_species": species,
        "species_values_accepted": list(METGENE_SPECIES),
        "gene_id_types_accepted": list(METGENE_GENE_ID_TYPES),
        "anatomy_filter": anatomy,
        "disease_filter": disease,
        "phenotype_filter": phenotype,
        "phenotype_filter_effect": phenotype_effect,
        "filter_vocabulary_status": "unenumerated_no_validation_endpoint",
        "registered_source_ids": [METGENE_SOURCE_ID],
        "decision_scope": "annotation_retrieval_only",
        "review_status": "requires_human_review",
        "licence_review_status": LICENCE_ACKNOWLEDGED
        if acknowledge_licence_review
        else LICENCE_UNACKNOWLEDGED,
        "licence_terms_url": TERMS_URL,
        "kegg_terms_url": KEGG_TERMS_URL,
        "persisted_kegg_derived_fields": bool(acknowledge_licence_review),
        "persisted_kegg_derived_fields_scope": (
            "Covers every KEGG-derived value: the compound, reaction, and study-candidate tables "
            "and the precomputed pathway count. When false, only retrieval metadata (per-context "
            "status, URL, and row count) is recorded."
        ),
        "citation": CITATION,
        "contexts": [
            {
                "context": outcome.context,
                "status": outcome.status,
                "url": outcome.url,
                "http_status": outcome.http_status,
                "row_count": outcome.row_count,
                "detail": outcome.detail,
            }
            for outcome in outcomes
        ],
        "contexts_available": list(METGENE_CONTEXTS),
        "contexts_requested": sorted(queried),
        "contexts_not_requested": not_requested,
        "not_requested_semantics": (
            "A context in contexts_not_requested was never queried. Nothing is known about it, and "
            "its absence from the outputs is not a source answer."
        ),
        "pathway_listing_status": PATHWAY_LISTING_STATUS,
        "pathway_listing_detail": PATHWAY_LISTING_DETAIL,
        # The pathway integer is itself a KEGG-derived retrieved value, so it is
        # withheld alongside the tables until the licence question is answered.
        "pathway_count_precomputed": (
            summary_record.get("pathway_count") if acknowledge_licence_review else None
        ),
        "pathway_count_status": (
            "retrieved"
            if acknowledge_licence_review and summary_record
            else "withheld_pending_licence_review"
            if not acknowledge_licence_review
            else "not_retrieved"
        ),
        "unavailable_contexts": sorted(
            outcome.context for outcome in outcomes if outcome.status == "unavailable"
        ),
        "unresolved_gene_contexts": sorted(
            outcome.context
            for outcome in outcomes
            if outcome.status == "gene_unresolved_or_source_error"
        ),
        "indeterminate_contexts": sorted(
            outcome.context for outcome in outcomes if outcome.status == "indeterminate_empty_body"
        ),
        # Counted only for contexts that were actually queried; a context that was
        # not requested has no count, rather than a count of zero.
        "row_counts": {
            key: value
            for key, value in (
                ("summary", len(summary_rows) if "summary" in queried else None),
                ("metabolites", len(metabolite_rows) if "metabolites" in queried else None),
                ("reactions", len(reaction_rows) if "reactions" in queried else None),
                ("study_candidates", len(study_rows) if "studies" in queried else None),
            )
            if value is not None
        },
        "escalation_count": len(escalations),
        "coverage_gap_semantics": COVERAGE_GAP_SEMANTICS,
        "inference_semantics": INFERENCE_SEMANTICS,
        "note": (
            "Retrieval evidence only. An absent row is a coverage gap and is never substituted by "
            "a nearby analyte, a precursor, or an ortholog."
        ),
    }
    provenance_path = write_json(out_dir / "metgene_provenance.json", provenance)

    return {
        "gene": gene,
        "species": species,
        "out_dir": out_dir,
        "outcomes": outcomes,
        "summary_rows": summary_rows,
        "metabolite_rows": metabolite_rows,
        "reaction_rows": reaction_rows,
        "study_candidate_rows": study_rows,
        "escalations": escalations,
        "written_paths": written,
        "escalations_path": escalations_path,
        "provenance_path": provenance_path,
        "provenance": provenance,
    }

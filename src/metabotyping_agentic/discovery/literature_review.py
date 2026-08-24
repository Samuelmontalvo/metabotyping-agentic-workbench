"""Offline screening and appraisal of retrieved bibliographic records.

This module is deliberately network-free: it consumes records produced by
``metabotyping_agentic.live_sources.literature_search`` (live mode) or converted from
synthetic publication fixtures (offline pilot), and it produces a deterministic,
provenance-preserving screening and appraisal table.

Three guardrails shape the design:

* **Unknown is not absent.** A bibliographic record carries no structured species,
  design, or assay fields. When the retrieved text cannot support a screening call the
  record is classified ``screening_uncertain_insufficient_text`` and escalated, never
  quietly excluded.
* **Inference is labeled.** Every screening flag records whether it came from a
  structured field or from title/abstract text matching.
* **A missing accession is not proof of no deposition.** Abstract text is not a data
  availability statement, so the absence of an accession is reported as an unresolved
  deposition question routed to review.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..io import read_csv_rows, read_json, write_csv_rows, write_json
from ..models import InclusionCriteria, PublicationRecord

SCREENED_FIELDNAMES = [
    "record_key",
    "screen_class",
    "evidence_tier",
    "species_scope",
    "species_basis",
    "screen_basis",
    "review_status",
    "title",
    "authors",
    "journal",
    "publication_year",
    "publication_types",
    "is_preprint",
    "has_preprint_version",
    "linked_published_doi",
    "doi",
    "pmid",
    "pmcid",
    "cited_by_count",
    "abstract_available",
    "human_evidence",
    "exercise_evidence",
    "metabolomics_evidence",
    "genetics_evidence",
    "cpet_evidence",
    "actigraphy_evidence",
    "body_composition_evidence",
    "diet_evidence",
    "intervention_design",
    "subject_term_evidence",
    "homonym_risk",
    "data_availability_evidence",
    "accessions_in_record_text",
    "source_systems",
    "cross_source_conflicts",
    "record_url",
    "source_urls",
]

ESCALATION_FIELDNAMES = [
    "record_key",
    "escalation",
    "reason",
    "decision_needed",
    "title",
    "record_url",
]

# Text patterns. Each group is matched against title + abstract + journal only, so a
# hit is always reported as text inference rather than as a structured assertion.
HUMAN_PATTERNS = (
    r"\bhuman(s|)\b",
    r"\bmen\b",
    r"\bwomen\b",
    r"\bparticipants?\b",
    r"\bsubjects?\b",
    r"\bpatients?\b",
    r"\bathletes?\b",
    r"\bvolunteers?\b",
    r"\bcohort\b",
    r"\bhomo sapiens\b",
)
RODENT_PATTERNS = (r"\bmice\b", r"\bmouse\b", r"\brats?\b", r"\bmurine\b", r"\brodents?\b", r"\bc57bl\b")
OTHER_ANIMAL_PATTERNS = (
    r"\bzebrafish\b",
    r"\bhorses?\b",
    r"\bequine\b",
    r"\bcanine\b",
    r"\bdogs?\b",
    r"\bpigs?\b",
    r"\bporcine\b",
    r"\bbovine\b",
    r"\bcows?\b",
    r"\bsheep\b",
    r"\bmacaques?\b",
    r"\bmonkeys?\b",
    r"\bdrosophila\b",
    r"\bc\. elegans\b",
)
IN_VITRO_PATTERNS = (
    r"\bin vitro\b",
    r"\bcell lines?\b",
    r"\bmyotubes?\b",
    r"\bhek293\b",
    r"\bhepg2\b",
    r"\brecombinant enzyme\b",
    r"\bcell culture\b",
)
METABOLOMICS_PATTERNS = (
    r"\bmetabolom",
    r"\bmetabolite",
    r"\bmass spectrometry\b",
    r"\blc-?ms\b",
    r"\bgc-?ms\b",
    r"\bnmr\b",
    r"\buntargeted\b",
    r"\btargeted panel\b",
    r"\blipidom",
)
EXERCISE_PATTERNS = (
    r"\bexercise\b",
    r"\btraining\b",
    r"\bphysical activity\b",
    r"\bendurance\b",
    r"\bresistance training\b",
    r"\bsprint\b",
    r"\bcycling\b",
    r"\brunning\b",
    r"\btreadmill\b",
    r"\bhiit\b",
    r"\bathletic performance\b",
    r"\bexertion\b",
)
GENETICS_PATTERNS = (r"\bgenetic", r"\bgwas\b", r"\bgenome-wide\b", r"\bsnp\b", r"\bheritab", r"\bpolygenic\b", r"\bmendelian randomi")
CPET_PATTERNS = (r"\bvo2\s?max\b", r"\bvo2peak\b", r"\bcardiopulmonary exercise test", r"\bcpet\b", r"\bpeak oxygen uptake\b")
ACTIGRAPHY_PATTERNS = (r"\bactigraph", r"\baccelerometer", r"\bwearable", r"\bstep count", r"\bfitness tracker")
BODY_COMPOSITION_PATTERNS = (r"\bbody composition\b", r"\bdexa\b", r"\bdxa\b", r"\bfat mass\b", r"\blean mass\b", r"\bbmi\b", r"\badiposity\b")
DIET_PATTERNS = (r"\bdiet", r"\bnutrition", r"\bfeeding\b", r"\bfood intake\b", r"\bcaloric\b", r"\bfasting\b")

DESIGN_PATTERNS = (
    ("randomized_controlled_trial", (r"\brandomi[sz]ed controlled trial\b", r"\brandomi[sz]ed\b.*\btrial\b", r"\brct\b")),
    ("interventional_exercise_bout_or_program", (r"\bacute (bout|exercise)\b", r"\bexercise (intervention|program|protocol|bout)\b", r"\btraining (intervention|program|study)\b", r"\bpre-?\s?and\s?post-?exercise\b")),
    ("observational_cohort_or_cross_sectional", (r"\bcohort\b", r"\bcross-?sectional\b", r"\bobservational\b", r"\bpopulation-based\b")),
    ("preclinical_experiment", (r"\bknockout\b", r"\bko mice\b", r"\bwild-?type\b", r"\btreadmill running in (mice|rats)\b")),
)

SECONDARY_TYPE_PATTERNS = (r"review", r"meta-analysis", r"systematic", r"editorial", r"comment", r"news", r"letter")
PRIMARY_TYPE_PATTERNS = (r"journal-article", r"journal article", r"research-article", r"research support", r"clinical trial")
NON_ARTICLE_TYPE_PATTERNS = (r"editorial", r"comment", r"news", r"letter", r"correction", r"erratum", r"retract")

# A name query cannot establish chemical identity. These banks separate "the queried
# name appears in a chemistry/physiology context" from "the same string is a materials
# abbreviation" (for example Lac-Phe as a lactide-phenylalanine copolymer), so a
# homonym is escalated instead of counted as subject evidence.
BIOLOGICAL_CONTEXT_PATTERNS = (
    r"\bmetabolom",
    r"\bmetabolite",
    r"\bplasma\b",
    r"\bserum\b",
    r"\bwhole blood\b",
    r"\burine\b",
    r"\bmuscle\b",
    r"\bexercise\b",
    r"\bphysical activity\b",
    r"\blactate\b",
    r"\blactic acid\b",
    r"\bcndp2\b",
    r"\bappetite\b",
    r"\bfood intake\b",
    r"\bobesity\b",
    r"\bmice\b",
    r"\bhuman",
    r"\bpharmacokinetic",
)
MATERIAL_CONTEXT_PATTERNS = (
    r"\bcopolymer",
    r"\bpolymer",
    r"\bpolylactide\b",
    r"\bpoly\(lact",
    r"\bscaffold",
    r"\bhydrogel",
    r"\bnanoparticle",
    r"\bmicelle",
    r"\bresin\b",
    r"\bcoating\b",
    r"\btissue engineering\b",
    r"\bdrug delivery\b",
)


def _normalize_for_name_match(value: str) -> tuple[str, str]:
    """Return space-normalized and punctuation-stripped forms of a name string.

    ``Lac-Phe``, ``Lac Phe`` and ``LacPhe`` must all match one another, so both a
    space-normalized form and a fully stripped form are compared.
    """

    lowered = str(value or "").lower()
    spaced = " ".join(re.sub(r"[^a-z0-9]+", " ", lowered).split())
    stripped = re.sub(r"[^a-z0-9]+", "", lowered)
    return spaced, stripped


def _name_in_text(term: str, text: str) -> bool:
    term_spaced, term_stripped = _normalize_for_name_match(term)
    text_spaced, text_stripped = _normalize_for_name_match(text)
    if not term_stripped:
        return False
    return term_spaced in text_spaced or term_stripped in text_stripped


def _subject_evidence(record: dict[str, Any], subject_terms: Iterable[str]) -> tuple[str, str]:
    """Locate the queried subject name in the record text and flag homonym risk."""

    terms = [term for term in subject_terms if str(term).strip()]
    if not terms:
        return "not_applicable_no_subject_term_declared", "not_applicable_no_subject_term_declared"
    title = str(record.get("title") or "")
    abstract = str(record.get("abstract") or "")
    in_title = any(_name_in_text(term, title) for term in terms)
    in_abstract = any(_name_in_text(term, abstract) for term in terms)
    if in_title:
        evidence = "subject_name_in_title"
    elif in_abstract:
        evidence = "subject_name_in_abstract"
    elif abstract:
        evidence = "subject_name_absent_from_title_and_abstract"
    else:
        evidence = "unknown_no_abstract_retrieved"

    text = _text_blob(record)
    if evidence in {"subject_name_in_title", "subject_name_in_abstract"}:
        material = _matches(text, MATERIAL_CONTEXT_PATTERNS)
        biological = _matches(text, BIOLOGICAL_CONTEXT_PATTERNS)
        if material and not biological:
            return evidence, "flagged_non_metabolite_homonym_context"
        if material and biological:
            return evidence, "mixed_material_and_biological_context"
        return evidence, "no_homonym_signal"
    return evidence, "not_assessed_subject_name_not_located"


# Repository accessions that bridge a publication back to a retrievable dataset.
ACCESSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("metabolomics_workbench", re.compile(r"\bST\d{6}\b")),
    ("metabolomics_workbench_analysis", re.compile(r"\bAN\d{6}\b")),
    ("metabolights", re.compile(r"\bMTBLS\d+\b")),
    ("metabobank", re.compile(r"\bMTBKS\d+\b")),
    ("geo", re.compile(r"\bGSE\d+\b")),
    ("pride", re.compile(r"\bPXD\d{6,}\b")),
    ("massive", re.compile(r"\bMSV\d{9,}\b")),
    ("arrayexpress", re.compile(r"\bE-MTAB-\d+\b")),
    ("bioproject", re.compile(r"\bPRJ[EDN][A-Z]\d+\b")),
    ("sra", re.compile(r"\bSR[PRXS]\d{5,}\b")),
    ("dbgap", re.compile(r"\bphs\d{6}(?:\.v\d+\.p\d+)?\b")),
    ("ega", re.compile(r"\bEGA[SD]\d{11}\b")),
    ("gwas_catalog", re.compile(r"\bGCST\d{6,}\b")),
)

_CONFLICT_FIELDS = ("title", "publication_year", "journal")


def _raw_text(record: dict[str, Any]) -> str:
    """Concatenate the searchable record text with its original casing preserved."""

    parts = [
        str(record.get("title") or ""),
        str(record.get("abstract") or ""),
        str(record.get("journal") or ""),
        str(record.get("notes") or ""),
    ]
    return " ".join(parts)


def _text_blob(record: dict[str, Any]) -> str:
    return _raw_text(record).lower()


def _matches(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _flag(value: bool, basis: str) -> str:
    """Render a screening flag with its evidence basis attached.

    ``unknown`` is a distinct value from ``no``: a text sweep that found nothing in a
    record with no abstract has not established absence.
    """

    if basis == "structured_field":
        return "yes:structured_field" if value else "no:structured_field"
    if value:
        return "yes:text_inference"
    return "no_signal:text_inference" if basis == "text_with_abstract" else "unknown:no_abstract_text"


def _is_positive(flag: str) -> bool:
    return flag.startswith("yes")


# ---------------------------------------------------------------------------
# Input adapters
# ---------------------------------------------------------------------------


def records_from_publications(publications: Iterable[PublicationRecord]) -> list[dict[str, Any]]:
    """Convert synthetic publication fixtures into the live record schema.

    The offline pilot has structured modality flags that live bibliographic records do
    not, so the converted rows carry ``evidence_basis=structured_field`` and keep the
    fixture provenance explicit.
    """

    records: list[dict[str, Any]] = []
    for publication in publications:
        doi = "" if publication.doi in {"not_reported", "not_available", ""} else publication.doi
        pmid = "" if publication.pmid in {"not_reported", "not_available", ""} else publication.pmid
        accession = "" if publication.repository_accession in {"not_available", "not_reported"} else publication.repository_accession
        records.append(
            {
                "record_key": f"doi:{doi.lower()}" if doi else (f"pmid:{pmid}" if pmid else f"study:{publication.study_id}"),
                "source_system": "local_synthetic_fixture",
                "source_subset": "mock_publications",
                "doi": doi.lower(),
                "pmid": pmid,
                "pmcid": "",
                "preprint_server": "",
                "title": publication.title,
                "authors": "",
                "journal": "",
                "publication_year": "",
                "publication_types": "journal-article",
                "is_preprint": "false",
                "is_open_access": "",
                "cited_by_count": "",
                "linked_published_doi": "",
                "preprint_version_count": "",
                "record_url": f"https://doi.org/{doi}" if doi else "",
                "abstract": "",
                "queried_expression": "offline fixture: data/examples/mock_publications.csv",
                "source_url": "data/examples/mock_publications.csv",
                "retrieved_via": "offline_fixture_load",
                "evidence_basis": "structured_field",
                "structured_flags": {
                    "human": publication.human,
                    "exercise": publication.exercise,
                    "metabolomics": publication.metabolomics,
                    "genetics": publication.genetics,
                    "cpet": publication.cpet,
                    "actigraphy": publication.actigraphy,
                    "body_composition": publication.body_composition,
                    "diet": publication.diet,
                },
                "declared_accession": accession,
                "study_id": publication.study_id,
                "notes": publication.notes,
            }
        )
    records.sort(key=lambda row: row["record_key"])
    return records


def load_literature_records(path: str | Path) -> list[dict[str, Any]]:
    """Load retrieved records from the JSON sidecar (preferred) or the CSV table."""

    path = Path(path)
    if path.is_dir():
        json_path = path / "literature_records.json"
        csv_path = path / "literature_records.csv"
        path = json_path if json_path.exists() else csv_path
    if path.suffix == ".json":
        payload = read_json(path)
        return [row for row in payload if isinstance(row, dict)]
    return [dict(row) for row in read_csv_rows(path)]


# ---------------------------------------------------------------------------
# Deduplication across sources
# ---------------------------------------------------------------------------


def _cluster_keys(record: dict[str, Any]) -> list[str]:
    keys = []
    doi = str(record.get("doi") or "").strip().lower()
    pmid = str(record.get("pmid") or "").strip()
    pmcid = str(record.get("pmcid") or "").strip().upper()
    published_doi = str(record.get("linked_published_doi") or "").strip().lower()
    if doi:
        keys.append(f"doi:{doi}")
    if pmid:
        keys.append(f"pmid:{pmid}")
    if pmcid:
        keys.append(f"pmcid:{pmcid}")
    if published_doi and published_doi != doi:
        # A preprint and the journal article it became are one study, so the preprint
        # server's published-DOI linkage merges them instead of counting two records.
        keys.append(f"doi:{published_doi}")
    if not keys:
        title = re.sub(r"[^a-z0-9]+", " ", str(record.get("title") or "").lower()).strip()
        keys.append(f"title:{title}|{str(record.get('publication_year') or '').strip()}")
    return keys


def dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge records that describe the same publication across sources.

    Identifier overlap (DOI, PMID, PMCID) is transitive, so records are unioned rather
    than matched pairwise. Field disagreements between sources are preserved as
    conflicts instead of being silently overwritten by the last source seen.
    """

    records = list(records)
    parent: dict[str, str] = {}

    def find(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    record_keys: list[list[str]] = []
    for record in records:
        keys = _cluster_keys(record)
        record_keys.append(keys)
        for key in keys:
            find(key)
        for key in keys[1:]:
            union(keys[0], key)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record, keys in zip(records, record_keys, strict=True):
        grouped.setdefault(find(keys[0]), []).append(record)

    clusters: list[dict[str, Any]] = []
    for cluster_key in sorted(grouped):
        members = grouped[cluster_key]
        # Prefer the member with the richest text so screening sees the best available
        # evidence, but keep every source's identifiers and URLs.
        # Prefer a peer-reviewed member over a preprint of the same study, then the
        # richest text. A preprint that became a journal article must be tiered as the
        # article it became, not as an unreviewed preprint.
        members_sorted = sorted(
            members,
            key=lambda row: (
                1 if str(row.get("is_preprint") or "").lower() == "true" else 0,
                -len(str(row.get("abstract") or "")),
                str(row.get("source_system") or ""),
            ),
        )
        primary = dict(members_sorted[0])
        conflicts: list[str] = []
        for field in _CONFLICT_FIELDS:
            values = {
                " ".join(str(member.get(field) or "").split()).lower()
                for member in members
                if str(member.get(field) or "").strip()
            }
            if len(values) > 1:
                conflicts.append(f"{field}: " + " != ".join(sorted(values)))
        for field in ("doi", "pmid", "pmcid", "linked_published_doi", "preprint_server", "cited_by_count", "abstract", "publication_types"):
            if not str(primary.get(field) or "").strip():
                for member in members_sorted[1:]:
                    value = str(member.get(field) or "").strip()
                    if value:
                        primary[field] = value
                        break
        preprint_flags = [str(member.get("is_preprint") or "").lower() == "true" for member in members]
        # Only an all-preprint cluster is a preprint. A mixed cluster is the published
        # record, with the preprint version noted rather than allowed to set the tier.
        primary["is_preprint"] = "true" if preprint_flags and all(preprint_flags) else "false"
        primary["has_preprint_version"] = "true" if any(preprint_flags) else "false"
        primary["record_key"] = cluster_key
        primary["source_systems"] = sorted({str(member.get("source_system") or "") for member in members})
        primary["source_urls"] = sorted({str(member.get("source_url") or "") for member in members if member.get("source_url")})
        primary["member_count"] = len(members)
        primary["cross_source_conflicts"] = conflicts
        clusters.append(primary)
    return clusters


# ---------------------------------------------------------------------------
# Screening and appraisal
# ---------------------------------------------------------------------------


def _evidence_tier(record: dict[str, Any]) -> str:
    types = str(record.get("publication_types") or "").lower()
    if str(record.get("is_preprint") or "").lower() == "true":
        return (
            "preprint_later_published"
            if str(record.get("linked_published_doi") or "").strip()
            else "preprint_not_peer_reviewed"
        )
    if _matches(types, (r"retract",)):
        return "retracted_or_retraction_notice"
    if _matches(types, (r"correction", r"erratum")):
        return "correction_or_erratum"
    if _matches(types, (r"review", r"meta-analysis", r"systematic")):
        return "peer_reviewed_secondary_synthesis"
    if _matches(types, (r"editorial", r"comment", r"news", r"letter")):
        return "editorial_or_commentary"
    if _matches(types, PRIMARY_TYPE_PATTERNS):
        return "peer_reviewed_primary"
    return "unknown_publication_type"


def _species_scope(text: str, has_abstract: bool, structured: dict[str, Any] | None) -> tuple[str, str]:
    if structured is not None:
        return ("human" if structured.get("human") else "non_human_or_unstated", "structured_field")
    human = _matches(text, HUMAN_PATTERNS)
    rodent = _matches(text, RODENT_PATTERNS)
    other_animal = _matches(text, OTHER_ANIMAL_PATTERNS)
    in_vitro = _matches(text, IN_VITRO_PATTERNS)
    basis = "title_abstract_text" if has_abstract else "title_only_text"
    if human and (rodent or other_animal):
        return "human_and_animal", basis
    if human:
        return "human", basis
    if rodent:
        return "rodent", basis
    if other_animal:
        return "other_animal", basis
    if in_vitro:
        return "in_vitro_or_enzymatic", basis
    return "not_stated_in_retrieved_text", ("no_species_term_in_abstract" if has_abstract else "no_abstract_text")


def _intervention_design(text: str) -> str:
    for label, patterns in DESIGN_PATTERNS:
        if _matches(text, patterns):
            return label
    return "not_stated_in_retrieved_text"


def _accessions(text: str, declared: str = "") -> list[str]:
    """Extract repository accessions from record text, preserving each source's casing.

    ``text`` must be the original-case record text: accession grammars are case-bearing
    (``ST003662``, ``phs000123``), so scanning a lowercased blob silently finds nothing.
    """

    found: set[str] = set()
    for namespace, pattern in ACCESSION_PATTERNS:
        for match in pattern.findall(text):
            found.add(f"{namespace}:{match}")
    declared = str(declared or "").strip()
    if declared:
        for namespace, pattern in ACCESSION_PATTERNS:
            if pattern.fullmatch(declared):
                found.add(f"{namespace}:{declared}")
                break
        else:
            found.add(f"declared:{declared}")
    return sorted(found)


def screen_record(
    record: dict[str, Any],
    criteria: InclusionCriteria,
    *,
    subject_terms: Iterable[str] = (),
) -> dict[str, Any]:
    """Classify one deduplicated record and record the basis of every call."""

    structured = record.get("structured_flags") if isinstance(record.get("structured_flags"), dict) else None
    abstract = str(record.get("abstract") or "").strip()
    has_abstract = bool(abstract)
    # A structured fixture row carries its evidence in fields, not in text.
    text_basis = "structured_field" if structured is not None else ("text_with_abstract" if has_abstract else "text_title_only")
    text = _text_blob(record)

    def flag(name: str, patterns: Iterable[str]) -> str:
        if structured is not None:
            return _flag(bool(structured.get(name)), "structured_field")
        return _flag(_matches(text, patterns), text_basis)

    human_flag = flag("human", HUMAN_PATTERNS)
    exercise_flag = flag("exercise", EXERCISE_PATTERNS)
    metabolomics_flag = flag("metabolomics", METABOLOMICS_PATTERNS)
    genetics_flag = flag("genetics", GENETICS_PATTERNS)
    cpet_flag = flag("cpet", CPET_PATTERNS)
    actigraphy_flag = flag("actigraphy", ACTIGRAPHY_PATTERNS)
    body_flag = flag("body_composition", BODY_COMPOSITION_PATTERNS)
    diet_flag = flag("diet", DIET_PATTERNS)

    species, species_basis = _species_scope(text, has_abstract, structured)
    tier = _evidence_tier(record)
    design = _intervention_design(text)
    accessions = _accessions(_raw_text(record), str(record.get("declared_accession") or ""))
    subject_term_evidence, homonym_risk = _subject_evidence(record, subject_terms)

    required = [term.lower() for term in criteria.required_terms]
    screen_basis_parts = [f"tier={tier}", f"species_basis={species_basis}", f"text_basis={text_basis}"]

    if tier in {"retracted_or_retraction_notice", "correction_or_erratum", "editorial_or_commentary"}:
        screen_class = "not_primary_evidence"
    elif structured is None and not has_abstract and not _is_positive(metabolomics_flag) and not _is_positive(exercise_flag):
        # No abstract and no decisive title signal: the record cannot be screened, and
        # calling that "excluded" would convert unknown into absent.
        screen_class = "screening_uncertain_insufficient_text"
        screen_basis_parts.append("uncertain_reason=no_abstract_returned")
    elif tier == "peer_reviewed_secondary_synthesis":
        screen_class = "secondary_synthesis"
    elif species in {"rodent", "other_animal", "in_vitro_or_enzymatic"} and not _is_positive(human_flag):
        screen_class = "animal_or_invitro_mechanistic"
    elif _is_positive(human_flag) and _is_positive(exercise_flag):
        screen_class = "direct_human_exercise"
    elif _is_positive(human_flag):
        screen_class = "human_non_exercise_context"
    elif species == "not_stated_in_retrieved_text":
        # An abstract was returned but names no species and no decisive modality, so the
        # record is unresolved for a different reason than a missing abstract.
        screen_class = "screening_uncertain_insufficient_text"
        screen_basis_parts.append("uncertain_reason=species_not_stated_in_abstract")
    else:
        screen_class = "non_relevant_context"

    if "human" in required and screen_class == "animal_or_invitro_mechanistic":
        screen_basis_parts.append("retained_as_mechanistic_background_not_as_required-term_match")

    review_status = (
        "requires_human_review"
        if screen_class in {"screening_uncertain_insufficient_text", "direct_human_exercise"}
        or record.get("cross_source_conflicts")
        or tier in {"preprint_not_peer_reviewed", "unknown_publication_type", "retracted_or_retraction_notice"}
        or homonym_risk in {"flagged_non_metabolite_homonym_context", "mixed_material_and_biological_context"}
        or subject_term_evidence == "subject_name_absent_from_title_and_abstract"
        else "advisory_only"
    )

    return {
        "record_key": record.get("record_key", ""),
        "screen_class": screen_class,
        "evidence_tier": tier,
        "species_scope": species,
        "species_basis": species_basis,
        "screen_basis": "; ".join(screen_basis_parts),
        "review_status": review_status,
        "title": record.get("title", ""),
        "authors": record.get("authors", ""),
        "journal": record.get("journal", ""),
        "publication_year": record.get("publication_year", ""),
        "publication_types": record.get("publication_types", ""),
        "is_preprint": record.get("is_preprint", ""),
        "has_preprint_version": record.get("has_preprint_version", ""),
        "linked_published_doi": record.get("linked_published_doi", ""),
        "doi": record.get("doi", ""),
        "pmid": record.get("pmid", ""),
        "pmcid": record.get("pmcid", ""),
        "cited_by_count": record.get("cited_by_count", ""),
        "abstract_available": "true" if has_abstract else "false",
        "human_evidence": human_flag,
        "exercise_evidence": exercise_flag,
        "metabolomics_evidence": metabolomics_flag,
        "genetics_evidence": genetics_flag,
        "cpet_evidence": cpet_flag,
        "actigraphy_evidence": actigraphy_flag,
        "body_composition_evidence": body_flag,
        "diet_evidence": diet_flag,
        "intervention_design": design,
        "subject_term_evidence": subject_term_evidence,
        "homonym_risk": homonym_risk,
        "data_availability_evidence": (
            "accession_in_record_text" if accessions else "no_accession_in_retrieved_text"
        ),
        "accessions_in_record_text": "; ".join(accessions),
        "source_systems": "; ".join(record.get("source_systems", []) or [str(record.get("source_system") or "")]),
        "cross_source_conflicts": "; ".join(record.get("cross_source_conflicts", []) or []),
        "record_url": record.get("record_url", ""),
        "source_urls": "; ".join(record.get("source_urls", []) or [str(record.get("source_url") or "")]),
    }


SCREEN_CLASS_ORDER = (
    "direct_human_exercise",
    "human_non_exercise_context",
    "animal_or_invitro_mechanistic",
    "secondary_synthesis",
    "screening_uncertain_insufficient_text",
    "non_relevant_context",
    "not_primary_evidence",
)


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    order = SCREEN_CLASS_ORDER.index(row["screen_class"]) if row["screen_class"] in SCREEN_CLASS_ORDER else 99
    year = row.get("publication_year") or "0"
    year_value = int(year) if str(year).isdigit() else 0
    citations = str(row.get("cited_by_count") or "")
    citation_value = int(citations) if citations.isdigit() else 0
    return (order, -citation_value, -year_value, row["record_key"])


def build_escalations(screened: Iterable[dict[str, Any]], retrieval_provenance: dict[str, Any] | None) -> list[dict[str, Any]]:
    escalations: list[dict[str, Any]] = []
    for row in screened:
        if row["screen_class"] == "screening_uncertain_insufficient_text":
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "unscreenable_record",
                    "reason": "retrieved record carries no abstract and no decisive title signal",
                    "decision_needed": "obtain full text or exclude explicitly; do not treat as screened-out",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
        if row["cross_source_conflicts"]:
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "cross_source_metadata_conflict",
                    "reason": row["cross_source_conflicts"],
                    "decision_needed": "confirm the authoritative bibliographic record before citing",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
        if row["evidence_tier"] == "preprint_not_peer_reviewed":
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "preprint_without_peer_review",
                    "reason": "preprint with no linked journal publication in the preprint server record",
                    "decision_needed": "decide whether the claim may be cited as evidence at this tier",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
        if row["evidence_tier"] == "retracted_or_retraction_notice":
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "retraction_flag_in_publication_type",
                    "reason": "publication type mentions retraction",
                    "decision_needed": "verify retraction status before any use",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
        if row["homonym_risk"] in {
            "flagged_non_metabolite_homonym_context",
            "mixed_material_and_biological_context",
        }:
            reason = (
                "the queried name appears only alongside materials-science context terms; the string "
                "match may not refer to the queried metabolite"
                if row["homonym_risk"] == "flagged_non_metabolite_homonym_context"
                else "the queried name appears alongside both materials-science and biological context "
                "terms, so which entity the string denotes is unresolved"
            )
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "possible_name_homonym",
                    "reason": reason,
                    "decision_needed": "confirm the chemical entity from the full text before counting this record as subject evidence",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
        if row["subject_term_evidence"] == "subject_name_absent_from_title_and_abstract":
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "subject_name_not_located_in_record",
                    "reason": (
                        "the index matched this record on full text, but the queried name does not appear "
                        "in the retrieved title or abstract"
                    ),
                    "decision_needed": "check the full text before treating this record as subject evidence",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
        if (
            row["screen_class"] == "direct_human_exercise"
            and row["data_availability_evidence"] == "no_accession_in_retrieved_text"
        ):
            escalations.append(
                {
                    "record_key": row["record_key"],
                    "escalation": "unresolved_data_deposition",
                    "reason": "no repository accession appears in the retrieved bibliographic text; absence here is not evidence of no deposition",
                    "decision_needed": "check the full-text data availability statement before recording a deposition gap",
                    "title": row["title"],
                    "record_url": row["record_url"],
                }
            )
    for source in (retrieval_provenance or {}).get("sources", []) or []:
        if source.get("status") == "unavailable":
            escalations.append(
                {
                    "record_key": f"source:{source.get('source_system')}",
                    "escalation": "retrieval_source_unavailable",
                    "reason": f"{source.get('source_system')} could not be reached: {source.get('detail', '')}",
                    "decision_needed": "re-run the lane from a permitted network egress before treating the sweep as complete",
                    "title": "",
                    "record_url": "",
                }
            )
        elif source.get("status") == "ok" and not source.get("pagination_complete"):
            escalations.append(
                {
                    "record_key": f"source:{source.get('source_system')}",
                    "escalation": "retrieval_truncated",
                    "reason": (
                        f"{source.get('source_system')} did not return a declared-complete result set: "
                        f"{source.get('retrieved_count')} retrieved of {source.get('reported_hit_count')} "
                        "reported hits"
                    ),
                    "decision_needed": "raise the retrieval cap or narrow the query before claiming a complete sweep",
                    "title": "",
                    "record_url": "",
                }
            )
    escalations.sort(key=lambda row: (row["escalation"], row["record_key"]))
    return escalations


def summarize(screened: list[dict[str, Any]], retrieval_provenance: dict[str, Any] | None) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in screened:
        counts[row["screen_class"]] = counts.get(row["screen_class"], 0) + 1
    tiers: dict[str, int] = {}
    for row in screened:
        tiers[row["evidence_tier"]] = tiers.get(row["evidence_tier"], 0) + 1
    species: dict[str, int] = {}
    for row in screened:
        species[row["species_scope"]] = species.get(row["species_scope"], 0) + 1
    subject_evidence: dict[str, int] = {}
    homonym: dict[str, int] = {}
    for row in screened:
        subject_evidence[row["subject_term_evidence"]] = subject_evidence.get(row["subject_term_evidence"], 0) + 1
        homonym[row["homonym_risk"]] = homonym.get(row["homonym_risk"], 0) + 1
    accession_rows = [row for row in screened if row["data_availability_evidence"] == "accession_in_record_text"]
    namespaces: dict[str, int] = {}
    for row in accession_rows:
        for item in row["accessions_in_record_text"].split("; "):
            if item:
                namespace = item.split(":", 1)[0]
                namespaces[namespace] = namespaces.get(namespace, 0) + 1
    provenance = retrieval_provenance or {}
    return {
        "record_count": len(screened),
        "screen_class_counts": dict(sorted(counts.items())),
        "evidence_tier_counts": dict(sorted(tiers.items())),
        "species_scope_counts": dict(sorted(species.items())),
        "subject_term_evidence_counts": dict(sorted(subject_evidence.items())),
        "homonym_risk_counts": dict(sorted(homonym.items())),
        "records_with_accession_in_text": len(accession_rows),
        "accession_namespace_counts": dict(sorted(namespaces.items())),
        "review_required_count": sum(1 for row in screened if row["review_status"] == "requires_human_review"),
        "unavailable_sources": list(provenance.get("unavailable_sources", []) or []),
        "truncated_sources": list(provenance.get("truncated_sources", []) or []),
        "sources_queried": [source.get("source_system") for source in provenance.get("sources", []) or []],
    }


def review_literature(
    records: Iterable[dict[str, Any]],
    criteria: InclusionCriteria,
    out_dir: str | Path,
    *,
    retrieval_provenance: dict[str, Any] | None = None,
    label: str = "literature",
    subject_terms: Iterable[str] = (),
) -> dict[str, Any]:
    """Screen, appraise, and persist a literature review table. Offline and deterministic."""

    subject_terms = [term for term in subject_terms if str(term).strip()]
    clusters = dedupe_records(records)
    screened = [screen_record(cluster, criteria, subject_terms=subject_terms) for cluster in clusters]
    screened.sort(key=_sort_key)
    escalations = build_escalations(screened, retrieval_provenance)
    summary = summarize(screened, retrieval_provenance)

    out_dir = Path(out_dir)
    screened_path = write_csv_rows(out_dir / f"{label}_screened.csv", screened, SCREENED_FIELDNAMES)
    escalations_path = write_csv_rows(out_dir / f"{label}_escalations.csv", escalations, ESCALATION_FIELDNAMES)
    review_path = write_json(
        out_dir / f"{label}_review.json",
        {
            "query": criteria.query,
            "subject_terms": list(subject_terms),
            "required_terms": list(criteria.required_terms),
            "preferred_terms": list(criteria.preferred_terms),
            "exclusions": list(criteria.exclusions),
            "decision_scope": "screening_and_appraisal_only",
            "summary": summary,
            "escalations": escalations,
            "records": screened,
            "semantics": {
                "screen_class": (
                    "screening_uncertain_insufficient_text is an unresolved record, not an exclusion; "
                    "animal_or_invitro_mechanistic is retained as background evidence and never as a "
                    "human required-term match."
                ),
                "evidence_flags": (
                    "yes/no:structured_field come from declared fields. yes/no_signal:text_inference come "
                    "from title/abstract matching. unknown:no_abstract_text means the record had no "
                    "abstract, so absence was never established."
                ),
                "data_availability_evidence": (
                    "no_accession_in_retrieved_text means no accession appeared in the retrieved "
                    "bibliographic text. It is not a data availability statement and is not evidence "
                    "that the study deposited nothing."
                ),
                "subject_term_evidence": (
                    "A full-text index match is not proof that the record is about the queried entity. "
                    "subject_name_absent_from_title_and_abstract and flagged_non_metabolite_homonym_context "
                    "both mean the string match is unverified, and both are escalated rather than counted."
                ),
            },
        },
    )
    return {
        "query": criteria.query,
        "subject_terms": list(subject_terms),
        "screened": screened,
        "escalations": escalations,
        "summary": summary,
        "screened_path": screened_path,
        "escalations_path": escalations_path,
        "review_path": review_path,
    }

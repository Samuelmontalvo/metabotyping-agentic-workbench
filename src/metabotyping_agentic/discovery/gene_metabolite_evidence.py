"""Offline appraisal of retrieved gene-centric annotation evidence.

Retrieval (``live_sources.metgene``) is deliberately separate from appraisal. This
module never touches the network. It turns retrieved annotation rows into an
inference ledger in which every hop of the chain

    gene -> KEGG reaction -> KEGG compound -> RefMet name -> Metabolomics Workbench study

is a separate labeled step, so the collapsed claim "this gene's metabolite was
measured in study ST######" cannot be produced by accident. Nothing here upgrades
an annotation into a measurement, resolves chemical identity, or scores a dataset.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..io import ensure_dir, read_csv_rows, write_csv_rows, write_json

LEDGER_FIELDNAMES = [
    "queried_gene",
    "queried_gene_id_type",
    "queried_species",
    "hop_index",
    "hop",
    "subject",
    "object",
    "evidence_class",
    "inference_basis",
    "establishes",
    "does_not_establish",
    "measurement_established",
    "next_evidence_required",
    "review_status",
    "source_url",
]

# Each hop states what it establishes and, more importantly, what it does not. The
# "does not establish" column is the one that keeps an annotation chain from being
# read as a measurement chain.
_HOP_CONTRACTS: dict[str, dict[str, str]] = {
    "gene_to_reaction": {
        "evidence_class": "database_annotation",
        "inference_basis": "kegg_gene_reaction_annotation",
        "establishes": "the gene product is annotated as catalysing this reaction",
        "does_not_establish": (
            "that the reaction is active in any tissue, condition, or individual studied"
        ),
        "next_evidence_required": "expression or activity evidence for the tissue and condition of interest",
    },
    "reaction_to_compound": {
        "evidence_class": "database_annotation",
        "inference_basis": "kegg_reaction_participant_annotation",
        "establishes": "the compound participates in the annotated reaction",
        "does_not_establish": (
            "that the compound was measured, detected, or quantified in any dataset"
        ),
        "next_evidence_required": "a study feature table that reports this compound",
    },
    "compound_to_standard_name": {
        "evidence_class": "nomenclature_mapping",
        "inference_basis": "kegg_compound_to_refmet_name_mapping",
        "establishes": "the source maps this compound accession to a standardized name",
        "does_not_establish": (
            "that two features sharing this name are the same chemical entity at MSI level 1"
        ),
        "next_evidence_required": "structure or identifier agreement adjudicated by metabolite identity resolution",
    },
    "standard_name_to_study": {
        "evidence_class": "name_indexed_retrieval",
        "inference_basis": "refmet_name_index_over_repository_studies",
        "establishes": "a repository study is indexed under this standardized name",
        "does_not_establish": (
            "what the study measured, in which matrix, on which platform, or with what result"
        ),
        "next_evidence_required": "a direct repository re-fetch of the study accession and its analysis metadata",
    },
    "pathway_count": {
        "evidence_class": "precomputed_count",
        "inference_basis": "source_precomputed_pathway_count",
        "establishes": "the source counts this many annotated pathways for the gene",
        "does_not_establish": (
            "which pathways they are; the source exposes no retrievable pathway listing"
        ),
        "next_evidence_required": "a registered pathway source such as Reactome, queried by stable identifier",
    },
}

COVERAGE_FIELDNAMES = [
    "queried_gene",
    "queried_species",
    "context",
    "status",
    "interpretation",
    "is_evidence_of_absence",
]

_STATUS_INTERPRETATION = {
    "ok": ("the source answered and returned rows", False),
    "no_hits": ("the source answered and holds no annotated rows for this gene product", False),
    "gene_not_annotated": ("the identifier resolved but the source holds no record for it", False),
    "gene_unresolved_or_source_error": (
        "an ambiguous server error that the source returns both for a wrong or wrongly cased "
        "identifier and for an outage",
        False,
    ),
    "unavailable": ("the source could not be reached, so its coverage is unknown", False),
    "indeterminate_empty_body": (
        "a zero-length response, which an unrecognised filter term also produces",
        False,
    ),
    "not_requested": (
        "the context was never queried, so nothing at all is known about it",
        False,
    ),
}


def _hop_row(
    hop: str,
    *,
    gene: str,
    gene_id_type: str,
    species: str,
    index: int,
    subject: str,
    obj: str,
    source_url: str,
) -> dict[str, Any]:
    contract = _HOP_CONTRACTS[hop]
    return {
        "queried_gene": gene,
        "queried_gene_id_type": gene_id_type,
        "queried_species": species,
        "hop_index": index,
        "hop": hop,
        "subject": subject or "not_reported",
        "object": obj or "not_reported",
        "evidence_class": contract["evidence_class"],
        "inference_basis": contract["inference_basis"],
        "establishes": contract["establishes"],
        "does_not_establish": contract["does_not_establish"],
        "measurement_established": "not_established",
        "next_evidence_required": contract["next_evidence_required"],
        "review_status": "requires_human_review",
        "source_url": source_url,
    }


def build_inference_ledger(
    *,
    summary_rows: Iterable[dict[str, Any]] = (),
    metabolite_rows: Iterable[dict[str, Any]] = (),
    reaction_rows: Iterable[dict[str, Any]] = (),
    study_candidate_rows: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Expand retrieved annotation rows into one ledger row per inference hop."""

    ledger: list[dict[str, Any]] = []

    for row in reaction_rows:
        ledger.append(
            _hop_row(
                "gene_to_reaction",
                gene=str(row.get("queried_gene", "")),
                gene_id_type=str(row.get("queried_gene_id_type", "")),
                species=str(row.get("queried_species", "")),
                index=1,
                subject=str(row.get("echoed_gene_identifier") or row.get("queried_gene", "")),
                obj=str(row.get("kegg_reaction_id", "")),
                source_url=str(row.get("source_url", "")),
            )
        )

    for row in metabolite_rows:
        gene = str(row.get("queried_gene", ""))
        gene_id_type = str(row.get("queried_gene_id_type", ""))
        species = str(row.get("queried_species", ""))
        source_url = str(row.get("source_url", ""))
        compound = str(row.get("kegg_compound_id", ""))
        ledger.append(
            _hop_row(
                "reaction_to_compound",
                gene=gene,
                gene_id_type=gene_id_type,
                species=species,
                index=2,
                subject=str(row.get("kegg_reaction_id", "")),
                obj=compound,
                source_url=source_url,
            )
        )
        # A compound with no standardized-name mapping cannot bridge to a study, so
        # the hop is recorded as unmapped rather than skipped.
        refmet_name = str(row.get("refmet_name", ""))
        mapped = str(row.get("refmet_mapping_status", "")) == "mapped"
        ledger.append(
            _hop_row(
                "compound_to_standard_name",
                gene=gene,
                gene_id_type=gene_id_type,
                species=species,
                index=3,
                subject=compound,
                obj=refmet_name if mapped else "absent_no_refmet_mapping",
                source_url=source_url,
            )
        )

    for row in study_candidate_rows:
        ledger.append(
            _hop_row(
                "standard_name_to_study",
                gene=str(row.get("queried_gene", "")),
                gene_id_type=str(row.get("queried_gene_id_type", "")),
                species=str(row.get("queried_species", "")),
                index=4,
                subject=str(row.get("refmet_name", "")),
                obj=str(row.get("study_id", "")),
                source_url=str(row.get("source_url", "")),
            )
        )

    for row in summary_rows:
        ledger.append(
            _hop_row(
                "pathway_count",
                gene=str(row.get("queried_gene", "")),
                gene_id_type=str(row.get("queried_gene_id_type", "")),
                species=str(row.get("queried_species", "")),
                index=0,
                subject=str(row.get("queried_gene", "")),
                obj=str(row.get("pathway_count", "")),
                source_url=str(row.get("source_url", "")),
            )
        )

    ledger.sort(key=lambda row: (row["hop_index"], row["subject"], row["object"]))
    return ledger


def build_coverage_ledger(contexts: Iterable[dict[str, Any]], *, gene: str, species: str) -> list[dict[str, Any]]:
    """State, per context, what the recorded status does and does not mean.

    No status is ever evidence of absence: the flag exists so a reader cannot infer
    one from a zero-row answer.
    """

    rows: list[dict[str, Any]] = []
    for context in contexts:
        status = str(context.get("status", ""))
        interpretation, is_absence = _STATUS_INTERPRETATION.get(
            status, ("an unclassified retrieval state", False)
        )
        rows.append(
            {
                "queried_gene": gene,
                "queried_species": species,
                "context": str(context.get("context", "")),
                "status": status,
                "interpretation": interpretation,
                "is_evidence_of_absence": is_absence,
            }
        )
    return rows


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return list(read_csv_rows(path)) if path.exists() else []


def build_gene_metabolite_evidence(
    records_dir: str | Path,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Re-derive the inference and coverage ledgers offline from retrieved records.

    Deterministic and network free: the same retrieved records always produce the
    same ledgers, so the appraisal can be regenerated and reviewed without
    re-querying the source.
    """

    records_dir = Path(records_dir)
    out_dir = ensure_dir(out_dir)
    provenance_path = records_dir / "metgene_provenance.json"
    if not provenance_path.exists():
        raise FileNotFoundError(
            f"No metgene_provenance.json in {records_dir}; run the retrieval lane first."
        )
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if not provenance.get("persisted_kegg_derived_fields", False):
        # Without the withheld rows the ledger would be empty, which reads as "the
        # source had nothing" rather than "the rows exist but were not written".
        raise ValueError(
            f"{records_dir} was retrieved with the licence question open "
            f"({provenance.get('licence_review_status', 'unknown')}), so no KEGG-derived row was "
            "persisted. An appraisal built from it would report an empty annotation chain as if "
            "the source held nothing. Re-run the retrieval with --acknowledge-licence-review once "
            "a reviewer has settled the licence question."
        )
    gene = str(provenance.get("queried_gene", ""))
    species = str(provenance.get("queried_species", ""))

    ledger = build_inference_ledger(
        summary_rows=_read_rows(records_dir / "metgene_summary.csv"),
        metabolite_rows=_read_rows(records_dir / "metgene_metabolites.csv"),
        reaction_rows=_read_rows(records_dir / "metgene_reactions.csv"),
        study_candidate_rows=_read_rows(records_dir / "metgene_study_candidates.csv"),
    )
    # Un-queried contexts appear in the coverage ledger too, so a reader cannot
    # mistake a narrowed request for a source that answered with nothing.
    contexts = list(provenance.get("contexts", []) or [])
    contexts.extend(
        {"context": name, "status": "not_requested"}
        for name in provenance.get("contexts_not_requested", []) or []
    )
    coverage = build_coverage_ledger(contexts, gene=gene, species=species)

    ledger_path = write_csv_rows(
        out_dir / "gene_metabolite_inference_ledger.csv", ledger, LEDGER_FIELDNAMES
    )
    coverage_path = write_csv_rows(
        out_dir / "gene_metabolite_coverage_ledger.csv", coverage, COVERAGE_FIELDNAMES
    )
    review_path = write_json(
        out_dir / "gene_metabolite_review.json",
        {
            "queried_gene": gene,
            "queried_species": species,
            "hop_counts": {
                hop: sum(1 for row in ledger if row["hop"] == hop) for hop in sorted(_HOP_CONTRACTS)
            },
            "licence_review_status": provenance.get("licence_review_status", ""),
            "pathway_listing_status": provenance.get("pathway_listing_status", ""),
            "contexts_not_requested": provenance.get("contexts_not_requested", []),
            "unavailable_contexts": provenance.get("unavailable_contexts", []),
            "unresolved_gene_contexts": provenance.get("unresolved_gene_contexts", []),
            "indeterminate_contexts": provenance.get("indeterminate_contexts", []),
            "decision_scope": "annotation_appraisal_only",
            "review_status": "requires_human_review",
            "note": (
                "Every ledger row is one annotation hop. No hop establishes that a metabolite was "
                "measured, and no chain of hops may be reported as a measurement result."
            ),
        },
    )
    return {
        "gene": gene,
        "species": species,
        "ledger": ledger,
        "coverage": coverage,
        "ledger_path": ledger_path,
        "coverage_path": coverage_path,
        "review_path": review_path,
    }

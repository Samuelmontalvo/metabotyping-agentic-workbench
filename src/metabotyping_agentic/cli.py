"""Command line interface for the offline MetaboTyping workbench."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .cohort_bundle import run_cohort_bundle
from .discovery.criteria import define_inclusion_criteria
from .discovery.gene_metabolite_evidence import build_gene_metabolite_evidence
from .discovery.literature import load_publications
from .discovery.literature_review import (
    load_literature_records,
    records_from_publications,
)
from .discovery.literature_review import (
    review_literature as run_review_literature,
)
from .discovery.recommender import build_recommendations
from .discovery.repositories import load_repository_records, repository_by_study
from .evaluation.benchmark import benchmark as run_benchmark
from .evaluation.motrpac_alignment import align_motrpac as run_motrpac_alignment
from .evaluation.quality_scoring import score_quality as run_quality_scoring
from .extraction.metadata_cards import extract_metadata_cards
from .extraction.variable_inventory import extract_variable_inventory
from .harmonization.crosswalk import build_crosswalk as run_build_crosswalk
from .harmonization.harmonization_plan import build_harmonization_plan
from .harmonization.harmonization_plan import review_crosswalk as run_review_crosswalk
from .io import ensure_dir, read_json, read_text, to_plain, write_csv_rows, write_json
from .knowledge.source_registry import build_retrieval_plan
from .live_sources.literature_search import LITERATURE_SOURCES, search_literature
from .live_sources.metabolomics_workbench import (
    compute_exact_mass,
    ingest_metabolomics_workbench_study,
    lookup_compound,
    lookup_mgp_gene_protein,
    search_metabolite_studies,
    search_moverz,
)
from .live_sources.metgene import (
    METGENE_CONTEXTS,
    lookup_gene_metabolite_annotations,
)
from .live_sources.motrpac_volcano_compare import compare_mw_motrpac_volcano
from .models import InclusionCriteria
from .reports.render import (
    render_catalog_report,
    render_evaluation_report,
    render_human_review_packet,
    render_literature_report,
    render_motrpac_alignment_report,
)
from .schemas import project_schema_path, validate_or_raise

try:  # pragma: no cover - optional dependency path
    import typer

    app = typer.Typer(help="MetaboTyping agentic workbench CLI")
    HAS_TYPER = True
except ModuleNotFoundError:  # pragma: no cover - fallback covered by smoke tests
    typer = None
    app = None
    HAS_TYPER = False


DEFAULT_QUERY = "human metabolomics datasets with exercise or actigraphy and genetics"


def _examples_dir() -> Path:
    return Path("data/examples")


def define_criteria_command(query: str = DEFAULT_QUERY, out: str = "data/extracted/criteria.json") -> Path:
    criteria = define_inclusion_criteria(query)
    return write_json(out, criteria)


def discover_command(criteria: str = "data/extracted/criteria.json", out: str = "data/extracted") -> list[Any]:
    criteria_model = InclusionCriteria.model_validate(read_json(criteria))
    examples = _examples_dir()
    publications = load_publications(examples / "mock_publications.csv")
    repositories = repository_by_study(load_repository_records(examples / "mock_repository_records.csv"))
    recommendations = build_recommendations(publications, repositories, criteria_model)
    out_dir = ensure_dir(out)
    rows = [to_plain(item) for item in recommendations]
    schema_path = project_schema_path("recommendation.schema.json")
    for row in rows:
        validate_or_raise(row, schema_path, label=f"recommendation {row['study_id']}")
    write_json(out_dir / "recommendations.json", rows)
    write_csv_rows(
        out_dir / "recommendations.csv",
        rows,
        ["study_id", "recommendation_class", "match_class", "score", "rationale", "mirage_flags"],
    )
    # The catalog report is a pilot-level artifact: run_pilot_command renders it
    # into its own --out. Rendering it here too wrote into a hardcoded "reports"
    # regardless of --out, so any standalone discover run (including the test
    # suite) silently overwrote the committed offline-pilot report.
    return recommendations


def extract_metadata_command(
    records: str,
    out: str = "data/extracted",
    publications: str | None = None,
    require_publication_match: bool = False,
) -> None:
    records_path = Path(records)
    publications_path: Path | None
    if publications is not None:
        publications_path = Path(publications)
    else:
        # Sibling discovery is portable for a self-contained cohort bundle.
        # Never fall back to the repository's pilot publications: doing so can
        # attach synthetic human/modality evidence to an unrelated unseen
        # dataset that happens to reuse a study identifier.
        sibling_candidates = (
            records_path.with_name("publications.csv"),
            records_path.with_name("mock_publications.csv"),
        )
        publications_path = next(
            (candidate for candidate in sibling_candidates if candidate.is_file()),
            None,
        )
    extract_metadata_cards(
        records_path,
        out,
        publications_path,
        require_publication_match=require_publication_match,
    )


def build_crosswalk_command(variables: str, out: str = "data/extracted") -> None:
    run_build_crosswalk(variables, out)


def review_crosswalk_command(crosswalk: str, out: str = "data/review") -> None:
    run_review_crosswalk(crosswalk, out)


def build_harmonization_plan_command(crosswalk: str, out: str = "reports") -> None:
    build_harmonization_plan(crosswalk, out)


def score_quality_command(metadata: str = "data/extracted", out: str = "data/extracted") -> Any:
    scores = run_quality_scoring(metadata, out)
    # As with discover_command: run_pilot_command renders the evaluation report
    # into its own --out. The hardcoded "reports" here overwrote the committed
    # offline-pilot report on any standalone score-quality run.
    return scores


def align_motrpac_command(metadata: str = "data/extracted", out: str = "reports") -> Any:
    alignments = run_motrpac_alignment(metadata, out)
    render_motrpac_alignment_report(alignments, out)
    return alignments


def benchmark_command(predicted: str = "data/extracted", gold: str = "data/examples", out: str = "reports") -> Any:
    return run_benchmark(predicted, gold, out)


def route_sources_command(
    lanes: str,
    identifiers: str = "",
    out: str = "data/extracted/source_retrieval_plan.json",
    require_open: bool = True,
) -> Path:
    lane_values = [value.strip() for value in lanes.replace(";", ",").split(",") if value.strip()]
    identifier_values = [
        value.strip() for value in identifiers.replace(";", ",").split(",") if value.strip()
    ]
    plan = build_retrieval_plan(lane_values, identifier_values, require_open=require_open)
    return write_json(out, plan)


def run_cohort_bundle_command(bundle: str, out: str) -> Any:
    return run_cohort_bundle(bundle, out)


def live_intake_metabolomics_workbench_command(
    study_id: str = "ST001789",
    out: str | None = None,
    check_data_endpoint: bool = True,
    require_blood_derived_sample_matrix: bool = True,
) -> Any:
    target = Path(out) if out else Path("/private/tmp/metabotyping-live") / f"metabolomics_workbench_{study_id.upper()}"
    return ingest_metabolomics_workbench_study(
        study_id,
        target,
        check_data_endpoint=check_data_endpoint,
        require_blood_derived_sample_matrix=require_blood_derived_sample_matrix,
    )


def live_search_metabolite_studies_command(
    query: str,
    out: str = "data/live/metabolite_search",
    name_variants: str = "",
) -> Any:
    variants = [item.strip() for item in name_variants.split(";") if item.strip()]
    return search_metabolite_studies(query, out, name_variants=variants)


def _gene_lookup_slug(species: str, gene_id_type: str, gene: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", f"{species}__{gene_id_type}__{gene}").strip("_")


def live_lookup_gene_metabolites_command(
    gene: str,
    out: str | None = None,
    species: str = "human",
    gene_id_type: str = "SYMBOL",
    anatomy: str = "NA",
    disease: str = "NA",
    contexts: str = "",
    acknowledge_licence_review: bool = False,
    review_out: str | None = None,
) -> Any:
    requested = [item.strip() for item in contexts.split(";") if item.strip()] or list(
        METGENE_CONTEXTS
    )
    out_dir = out or f"data/live/metgene/{_gene_lookup_slug(species, gene_id_type, gene)}"
    result = lookup_gene_metabolite_annotations(
        gene,
        out_dir,
        species=species,
        gene_id_type=gene_id_type,
        contexts=requested,
        anatomy=anatomy,
        disease=disease,
        acknowledge_licence_review=acknowledge_licence_review,
    )
    if acknowledge_licence_review:
        # The offline appraisal reads the persisted rows, so it can only run once the
        # licence question has been answered and those rows exist.
        result["evidence"] = build_gene_metabolite_evidence(out_dir, review_out or out_dir)
    return result


def live_lookup_compound_command(
    value: str,
    out: str | None = None,
    input_item: str = "pubchem_cid",
    output_item: str = "all",
) -> Any:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{input_item}__{value}").strip("_")
    return lookup_compound(
        value,
        out or f"data/live/mw_compound/{slug}",
        input_item=input_item,
        output_item=output_item,
    )


def live_lookup_mgp_command(
    value: str,
    out: str | None = None,
    context: str = "gene",
    input_item: str = "gene_symbol",
) -> Any:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{context}__{input_item}__{value}").strip("_")
    return lookup_mgp_gene_protein(
        value,
        out or f"data/live/mw_mgp/{slug}",
        context=context,
        input_item=input_item,
    )


def live_search_mass_command(
    mz: str = "",
    abbreviation: str = "",
    out: str | None = None,
    adduct: str = "M+H",
    tolerance: float = 0.02,
    database: str = "REFMET",
) -> Any:
    mz = str(mz).strip()
    abbreviation = str(abbreviation).strip()
    if bool(mz) == bool(abbreviation):
        raise ValueError("Provide exactly one of --mz (precursor search) or --abbreviation (exact mass).")
    if mz:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{database}__{mz}__{adduct}").strip("_")
        return search_moverz(
            mz,
            out or f"data/live/mw_mass/{slug}",
            adduct=adduct,
            tolerance_da=tolerance,
            database=database,
        )
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"exactmass__{abbreviation}__{adduct}").strip("_")
    return compute_exact_mass(abbreviation, out or f"data/live/mw_mass/{slug}", adduct=adduct)


def live_compare_mw_motrpac_volcano_command(
    mw_study_id: str = "ST001789",
    motrpac_release: str = "human-precovid-sed-adu",
    contrast_mode: str = "all-acute",
    motrpac_scope: str = "blood-plasma",
    out: str = "/private/tmp/metabotyping-live/comparisons/mw_ST001789_vs_motrpac_human_precovid",
    top_n: int = 6,
    mw_data_json: str | None = None,
    mw_factors_json: str | None = None,
    motrpac_da_dir: str | None = None,
    motrpac_plot_contrast_mode: str = "between-groups",
    motrpac_omics_assay: str = "all",
    motrpac_group_contrasts: str = "all",
    mw_reference_contrast_key: str = "auto",
    skip_plots: bool = False,
) -> Any:
    if contrast_mode != "all-acute":
        raise ValueError("Only --contrast-mode all-acute is currently supported.")
    return compare_mw_motrpac_volcano(
        mw_study_id=mw_study_id,
        motrpac_release=motrpac_release,
        motrpac_scope=motrpac_scope,
        out=out,
        top_n=top_n,
        mw_data_json=mw_data_json,
        mw_factors_json=mw_factors_json,
        motrpac_da_dir=motrpac_da_dir,
        motrpac_plot_contrast_mode=motrpac_plot_contrast_mode,
        motrpac_omics_assay_filter=motrpac_omics_assay,
        motrpac_group_contrast_filter=motrpac_group_contrasts,
        mw_reference_contrast_key=mw_reference_contrast_key,
        skip_plots=skip_plots,
    )


def _split_terms(value: str) -> list[str]:
    """Split a ``;``-separated CLI term list, preserving order and dropping blanks."""

    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return slug or "query"


def review_literature_command(
    records: str,
    query: str = DEFAULT_QUERY,
    out: str = "data/extracted",
    reports_out: str = "reports",
    label: str = "literature",
    subject_terms: str = "",
    report_title: str = "Literature Evidence Report",
    report_filename: str = "literature_report.md",
) -> Any:
    """Screen and report an existing literature record set. Offline; no network access."""

    records_path = Path(records)
    provenance_path = (records_path if records_path.is_dir() else records_path.parent) / "literature_provenance.json"
    retrieval_provenance = read_json(provenance_path) if provenance_path.exists() else None
    criteria = define_inclusion_criteria(query)
    declared_subject_terms = _split_terms(subject_terms)
    if not declared_subject_terms and retrieval_provenance:
        # Reuse the retrieval query as the subject term when re-screening a fetched set.
        declared_subject_terms = [
            term
            for term in [
                str(retrieval_provenance.get("query_original") or ""),
                *(retrieval_provenance.get("name_variants_searched") or []),
            ]
            if term
        ]
    review = run_review_literature(
        load_literature_records(records_path),
        criteria,
        out,
        retrieval_provenance=retrieval_provenance,
        label=label,
        subject_terms=declared_subject_terms,
    )
    render_literature_report(
        review,
        reports_out,
        retrieval_provenance=retrieval_provenance,
        filename=report_filename,
        title=report_title,
    )
    return review


def live_search_literature_command(
    query: str,
    out: str | None = None,
    name_variants: str = "",
    context_terms: str = "",
    sources: str = "",
    max_records_per_source: int = 300,
    reports_out: str = "reports_live/literature",
) -> Any:
    """Retrieve, screen, and report literature for one topic. Requires network access."""

    slug = _slug(query)
    out_dir = Path(out) if out else Path("data/live/literature") / slug
    requested = _split_terms(sources) or list(LITERATURE_SOURCES)
    variants = _split_terms(name_variants)
    result = search_literature(
        query,
        out_dir,
        name_variants=variants,
        context_terms=_split_terms(context_terms),
        sources=requested,
        max_records_per_source=max_records_per_source,
        generated_utc=datetime.now(UTC).isoformat(),
    )
    criteria = define_inclusion_criteria(query)
    review = run_review_literature(
        result["records"],
        criteria,
        out_dir,
        retrieval_provenance=result["provenance"],
        label="literature",
        subject_terms=[query, *variants],
    )
    render_literature_report(
        review,
        reports_out,
        retrieval_provenance=result["provenance"],
        filename=f"{slug}_literature_report.md",
        title=f"Literature Evidence Report — {query}",
    )
    return {"retrieval": result, "review": review}


def run_pilot_command(out: str = "reports") -> None:
    ensure_dir(out)
    ensure_dir("data/extracted")
    ensure_dir("data/review")
    query_path = _examples_dir() / "pilot_query.txt"
    query = read_text(query_path).strip() if query_path.exists() else DEFAULT_QUERY
    define_criteria_command(query=query, out="data/extracted/criteria.json")
    recommendations = discover_command(criteria="data/extracted/criteria.json", out="data/extracted")
    publications = load_publications(_examples_dir() / "mock_publications.csv")
    literature_records = records_from_publications(publications)
    # The offline pilot has no retrieval lane, so the fixture itself is declared as the
    # source rather than leaving the provenance table empty.
    literature_provenance = {
        "query_original": query,
        "name_variants_searched": [],
        "context_terms": [],
        "unavailable_sources": [],
        "truncated_sources": [],
        "sources": [
            {
                "source_system": "local_synthetic_fixture",
                "status": "ok",
                "queried_expression": "data/examples/mock_publications.csv",
                "reported_hit_count": len(literature_records),
                "retrieved_count": len(literature_records),
                "pagination_complete": True,
                "detail": "offline pilot fixture; no network access and no live index queried",
                "endpoints": [],
            }
        ],
    }
    literature_review = run_review_literature(
        literature_records,
        define_inclusion_criteria(query),
        "data/extracted",
        retrieval_provenance=literature_provenance,
        label="literature",
    )
    extract_metadata_command(records=str(_examples_dir() / "mock_repository_records.csv"), out="data/extracted")
    extract_variable_inventory(_examples_dir() / "mock_variable_dictionary.csv", "data/extracted")
    build_crosswalk_command(variables=str(_examples_dir() / "mock_variable_dictionary.csv"), out="data/extracted")
    review_crosswalk_command(crosswalk="data/extracted/crosswalk.csv", out="data/review")
    build_harmonization_plan_command(crosswalk="data/extracted/crosswalk.csv", out=out)
    scores = score_quality_command(metadata="data/extracted", out="data/extracted")
    alignments = align_motrpac_command(metadata="data/extracted", out=out)
    benchmark_command(predicted="data/extracted", gold="data/examples", out=out)
    render_catalog_report(recommendations, out)
    render_evaluation_report(scores, out)
    render_motrpac_alignment_report(alignments, out)
    render_human_review_packet("data/review", out)
    render_literature_report(
        literature_review,
        out,
        retrieval_provenance=literature_provenance,
        title="Literature Screening Report (offline pilot)",
    )


if HAS_TYPER:  # pragma: no cover - this path depends on optional Typer

    @app.command("define-criteria")
    def typer_define_criteria(
        query: str = typer.Option(DEFAULT_QUERY, "--query"),
        out: str = typer.Option("data/extracted/criteria.json", "--out"),
    ) -> None:
        define_criteria_command(query, out)

    @app.command("discover")
    def typer_discover(
        criteria: str = typer.Option("data/extracted/criteria.json", "--criteria"),
        out: str = typer.Option("data/extracted", "--out"),
    ) -> None:
        discover_command(criteria, out)

    @app.command("extract-metadata")
    def typer_extract_metadata(
        records: str = typer.Option(..., "--records"),
        out: str = typer.Option("data/extracted", "--out"),
        publications: str | None = typer.Option(None, "--publications"),
        require_publication_match: bool = typer.Option(
            False,
            "--require-publication-match",
        ),
    ) -> None:
        extract_metadata_command(records, out, publications, require_publication_match)

    @app.command("build-crosswalk")
    def typer_build_crosswalk(
        variables: str = typer.Option(..., "--variables"),
        out: str = typer.Option("data/extracted", "--out"),
    ) -> None:
        build_crosswalk_command(variables, out)

    @app.command("review-crosswalk")
    def typer_review_crosswalk(
        crosswalk: str = typer.Option(..., "--crosswalk"),
        out: str = typer.Option("data/review", "--out"),
    ) -> None:
        review_crosswalk_command(crosswalk, out)

    @app.command("build-harmonization-plan")
    def typer_build_harmonization_plan(
        crosswalk: str = typer.Option(..., "--crosswalk"),
        out: str = typer.Option("reports", "--out"),
    ) -> None:
        build_harmonization_plan_command(crosswalk, out)

    @app.command("score-quality")
    def typer_score_quality(
        metadata: str = typer.Option("data/extracted", "--metadata"),
        out: str = typer.Option("data/extracted", "--out"),
    ) -> None:
        score_quality_command(metadata, out)

    @app.command("align-motrpac")
    def typer_align_motrpac(
        metadata: str = typer.Option("data/extracted", "--metadata"),
        out: str = typer.Option("reports", "--out"),
    ) -> None:
        align_motrpac_command(metadata, out)

    @app.command("benchmark")
    def typer_benchmark(
        predicted: str = typer.Option("data/extracted", "--predicted"),
        gold: str = typer.Option("data/examples", "--gold"),
        out: str = typer.Option("reports", "--out"),
    ) -> None:
        benchmark_command(predicted, gold, out)

    @app.command("route-sources")
    def typer_route_sources(
        lanes: str = typer.Option(..., "--lanes"),
        identifiers: str = typer.Option("", "--identifiers"),
        out: str = typer.Option("data/extracted/source_retrieval_plan.json", "--out"),
        require_open: bool = typer.Option(True, "--require-open/--include-restricted"),
    ) -> None:
        route_sources_command(lanes, identifiers, out, require_open)

    @app.command("run-pilot")
    def typer_run_pilot(out: str = typer.Option("reports", "--out")) -> None:
        run_pilot_command(out)

    @app.command("run-cohort-bundle")
    def typer_run_cohort_bundle(
        bundle: str = typer.Option(..., "--bundle"),
        out: str = typer.Option(..., "--out"),
    ) -> None:
        run_cohort_bundle_command(bundle, out)

    @app.command("live-intake-metabolomics-workbench")
    def typer_live_intake_metabolomics_workbench(
        study_id: str = typer.Option("ST001789", "--study-id"),
        out: str | None = typer.Option(None, "--out"),
        check_data_endpoint: bool = typer.Option(True, "--check-data-endpoint/--skip-data-check"),
        require_blood_derived_sample_matrix: bool = typer.Option(
            True,
            "--require-blood-derived-sample-matrix/--allow-non-blood-derived-sample-matrix",
        ),
    ) -> None:
        live_intake_metabolomics_workbench_command(
            study_id,
            out,
            check_data_endpoint,
            require_blood_derived_sample_matrix,
        )

    @app.command("review-literature")
    def typer_review_literature(
        records: str = typer.Option(..., "--records"),
        query: str = typer.Option(DEFAULT_QUERY, "--query"),
        # Must match the argparse defaults below. typer is a required
        # dependency, so this is the live path: leaving it on data/extracted and
        # reports/ meant a no-flag run still overwrote the offline pilot's
        # synthetic literature artifacts.
        out: str = typer.Option("data/live/literature", "--out"),
        reports_out: str = typer.Option("reports_live/literature", "--reports-out"),
        label: str = typer.Option("literature", "--label"),
        subject_terms: str = typer.Option("", "--subject-terms"),
        report_filename: str = typer.Option("literature_report.md", "--report-filename"),
        report_title: str = typer.Option("Literature Evidence Report", "--report-title"),
    ) -> None:
        review_literature_command(
            records,
            query,
            out,
            reports_out,
            label,
            subject_terms=subject_terms,
            report_filename=report_filename,
            report_title=report_title,
        )

    @app.command("live-search-literature")
    def typer_live_search_literature(
        query: str = typer.Option(..., "--query"),
        out: str | None = typer.Option(None, "--out"),
        name_variants: str = typer.Option("", "--name-variants"),
        context_terms: str = typer.Option("", "--context-terms"),
        sources: str = typer.Option("", "--sources"),
        max_records_per_source: int = typer.Option(300, "--max-records-per-source"),
        reports_out: str = typer.Option("reports_live/literature", "--reports-out"),
    ) -> None:
        live_search_literature_command(
            query,
            out,
            name_variants,
            context_terms,
            sources,
            max_records_per_source,
            reports_out,
        )

    @app.command("live-search-metabolite-studies")
    def typer_live_search_metabolite_studies(
        query: str = typer.Option(..., "--query"),
        out: str = typer.Option("data/live/metabolite_search", "--out"),
        name_variants: str = typer.Option("", "--name-variants"),
    ) -> None:
        live_search_metabolite_studies_command(query, out, name_variants)

    @app.command("live-lookup-gene-metabolites")
    def typer_live_lookup_gene_metabolites(
        gene: str = typer.Option(..., "--gene"),
        out: str | None = typer.Option(None, "--out"),
        species: str = typer.Option("human", "--species"),
        gene_id_type: str = typer.Option("SYMBOL", "--gene-id-type"),
        anatomy: str = typer.Option("NA", "--anatomy"),
        disease: str = typer.Option("NA", "--disease"),
        contexts: str = typer.Option("", "--contexts", help="; separated subset of " + ", ".join(METGENE_CONTEXTS)),
        acknowledge_licence_review: bool = typer.Option(
            False,
            "--acknowledge-licence-review/--withhold-kegg-derived-rows",
            help="Without this flag no KEGG-derived row is written to disk.",
        ),
        review_out: str | None = typer.Option(None, "--review-out"),
    ) -> None:
        live_lookup_gene_metabolites_command(
            gene,
            out,
            species,
            gene_id_type,
            anatomy,
            disease,
            contexts,
            acknowledge_licence_review,
            review_out,
        )

    @app.command("live-lookup-compound")
    def typer_live_lookup_compound(
        value: str = typer.Option(..., "--value"),
        out: str | None = typer.Option(None, "--out"),
        input_item: str = typer.Option("pubchem_cid", "--input-item"),
        output_item: str = typer.Option("all", "--output-item"),
    ) -> None:
        live_lookup_compound_command(value, out, input_item, output_item)

    @app.command("live-lookup-mw-gene-protein")
    def typer_live_lookup_mgp(
        value: str = typer.Option(..., "--value"),
        out: str | None = typer.Option(None, "--out"),
        context: str = typer.Option("gene", "--context"),
        input_item: str = typer.Option("gene_symbol", "--input-item"),
    ) -> None:
        live_lookup_mgp_command(value, out, context, input_item)

    @app.command("live-search-mass")
    def typer_live_search_mass(
        mz: str = typer.Option("", "--mz"),
        abbreviation: str = typer.Option("", "--abbreviation"),
        out: str | None = typer.Option(None, "--out"),
        adduct: str = typer.Option("M+H", "--adduct"),
        tolerance: float = typer.Option(0.02, "--tolerance"),
        database: str = typer.Option("REFMET", "--database"),
    ) -> None:
        live_search_mass_command(mz, abbreviation, out, adduct, tolerance, database)

    @app.command("live-compare-mw-motrpac-volcano")
    def typer_live_compare_mw_motrpac_volcano(
        mw_study_id: str = typer.Option("ST001789", "--mw-study-id"),
        motrpac_release: str = typer.Option("human-precovid-sed-adu", "--motrpac-release"),
        contrast_mode: str = typer.Option("all-acute", "--contrast-mode"),
        motrpac_scope: str = typer.Option("blood-plasma", "--motrpac-scope"),
        out: str = typer.Option(
            "/private/tmp/metabotyping-live/comparisons/mw_ST001789_vs_motrpac_human_precovid",
            "--out",
        ),
        top_n: int = typer.Option(6, "--top-n"),
        mw_data_json: str | None = typer.Option(None, "--mw-data-json"),
        mw_factors_json: str | None = typer.Option(None, "--mw-factors-json"),
        motrpac_da_dir: str | None = typer.Option(None, "--motrpac-da-dir"),
        motrpac_plot_contrast_mode: str = typer.Option("between-groups", "--motrpac-plot-contrast-mode"),
        motrpac_omics_assay: str = typer.Option("all", "--motrpac-omics-assay"),
        motrpac_group_contrasts: str = typer.Option("all", "--motrpac-group-contrasts"),
        mw_reference_contrast_key: str = typer.Option("auto", "--mw-reference-contrast-key"),
        skip_plots: bool = typer.Option(False, "--skip-plots"),
    ) -> None:
        live_compare_mw_motrpac_volcano_command(
            mw_study_id=mw_study_id,
            motrpac_release=motrpac_release,
            contrast_mode=contrast_mode,
            motrpac_scope=motrpac_scope,
            out=out,
            top_n=top_n,
            mw_data_json=mw_data_json,
            mw_factors_json=mw_factors_json,
            motrpac_da_dir=motrpac_da_dir,
            motrpac_plot_contrast_mode=motrpac_plot_contrast_mode,
            motrpac_omics_assay=motrpac_omics_assay,
            motrpac_group_contrasts=motrpac_group_contrasts,
            mw_reference_contrast_key=mw_reference_contrast_key,
            skip_plots=skip_plots,
        )


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse frontend.

    Exposed separately so tests can inspect option defaults without executing a
    command, which is how the typer/argparse default drift is caught.
    """

    parser = argparse.ArgumentParser(prog="metabo-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("define-criteria")
    p.add_argument("--query", default=DEFAULT_QUERY)
    p.add_argument("--out", default="data/extracted/criteria.json")

    p = subparsers.add_parser("discover")
    p.add_argument("--criteria", default="data/extracted/criteria.json")
    p.add_argument("--out", default="data/extracted")

    p = subparsers.add_parser("extract-metadata")
    p.add_argument("--records", required=True)
    p.add_argument("--out", default="data/extracted")
    p.add_argument("--publications", default=None)
    p.add_argument("--require-publication-match", action="store_true")

    p = subparsers.add_parser("build-crosswalk")
    p.add_argument("--variables", required=True)
    p.add_argument("--out", default="data/extracted")

    p = subparsers.add_parser("review-crosswalk")
    p.add_argument("--crosswalk", required=True)
    p.add_argument("--out", default="data/review")

    p = subparsers.add_parser("build-harmonization-plan")
    p.add_argument("--crosswalk", required=True)
    p.add_argument("--out", default="reports")

    p = subparsers.add_parser("score-quality")
    p.add_argument("--metadata", default="data/extracted")
    p.add_argument("--out", default="data/extracted")

    p = subparsers.add_parser("align-motrpac")
    p.add_argument("--metadata", default="data/extracted")
    p.add_argument("--out", default="reports")

    p = subparsers.add_parser("benchmark")
    p.add_argument("--predicted", default="data/extracted")
    p.add_argument("--gold", default="data/examples")
    p.add_argument("--out", default="reports")

    p = subparsers.add_parser("route-sources")
    p.add_argument("--lanes", required=True)
    p.add_argument("--identifiers", default="")
    p.add_argument("--out", default="data/extracted/source_retrieval_plan.json")
    p.add_argument("--include-restricted", action="store_true")

    p = subparsers.add_parser("run-pilot")
    p.add_argument("--out", default="reports")

    p = subparsers.add_parser("run-cohort-bundle")
    p.add_argument("--bundle", required=True)
    p.add_argument("--out", required=True)

    p = subparsers.add_parser("live-intake-metabolomics-workbench")
    p.add_argument("--study-id", default="ST001789")
    p.add_argument("--out", default=None)
    p.add_argument("--skip-data-check", action="store_true")
    p.add_argument("--allow-non-blood-derived-sample-matrix", action="store_true")

    p = subparsers.add_parser("review-literature")
    p.add_argument("--records", required=True)
    p.add_argument("--query", default=DEFAULT_QUERY)
    # Live-derived defaults. reports/ and data/extracted/ hold the offline
    # pilot's synthetic artifacts, so a no-flag invocation used to overwrite
    # reports/literature_report.md with live output.
    p.add_argument("--out", default="data/live/literature")
    p.add_argument("--reports-out", default="reports_live/literature")
    p.add_argument("--label", default="literature")
    p.add_argument("--subject-terms", default="")
    p.add_argument("--report-filename", default="literature_report.md")
    p.add_argument("--report-title", default="Literature Evidence Report")

    p = subparsers.add_parser("live-search-literature")
    p.add_argument("--query", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--name-variants", default="")
    p.add_argument("--context-terms", default="")
    p.add_argument("--sources", default="", help="; separated subset of " + ", ".join(LITERATURE_SOURCES))
    p.add_argument("--max-records-per-source", type=int, default=300)
    p.add_argument("--reports-out", default="reports_live/literature")

    p = subparsers.add_parser("live-search-metabolite-studies")
    p.add_argument("--query", required=True)
    p.add_argument("--out", default="data/live/metabolite_search")
    p.add_argument("--name-variants", default="")

    p = subparsers.add_parser("live-lookup-gene-metabolites")
    p.add_argument("--gene", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--species", default="human")
    p.add_argument("--gene-id-type", default="SYMBOL")
    p.add_argument("--anatomy", default="NA")
    p.add_argument("--disease", default="NA")
    p.add_argument("--contexts", default="", help="; separated subset of " + ", ".join(METGENE_CONTEXTS))
    p.add_argument(
        "--acknowledge-licence-review",
        action="store_true",
        help="Without this flag no KEGG-derived row is written to disk.",
    )
    p.add_argument("--review-out", default=None)

    p = subparsers.add_parser("live-lookup-compound")
    p.add_argument("--value", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--input-item", default="pubchem_cid")
    p.add_argument("--output-item", default="all")

    p = subparsers.add_parser("live-lookup-mw-gene-protein")
    p.add_argument("--value", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--context", default="gene")
    p.add_argument("--input-item", default="gene_symbol")

    p = subparsers.add_parser("live-search-mass")
    p.add_argument("--mz", default="")
    p.add_argument("--abbreviation", default="")
    p.add_argument("--out", default=None)
    p.add_argument("--adduct", default="M+H")
    p.add_argument("--tolerance", type=float, default=0.02)
    p.add_argument("--database", default="REFMET")

    p = subparsers.add_parser("live-compare-mw-motrpac-volcano")
    p.add_argument("--mw-study-id", default="ST001789")
    p.add_argument("--motrpac-release", default="human-precovid-sed-adu")
    p.add_argument("--contrast-mode", default="all-acute")
    p.add_argument("--motrpac-scope", default="blood-plasma")
    p.add_argument("--out", default="/private/tmp/metabotyping-live/comparisons/mw_ST001789_vs_motrpac_human_precovid")
    p.add_argument("--top-n", type=int, default=6)
    p.add_argument("--mw-data-json", default=None)
    p.add_argument("--mw-factors-json", default=None)
    p.add_argument("--motrpac-da-dir", default=None)
    p.add_argument("--motrpac-plot-contrast-mode", default="between-groups")
    p.add_argument("--motrpac-omics-assay", default="all")
    p.add_argument("--motrpac-group-contrasts", default="all")
    p.add_argument("--mw-reference-contrast-key", default="auto")
    p.add_argument("--skip-plots", action="store_true")

    return parser


def _argparse_main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "define-criteria":
        define_criteria_command(args.query, args.out)
    elif args.command == "discover":
        discover_command(args.criteria, args.out)
    elif args.command == "extract-metadata":
        extract_metadata_command(
            args.records,
            args.out,
            args.publications,
            args.require_publication_match,
        )
    elif args.command == "build-crosswalk":
        build_crosswalk_command(args.variables, args.out)
    elif args.command == "review-crosswalk":
        review_crosswalk_command(args.crosswalk, args.out)
    elif args.command == "build-harmonization-plan":
        build_harmonization_plan_command(args.crosswalk, args.out)
    elif args.command == "score-quality":
        score_quality_command(args.metadata, args.out)
    elif args.command == "align-motrpac":
        align_motrpac_command(args.metadata, args.out)
    elif args.command == "benchmark":
        benchmark_command(args.predicted, args.gold, args.out)
    elif args.command == "route-sources":
        route_sources_command(
            args.lanes,
            args.identifiers,
            args.out,
            require_open=not args.include_restricted,
        )
    elif args.command == "run-pilot":
        run_pilot_command(args.out)
    elif args.command == "run-cohort-bundle":
        run_cohort_bundle_command(args.bundle, args.out)
    elif args.command == "live-intake-metabolomics-workbench":
        live_intake_metabolomics_workbench_command(
            study_id=args.study_id,
            out=args.out,
            check_data_endpoint=not args.skip_data_check,
            require_blood_derived_sample_matrix=not args.allow_non_blood_derived_sample_matrix,
        )
    elif args.command == "review-literature":
        review_literature_command(
            records=args.records,
            query=args.query,
            out=args.out,
            reports_out=args.reports_out,
            label=args.label,
            subject_terms=args.subject_terms,
            report_filename=args.report_filename,
            report_title=args.report_title,
        )
    elif args.command == "live-search-literature":
        live_search_literature_command(
            query=args.query,
            out=args.out,
            name_variants=args.name_variants,
            context_terms=args.context_terms,
            sources=args.sources,
            max_records_per_source=args.max_records_per_source,
            reports_out=args.reports_out,
        )
    elif args.command == "live-search-metabolite-studies":
        live_search_metabolite_studies_command(args.query, args.out, args.name_variants)
    elif args.command == "live-lookup-gene-metabolites":
        live_lookup_gene_metabolites_command(
            gene=args.gene,
            out=args.out,
            species=args.species,
            gene_id_type=args.gene_id_type,
            anatomy=args.anatomy,
            disease=args.disease,
            contexts=args.contexts,
            acknowledge_licence_review=args.acknowledge_licence_review,
            review_out=args.review_out,
        )
    elif args.command == "live-lookup-compound":
        live_lookup_compound_command(
            value=args.value,
            out=args.out,
            input_item=args.input_item,
            output_item=args.output_item,
        )
    elif args.command == "live-lookup-mw-gene-protein":
        live_lookup_mgp_command(
            value=args.value,
            out=args.out,
            context=args.context,
            input_item=args.input_item,
        )
    elif args.command == "live-search-mass":
        live_search_mass_command(
            mz=args.mz,
            abbreviation=args.abbreviation,
            out=args.out,
            adduct=args.adduct,
            tolerance=args.tolerance,
            database=args.database,
        )
    elif args.command == "live-compare-mw-motrpac-volcano":
        live_compare_mw_motrpac_volcano_command(
            mw_study_id=args.mw_study_id,
            motrpac_release=args.motrpac_release,
            contrast_mode=args.contrast_mode,
            motrpac_scope=args.motrpac_scope,
            out=args.out,
            top_n=args.top_n,
            mw_data_json=args.mw_data_json,
            mw_factors_json=args.mw_factors_json,
            motrpac_da_dir=args.motrpac_da_dir,
            motrpac_plot_contrast_mode=args.motrpac_plot_contrast_mode,
            motrpac_omics_assay=args.motrpac_omics_assay,
            motrpac_group_contrasts=args.motrpac_group_contrasts,
            mw_reference_contrast_key=args.mw_reference_contrast_key,
            skip_plots=args.skip_plots,
        )


def main(argv: list[str] | None = None) -> None:
    if HAS_TYPER and argv is None:  # pragma: no cover
        app()
    else:
        _argparse_main(argv)


if __name__ == "__main__":
    main()

"""Offline registry and routing rules for metabolomics evidence sources.

The registry describes where evidence *could* be retrieved; it does not claim
that every source has a live adapter in this MVP.  Routing is deterministic and
keeps source breadth separate from chemical identity resolution.  In
particular, a name query can select candidate sources but can never establish
that two analytical features represent the same metabolite.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    name: str
    lanes: tuple[str, ...]
    identifier_namespaces: tuple[str, ...]
    evidence_types: tuple[str, ...]
    implementation_status: str
    access_policy: str
    open_access: bool
    homepage: str
    limitations: tuple[str, ...]
    priority: int = 50


SOURCE_REGISTRY: tuple[SourceDescriptor, ...] = (
    SourceDescriptor(
        "metabolomics_workbench",
        "Metabolomics Workbench",
        ("study_discovery", "assay_metadata", "exercise_metabolomics"),
        ("metabolomics_workbench",),
        ("study_metadata", "assay_metadata", "metabolite_table", "processed_data"),
        "core_live_adapter_and_offline_fixtures",
        "public_metadata_with_study_specific_data_terms",
        True,
        "https://www.metabolomicsworkbench.org/",
        ("metadata completeness varies by study", "accession does not establish metabolite identity"),
        95,
    ),
    SourceDescriptor(
        "metabolights",
        "MetaboLights",
        ("study_discovery", "assay_metadata"),
        ("metabolights",),
        ("study_metadata", "ISA metadata", "raw_and_processed_file_inventory"),
        "life_science_plugin_connector_optional",
        "public_archive",
        True,
        "https://www.ebi.ac.uk/metabolights/",
        ("study-level records require file-level follow-up",),
        90,
    ),
    SourceDescriptor(
        "metabobank",
        "MetaboBank",
        ("study_discovery", "assay_metadata"),
        ("metabobank",),
        ("study_metadata", "raw_and_processed_file_inventory"),
        "registry_only_planned_adapter",
        "public_archive",
        True,
        "https://mb2.ddbj.nig.ac.jp/",
        ("adapter and synthetic response fixtures are not yet implemented",),
        65,
    ),
    SourceDescriptor(
        "gnps_massive",
        "GNPS / MassIVE",
        ("study_discovery", "spectral_annotation", "molecular_networking"),
        ("massive", "gnps_library"),
        ("mass_spectra", "spectral_library_match", "molecular_network"),
        "registry_only_planned_adapter",
        "public_archive_with_dataset_specific_terms",
        True,
        "https://gnps.ucsd.edu/",
        ("library matches are annotation evidence, not confirmed identities",),
        85,
    ),
    SourceDescriptor(
        "motrpac_datahub",
        "MoTrPAC Data Hub",
        ("study_discovery", "assay_metadata", "exercise_metabolomics", "analysis_results"),
        ("motrpac_release",),
        ("study_metadata", "differential_results", "multi_tissue_time_course"),
        "core_specialized_adapter_and_offline_fixtures",
        "public_release_with_release_specific_terms",
        True,
        "https://motrpac-data.org/",
        ("release, tissue, assay, sex, group, and contrast must remain explicit",),
        100,
    ),
    SourceDescriptor(
        "europe_pmc",
        "Europe PMC",
        ("literature", "study_discovery"),
        ("pmid", "pmcid", "doi"),
        ("bibliographic_record", "abstract", "full_text_link", "preprint_record", "citation_count"),
        "core_live_adapter",
        "public_index_with_source_specific_text_licences",
        True,
        "https://europepmc.org/",
        (
            "indexes MEDLINE, PMC, and preprints in one result set, so the source subset must stay explicit",
            "a bibliographic hit does not establish that the study measured the queried analyte",
        ),
        95,
    ),
    SourceDescriptor(
        "pubmed",
        "PubMed / MEDLINE (NCBI E-utilities)",
        ("literature",),
        ("pmid", "doi"),
        ("bibliographic_record", "publication_type", "mesh_indexing"),
        "core_live_adapter",
        "public_index",
        True,
        "https://pubmed.ncbi.nlm.nih.gov/",
        (
            "E-utilities blocks some shared egress addresses, and a block must be recorded as unavailable rather than as zero hits",
            "esummary carries no abstract, so text-based screening needs a second source",
        ),
        90,
    ),
    SourceDescriptor(
        "crossref",
        "Crossref",
        ("literature",),
        ("doi",),
        ("bibliographic_record", "publication_type", "publisher_metadata", "reference_count"),
        "core_live_adapter",
        "public_index",
        True,
        "https://www.crossref.org/",
        (
            "relevance search returns a ranked sample and never a declared-complete result set",
            "abstracts are present only when the publisher deposited them",
        ),
        75,
    ),
    SourceDescriptor(
        "biorxiv_medrxiv",
        "bioRxiv / medRxiv",
        ("literature",),
        ("doi",),
        ("preprint_record", "preprint_version_history", "published_journal_linkage"),
        "core_live_adapter",
        "public_preprint_server",
        True,
        "https://www.biorxiv.org/",
        (
            "preprints are not peer reviewed and must stay in a separate evidence tier",
            "the detail endpoint resolves one DOI at a time, so linkage coverage is capped by the lookup budget",
        ),
        70,
    ),
    SourceDescriptor(
        "chebi",
        "ChEBI",
        ("chemical_identity", "chemical_classification", "ontology"),
        ("chebi", "inchikey"),
        ("curated_compound_record", "ontology_relationship", "structure"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://www.ebi.ac.uk/chebi/",
        ("ontology or synonym agreement alone does not prove feature identity",),
        100,
    ),
    SourceDescriptor(
        "pubchem",
        "PubChem",
        ("chemical_identity", "chemical_properties", "bioassays"),
        ("pubchem_cid", "inchikey"),
        ("compound_record", "structure", "computed_property", "bioassay_summary"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://pubchem.ncbi.nlm.nih.gov/",
        ("substance records and compound records must not be conflated",),
        95,
    ),
    SourceDescriptor(
        "hmdb",
        "Human Metabolome Database",
        ("chemical_identity", "biological_context", "pathways", "disease_context"),
        ("hmdb", "inchikey"),
        ("metabolite_record", "biospecimen_context", "pathway_annotation", "spectrum_link"),
        "life_science_plugin_connector_optional",
        "public_search_with_database_terms",
        True,
        "https://hmdb.ca/",
        ("search results require targeted record verification", "database version must be recorded"),
        95,
    ),
    SourceDescriptor(
        "refmet",
        "RefMet",
        ("chemical_nomenclature", "chemical_classification"),
        ("refmet",),
        ("standard_name", "super_class", "main_class", "sub_class"),
        "core_offline_snapshot",
        "public_database",
        True,
        "https://www.metabolomicsworkbench.org/databases/refmet/",
        ("classification is not a substitute for structural identity", "snapshot release must be recorded"),
        100,
    ),
    SourceDescriptor(
        "lipidmaps",
        "LIPID MAPS",
        ("chemical_identity", "chemical_classification", "lipidomics"),
        ("lipidmaps", "inchikey"),
        ("lipid_structure", "lipid_class", "standardized_nomenclature"),
        "registry_only_planned_adapter",
        "public_database",
        True,
        "https://www.lipidmaps.org/",
        ("reported lipid resolution must match measured structural evidence",),
        95,
    ),
    SourceDescriptor(
        "massbank",
        "MassBank",
        ("spectral_annotation", "chemical_identity"),
        ("massbank",),
        ("reference_mass_spectrum", "instrument_metadata", "candidate_match"),
        "registry_only_planned_adapter",
        "public_database",
        True,
        "https://massbank.eu/MassBank/",
        ("spectral similarity without an in-run authentic standard is not MSI level 1",),
        90,
    ),
    SourceDescriptor(
        "mona",
        "MassBank of North America (MoNA)",
        ("spectral_annotation", "chemical_identity"),
        ("mona",),
        ("reference_mass_spectrum", "candidate_match"),
        "registry_only_planned_adapter",
        "public_database",
        True,
        "https://mona.fiehnlab.ucdavis.edu/",
        ("library provenance and instrument compatibility must be checked",),
        80,
    ),
    SourceDescriptor(
        "reactome",
        "Reactome",
        ("pathways", "biological_context"),
        ("reactome", "chebi"),
        ("species_specific_pathway", "participant_mapping", "event_hierarchy"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://reactome.org/",
        ("pathway mapping should use stable entity identifiers and species",),
        100,
    ),
    SourceDescriptor(
        "rhea",
        "Rhea",
        ("reactions", "pathways", "biological_context"),
        ("rhea", "chebi"),
        ("curated_biochemical_reaction", "ChEBI_participant_mapping"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://www.rhea-db.org/",
        ("reaction participation does not establish pathway activity",),
        95,
    ),
    SourceDescriptor(
        "wikipathways",
        "WikiPathways",
        ("pathways", "biological_context"),
        ("wikipathways",),
        ("community_curated_pathway", "identifier_mapping"),
        "registry_only_planned_adapter",
        "open_community_database",
        True,
        "https://www.wikipathways.org/",
        ("curation status and pathway version must be preserved",),
        75,
    ),
    SourceDescriptor(
        "kegg",
        "KEGG",
        ("pathways", "reactions", "chemical_identity"),
        ("kegg_compound", "kegg_pathway"),
        ("pathway", "reaction", "compound_record"),
        "registry_only_manual_or_licensed",
        "license_and_API_use_require_review",
        False,
        "https://www.kegg.jp/",
        ("redistribution and automated access may be restricted",),
        70,
    ),
    SourceDescriptor(
        "gwas_catalog",
        "GWAS Catalog",
        ("genetics", "biological_context"),
        ("gwas_study", "rsid", "efo"),
        ("study", "variant_trait_association", "mapped_gene"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://www.ebi.ac.uk/gwas/",
        ("association is not causation", "ancestry and phenotype definition must be retained"),
        95,
    ),
    SourceDescriptor(
        "gtex",
        "GTEx",
        ("genetics", "expression", "biological_context"),
        ("rsid", "ensembl_gene"),
        ("tissue_eQTL", "gene_expression"),
        "life_science_plugin_connector_optional",
        "public_database_with_data_use_terms",
        True,
        "https://gtexportal.org/",
        ("tissue, genome build, allele orientation, and cohort context are mandatory",),
        85,
    ),
    SourceDescriptor(
        "pride",
        "PRIDE Archive",
        ("study_discovery", "proteomics", "multi_omics_context"),
        ("pride",),
        ("proteomics_project_metadata", "file_inventory"),
        "life_science_plugin_connector_optional",
        "public_archive",
        True,
        "https://www.ebi.ac.uk/pride/",
        ("protein evidence must not be treated as metabolite evidence",),
        75,
    ),
    SourceDescriptor(
        "uniprot",
        "UniProt",
        ("proteins", "biological_context", "multi_omics_context"),
        ("uniprot",),
        ("protein_function", "cross_reference", "sequence"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://www.uniprot.org/",
        ("protein annotations require reviewed/unreviewed status",),
        80,
    ),
    SourceDescriptor(
        "chembl",
        "ChEMBL",
        ("pharmacology", "chemical_identity", "biological_context"),
        ("chembl", "inchikey"),
        ("compound", "target", "activity", "mechanism"),
        "life_science_plugin_connector_optional",
        "public_database",
        True,
        "https://www.ebi.ac.uk/chembl/",
        ("bioactivity assay context and units must be preserved",),
        80,
    ),
    SourceDescriptor(
        "mqacc",
        "Metabolomics Quality Assurance and Quality Control Consortium",
        ("qa_qc", "assay_metadata", "cross_platform_harmonization"),
        (),
        ("QA_QC_reporting_guidance", "reference_material_guidance"),
        "standards_reference",
        "public_guidance",
        True,
        "https://www.mqacc.org/",
        ("guidance is not a study-level quality measurement",),
        100,
    ),
    SourceDescriptor(
        "comets",
        "Consortium of Metabolomics Studies (COMETS)",
        ("cross_platform_harmonization", "meta_analysis"),
        (),
        ("cross_platform_matching_guidance", "study_level_meta_analysis"),
        "standards_reference",
        "public_methods_reference",
        True,
        "https://www.comets-analytics.org/",
        ("platform heterogeneity must be evaluated rather than erased",),
        95,
    ),
    SourceDescriptor(
        "lipidomics_standards_initiative",
        "Lipidomics Standards Initiative",
        ("lipidomics", "qa_qc", "cross_platform_harmonization"),
        (),
        ("minimal_reporting_checklist", "identification_and_quantification_guidance"),
        "standards_reference",
        "public_guidance",
        True,
        "https://lipidomicstandards.org/",
        ("lipidomics-specific rules do not automatically generalize to all metabolites",),
        95,
    ),
)


LANE_ALIASES = {
    "assay": "assay_metadata",
    "class": "chemical_classification",
    "classification": "chemical_classification",
    "compound": "chemical_identity",
    "dataset": "study_discovery",
    "datasets": "study_discovery",
    "exercise": "exercise_metabolomics",
    "gene": "genetics",
    "genes": "genetics",
    "identity": "chemical_identity",
    "lipids": "lipidomics",
    "lit": "literature",
    "literature_review": "literature",
    "paper": "literature",
    "papers": "literature",
    "preprint": "literature",
    "preprints": "literature",
    "publication": "literature",
    "publications": "literature",
    "metabolite": "chemical_identity",
    "metabolites": "chemical_identity",
    "network": "pathways",
    "pathway": "pathways",
    "qc": "qa_qc",
    "repository": "study_discovery",
    "spectra": "spectral_annotation",
    "spectrum": "spectral_annotation",
}


IDENTIFIER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("inchikey", re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$", re.IGNORECASE)),
    ("chebi", re.compile(r"^CHEBI:\d+$", re.IGNORECASE)),
    ("hmdb", re.compile(r"^HMDB\d{7,}$", re.IGNORECASE)),
    ("refmet", re.compile(r"^RM\d{7,}$", re.IGNORECASE)),
    ("lipidmaps", re.compile(r"^LM[A-Z]{2}\d{4,}$", re.IGNORECASE)),
    ("pubchem_cid", re.compile(r"^(?:PUBCHEM\s*)?CID[:\s_-]*\d+$", re.IGNORECASE)),
    ("metabolights", re.compile(r"^MTBLS\d+$", re.IGNORECASE)),
    ("metabolomics_workbench", re.compile(r"^ST\d{6,}$", re.IGNORECASE)),
    ("metabobank", re.compile(r"^MTBKS\d+$", re.IGNORECASE)),
    ("pride", re.compile(r"^PXD\d{6,}$", re.IGNORECASE)),
    ("massive", re.compile(r"^MSV\d{9,}$", re.IGNORECASE)),
    ("reactome", re.compile(r"^R-[A-Z]{3}-\d+$", re.IGNORECASE)),
    ("rhea", re.compile(r"^RHEA:\d+$", re.IGNORECASE)),
    ("rsid", re.compile(r"^RS\d+$", re.IGNORECASE)),
    ("ensembl_gene", re.compile(r"^ENS[A-Z]*G\d+(?:\.\d+)?$", re.IGNORECASE)),
    ("uniprot", re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9])$", re.IGNORECASE)),
    ("chembl", re.compile(r"^CHEMBL\d+$", re.IGNORECASE)),
    ("doi", re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?10\.\d{4,9}/\S+$", re.IGNORECASE)),
    ("pmcid", re.compile(r"^PMC\d{6,}$", re.IGNORECASE)),
    ("kegg_compound", re.compile(r"^C\d{5}$", re.IGNORECASE)),
    ("kegg_pathway", re.compile(r"^(?:MAP|HSA|RNO)\d{5}$", re.IGNORECASE)),
)


MINIMUM_EVIDENCE_BY_LANE = {
    "chemical_identity": (
        "preserve every source identifier assertion and database release",
        "require structure or identifier agreement for auto-merge",
        "route name-only, stereochemical, isomeric, adduct, and salt ambiguity to review",
    ),
    "chemical_classification": (
        "retain ontology source, release, and hierarchy level",
        "keep class membership separate from chemical identity",
    ),
    "study_discovery": (
        "retain every repository/accession pair",
        "record pagination completeness, access status, and retrieval failures",
    ),
    "assay_metadata": (
        "retain matrix, collection timing, platform, chromatography, ionization, polarity, and quantification scale",
        "record QC, blanks, internal/reference standards, batches, run order, drift, LOD/LOQ, and missingness",
    ),
    "spectral_annotation": (
        "retain library, library version, instrument conditions, precursor/adduct, score, and candidate set",
        "do not label a library-only match as confirmed identity",
    ),
    "pathways": (
        "use stable entity identifiers and explicit species",
        "declare assay-specific background, coverage, ambiguity, and multiplicity correction",
    ),
    "exercise_metabolomics": (
        "retain group, sex, tissue/matrix, timepoint, assay, and contrast orientation",
        "do not interpret visual similarity as harmonized replication",
    ),
    "cross_platform_harmonization": (
        "separate absolute concentration, semi-quantitative abundance, normalized relative abundance, and feature intensity",
        "evaluate platform heterogeneity and leave-one-platform-out sensitivity",
    ),
    "qa_qc": (
        "record rather than infer QA/QC evidence",
        "surface missing QC evidence as unknown, not as acceptable quality",
    ),
    "genetics": (
        "retain genome build, alleles, ancestry, phenotype definition, and association design",
    ),
    "literature": (
        "retain the exact query expression, endpoint URL, reported hit count, retrieved count, and pagination completeness",
        "record an unreachable index as unavailable, never as zero matching publications",
        "keep peer-reviewed, preprint, secondary-synthesis, and retracted records in separate evidence tiers",
        "label species, design, and modality evidence taken from title or abstract text as inference",
        "treat a missing accession in bibliographic text as an unresolved deposition question, not a deposition gap",
    ),
}


def _normalize_lane(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return LANE_ALIASES.get(key, key)


def supported_lanes() -> tuple[str, ...]:
    return tuple(sorted({lane for source in SOURCE_REGISTRY for lane in source.lanes}))


def infer_identifier_namespace(value: str) -> str | None:
    text = str(value).strip()
    for namespace, pattern in IDENTIFIER_PATTERNS:
        if pattern.fullmatch(text):
            return namespace
    return None


def validate_registry(registry: Iterable[SourceDescriptor] = SOURCE_REGISTRY) -> list[str]:
    rows = list(registry)
    errors: list[str] = []
    ids = [row.source_id for row in rows]
    duplicates = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    errors.extend(f"duplicate source_id: {source_id}" for source_id in duplicates)
    for row in rows:
        if not row.lanes:
            errors.append(f"{row.source_id}: at least one lane is required")
        if not 0 <= row.priority <= 100:
            errors.append(f"{row.source_id}: priority must be between 0 and 100")
        if not row.homepage.startswith("https://"):
            errors.append(f"{row.source_id}: homepage must use https")
        if not row.evidence_types:
            errors.append(f"{row.source_id}: evidence_types are required")
        if not row.limitations:
            errors.append(f"{row.source_id}: limitations are required")
    return errors


def build_retrieval_plan(
    lanes: Iterable[str],
    identifiers: Iterable[str] = (),
    *,
    require_open: bool = True,
    max_sources: int | None = 12,
) -> dict[str, object]:
    requested_lanes = tuple(dict.fromkeys(_normalize_lane(value) for value in lanes if str(value).strip()))
    if not requested_lanes:
        raise ValueError("At least one research lane is required.")
    unsupported = sorted(set(requested_lanes) - set(supported_lanes()))
    if unsupported:
        raise ValueError(
            "Unsupported research lane(s): " + ", ".join(unsupported) + ". Supported lanes: " + ", ".join(supported_lanes())
        )

    identifier_rows = []
    recognized_namespaces: set[str] = set()
    for raw in identifiers:
        value = str(raw).strip()
        if not value:
            continue
        namespace = infer_identifier_namespace(value)
        identifier_rows.append(
            {
                "value": value,
                "namespace": namespace or "unresolved",
                "status": "recognized_identifier" if namespace else "requires_entity_resolution",
            }
        )
        if namespace:
            recognized_namespaces.add(namespace)

    candidates: list[tuple[int, SourceDescriptor, list[str]]] = []
    for source in SOURCE_REGISTRY:
        lane_overlap = sorted(set(requested_lanes) & set(source.lanes))
        namespace_overlap = sorted(recognized_namespaces & set(source.identifier_namespaces))
        if not lane_overlap and not namespace_overlap:
            continue
        if require_open and not source.open_access:
            continue
        score = source.priority + 20 * len(lane_overlap) + 35 * len(namespace_overlap)
        reasons = [f"covers lane: {lane}" for lane in lane_overlap]
        reasons.extend(f"accepts identifier namespace: {namespace}" for namespace in namespace_overlap)
        candidates.append((score, source, reasons))

    candidates.sort(key=lambda item: (-item[0], item[1].source_id))
    if max_sources is not None:
        if max_sources <= 0:
            raise ValueError("max_sources must be positive or None.")
        candidates = candidates[:max_sources]

    routed_sources = []
    covered_lanes: set[str] = set()
    for score, source, reasons in candidates:
        covered_lanes.update(set(requested_lanes) & set(source.lanes))
        row = asdict(source)
        row.update({"routing_score": score, "routing_reasons": reasons})
        routed_sources.append(row)

    warnings: list[str] = []
    unresolved = [row["value"] for row in identifier_rows if row["namespace"] == "unresolved"]
    if unresolved:
        warnings.append(
            "Unrecognized values can route a search but cannot establish metabolite identity: " + ", ".join(unresolved)
        )
    missing_lanes = sorted(set(requested_lanes) - covered_lanes)
    if missing_lanes:
        warnings.append("No eligible source covered lane(s): " + ", ".join(missing_lanes))
    if require_open and any(
        set(requested_lanes) & set(source.lanes) and not source.open_access for source in SOURCE_REGISTRY
    ):
        warnings.append("Restricted or license-reviewed sources were excluded by require_open=true.")
    if not routed_sources:
        warnings.append("The routing plan contains no executable or reference source candidates.")

    evidence_requirements = {
        lane: list(MINIMUM_EVIDENCE_BY_LANE.get(lane, ("retain source and retrieval provenance",)))
        for lane in requested_lanes
    }
    return {
        "schema_version": "1.0",
        "requested_lanes": list(requested_lanes),
        "identifiers": identifier_rows,
        "require_open": require_open,
        "sources": routed_sources,
        "covered_lanes": sorted(covered_lanes),
        "missing_lanes": missing_lanes,
        "minimum_evidence_requirements": evidence_requirements,
        "decision_rules": [
            "Source selection is not entity resolution.",
            "Names and synonyms alone never authorize an automatic metabolite merge.",
            "Cross-source conflicts and one-to-many mappings remain visible for human review.",
            "Planned and optional connectors are labeled and must not be reported as executed retrievals.",
        ],
        "warnings": warnings,
    }


_REGISTRY_ERRORS = validate_registry()
if _REGISTRY_ERRORS:  # pragma: no cover - defensive import-time invariant
    raise RuntimeError("Invalid metabolomics source registry: " + "; ".join(_REGISTRY_ERRORS))

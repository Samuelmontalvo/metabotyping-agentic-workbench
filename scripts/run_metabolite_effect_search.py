#!/usr/bin/env python3
"""Run the `metabolite-effect-search` skill against local MW and MoTrPAC effect
tables. Follows the workflow in `.claude/skills/metabolite-effect-search/SKILL.md`.

Inputs are read locally (no network). Outputs:
  - reports_live/metabolite_effects_<query_slug>.md
  - data/extracted/metabolite_effects_<query_slug>.csv
  - data/extracted/metabolite_effects_<query_slug>.json
  - reports_live/refmet_enrichment_<query_slug>_<level>.md
  - data/extracted/refmet_enrichment_<query_slug>_<level>.csv
  - data/extracted/refmet_enrichment_<query_slug>_<level>.json

Usage:
  .venv/bin/python scripts/run_metabolite_effect_search.py "Leucine" --type metabolite
  .venv/bin/python scripts/run_metabolite_effect_search.py "acylcarnitine" --type class
  .venv/bin/python scripts/run_metabolite_effect_search.py "Amino acids and peptides" --type enrichment --level main_class
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

# --- effect tables present locally; declared in SKILL.md ----------------------
EFFECT_TABLES = [
    {
        "path": "data/live/volcano_human_ST004303.csv",
        "source_system": "Metabolomics Workbench",
        "study_id": "ST004303",
        "study_title": "Exercise intensity modulates the human plasma secretome (Rockefeller)",
        "study_link": "https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST004303",
        "accession_or_contrast": "ST004303 :: post (4P) vs pre (1P), paired, MIE+SIE pooled",
        "contrast_orientation": "positive log2fc = HIGHER post-exercise (late, ~late-post)",
        "sample_matrix": "plasma",
        "species": "Homo sapiens",
        "intervention_timing": "acute, post (Time 4P) vs pre (Time 1P)",
        "platform_default": "LC-MS HILIC (MW analysis AN007160)",
        "assay_panel_default": "AN007160",
        "sex_field": None,
    },
    {
        "path": "data/live/volcano_motrpac_human_plasma_endur_post.csv",
        "source_system": "MoTrPAC DataHub",
        "study_id": "human-precovid-sed-adu",
        "study_title": "MoTrPAC human acute exercise (precovid sedentary adults)",
        "study_link": "https://motrpac-data.org/data-download",
        "accession_or_contrast": "ADUEndur.post_3.5_4_hr - ADUEndur.pre_exercise",
        "contrast_orientation": "positive log2fc = HIGHER post-exercise (endurance, late post)",
        "sample_matrix": "plasma",
        "species": "Homo sapiens",
        "intervention_timing": "acute, endurance bout, late post (~3.5-4 hr) vs pre",
        "platform_default": "DREAM mixed-model across 6 untargeted + 5 targeted plasma panels",
        "assay_panel_field": "platform",
        "assay_panel_default": "not_reported",
        "sex_field": None,
    },
    {
        "path": "data/live/volcano_motrpac_pass1b06_plasma_8w.csv",
        "source_system": "MoTrPAC DataHub",
        "study_id": "pass1b06",
        "study_title": "MoTrPAC PASS1B-06 rat endurance training (plasma, 8 weeks)",
        "study_link": "https://motrpac-data.org/data-download",
        "accession_or_contrast": "pass1b06 plasma :: 8w training vs sedentary control",
        "contrast_orientation": "positive log2fc = HIGHER at 8w training vs sedentary",
        "sample_matrix": "plasma",
        "species": "Rattus norvegicus",
        "intervention_timing": "8-week endurance training vs sedentary control",
        "platform_default": "MoTrPAC consortium timewise DEA (search_public API)",
        "assay_panel_default": "metabolomics_timewise",
        "sex_field": "sex",
    },
]

DEFAULT_FDR = 0.05

# Curated annotation source (RefMet bulk database, super/main/sub class).
REFMET_ANNOT = "data/live/refmet_annotations.csv"
REFMET_ANNOT_SOURCE = "RefMet"
# The current local CSV does not carry a release/version column. Keep that
# absence explicit rather than substituting the file mtime for a scientific
# database release.
REFMET_ANNOT_RELEASE_FALLBACK = "not_recorded_in_local_snapshot"

REFMET_LEVELS = {
    "superclass": ("super_class", "super_class"),
    "super_class": ("super_class", "super_class"),
    "super class": ("super_class", "super_class"),
    "main": ("main_class", "main_class"),
    "class": ("main_class", "main_class"),
    "main_class": ("main_class", "main_class"),
    "subclass": ("sub_class", "sub_class"),
    "sub_class": ("sub_class", "sub_class"),
    "sub class": ("sub_class", "sub_class"),
}

ENRICHMENT_COLUMNS = [
    "query_original",
    "query_type",
    "refmet_level",
    "refmet_label",
    "match_basis",
    "match_confidence",
    "review_status",
    "decision_scope",
    "harmonization_eligibility",
    "identity_evidence_level",
    "source_system",
    "study_id",
    "species",
    "sample_matrix",
    "assay_panel",
    "sex_or_subgroup",
    "accession_or_contrast",
    "analysis_stratum",
    "analysis_stratum_fields",
    "n_class_rows",
    "n_class_significant",
    "n_class_up_significant",
    "n_class_down_significant",
    "class_significant_fraction",
    "n_background_rows",
    "n_background_significant",
    "n_nonclass_background_rows",
    "n_nonclass_background_significant",
    "background_significant_fraction",
    "enrichment_ratio",
    "fisher_exact_p",
    "fisher_exact_q",
    "bh_test_count",
    "multiple_testing_method",
    "multiple_testing_scope",
    "enrichment_significance_call",
    "n_class_identifier_supported",
    "n_background_identifier_supported",
    "source_systems",
    "study_ids",
    "source_files",
    "example_metabolites",
    "example_refmet_ids",
    "refmet_annotation_sources",
    "refmet_annotation_releases",
    "refmet_annotation_provenance",
    "significance_threshold",
    "interpretation",
    "missing_evidence",
]

# Name-pattern rules for class queries WITHOUT a curated annotation hit.
# Marked as inferred_name_pattern -> requires_human_review. Non-capturing groups.
CLASS_PATTERNS = {
    "acylcarnitine": re.compile(r"\b(?:car[\s(:]|acylcarnitine|carnitine)", re.IGNORECASE),
    "lpc":           re.compile(r"\blpc[\s(]", re.IGNORECASE),
    "pc":            re.compile(r"\bpc[\s(]", re.IGNORECASE),
    "pe":            re.compile(r"\bpe[\s(]", re.IGNORECASE),
    "tg":            re.compile(r"\btg[\s(]", re.IGNORECASE),
    "amino acid":    re.compile(r"(?:leucine|isoleucine|valine|alanine|glycine|serine|threonine|"
                                r"methionine|cysteine|phenylalanine|tyrosine|tryptophan|histidine|"
                                r"lysine|arginine|aspart|glutam|proline|asparagine|glutamine)",
                                re.IGNORECASE),
    "bcaa":          re.compile(r"(?:leucine|isoleucine|alloisoleucine|valine)", re.IGNORECASE),
    "fatty acid":    re.compile(r"(?:\bfa\(|[0-9]+:[0-9]+|hexanoic|octanoic|decanoic|lauric|"
                                r"myristic|palmitic|stearic|oleic|linoleic|arachidonic|"
                                r"docosahexaenoic|eicosa)", re.IGNORECASE),
    "bile acid":     re.compile(r"(?:cholic|chenodeoxycholic|deoxycholic|lithocholic|taurine\s+conj|glyco)",
                                re.IGNORECASE),
    "kynurenine":    re.compile(r"(?:kynurenine|kynurenic|tryptophan|indole|quinolin)", re.IGNORECASE),
    "nucleotide":    re.compile(r"(?:adenosine|adenine|inosine|hypoxanthine|xanthine|guanosine|"
                                r"uridine|cytidine|thymidine|pseudouridine)", re.IGNORECASE),
}


def class_norm(s: str) -> str:
    """Normalize a class label for comparison: lowercase, alphanumeric only,
    strip a trailing plural 's'. 'Acyl carnitines' and 'acylcarnitine' both -> 'acylcarnitine'."""
    t = re.sub(r"[^a-z0-9]+", "", str(s).lower())
    return t[:-1] if t.endswith("s") else t


# RefMet annotation lookups. Name annotation and stable-identifier evidence are
# deliberately separate: resolving a name to a RefMet row does not prove that
# the source feature was identified to that chemical entity.
_REFMET_CACHE: dict | None = None
_REFMET_ID_CACHE: dict | None = None
_REFMET_CACHE_PATH: str | None = None


def load_refmet() -> dict:
    global _REFMET_CACHE, _REFMET_ID_CACHE, _REFMET_CACHE_PATH
    p = Path(REFMET_ANNOT)
    cache_path = str(p.resolve())
    if _REFMET_CACHE is not None and _REFMET_CACHE_PATH == cache_path:
        return _REFMET_CACHE
    if not p.exists():
        print(f"[warn] no RefMet annotation file at {p} — class queries fall back to name patterns only")
        _REFMET_CACHE = {}
        _REFMET_ID_CACHE = {}
        _REFMET_CACHE_PATH = cache_path
        return _REFMET_CACHE
    ann = pd.read_csv(p)
    lut: dict[str, dict] = {}
    id_lut: dict[str, dict] = {}
    ambiguous_names: set[str] = set()
    ambiguous_ids: set[str] = set()

    def first_present(row: pd.Series, columns: tuple[str, ...], fallback: str) -> str:
        for column in columns:
            value = clean_text(row.get(column))
            if value:
                return value
        return fallback

    for _, r in ann.iterrows():
        name = clean_text(r.get("name"))
        if not name:
            continue
        refmet_id = clean_text(r.get("refmet_id"))
        record = {
            "name": name,
            "super_class": clean_text(r.get("super_class")),
            "main_class": clean_text(r.get("main_class")),
            "sub_class": clean_text(r.get("sub_class")),
            "refmet_id": refmet_id,
            "annotation_source": first_present(
                r,
                ("annotation_source", "source"),
                REFMET_ANNOT_SOURCE,
            ),
            "annotation_release": first_present(
                r,
                ("annotation_release", "release", "release_date", "version"),
                REFMET_ANNOT_RELEASE_FALLBACK,
            ),
            "annotation_provenance": first_present(
                r,
                ("annotation_provenance", "provenance"),
                str(p),
            ),
        }
        name_key = normalize(name)
        previous = lut.get(name_key)
        if previous is not None and previous.get("refmet_id") != refmet_id:
            ambiguous_names.add(name_key)
        else:
            lut[name_key] = record

        if refmet_id:
            id_key = normalize(refmet_id)
            previous_id = id_lut.get(id_key)
            if previous_id is not None and previous_id.get("name") != name:
                ambiguous_ids.add(id_key)
            else:
                id_lut[id_key] = record

    for key in ambiguous_names:
        lut.pop(key, None)
    for key in ambiguous_ids:
        id_lut.pop(key, None)
    _REFMET_CACHE = lut
    _REFMET_ID_CACHE = id_lut
    _REFMET_CACHE_PATH = cache_path
    return lut


def annotate(refmet_name: str) -> dict:
    return load_refmet().get(normalize(refmet_name), {})


def annotate_refmet_id(refmet_id: str) -> dict:
    load_refmet()
    return (_REFMET_ID_CACHE or {}).get(normalize(refmet_id), {})


def annotation_for_effect_row(r: pd.Series) -> dict:
    """Resolve hierarchy annotation while keeping identity evidence explicit.

    A source-carried RefMet identifier that resolves without a name conflict is
    stable-identifier support. An exact lookup of ``refmet_name`` is annotation
    evidence only and remains review-required for chemical identity.
    """
    source_refmet_id = clean_text(r.get("refmet_id"))
    refmet_name = clean_text(r.get("refmet_name"))
    metabolite_name = clean_text(r.get("metabolite"))
    name_for_lookup = refmet_name or metabolite_name
    name_annotation = annotate(name_for_lookup) if name_for_lookup else {}

    if source_refmet_id:
        id_annotation = annotate_refmet_id(source_refmet_id)
        if id_annotation:
            name_refmet_id = clean_text(name_annotation.get("refmet_id")) if name_annotation else None
            id_refmet_id = clean_text(id_annotation.get("refmet_id"))
            if name_refmet_id and normalize(name_refmet_id) != normalize(id_refmet_id):
                return {
                    "annotation": id_annotation,
                    "source_refmet_id": source_refmet_id,
                    "resolution_basis": "source_refmet_id_name_conflict",
                    "stable_identifier_supported": False,
                    "identifier_conflict": True,
                }
            return {
                "annotation": id_annotation,
                "source_refmet_id": source_refmet_id,
                "resolution_basis": "source_refmet_id",
                "stable_identifier_supported": True,
                "identifier_conflict": False,
            }
        return {
            "annotation": name_annotation,
            "source_refmet_id": source_refmet_id,
            "resolution_basis": (
                "unresolved_source_refmet_id_name_lookup"
                if name_annotation
                else "unresolved_source_refmet_id"
            ),
            "stable_identifier_supported": False,
            "identifier_conflict": False,
        }

    return {
        "annotation": name_annotation,
        "source_refmet_id": None,
        "resolution_basis": "exact_name_lookup" if name_annotation else "unresolved",
        "stable_identifier_supported": False,
        "identifier_conflict": False,
    }


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def clean_text(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "na", "none"}:
        return None
    return text


def safe_float(value) -> float:
    return float(value) if pd.notna(value) else np.nan


def resolve_refmet_level(level: str) -> tuple[str, str]:
    key = normalize(level).replace("_", " ")
    key = re.sub(r"\s+", " ", key)
    if key in REFMET_LEVELS:
        return REFMET_LEVELS[key]
    compact = key.replace(" ", "_")
    if compact in REFMET_LEVELS:
        return REFMET_LEVELS[compact]
    raise ValueError(f"unsupported RefMet level: {level}")


def hierarchy_label_matches(label: str, query: str) -> bool:
    if not query or class_norm(query) in {"all", "any", "*"}:
        return True
    qn = class_norm(query)
    ln = class_norm(label)
    return qn == ln or qn in ln or ln in qn


def load_tables() -> list[tuple[pd.DataFrame, dict]]:
    out = []
    for meta in EFFECT_TABLES:
        p = Path(meta["path"])
        if not p.exists():
            print(f"[warn] missing: {p}")
            continue
        df = pd.read_csv(p)
        df["_metabolite_norm"] = df["metabolite"].astype(str).map(normalize)
        df["_refmet_norm"] = df["refmet_name"].astype(str).map(normalize)
        if "refmet_id" in df.columns:
            df["_refmet_id_norm"] = df["refmet_id"].fillna("").astype(str).map(normalize)
        else:
            df["_refmet_id_norm"] = ""
        out.append((df, meta))
    return out


ANALYSIS_STRATUM_FIELDS = (
    "source_system",
    "study_id",
    "species",
    "sample_matrix",
    "assay_panel",
    "accession_or_contrast",
    "sex_or_subgroup",
)


def analysis_stratum_value(values: dict) -> str:
    return " | ".join(
        f"{field}={clean_text(values.get(field)) or 'not_reported'}"
        for field in ANALYSIS_STRATUM_FIELDS
    )


def assay_panel_for_row(r: pd.Series, meta: dict) -> str:
    candidates = [
        meta.get("assay_panel_field") and r.get(meta["assay_panel_field"]),
        r.get("assay_panel"),
        r.get("assay"),
        r.get("platform"),
        meta.get("assay_panel_default"),
    ]
    for candidate in candidates:
        value = clean_text(candidate)
        if value:
            return value
    return "not_reported"


def build_effect_record(
    r: pd.Series,
    meta: dict,
    query: str,
    qtype: str,
    matched_term: str,
    match_basis: str,
    match_confidence: str,
    review_status: str,
) -> dict:
    metabolite_raw = clean_text(r.get("metabolite"))
    refmet_raw = clean_text(r.get("refmet_name"))
    display_term = matched_term or metabolite_raw or refmet_raw or "unlabeled_metabolite"
    log2fc = safe_float(r.get("log2fc"))
    pval = safe_float(r.get("p_value"))
    fdr = safe_float(r.get("fdr"))
    sig = pd.notna(fdr) and fdr < DEFAULT_FDR
    if pd.notna(log2fc):
        direction = (
            "up_in_numerator"
            if log2fc > 0
            else ("down_in_numerator" if log2fc < 0 else "no_change")
        )
    else:
        direction = "orientation_unknown"

    annotation_result = annotation_for_effect_row(r)
    ann = annotation_result["annotation"]
    source_refmet_id = annotation_result["source_refmet_id"]
    identifier_supported = bool(annotation_result["stable_identifier_supported"])
    annotation_basis = annotation_result["resolution_basis"]

    identity_sensitive_bases = {
        "exact_name_match",
        "exact_refmet_id_match",
        "refmet_curated_class",
        "refmet_curated_annotation",
    }
    if identifier_supported and match_basis in identity_sensitive_bases:
        match_confidence = "curated_identifier_supported"
        review_status = "accepted_curated"
    elif match_basis in identity_sensitive_bases:
        match_confidence = (
            "exact_name_only"
            if match_basis == "exact_name_match"
            else "annotation_name_lookup_only"
        )
        review_status = "requires_human_review"
    else:
        review_status = "requires_human_review"

    identity_evidence_level = (
        "source_stable_identifier_assertion"
        if identifier_supported
        else ("name_resolved_annotation_only" if ann else "unresolved")
    )

    platform = clean_text(r.get("platform")) or clean_text(meta.get("platform_default")) or "not_reported"
    assay_panel = assay_panel_for_row(r, meta)
    sex_or_subgroup = (
        clean_text(r.get(meta["sex_field"]))
        if meta.get("sex_field")
        else None
    ) or "all_or_not_reported"
    species = clean_text(meta.get("species")) or "not_reported"
    stratum_values = {
        "source_system": meta["source_system"],
        "study_id": meta["study_id"],
        "species": species,
        "sample_matrix": meta["sample_matrix"],
        "assay_panel": assay_panel,
        "accession_or_contrast": meta["accession_or_contrast"],
        "sex_or_subgroup": sex_or_subgroup,
    }
    analysis_stratum = analysis_stratum_value(stratum_values)

    missing = []
    if pd.isna(pval):
        missing.append("p_value")
    if pd.isna(fdr):
        missing.append("fdr")
    if not meta.get("contrast_orientation"):
        missing.append("contrast_orientation")
    if not ann:
        missing.append("refmet_class_annotation")
    elif ann.get("annotation_release") == REFMET_ANNOT_RELEASE_FALLBACK:
        missing.append("refmet_annotation_release")
    if not metabolite_raw:
        missing.append("source_metabolite_name")
    if not refmet_raw:
        missing.append("refmet_name")
    if not source_refmet_id:
        missing.append("source_stable_metabolite_identifier")
    elif annotation_basis.startswith("unresolved_source_refmet_id"):
        missing.append("unresolved_source_refmet_id")
    if annotation_result["identifier_conflict"]:
        missing.append("source_refmet_id_name_conflict")
    if ann and not identifier_supported:
        missing.append("chemical_identity_not_identifier_supported")

    if pd.notna(log2fc):
        numerator = (
            meta["contrast_orientation"].split("= ")[-1]
            if "= " in meta["contrast_orientation"]
            else "numerator"
        )
        interpret = (
            f"{abs(log2fc):.2f} log2-units "
            f"{'higher' if log2fc > 0 else 'lower'} in {numerator} "
            f"(p={pval:.2e}, FDR={fdr:.2e})"
        )
    else:
        interpret = "orientation unknown"

    return {
        "query_original": query,
        "query_type": qtype,
        "matched_term": display_term,
        "match_basis": match_basis,
        "match_confidence": match_confidence,
        "review_status": review_status,
        "decision_scope": "retrieval_and_annotation_match_only",
        "harmonization_eligibility": "requires_assay_identity_review",
        "identity_evidence_level": identity_evidence_level,
        "source_system": meta["source_system"],
        "study_id": meta["study_id"],
        "study_title": meta["study_title"],
        "accession_or_contrast": meta["accession_or_contrast"],
        "study_link": meta["study_link"],
        "sample_matrix": meta["sample_matrix"],
        "species": species,
        "intervention_timing": meta["intervention_timing"],
        "platform": platform,
        "assay_panel": assay_panel,
        "sex_or_subgroup": sex_or_subgroup,
        "analysis_stratum": analysis_stratum,
        "analysis_stratum_fields": ";".join(ANALYSIS_STRATUM_FIELDS),
        "metabolite": metabolite_raw or display_term,
        "refmet_name": refmet_raw or display_term,
        "refmet_id": clean_text(ann.get("refmet_id")) or source_refmet_id or "not_available",
        "source_refmet_id": source_refmet_id or "not_available",
        "refmet_annotation_match_basis": annotation_basis,
        "identity_stable_identifier_supported": identifier_supported,
        "refmet_annotation_source": clean_text(ann.get("annotation_source")) or "not_available",
        "refmet_annotation_release": clean_text(ann.get("annotation_release")) or "not_available",
        "refmet_annotation_provenance": clean_text(ann.get("annotation_provenance")) or "not_available",
        "source_metabolite_raw": metabolite_raw or "",
        "class": ann.get("main_class"),
        "superclass": ann.get("super_class"),
        "subclass": ann.get("sub_class"),
        "log2fc": log2fc,
        "p_value": pval,
        "fdr": fdr,
        "direction": direction,
        "significance_call": (
            "significant_FDR<0.05"
            if sig
            else ("not_significant" if pd.notna(fdr) else "no_fdr")
        ),
        "effect_interpretation": interpret,
        "provenance_file": meta["path"],
        "missing_evidence": ";".join(missing) if missing else "",
    }


def match_rows(df: pd.DataFrame, query: str, qtype: str):
    """Return filtered rows plus row-aligned match basis and confidence series."""
    qn = normalize(query)
    if qtype == "metabolite":
        exact_m = df["_metabolite_norm"].eq(qn)
        exact_r = df["_refmet_norm"].eq(qn)
        exact_id = df.get("_refmet_id_norm", pd.Series("", index=df.index)).eq(qn)
        exact = exact_m | exact_r | exact_id
        sub = (df["_metabolite_norm"].str.contains(re.escape(qn), na=False)
               | df["_refmet_norm"].str.contains(re.escape(qn), na=False)) & ~exact
        basis = pd.Series(
            np.where(
                exact_id,
                "exact_refmet_id_match",
                np.where(
                    exact,
                    "exact_name_match",
                    np.where(sub, "substring_name_match", None),
                ),
            ),
            index=df.index,
        )
        keep = exact | sub
        # Exact names are retrieval evidence, not confirmed chemical identity.
        # build_effect_record upgrades only rows supported by a source-carried,
        # resolvable RefMet identifier.
        conf = pd.Series(np.where(exact_id, "curated_identifier_candidate",
                          np.where(exact, "exact_name_only",
                          np.where(sub, "substring_name_only", None))), index=df.index)
        return df[keep], basis[keep], conf[keep]
    elif qtype in ("class", "superclass", "super class", "subclass"):
        qc = class_norm(query)
        # 1) curated: refmet_name annotated to a class whose super/main/sub matches the query
        def curated_hit(row: pd.Series) -> bool:
            a = annotation_for_effect_row(row)["annotation"]
            if not a:
                return False
            for lvl in ("sub_class", "main_class", "super_class"):
                val = a.get(lvl)
                if val and (class_norm(val) == qc or qc in class_norm(val) or class_norm(val) in qc):
                    return True
            return False
        curated_mask = df.apply(curated_hit, axis=1)

        # 2) pattern fallback for rows the curated table did not resolve
        pat = CLASS_PATTERNS.get(qn)
        if pat is not None:
            pat_mask = (df["metabolite"].astype(str).str.contains(pat, na=False)
                        | df["refmet_name"].astype(str).str.contains(pat, na=False))
        else:
            pat_mask = (df["metabolite"].astype(str).str.contains(re.escape(qn), case=False, na=False)
                        | df["refmet_name"].astype(str).str.contains(re.escape(qn), case=False, na=False))
        pat_only = pat_mask & ~curated_mask

        keep = curated_mask | pat_only
        basis = pd.Series(np.where(curated_mask, "refmet_curated_class",
                          np.where(pat_only, "inferred_name_pattern", None)), index=df.index)
        conf = pd.Series(np.where(curated_mask, "annotation_name_lookup_only",
                          np.where(pat_only, "inferred_name_pattern", None)), index=df.index)
        return df[keep], basis[keep], conf[keep]
    else:
        # unknown — try both routes; metabolite first
        return match_rows(df, query, "metabolite")


def run_search(query: str, qtype: str = "metabolite") -> pd.DataFrame:
    rows = []
    for df, meta in load_tables():
        sub, basis, conf = match_rows(df, query, qtype)
        if sub.empty:
            continue
        for i, r in sub.iterrows():
            metabolite_raw = clean_text(r.get("metabolite"))
            refmet_raw = clean_text(r.get("refmet_name"))
            display_term = metabolite_raw or refmet_raw or "unlabeled_metabolite"
            rows.append(
                build_effect_record(
                    r=r,
                    meta=meta,
                    query=query,
                    qtype=qtype,
                    matched_term=display_term,
                    match_basis=basis.loc[i],
                    match_confidence=conf.loc[i],
                    review_status="requires_human_review",
                )
            )
    out = pd.DataFrame(rows)
    return out


def collect_effect_universe() -> pd.DataFrame:
    """Return all local effect rows with shared provenance and RefMet annotations."""
    rows = []
    for df, meta in load_tables():
        for _, r in df.iterrows():
            metabolite_raw = clean_text(r.get("metabolite"))
            refmet_raw = clean_text(r.get("refmet_name"))
            display_term = metabolite_raw or refmet_raw or "unlabeled_metabolite"
            ann = annotation_for_effect_row(r)["annotation"]
            rows.append(
                build_effect_record(
                    r=r,
                    meta=meta,
                    query="all",
                    qtype="background",
                    matched_term=display_term,
                    match_basis="refmet_curated_annotation" if ann else "unannotated_effect_row",
                    match_confidence="annotation_name_lookup_only" if ann else "unannotated",
                    review_status="requires_human_review",
                )
            )
    return pd.DataFrame(rows)


def fisher_right_tail_p_value(class_rows: int, class_sig: int, total_rows: int, total_sig: int) -> float:
    """One-sided Fisher/hypergeometric enrichment P(significant >= observed)."""
    if class_rows <= 0 or total_rows <= 0 or total_sig < 0 or total_sig > total_rows:
        return np.nan
    max_x = min(class_rows, total_sig)
    min_x = max(0, class_rows - (total_rows - total_sig))
    if class_sig < min_x or class_sig > max_x:
        return np.nan
    # Exact integer arithmetic, not log-gamma floats. This p-value is published
    # in committed artifacts and diffed byte-for-byte by CI, so it has to be
    # identical everywhere. The float form was not: naive summation split 3.11
    # from 3.12+ (Neumaier), and even with math.fsum the x86_64 and arm64 libm
    # builds of math.exp/math.lgamma disagreed in the 13th digit
    # (0.03461840394428 vs ...34888 for the same inputs). math.comb is exact,
    # so a single final division is the only rounding step and the result is
    # bit-identical on every interpreter and architecture. Verified on
    # 3.11.15 arm64, 3.12.8 x86_64 and 3.14.4 arm64. It is also fast: the
    # largest realistic case runs 300 times in ~0.01s.
    denominator = math.comb(total_rows, class_rows)
    if denominator == 0:
        return np.nan
    numerator = sum(
        math.comb(total_sig, x) * math.comb(total_rows - total_sig, class_rows - x)
        for x in range(class_sig, max_x + 1)
    )
    return min(1.0, numerator / denominator)


def bh_adjust_p_values(p_values) -> np.ndarray:
    """Benjamini-Hochberg adjustment over the supplied, declared test family."""
    values = np.asarray(list(p_values), dtype=float)
    adjusted = np.full(values.shape, np.nan, dtype=float)
    finite_indices = np.flatnonzero(np.isfinite(values))
    test_count = len(finite_indices)
    if test_count == 0:
        return adjusted

    ordered_indices = finite_indices[np.argsort(values[finite_indices], kind="mergesort")]
    running_min = 1.0
    for reverse_position in range(test_count - 1, -1, -1):
        index = ordered_indices[reverse_position]
        rank = reverse_position + 1
        candidate = values[index] * test_count / rank
        running_min = min(running_min, candidate)
        adjusted[index] = min(1.0, running_min)
    return adjusted


def _single_stratum_value(group: pd.DataFrame, column: str) -> str:
    values = group[column].dropna().astype(str).drop_duplicates().tolist()
    if len(values) != 1:
        raise ValueError(
            f"analysis_stratum is not homogeneous for {column}: {values}"
        )
    return values[0]


def run_refmet_enrichment(query: str = "all", level: str = "main_class") -> pd.DataFrame:
    """Summarize significant-effect enrichment by RefMet super/main/sub class.

    Each statistical background is restricted to one declared analysis stratum:
    source/study, species, matrix, assay or panel, contrast, and subgroup. Human
    MW, human MoTrPAC panels, and rat rows are therefore never exchangeable
    observations in the same Fisher test. Class p-values are BH-adjusted across
    all tested labels within that stratum before an optional label query is
    applied. This is over-representation accounting, not pathway mechanism.
    """
    level_col, level_name = resolve_refmet_level(level)
    universe = collect_effect_universe()
    if universe.empty:
        return pd.DataFrame(columns=ENRICHMENT_COLUMNS)

    effect_col = {"super_class": "superclass", "main_class": "class", "sub_class": "subclass"}[level_col]
    annotated = universe[
        universe[effect_col].notna()
        & universe[effect_col].astype(str).str.strip().ne("")
    ].copy()
    if annotated.empty:
        return pd.DataFrame(columns=ENRICHMENT_COLUMNS)

    records = []

    for analysis_stratum, stratum in annotated.groupby("analysis_stratum", sort=True):
        total_rows = len(stratum)
        total_sig = int(stratum["significance_call"].eq("significant_FDR<0.05").sum())
        background_fraction = total_sig / total_rows if total_rows else np.nan
        background_identifier_supported = int(
            stratum["identity_stable_identifier_supported"].astype(bool).sum()
        )
        stratum_records = []

        for label, grp in stratum.groupby(effect_col, sort=True):
            label_text = str(label)
            sig = grp[grp["significance_call"].eq("significant_FDR<0.05")]
            class_rows = len(grp)
            class_sig = len(sig)
            class_fraction = class_sig / class_rows if class_rows else np.nan
            enrichment_ratio = (
                class_fraction / background_fraction
                if pd.notna(background_fraction) and background_fraction > 0
                else np.nan
            )
            p_value = fisher_right_tail_p_value(
                class_rows=class_rows,
                class_sig=class_sig,
                total_rows=total_rows,
                total_sig=total_sig,
            )
            class_identifier_supported = int(
                grp["identity_stable_identifier_supported"].astype(bool).sum()
            )
            all_class_identities_supported = class_identifier_supported == class_rows
            missing = []
            if class_rows < 3:
                missing.append("small_refmet_class_n")
            if class_sig == 0:
                missing.append("no_significant_effects_in_class")
            if not all_class_identities_supported:
                missing.append(
                    f"name_only_or_unresolved_identity_rows_in_class:{class_rows - class_identifier_supported}"
                )

            examples_frame = grp.sort_values("p_value", na_position="last")
            examples = (
                examples_frame["matched_term"]
                .dropna()
                .astype(str)
                .drop_duplicates()
                .head(8)
                .tolist()
            )
            example_refmet_ids = (
                examples_frame["refmet_id"]
                .dropna()
                .astype(str)
                .loc[lambda values: values.ne("not_available")]
                .drop_duplicates()
                .head(8)
                .tolist()
            )
            annotation_sources = sorted(
                set(grp["refmet_annotation_source"].astype(str)) - {"not_available"}
            )
            annotation_releases = sorted(
                set(grp["refmet_annotation_release"].astype(str)) - {"not_available"}
            )
            annotation_provenance = sorted(
                set(grp["refmet_annotation_provenance"].astype(str)) - {"not_available"}
            )
            if REFMET_ANNOT_RELEASE_FALLBACK in annotation_releases:
                missing.append("refmet_annotation_release_not_recorded")

            source_system = _single_stratum_value(stratum, "source_system")
            study_id = _single_stratum_value(stratum, "study_id")
            species = _single_stratum_value(stratum, "species")
            sample_matrix = _single_stratum_value(stratum, "sample_matrix")
            assay_panel = _single_stratum_value(stratum, "assay_panel")
            sex_or_subgroup = _single_stratum_value(stratum, "sex_or_subgroup")
            accession_or_contrast = _single_stratum_value(stratum, "accession_or_contrast")
            source_files = sorted(set(grp["provenance_file"].astype(str)))

            stratum_records.append({
                "query_original": query,
                "query_type": "enrichment",
                "refmet_level": level_name,
                "refmet_label": label_text,
                "match_basis": "refmet_hierarchy_annotation",
                "match_confidence": (
                    "curated_identifier_supported"
                    if all_class_identities_supported
                    else "annotation_name_lookup_identity_unconfirmed"
                ),
                "review_status": (
                    "accepted_curated"
                    if all_class_identities_supported
                    else "requires_human_review"
                ),
                "decision_scope": "within_stratum_class_overrepresentation",
                "harmonization_eligibility": "not_applicable_do_not_harmonize_from_enrichment",
                "identity_evidence_level": (
                    "all_source_stable_identifier_assertions"
                    if all_class_identities_supported
                    else "contains_name_resolved_or_unresolved_rows"
                ),
                "source_system": source_system,
                "study_id": study_id,
                "species": species,
                "sample_matrix": sample_matrix,
                "assay_panel": assay_panel,
                "sex_or_subgroup": sex_or_subgroup,
                "accession_or_contrast": accession_or_contrast,
                "analysis_stratum": analysis_stratum,
                "analysis_stratum_fields": ";".join(ANALYSIS_STRATUM_FIELDS),
                "n_class_rows": class_rows,
                "n_class_significant": class_sig,
                "n_class_up_significant": int(sig["direction"].eq("up_in_numerator").sum()),
                "n_class_down_significant": int(sig["direction"].eq("down_in_numerator").sum()),
                "class_significant_fraction": class_fraction,
                "n_background_rows": total_rows,
                "n_background_significant": total_sig,
                "n_nonclass_background_rows": total_rows - class_rows,
                "n_nonclass_background_significant": total_sig - class_sig,
                "background_significant_fraction": background_fraction,
                "enrichment_ratio": enrichment_ratio,
                "fisher_exact_p": p_value,
                "fisher_exact_q": np.nan,
                "bh_test_count": 0,
                "multiple_testing_method": "Benjamini-Hochberg",
                "multiple_testing_scope": "analysis_stratum",
                "enrichment_significance_call": "not_tested",
                "n_class_identifier_supported": class_identifier_supported,
                "n_background_identifier_supported": background_identifier_supported,
                "source_systems": source_system,
                "study_ids": study_id,
                "source_files": ";".join(source_files),
                "example_metabolites": "; ".join(examples),
                "example_refmet_ids": ";".join(example_refmet_ids),
                "refmet_annotation_sources": ";".join(annotation_sources) or "not_available",
                "refmet_annotation_releases": ";".join(annotation_releases) or "not_available",
                "refmet_annotation_provenance": ";".join(annotation_provenance) or "not_available",
                "significance_threshold": f"source FDR<{DEFAULT_FDR}; class BH q<0.05",
                "interpretation": "pending within-stratum multiple-testing adjustment",
                "missing_evidence": ";".join(missing),
            })

        q_values = bh_adjust_p_values(record["fisher_exact_p"] for record in stratum_records)
        test_count = len(stratum_records)
        for record, q_value in zip(stratum_records, q_values):
            record["fisher_exact_q"] = q_value
            record["bh_test_count"] = test_count
            record["enrichment_significance_call"] = (
                "significant_BH_q<0.05"
                if pd.notna(q_value) and q_value < 0.05
                else "not_significant_BH_q>=0.05"
            )
            ratio_text = (
                f"{record['enrichment_ratio']:.2f}"
                if pd.notna(record["enrichment_ratio"])
                else "not_estimable"
            )
            q_text = f"{q_value:.2e}" if pd.notna(q_value) else "not_estimable"
            record["interpretation"] = (
                f"Within {analysis_stratum}, {record['refmet_label']} has "
                f"{record['n_class_significant']}/{record['n_class_rows']} annotated rows "
                f"significant at source FDR<{DEFAULT_FDR}; enrichment ratio={ratio_text}, "
                f"one-sided Fisher p={record['fisher_exact_p']:.2e}, BH q={q_text} "
                f"across {test_count} {level_name} tests in this stratum."
            )
        records.extend(stratum_records)

    all_results = pd.DataFrame(records, columns=ENRICHMENT_COLUMNS)
    if all_results.empty:
        return all_results
    out = all_results[
        all_results["refmet_label"].map(lambda label: hierarchy_label_matches(label, query))
    ].copy()
    return out.sort_values(
        ["fisher_exact_q", "fisher_exact_p", "enrichment_ratio", "analysis_stratum"],
        ascending=[True, True, False, True],
        na_position="last",
    ).reset_index(drop=True)


def write_report(out: pd.DataFrame, query: str, qtype: str) -> Path:
    slug = slugify(query)
    csv_path = Path(f"data/extracted/metabolite_effects_{slug}.csv")
    json_path = Path(f"data/extracted/metabolite_effects_{slug}.json")
    md_path = Path(f"reports_live/metabolite_effects_{slug}.md")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    out.to_csv(csv_path, index=False)
    out.to_json(json_path, orient="records", indent=2)

    # build markdown
    lines = [
        f"# Metabolite effect search — `{query}` (type: {qtype})",
        "",
        f"- Effect tables scanned: {len(EFFECT_TABLES)}",
        f"- Matched rows: **{len(out)}**",
        f"- Significance threshold: FDR < {DEFAULT_FDR}",
        "- Match basis distribution: " + ", ".join(f"{k}={int(v)}" for k, v in out["match_basis"].value_counts().items()),
        "",
        "## Results (sorted by p_value)",
        "",
        "| source | study | species | assay/panel | matched_term | RefMet ID | sex | log2fc | p_value | FDR | direction | basis | review |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|",
    ]
    sub = out.sort_values("p_value", na_position="last").head(40)
    for _, r in sub.iterrows():
        sex = r["sex_or_subgroup"] or "—"
        sysstr = f"MW [{r['study_id']}]({r['study_link']})" if r["source_system"].startswith("Metabolomics") \
                 else f"MoTrPAC ({r['study_id']})"
        lines.append(
            f"| {r['source_system'].split()[0]} | {sysstr} | {r['species']} | {r['assay_panel']} | "
            f"{str(r['matched_term'])[:32]} | {r['refmet_id']} | {sex} | "
            f"{r['log2fc']:+.2f} | {r['p_value']:.2e} | {r['fdr']:.2e} | {r['direction']} | "
            f"{r['match_basis']} | {r['review_status']} |"
        )
    lines += [
        "",
        "## Contrast orientations (so directions are interpretable)",
    ]
    for t in EFFECT_TABLES:
        lines.append(f"- **{t['study_id']}** ({t['source_system']}) — {t['contrast_orientation']}")
    lines += [
        "",
        "## Per-study summary (significant @ FDR<0.05)",
        "",
        "| source_system | study_id | n_matched | n_significant | n_up_sig | n_down_sig |",
        "|---|---|---:|---:|---:|---:|",
    ]
    if not out.empty:
        for (sys_, sid), grp in out.groupby(["source_system", "study_id"], sort=False):
            sig = grp[grp["significance_call"] == "significant_FDR<0.05"]
            up = sig[sig["log2fc"] > 0]
            dn = sig[sig["log2fc"] < 0]
            lines.append(f"| {sys_} | {sid} | {len(grp)} | {len(sig)} | {len(up)} | {len(dn)} |")
    n_curated = int((out["match_basis"] == "refmet_curated_class").sum())
    n_pattern = int((out["match_basis"] == "inferred_name_pattern").sum())
    lines += [
        "",
        "## Notes",
        f"- Class matches: {n_curated} `refmet_curated_class` (hierarchy annotation available) + "
          f"{n_pattern} `inferred_name_pattern` (name-pattern only). Both remain review-required unless "
          "the source row carries a RefMet identifier that resolves without a name conflict.",
        "- Curated class membership uses the RefMet bulk database (`data/live/refmet_annotations.csv`, "
          "super/main/sub class). `refmet_id`, annotation provenance, and annotation release are emitted; "
          "the current snapshot explicitly reports its release as not recorded.",
        "- An exact metabolite-name hit is retrieval evidence, not confirmed chemical identity. A RefMet ID "
          "assigned through name lookup is shown for review but does not by itself change `review_status`.",
        "- `accepted_curated` is scoped only to a source-identifier-supported retrieval/annotation match. "
          "Every effect row remains `requires_assay_identity_review` for harmonization or raw-value pooling.",
        "- Direction is reported from the declared contrast orientation; positive log2fc = numerator side.",
        "- For MW ST004303, units are arbitrary MS intensities; a paired t-test was applied to log2 abundance.",
        "- For MoTrPAC tables, statistics are the consortium's precomputed DEA (DREAM mixed model for human, "
          "timewise DEA for rat); they are NOT recomputed here.",
    ]
    md_path.write_text("\n".join(lines))
    return md_path


def write_enrichment_report(out: pd.DataFrame, query: str, level: str) -> Path:
    _, level_name = resolve_refmet_level(level)
    slug = slugify(query)
    level_slug = slugify(level_name)
    csv_path = Path(f"data/extracted/refmet_enrichment_{slug}_{level_slug}.csv")
    json_path = Path(f"data/extracted/refmet_enrichment_{slug}_{level_slug}.json")
    md_path = Path(f"reports_live/refmet_enrichment_{slug}_{level_slug}.md")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    out.to_csv(csv_path, index=False)
    out.to_json(json_path, orient="records", indent=2)

    lines = [
        f"# RefMet hierarchy enrichment — `{query}` ({level_name})",
        "",
        f"- Effect tables scanned: {len(EFFECT_TABLES)}",
        f"- Matching RefMet labels: **{len(out)}**",
        f"- Analysis strata represented: **{out['analysis_stratum'].nunique()}**",
        f"- Significance threshold: FDR < {DEFAULT_FDR}",
        "- Background: each test uses only RefMet-annotated rows from its declared study × species × "
          "sample matrix × assay/panel × contrast × subgroup analysis stratum.",
        "- Human MW, human MoTrPAC panels, and rat strata are never pooled as exchangeable observations.",
        "- Multiple testing: Benjamini-Hochberg across all tested RefMet labels within each analysis stratum.",
        "- Interpretation: over-representation of significant effect rows, not a pathway or mechanism claim.",
        "",
        "## Enrichment summary",
        "",
        "| study | species | assay/panel | subgroup | RefMet label | n rows | background n | n sig | ratio | Fisher p | BH q | tests | review |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in out.head(40).iterrows():
        lines.append(
            f"| {r['study_id']} | {r['species']} | {r['assay_panel']} | {r['sex_or_subgroup']} | "
            f"{r['refmet_label']} | {int(r['n_class_rows'])} | {int(r['n_background_rows'])} | "
            f"{int(r['n_class_significant'])} | {r['enrichment_ratio']:.2f} | "
            f"{r['fisher_exact_p']:.2e} | {r['fisher_exact_q']:.2e} | "
            f"{int(r['bh_test_count'])} | {r['review_status']} |"
        )

    lines += [
        "",
        "## Provenance",
    ]
    for t in EFFECT_TABLES:
        lines.append(f"- **{t['study_id']}** ({t['source_system']}) — `{t['path']}`")

    lines += [
        "",
        "## Notes",
        "- RefMet hierarchy columns, IDs, annotation provenance, and release fields come from "
          "`data/live/refmet_annotations.csv`; the current snapshot does not record a RefMet release.",
        "- Rows without a RefMet hierarchy label are excluded from the enrichment background for that hierarchy level.",
        "- A name-resolved RefMet annotation does not confirm source-feature identity; those rows remain "
          "`requires_human_review` unless the source row carries a consistent stable RefMet identifier.",
        "- Enrichment decisions are scoped to within-stratum class over-representation and are explicitly "
          "ineligible as metabolite harmonization evidence.",
        "- Fisher p-values are BH-adjusted only against class tests from the same `analysis_stratum`; "
          "q-values from different strata are reported side by side but are not a pooled analysis.",
        "- Small classes and classes without significant effects are flagged in `missing_evidence`.",
        "- Use the row-level metabolite report before making harmonization, pathway, or mechanistic claims.",
    ]
    md_path.write_text("\n".join(lines))
    return md_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="metabolite name, RefMet class label, or 'all' for enrichment")
    ap.add_argument("--type", default="metabolite",
                    choices=[
                        "metabolite", "class", "superclass", "super class", "subclass",
                        "enrichment", "unknown",
                    ])
    ap.add_argument(
        "--level",
        default="main_class",
        choices=[
            "superclass", "super_class", "super class", "class", "main_class",
            "subclass", "sub_class", "sub class",
        ],
        help="RefMet hierarchy level for --type enrichment",
    )
    args = ap.parse_args()
    if args.type == "enrichment":
        out = run_refmet_enrichment(args.query, args.level)
        if out.empty:
            print(f"[no enrichment matches] query='{args.query}' level={args.level}")
            return
        md = write_enrichment_report(out, args.query, args.level)
        print(f"[ok] summarized {len(out)} RefMet labels -> {md}")
        print(out.head(15)[[
            "study_id", "species", "assay_panel", "sex_or_subgroup", "refmet_level",
            "refmet_label", "n_class_rows", "n_class_significant", "enrichment_ratio",
            "fisher_exact_p", "fisher_exact_q", "bh_test_count",
        ]].to_string(index=False))
        return

    out = run_search(args.query, args.type)
    if out.empty:
        print(f"[no matches] query='{args.query}' type={args.type}")
        return
    md = write_report(out, args.query, args.type)
    print(f"[ok] matched {len(out)} rows -> {md}")
    print(out.sort_values("p_value", na_position="last")
              .head(15)[["source_system", "study_id", "species", "assay_panel", "matched_term",
                         "refmet_id", "log2fc", "p_value", "fdr", "direction", "sex_or_subgroup",
                         "match_basis", "review_status"]].to_string(index=False))


if __name__ == "__main__":
    main()

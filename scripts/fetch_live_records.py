#!/usr/bin/env python3
"""Live ingestion: pull real Metabolomics Workbench (and MoTrPAC-on-MW) studies
and map them into the workbench's repository_records + publications schemas.

This is the ONLY networked entry point in the project. It writes to data/live/
so the offline synthetic fixtures under data/examples/ remain untouched and the
offline pilot stays fully reproducible.

Provenance: every emitted row records the exact MW REST URLs it was derived from
in data/live/provenance.json.

Usage:
    python3 scripts/fetch_live_records.py                # curated study set
    python3 scripts/fetch_live_records.py ST004303 ST003807 ...   # explicit IDs
    python3 scripts/fetch_live_records.py --full-corpus-snapshot  # bulk indexes
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import sys
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

MW_REST = "https://www.metabolomicsworkbench.org/rest/study/study_id/{sid}/{scope}"
OUT_DIR = Path("data/live")

# Curated real, public studies. Roles are documentation only; the skills decide
# the actual classification from the fetched evidence.
CURATED = [
    "ST004303",  # Human, exercise intensity plasma secretome (Rockefeller)
    "ST003807",  # Human, HIIT + metformin lipidomics (CEU San Pablo)
    "ST002916",  # MoTrPAC rat endurance training, heart (expected animal-exclusion)
]

# Human MoTrPAC note: the human arm of MoTrPAC is published via the MoTrPAC
# DataHub (motrpac-data.org) and is largely access-controlled / not exposed as a
# clean public REST feed. MW hosts only the rat ("PASS1B") metabolomics. We pull
# the rat study as the MoTrPAC representative and flag the human arm as an
# enrichment/availability gap rather than fabricating a record for it.

TIMEOUT = 30

FULL_CORPUS_FLAG = "--full-corpus-snapshot"


def fetch(sid: str, scope: str):
    url = MW_REST.format(sid=sid, scope=scope)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        return (json.loads(raw) if raw.strip() else None), url
    except Exception as exc:  # noqa: BLE001 - record the failure as evidence
        return {"_error": str(exc)}, url


def _rows(payload):
    """MW returns either a single dict or a dict-of-numbered-dicts."""
    if not payload or "_error" in payload:
        return []
    if all(isinstance(v, dict) for v in payload.values()):
        return list(payload.values())
    return [payload]


def _required_rows(study_id: str, scope: str) -> tuple[list[dict], str]:
    payload, url = fetch(study_id, scope)
    if not payload or (isinstance(payload, dict) and "_error" in payload):
        raise RuntimeError(f"Could not fetch {scope} for {study_id}: {payload}")
    return _rows(payload), url


def _deduplicate(rows: list[dict], key: str) -> tuple[list[dict], int]:
    """Keep the first source row for a stable identifier and count duplicates."""

    output: list[dict] = []
    seen: set[str] = set()
    duplicate_count = 0
    for row in rows:
        value = str(row.get(key) or "").strip()
        if not value:
            output.append(row)
            continue
        if value in seen:
            duplicate_count += 1
            continue
        seen.add(value)
        output.append(row)
    return output, duplicate_count


def _write_json(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _all_columns(rows: list[dict], preferred: list[str]) -> list[str]:
    observed = {str(key) for row in rows for key in row}
    return [key for key in preferred if key in observed] + sorted(observed - set(preferred))


def _assay_label(analysis: dict, untargeted_ids: set[str]) -> tuple[str, str]:
    analysis_id = str(analysis.get("analysis_id") or "").strip()
    if analysis_id in untargeted_ids:
        return "explicit_untargeted", "Metabolomics Workbench untarg_studies index"

    text = " ".join(
        str(value or "")
        for value in (
            analysis.get("analysis_summary"),
            analysis.get("analysis_display"),
            analysis.get("analysis_type"),
        )
    ).lower()
    if re.search(r"\buntargeted\b|\bun-targeted\b|\bnon-targeted\b", text):
        return "explicit_untargeted", "analysis text label"
    if re.search(r"\btargeted\b", text):
        return "explicit_targeted", "analysis text label; lower bound"
    return "unclassified_or_other", "no explicit targeted/untargeted label"


def fetch_full_corpus_snapshot(out_dir: Path) -> None:
    """Freeze the bulk MW indexes needed for a denominator-safe landscape report.

    This deliberately does not fetch one metabolite table per study. The bulk
    ``number_of_metabolites`` endpoint supplies analysis-level feature counts, while
    the repository's RefMet snapshot remains a separate reference vocabulary.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    retrieval_time = datetime.now(UTC).replace(microsecond=0).isoformat()

    raw_species_rows, species_url = _required_rows("ST", "species")
    numeric_ids = [
        int(match.group(1))
        for row in raw_species_rows
        if (match := re.fullmatch(r"ST(\d{6})", str(row.get("Study ID") or "")))
    ]
    if not numeric_ids:
        raise RuntimeError("The species index did not contain any valid MW study identifiers")
    prefixes = [f"ST{index:03d}" for index in range(max(numeric_ids) // 1000 + 1)]

    source_urls: dict[str, list[str] | str] = {"species": species_url}
    bulk: dict[str, list[dict]] = {
        "summaries": [],
        "analyses": [],
        "analysis_metabolite_counts": [],
    }
    for scope, key in (
        ("summary", "summaries"),
        ("analysis", "analyses"),
        ("number_of_metabolites", "analysis_metabolite_counts"),
    ):
        urls: list[str] = []
        for prefix in prefixes:
            rows, url = _required_rows(prefix, scope)
            bulk[key].extend(rows)
            urls.append(url)
            print(f"[fetch] {scope:<22} {prefix}: {len(rows)} rows", flush=True)
        source_urls[scope] = urls

    untargeted_rows, untargeted_url = _required_rows("X", "untarg_studies")
    source_urls["untarg_studies"] = untargeted_url

    summary_rows, duplicate_summaries = _deduplicate(bulk["summaries"], "study_id")
    analysis_rows, duplicate_analyses = _deduplicate(bulk["analyses"], "analysis_id")
    count_rows, duplicate_counts = _deduplicate(bulk["analysis_metabolite_counts"], "analysis_id")
    untargeted_rows, duplicate_untargeted = _deduplicate(untargeted_rows, "analysis_id")
    species_rows: list[dict] = []
    seen_species_pairs: set[tuple[str, str]] = set()
    duplicate_species_pairs = 0
    for row in raw_species_rows:
        pair = (str(row.get("Study ID") or ""), str(row.get("Latin name") or ""))
        if pair in seen_species_pairs:
            duplicate_species_pairs += 1
            continue
        seen_species_pairs.add(pair)
        species_rows.append(row)
    summary_rows.sort(key=lambda row: str(row.get("study_id") or ""))
    analysis_rows.sort(key=lambda row: str(row.get("analysis_id") or ""))
    count_rows.sort(key=lambda row: str(row.get("analysis_id") or ""))
    untargeted_rows.sort(key=lambda row: str(row.get("analysis_id") or ""))
    species_rows.sort(
        key=lambda row: (str(row.get("Study ID") or ""), str(row.get("Latin name") or ""))
    )

    summary_by_study = {
        str(row.get("study_id") or ""): row for row in summary_rows if row.get("study_id")
    }
    untargeted_ids = {
        str(row.get("analysis_id") or "").strip()
        for row in untargeted_rows
        if row.get("analysis_id")
    }
    classified_analyses: list[dict] = []
    study_assay_labels: dict[str, set[str]] = {}
    analysis_count_by_study: Counter[str] = Counter()
    for row in analysis_rows:
        study_id = str(row.get("study_id") or "").strip()
        label, basis = _assay_label(row, untargeted_ids)
        annotated = dict(row)
        annotated["assay_scope"] = label
        annotated["assay_scope_basis"] = basis
        classified_analyses.append(annotated)
        study_assay_labels.setdefault(study_id, set()).add(label)
        analysis_count_by_study[study_id] += 1

    study_assay_rows: list[dict] = []
    for study_id in sorted(summary_by_study):
        labels = study_assay_labels.get(study_id, set())
        has_targeted = "explicit_targeted" in labels
        has_untargeted = "explicit_untargeted" in labels
        if has_targeted and has_untargeted:
            category = "both_explicit"
        elif has_targeted:
            category = "targeted_explicit_only"
        elif has_untargeted:
            category = "untargeted_explicit_only"
        else:
            category = "neither_explicit_or_no_analysis"
        study_assay_rows.append(
            {
                "study_id": study_id,
                "has_explicit_targeted_analysis": has_targeted,
                "has_explicit_untargeted_analysis": has_untargeted,
                "study_assay_category": category,
                "analysis_count": analysis_count_by_study[study_id],
            }
        )

    species_studies: dict[str, set[str]] = {}
    species_common_names: dict[str, set[str]] = {}
    species_by_study: dict[str, set[str]] = {}
    for row in species_rows:
        study_id = str(row.get("Study ID") or "").strip()
        latin = str(row.get("Latin name") or "unknown").strip() or "unknown"
        common = str(row.get("Common name") or "unknown").strip() or "unknown"
        species_studies.setdefault(latin, set()).add(study_id)
        species_common_names.setdefault(latin, set()).add(common)
        species_by_study.setdefault(study_id, set()).add(latin)
    species_distribution = [
        {
            "latin_name": latin,
            "common_names": "; ".join(sorted(species_common_names[latin])),
            "study_count": len(study_ids),
            "percent_of_species_annotated_studies": round(
                100 * len(study_ids) / max(len(species_by_study), 1), 4
            ),
        }
        for latin, study_ids in species_studies.items()
    ]
    species_distribution.sort(key=lambda row: (-int(row["study_count"]), row["latin_name"]))

    analysis_scope_counts = Counter(row["assay_scope"] for row in classified_analyses)
    study_category_counts = Counter(row["study_assay_category"] for row in study_assay_rows)
    numeric_metabolite_counts = [
        int(str(row.get("num_metabolites") or "0"))
        for row in count_rows
        if str(row.get("num_metabolites") or "").strip().isdigit()
    ]
    summary_study_ids = set(summary_by_study)
    species_study_ids = set(species_by_study)

    raw_files = {
        "study_summaries.json": summary_rows,
        "study_species.json": species_rows,
        "analyses.json": analysis_rows,
        "analysis_metabolite_counts.json": count_rows,
        "untargeted_analyses.json": untargeted_rows,
    }
    written: list[Path] = []
    for filename, payload in raw_files.items():
        written.append(_write_json(out_dir / filename, payload))

    csv_outputs = (
        (
            "study_summaries.csv",
            summary_rows,
            ["study_id", "study_title", "species", "analysis_type", "number_of_samples", "submission_date", "release_date", "institute"],
        ),
        (
            "study_species.csv",
            species_rows,
            ["Study ID", "Latin name", "Common name"],
        ),
        (
            "analyses.csv",
            classified_analyses,
            ["study_id", "analysis_id", "analysis_summary", "analysis_type", "chromatography_type", "ms_instrument_type", "ion_mode", "units", "assay_scope", "assay_scope_basis"],
        ),
        (
            "analysis_metabolite_counts.csv",
            count_rows,
            ["study_id", "analysis_id", "num_metabolites", "num_samples", "analysis_type", "study_title"],
        ),
        (
            "untargeted_analyses.csv",
            untargeted_rows,
            ["study_id", "analysis_id", "analysis_display", "study_title", "subject_species", "institute"],
        ),
        (
            "species_distribution.csv",
            species_distribution,
            ["latin_name", "common_names", "study_count", "percent_of_species_annotated_studies"],
        ),
        (
            "study_assay_scope.csv",
            study_assay_rows,
            ["study_id", "has_explicit_targeted_analysis", "has_explicit_untargeted_analysis", "study_assay_category", "analysis_count"],
        ),
    )
    for filename, rows, preferred in csv_outputs:
        path = out_dir / filename
        write_csv(path, rows, _all_columns(rows, preferred))
        written.append(path)

    corpus_summary = {
        "schema_version": "mw-corpus-snapshot-1.0",
        "retrieved_at_utc": retrieval_time,
        "scope": "Metabolomics Workbench bulk public REST indexes",
        "study_count": len(summary_rows),
        "study_summary_duplicate_rows_removed": duplicate_summaries,
        "species_source_row_count": len(raw_species_rows),
        "species_unique_study_latin_name_pair_count": len(species_rows),
        "species_duplicate_pair_rows_removed": duplicate_species_pairs,
        "species_annotated_study_count": len(species_by_study),
        "species_missing_study_count": len(summary_study_ids - species_study_ids),
        "species_index_only_study_count": len(species_study_ids - summary_study_ids),
        "single_species_study_count": sum(len(values) == 1 for values in species_by_study.values()),
        "multi_species_study_count": sum(len(values) > 1 for values in species_by_study.values()),
        "distinct_latin_name_count": len(species_studies),
        "analysis_count": len(analysis_rows),
        "analysis_duplicate_rows_removed": duplicate_analyses,
        "analysis_scope_counts": dict(sorted(analysis_scope_counts.items())),
        "study_assay_category_counts": dict(sorted(study_category_counts.items())),
        "explicit_untargeted_index_analysis_count": len(untargeted_rows),
        "explicit_untargeted_index_study_count": len(
            {str(row.get("study_id") or "") for row in untargeted_rows}
        ),
        "untargeted_duplicate_rows_removed": duplicate_untargeted,
        "analysis_metabolite_count_rows": len(count_rows),
        "analysis_metabolite_count_duplicate_rows_removed": duplicate_counts,
        "analysis_metabolite_numeric_count_rows": len(numeric_metabolite_counts),
        "analysis_metabolite_blank_count_rows": len(count_rows) - len(numeric_metabolite_counts),
        "analyses_without_metabolite_count_record": len(analysis_rows) - len(count_rows),
        "analysis_feature_row_sum": sum(numeric_metabolite_counts),
        "analysis_feature_count_median": (
            statistics.median(numeric_metabolite_counts) if numeric_metabolite_counts else None
        ),
        "analysis_feature_count_minimum": min(numeric_metabolite_counts)
        if numeric_metabolite_counts
        else None,
        "analysis_feature_count_maximum": max(numeric_metabolite_counts)
        if numeric_metabolite_counts
        else None,
        "interpretation": {
            "targeted": "Explicit text-labelled targeted count is a lower bound; MW exposes no parallel targeted-only bulk index.",
            "untargeted": "Untargeted counts use the dedicated MW untarg_studies index; analysis-text checks do not replace that index.",
            "feature_rows": "The sum is analysis-level reported feature rows, not unique chemical entities.",
            "species": "Species percentages may sum above 100% because a study can list multiple organisms.",
        },
        "source_urls": source_urls,
    }
    summary_path = _write_json(out_dir / "corpus_summary.json", corpus_summary)
    written.append(summary_path)
    manifest = {
        "schema_version": "mw-corpus-snapshot-manifest-1.0",
        "retrieved_at_utc": retrieval_time,
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in sorted(written)
        },
        "notes": [
            "Additional source rows sharing a stable study_id or analysis_id are counted and removed; content identity is not assumed.",
            "No per-study quantitative matrix was fetched.",
            "RefMet taxonomy is intentionally not folded into this corpus snapshot.",
        ],
    }
    _write_json(out_dir / "manifest.json", manifest)
    print(f"[ok] full corpus snapshot -> {out_dir}")
    print(json.dumps(corpus_summary, indent=2, sort_keys=True))


def derive_record(sid: str):
    summary, summ_url = fetch(sid, "summary")
    factors, fact_url = fetch(sid, "factors")
    analysis, anal_url = fetch(sid, "analysis")

    if not summary or "_error" in summary:
        raise RuntimeError(f"Could not fetch summary for {sid}: {summary}")

    title = summary.get("study_title", "unknown")
    species = (summary.get("species") or "").strip()
    is_human = species.lower() == "homo sapiens"
    n_samples = int((summary.get("number_of_samples") or "0").split()[0] or 0)

    # --- sample-level evidence from factors ---
    frows = _rows(factors)
    sources, times, treatments, subjects, has_raw = Counter(), set(), set(), set(), False
    for fr in frows:
        src = (fr.get("sample_source") or "").strip()
        if src and not src.startswith("_"):
            sources[src] += 1
        if (fr.get("raw_data") or "").strip():
            has_raw = True
        for part in (fr.get("factors") or "").split("|"):
            part = part.strip()
            if part.lower().startswith("time:"):
                v = part.split(":", 1)[1].strip()
                if v.lower() not in ("blank", "qc", ""):
                    times.add(v)
            elif part.lower().startswith("treatment:"):
                v = part.split(":", 1)[1].strip()
                if v.lower() not in ("blank", "qc", ""):
                    treatments.add(v)
            elif part.lower().startswith("subject:"):
                v = part.split(":", 1)[1].strip()
                if v.lower() not in ("blank", "qc", ""):
                    subjects.add(v)

    sample_matrix = sources.most_common(1)[0][0].lower() if sources else "unknown"
    sample_size = len(subjects) if subjects else n_samples

    timing_bits = []
    if treatments:
        timing_bits.append("arms: " + ", ".join(sorted(treatments)))
    if times:
        timing_bits.append("timepoints: " + ", ".join(sorted(times)))
    biospecimen_timing = "; ".join(timing_bits) or "unknown"

    # --- platform from analysis ---
    arows = _rows(analysis)
    plat_bits = []
    for ar in arows[:1]:
        for key in ("chromatography_type", "analysis_type", "ms_instrument_type"):
            val = (ar.get(key) or "").strip()
            if val:
                plat_bits.append(val)
    assay_platform = (" ".join(plat_bits) + (f" {sample_matrix}" if sample_matrix != "unknown" else "")).strip() or summary.get("analysis_type", "unknown")

    # has_codebook: MW exposes a structured factor table -> treat presence of
    # >=1 real factor dimension as a partial codebook; else False (scientific gap).
    has_codebook = bool(times or treatments or subjects)

    # --- modality flags (honest keyword inference from title) ---
    t = title.lower()
    exercise = any(k in t for k in ("exercise", "training", "interval", "hiit", "cycling", "endurance", "aerobic", "resistance"))
    cpet = any(k in t for k in ("vo2", "cpet", "cardiopulmonary", "ergometer"))
    diet = any(k in t for k in ("diet", "nutrition", "fasting", "caloric", "metformin"))
    body_comp = any(k in t for k in ("body composition", "adipos", "fat mass", "lean mass"))
    genetics = any(k in t for k in ("genotype", "genetic", "genom", "snp", "gwas"))
    actigraphy = any(k in t for k in ("actigraph", "accelerometer", "wearable"))

    modalities = ["metabolomics"]
    for flag, name in [(exercise, "exercise"), (actigraphy, "actigraphy"), (genetics, "genetics"),
                       (cpet, "cpet"), (body_comp, "body_composition"), (diet, "diet")]:
        if flag:
            modalities.append(name)

    repo_record = {
        "study_id": sid,
        "repository": "Metabolomics Workbench",
        "accession": sid,
        "public_status": "public",
        "has_metadata": "true",
        "has_codebook": "true" if has_codebook else "false",
        "has_data_files": "true" if has_raw else "false",
        "assay_platform": assay_platform,
        "sample_matrix": sample_matrix,
        "biospecimen_timing": biospecimen_timing,
        "sample_size": sample_size,
        "modalities": ";".join(modalities),
    }

    pub_record = {
        "study_id": sid,
        "title": title,
        "doi": "",
        "pmid": "",
        "human": "true" if is_human else "false",
        "exercise": "true" if exercise else "false",
        "actigraphy": "true" if actigraphy else "false",
        "metabolomics": "true",
        "genetics": "true" if genetics else "false",
        "cpet": "true" if cpet else "false",
        "body_composition": "true" if body_comp else "false",
        "diet": "true" if diet else "false",
        "repository_accession": sid,
        "notes": f"Live MW record. Species={species or 'unknown'}. {summary.get('institute','')}.".strip(),
    }

    provenance = {
        "study_id": sid,
        "sources": {"summary": summ_url, "factors": fact_url, "analysis": anal_url},
        "release_date": summary.get("release_date"),
        "license": summary.get("license"),
        "study_url": summary.get("study_url"),
    }
    return repo_record, pub_record, provenance


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    import csv
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def main(argv: list[str]) -> None:
    if argv and argv[0] == FULL_CORPUS_FLAG:
        if len(argv) > 2:
            raise SystemExit(
                f"usage: {Path(sys.argv[0]).name} {FULL_CORPUS_FLAG} [output_directory]"
            )
        snapshot_dir = Path(argv[1]) if len(argv) == 2 else OUT_DIR / "mw_corpus_snapshot"
        fetch_full_corpus_snapshot(snapshot_dir)
        return

    sids = argv or CURATED
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    repo_rows, pub_rows, prov = [], [], []
    for sid in sids:
        print(f"[fetch] {sid} ...", flush=True)
        rr, pr, pv = derive_record(sid)
        repo_rows.append(rr)
        pub_rows.append(pr)
        prov.append(pv)
        print(f"        title={pr['title'][:70]!r} human={pr['human']} modalities={rr['modalities']}", flush=True)

    write_csv(OUT_DIR / "repository_records.csv", repo_rows, [
        "study_id", "repository", "accession", "public_status", "has_metadata",
        "has_codebook", "has_data_files", "assay_platform", "sample_matrix",
        "biospecimen_timing", "sample_size", "modalities",
    ])
    write_csv(OUT_DIR / "publications.csv", pub_rows, [
        "study_id", "title", "doi", "pmid", "human", "exercise", "actigraphy",
        "metabolomics", "genetics", "cpet", "body_composition", "diet",
        "repository_accession", "notes",
    ])
    (OUT_DIR / "provenance.json").write_text(json.dumps(prov, indent=2))
    print(f"\n[ok] wrote {len(repo_rows)} records -> {OUT_DIR}/repository_records.csv")
    print(f"[ok] wrote {len(pub_rows)} publications -> {OUT_DIR}/publications.csv")
    print(f"[ok] provenance -> {OUT_DIR}/provenance.json")


if __name__ == "__main__":
    main(sys.argv[1:])

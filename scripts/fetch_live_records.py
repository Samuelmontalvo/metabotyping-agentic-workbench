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
"""
from __future__ import annotations

import json
import sys
import urllib.request
from collections import Counter
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

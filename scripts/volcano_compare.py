#!/usr/bin/env python3
"""Side-by-side volcano comparison: MW human exercise study vs MoTrPAC.

LEFT  : Metabolomics Workbench ST004303 (human plasma, acute exercise).
        Contrast = post vs pre (Time 4P vs 1P), paired within subject, both
        intensity arms (MIE + SIE) pooled. We compute log2 fold-change and a
        paired t-test p-value per named metabolite from the raw abundance matrix.
RIGHT : MoTrPAC HUMAN (human-precovid-sed-adu) plasma acute-exercise differential
        metabolomics, downloaded from the MoTrPAC DataHub via signed URLs (the
        externally-released v1.3 "da" tables across 6 untargeted + 5 targeted
        metabolomics platforms). Contrast = endurance, late post (3.5-4 hr) vs
        pre-exercise. logFC / p_value are the consortium's precomputed DREAM-model
        differential stats.

Both panels are therefore HUMAN PLASMA acute-exercise post-vs-pre comparisons.

This is the only networked entry point for this analysis (Live Ingestion Mode):
network is confined here, outputs land in data/live/ and reports_live/, and
provenance is recorded. The offline pilot is untouched.

CAVEATS (also stamped on the figure): different cohorts, platforms and statistical
models. Human ST004303 units are arbitrary MS intensities with a paired t-test we
compute here; MoTrPAC stats are mixed-model (DREAM) logFC/p from targeted+untargeted
panels. A rat-training comparison (pass1b06) remains available via --source rat.

Usage:
    .venv/bin/python scripts/volcano_compare.py              # human vs human (default)
    .venv/bin/python scripts/volcano_compare.py --source rat # human vs MoTrPAC rat training
"""
from __future__ import annotations

import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

MW_REST = "https://www.metabolomicsworkbench.org/rest/study/study_id/{sid}/{scope}"
MOTRPAC_SEARCH = "https://search.motrpac-data.org/api/search_public"
MOTRPAC_SIGNEDURL = "https://services.motrpac-data.org/v1/signedurl"
MOTRPAC_BUCKET = "motrpac-data-hub"
# Public API-gateway key baked into the DataHub web app (not a secret).
MOTRPAC_KEY = "AIzaSyBwfwfqDmVq6PG7BTlv7bPFOsbngGP7BN8"

HUMAN_SID = "ST004303"
HUMAN_PRE, HUMAN_POST = "1P", "4P"           # pre / post timepoints

# MoTrPAC HUMAN plasma (T02) acute-exercise differential-analysis tables (released v1.3).
MOTRPAC_HUMAN_OBJECTS = [
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/human-precovid-sed-adu_t02-plasma_metab-t-amines_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/human-precovid-sed-adu_t02-plasma_metab-t-conv_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/human-precovid-sed-adu_t02-plasma_metab-t-imm-crt_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/human-precovid-sed-adu_t02-plasma_metab-t-oxylipneg_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-targeted/da/human-precovid-sed-adu_t02-plasma_metab-t-tca_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/human-precovid-sed-adu_t02-plasma_metab-u-hilicpos_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/human-precovid-sed-adu_t02-plasma_metab-u-ionpneg_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/human-precovid-sed-adu_t02-plasma_metab-u-lrpneg_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/human-precovid-sed-adu_t02-plasma_metab-u-lrppos_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/human-precovid-sed-adu_t02-plasma_metab-u-rpneg_da_dream-acute_v1.3.txt",
    "analysis/human-precovid-sed-adu/v1.3/metabolomics-untargeted/da/human-precovid-sed-adu_t02-plasma_metab-u-rppos_da_dream-acute_v1.3.txt",
]
# Acute-exercise contrast: endurance, late post (3.5-4 hr) vs pre (matches MW late timepoint).
MOTRPAC_HUMAN_CONTRAST = "group_timepointADUEndur.post_3.5_4_hr - group_timepointADUEndur.pre_exercise"

# Rat-training fallback (--source rat)
MOTRPAC_RAT_STUDY = "pass1b06"
MOTRPAC_RAT_TISSUE = "plasma"
MOTRPAC_RAT_GROUP = "8w"

P_THRESH = 0.05
LOG2FC_THRESH = 1.0
TOP_N_LABELS = 8
TIMEOUT = 90

OUT_DATA = Path("data/live")
OUT_REPORTS = Path("reports_live")
PROVENANCE = []


# --------------------------------------------------------------------------- #
# HTTP helpers (mirrors scripts/fetch_live_records.py style)
# --------------------------------------------------------------------------- #
def _get(url: str):
    PROVENANCE.append({"method": "GET", "url": url})
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, payload: dict):
    PROVENANCE.append({"method": "POST", "url": url, "body": payload})
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _signed_url(obj: str) -> str:
    """Resolve a MoTrPAC DataHub object path to a temporary signed download URL."""
    url = (f"{MOTRPAC_SIGNEDURL}?bucket={MOTRPAC_BUCKET}"
           f"&object={urllib.parse.quote(obj)}&key={MOTRPAC_KEY}")
    PROVENANCE.append({"method": "GET", "url": f"{MOTRPAC_SIGNEDURL}?bucket={MOTRPAC_BUCKET}&object={obj}&key=<key>"})
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))["url"]


def _bh_fdr(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg FDR. NaN-safe."""
    p = np.asarray(pvals, dtype=float)
    out = np.full_like(p, np.nan)
    mask = ~np.isnan(p)
    pm = p[mask]
    n = pm.size
    if n == 0:
        return out
    order = np.argsort(pm)
    ranked = pm[order]
    adj = ranked * n / (np.arange(n) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    res = np.empty(n)
    res[order] = adj
    out[mask] = res
    return out


# --------------------------------------------------------------------------- #
# Human side — compute volcano from raw MW abundance matrix
# --------------------------------------------------------------------------- #
def _parse_factors(factors_json: dict) -> dict:
    """sample_name -> {Subject, Treatment, Time, source}."""
    meta = {}
    for v in factors_json.values():
        name = v.get("local_sample_id")
        parts = {}
        for chunk in (v.get("factors") or "").split("|"):
            chunk = chunk.strip()
            if ":" in chunk:
                k, val = chunk.split(":", 1)
                parts[k.strip()] = val.strip()
        meta[name] = {
            "subject": parts.get("Subject", ""),
            "treatment": parts.get("Treatment", ""),
            "time": parts.get("Time", ""),
            "source": (v.get("sample_source") or "").strip(),
        }
    return meta


def compute_human_volcano() -> pd.DataFrame:
    print(f"[human] fetching MW {HUMAN_SID} data + factors ...")
    data_json = _get(MW_REST.format(sid=HUMAN_SID, scope="data"))
    factors_json = _get(MW_REST.format(sid=HUMAN_SID, scope="factors"))
    meta = _parse_factors(factors_json)

    # Long -> wide: rows = metabolite, cols = sample
    records = {}
    refmet = {}
    for entry in data_json.values():
        name = entry.get("metabolite_name")
        refmet[name] = entry.get("refmet_name") or name
        vals = {}
        for sample, raw in (entry.get("DATA") or {}).items():
            try:
                vals[sample] = float(raw)
            except (TypeError, ValueError):
                vals[sample] = np.nan
        records[name] = vals
    mat = pd.DataFrame(records).T  # metabolite x sample

    # Assign samples to pre/post (real biospecimen samples only)
    pre_by_subj, post_by_subj = {}, {}
    for sample, m in meta.items():
        if m["source"].lower() != "blood":
            continue
        if m["time"] == HUMAN_PRE:
            pre_by_subj[m["subject"]] = sample
        elif m["time"] == HUMAN_POST:
            post_by_subj[m["subject"]] = sample
    paired_subjects = sorted(set(pre_by_subj) & set(post_by_subj))
    pre_samples = [pre_by_subj[s] for s in paired_subjects]
    post_samples = [post_by_subj[s] for s in paired_subjects]
    print(f"[human] paired subjects (post {HUMAN_POST} vs pre {HUMAN_PRE}): {len(paired_subjects)}")

    rows = []
    for met in mat.index:
        pre = mat.loc[met, pre_samples].astype(float).to_numpy()
        post = mat.loc[met, post_samples].astype(float).to_numpy()
        ok = ~np.isnan(pre) & ~np.isnan(post) & (pre > 0) & (post > 0)
        if ok.sum() < 3:
            continue
        lpre, lpost = np.log2(pre[ok]), np.log2(post[ok])
        log2fc = float(np.mean(lpost - lpre))
        try:
            _, pval = stats.ttest_rel(lpost, lpre)
        except Exception:
            pval = np.nan
        rows.append((met, refmet.get(met, met), log2fc, float(pval)))

    df = pd.DataFrame(rows, columns=["metabolite", "refmet_name", "log2fc", "p_value"])
    df["fdr"] = _bh_fdr(df["p_value"].to_numpy())
    df["neg_log10_p"] = -np.log10(df["p_value"].replace(0, np.nan))
    print(f"[human] metabolites with usable paired data: {len(df)}")
    return df


# --------------------------------------------------------------------------- #
# MoTrPAC side — fetch precomputed differential stats (pluggable)
# --------------------------------------------------------------------------- #
def fetch_motrpac_human_volcano() -> pd.DataFrame:
    """MoTrPAC HUMAN plasma acute-exercise DA: download released v1.3 da tables
    across all metabolomics platforms, keep the endurance late-post vs pre contrast."""
    print(f"[motrpac-human] downloading {len(MOTRPAC_HUMAN_OBJECTS)} plasma DA tables via signed URLs ...")
    frames = []
    for obj in MOTRPAC_HUMAN_OBJECTS:
        platform = obj.split("_t02-plasma_")[1].split("_da")[0]  # e.g. metab-u-rppos
        url = _signed_url(obj)
        df = pd.read_csv(url, sep="\t")
        df = df[df["contrast"] == MOTRPAC_HUMAN_CONTRAST].copy()
        df["platform"] = platform
        frames.append(df)
        print(f"    {platform:18} features={len(df)}")
    allp = pd.concat(frames, ignore_index=True)
    for col in ("logFC", "p_value", "adj_p_value"):
        allp[col] = pd.to_numeric(allp[col], errors="coerce")
    # feature_id can repeat across platforms; disambiguate by appending platform suffix.
    label = allp["feature_id"].astype(str)
    out = pd.DataFrame({
        "metabolite": (label + " [" + allp["platform"] + "]").to_numpy(),
        "refmet_name": label.to_numpy(),
        "log2fc": allp["logFC"].to_numpy(),
        "p_value": allp["p_value"].to_numpy(),
        "fdr": allp["adj_p_value"].to_numpy(),
        "platform": allp["platform"].to_numpy(),
    })
    out["neg_log10_p"] = -np.log10(out["p_value"].replace(0, np.nan))
    out = out.dropna(subset=["log2fc", "p_value"]).reset_index(drop=True)
    print(f"[motrpac-human] features (endurance post 3.5-4hr vs pre): {len(out)}")
    return out


def fetch_motrpac_rat_volcano(tissue: str = MOTRPAC_RAT_TISSUE, group: str = MOTRPAC_RAT_GROUP) -> pd.DataFrame:
    print(f"[motrpac-rat] querying search_public study={MOTRPAC_RAT_STUDY} omics=metabolomics ...")
    resp = _post(MOTRPAC_SEARCH, {"study": MOTRPAC_RAT_STUDY, "omics": "metabolomics", "size": 100000})
    blk = resp["result"]["metabolomics_timewise"]
    df = pd.DataFrame(blk["data"], columns=blk["headers"])
    df = df[(df["tissue"] == tissue) & (df["comparison_group"] == group)].copy()
    for col in ("logFC", "p_value", "adj_p_value"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    name = df["refmet_name"].where(df["refmet_name"].astype(str).str.len() > 0, df["metabolite"])
    out = pd.DataFrame({
        "metabolite": df["metabolite"].to_numpy(),
        "refmet_name": name.to_numpy(),
        "log2fc": df["logFC"].to_numpy(),
        "p_value": df["p_value"].to_numpy(),
        "fdr": df["adj_p_value"].to_numpy(),
    })
    out["neg_log10_p"] = -np.log10(out["p_value"].replace(0, np.nan))
    out = out.dropna(subset=["log2fc", "p_value"]).reset_index(drop=True)
    print(f"[motrpac-rat] {tissue} / {group} differential rows: {len(out)}")
    return out


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def _draw(ax, df, title):
    x = df["log2fc"].to_numpy()
    y = df["neg_log10_p"].to_numpy()
    sig = (df["p_value"] < P_THRESH) & (df["log2fc"].abs() > LOG2FC_THRESH)
    up = sig & (df["log2fc"] > 0)
    down = sig & (df["log2fc"] < 0)
    ns = ~sig

    ax.scatter(x[ns], y[ns], s=10, c="#b8b8b8", alpha=0.5, linewidths=0, label="ns")
    ax.scatter(x[up], y[up], s=14, c="#d62728", alpha=0.8, linewidths=0, label="up")
    ax.scatter(x[down], y[down], s=14, c="#1f77b4", alpha=0.8, linewidths=0, label="down")

    ax.axhline(-math.log10(P_THRESH), ls="--", lw=0.8, c="grey")
    ax.axvline(LOG2FC_THRESH, ls="--", lw=0.8, c="grey")
    ax.axvline(-LOG2FC_THRESH, ls="--", lw=0.8, c="grey")

    # label top hits by significance among the significant set
    labelled = df[sig].nlargest(TOP_N_LABELS, "neg_log10_p")
    for _, r in labelled.iterrows():
        txt = str(r["refmet_name"])[:22]
        ax.annotate(txt, (r["log2fc"], r["neg_log10_p"]), fontsize=6,
                    xytext=(3, 3), textcoords="offset points", color="#333")

    ax.set_title(title, fontsize=10)
    ax.set_xlabel("log2 fold-change")
    ax.set_ylabel("-log10 p-value")
    ax.legend(fontsize=7, loc="upper right", framealpha=0.6)
    n_sig = int(sig.sum())
    ax.text(0.02, 0.97, f"n={len(df)} | sig={n_sig}", transform=ax.transAxes,
            fontsize=7, va="top", color="#444")


def plot_side_by_side(human_df, motrpac_df, path_png: Path, right_title: str, suptitle: str, caption: str):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    _draw(axes[0], human_df,
          f"MW {HUMAN_SID} — human plasma\npost vs pre ({HUMAN_POST} vs {HUMAN_PRE}), paired, MIE+SIE")
    _draw(axes[1], motrpac_df, right_title)
    fig.suptitle(suptitle, fontsize=12, fontweight="bold")
    fig.text(0.5, 0.005, caption, ha="center", fontsize=7, color="#555", wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(path_png, dpi=150)
    fig.savefig(path_png.with_suffix(".svg"))
    print(f"[plot] wrote {path_png} (+ .svg)")


# --------------------------------------------------------------------------- #
# Metabolite-scan lane (single-metabolite cross-species evidence)
#
# Retrieval + effect extraction only. A name match is screening evidence, not
# MSI-level chemical identity, and absence of a feature is reported as a
# coverage gap rather than as a null effect.
# --------------------------------------------------------------------------- #
SCAN_OUT = Path("data/live/metabolite_scan")


def _norm_name(value) -> str:
    """Lowercase, strip punctuation/whitespace so 'N-Lactoyl phenylalanine',
    'N-lactoylphenylalanine' and 'Lac-Phe' style spellings collapse to one key."""
    text = str(value or "").lower()
    return "".join(ch for ch in text if ch.isalnum())


def _name_matches(value, keys: set[str]) -> bool:
    normalized = _norm_name(value)
    if not normalized:
        return False
    return any(key and (key == normalized or key in normalized) for key in keys)


def _mw_scan_sample_map(factors_json: dict) -> dict:
    """local_sample_id -> {participant, timepoint, sex, source} for pre/post designs.

    Handles the 'Collectionpoint:Before|After' + '<participant>_<Before|After>'
    convention used by ST003662; other conventions fall through as unknown and
    are reported rather than guessed.
    """
    meta = {}
    for entry in factors_json.values():
        name = entry.get("local_sample_id")
        parts = {}
        for chunk in (entry.get("factors") or "").split("|"):
            chunk = chunk.strip()
            if ":" in chunk:
                key, value = chunk.split(":", 1)
                parts[key.strip().lower()] = value.strip()
        collection = parts.get("collectionpoint", "")
        timepoint = {"before": "pre", "after": "post"}.get(collection.lower(), "")
        participant = ""
        if timepoint and "_" in str(name):
            participant = str(name).rsplit("_", 1)[0]
        meta[name] = {
            "participant": participant,
            "timepoint": timepoint,
            "collectionpoint": collection,
            "sex": parts.get("sex_participant", "") or "not_reported",
            "source": (entry.get("sample_source") or "").strip(),
        }
    return meta


def _mw_scan_matrix(data_json: dict):
    records, refmet = {}, {}
    for entry in data_json.values():
        name = entry.get("metabolite_name")
        refmet[name] = entry.get("refmet_name") or name
        values = {}
        for sample, raw in (entry.get("DATA") or {}).items():
            try:
                values[sample] = float(raw)
            except (TypeError, ValueError):
                values[sample] = np.nan
        records[name] = values
    return pd.DataFrame(records).T, refmet


def _paired_stats(matrix, metabolite, pre_samples, post_samples):
    pre = matrix.loc[metabolite, pre_samples].astype(float).to_numpy()
    post = matrix.loc[metabolite, post_samples].astype(float).to_numpy()
    ok = ~np.isnan(pre) & ~np.isnan(post) & (pre > 0) & (post > 0)
    if ok.sum() < 3:
        return None
    lpre, lpost = np.log2(pre[ok]), np.log2(post[ok])
    try:
        _, pval = stats.ttest_rel(lpost, lpre)
    except Exception:
        pval = np.nan
    return {
        "log2fc": float(np.mean(lpost - lpre)),
        "p_value": float(pval),
        "n_pairs": int(ok.sum()),
        "mean_pre": float(np.mean(pre[ok])),
        "mean_post": float(np.mean(post[ok])),
    }


def scan_mw_study(study_id: str, keys: set[str]):
    """Whole-metabolome pre/post volcano for one MW study, plus the queried rows."""
    print(f"[scan-mw] fetching MW {study_id} data + factors ...")
    data_json = _get(MW_REST.format(sid=study_id, scope="data"))
    factors_json = _get(MW_REST.format(sid=study_id, scope="factors"))
    summary = _get(MW_REST.format(sid=study_id, scope="summary"))
    matrix, refmet = _mw_scan_matrix(data_json)
    meta = _mw_scan_sample_map(factors_json)

    strata = {"all": None}
    sexes = sorted({m["sex"] for m in meta.values() if m["timepoint"] and m["sex"] in {"m", "f"}})
    for sex in sexes:
        strata[sex] = sex

    volcano_rows, queried_rows = [], []
    stratum_sizes = {}
    paired_samples_by_participant: dict[str, dict[str, str]] = {}
    for stratum, sex_filter in strata.items():
        pre_by, post_by = {}, {}
        for sample, m in meta.items():
            if not m["participant"] or (m["source"] or "").lower() not in {"blood", "plasma", "serum"}:
                continue
            if sex_filter is not None and m["sex"] != sex_filter:
                continue
            if m["timepoint"] == "pre":
                pre_by[m["participant"]] = sample
            elif m["timepoint"] == "post":
                post_by[m["participant"]] = sample
        paired = [pid for pid in sorted(set(pre_by) & set(post_by))
                  if pre_by[pid] in matrix.columns and post_by[pid] in matrix.columns]
        pre_samples = [pre_by[pid] for pid in paired]
        post_samples = [post_by[pid] for pid in paired]
        stratum_sizes[stratum] = len(paired)
        if stratum == "all":
            for pid in paired:
                paired_samples_by_participant[pid] = {
                    "pre": pre_by[pid],
                    "post": post_by[pid],
                    "sex": meta[post_by[pid]]["sex"],
                }
        print(f"[scan-mw]   stratum={stratum} paired participants={len(paired)}")
        if len(paired) < 3:
            continue
        rows = []
        for metabolite in matrix.index:
            result = _paired_stats(matrix, metabolite, pre_samples, post_samples)
            if result is None:
                continue
            rows.append({
                "study_id": study_id,
                "stratum": stratum,
                "metabolite": metabolite,
                "refmet_name": refmet.get(metabolite, metabolite),
                **result,
            })
        frame = pd.DataFrame(rows)
        frame["fdr"] = _bh_fdr(frame["p_value"].to_numpy())
        frame["neg_log10_p"] = -np.log10(frame["p_value"].replace(0, np.nan))
        volcano_rows.append(frame)
        hits = frame[frame.apply(
            lambda r: _name_matches(r["metabolite"], keys) or _name_matches(r["refmet_name"], keys), axis=1)]
        queried_rows.append(hits)

    volcano = pd.concat(volcano_rows, ignore_index=True) if volcano_rows else pd.DataFrame()
    queried = pd.concat(queried_rows, ignore_index=True) if queried_rows else pd.DataFrame()

    # Sample-level values for the queried metabolite only. The full abundance matrix is
    # never persisted; one metabolite is kept so individual pre/post responses can be
    # plotted without re-fetching, using the study's own de-identified sample codes.
    sample_rows = []
    queried_features = sorted({str(name) for name in queried.get("metabolite", pd.Series(dtype=str))})
    for feature in queried_features:
        for participant, samples in paired_samples_by_participant.items():
            pre_value = matrix.at[feature, samples["pre"]] if samples["pre"] in matrix.columns else np.nan
            post_value = matrix.at[feature, samples["post"]] if samples["post"] in matrix.columns else np.nan
            sample_rows.append({
                "study_id": study_id,
                "metabolite": feature,
                "refmet_name": refmet.get(feature, feature),
                "participant_code": participant,
                "sex": samples["sex"],
                "pre_sample": samples["pre"],
                "post_sample": samples["post"],
                "value_pre": pre_value,
                "value_post": post_value,
                "unit": "umol/L whole blood (study-reported)",
            })
    sample_level = pd.DataFrame(sample_rows)
    context = {
        "study_id": study_id,
        "study_title": summary.get("study_title", "") if isinstance(summary, dict) else "",
        "species": summary.get("species", "") if isinstance(summary, dict) else "",
        "license": summary.get("license", "") if isinstance(summary, dict) else "",
        "study_link": f"https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID={study_id}",
        "paired_participants_by_stratum": stratum_sizes,
        "features_measured": int(matrix.shape[0]),
        "queried_feature_hits": int(len(queried)),
        "contrast": "post-exercise vs pre-exercise (Collectionpoint After vs Before)",
        "statistic": "paired t-test on log2 abundance, BH-adjusted within stratum",
        "orientation": "positive log2fc = higher post-exercise",
    }
    return volcano, queried, sample_level, context


def scan_rat_pass1b06(keys: set[str]):
    """Full pass1b-06 metabolomics timewise table, scanned across all tissues/timepoints."""
    print("[scan-rat] querying search_public study=pass1b06 omics=metabolomics ...")
    resp = _post(MOTRPAC_SEARCH, {"study": MOTRPAC_RAT_STUDY, "omics": "metabolomics", "size": 200000})
    block = resp["result"]["metabolomics_timewise"]
    df = pd.DataFrame(block["data"], columns=block["headers"])
    for col in ("logFC", "p_value", "adj_p_value"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    name_cols = [c for c in ("refmet_name", "metabolite", "feature_id") if c in df.columns]
    mask = pd.Series(False, index=df.index)
    for col in name_cols:
        mask |= df[col].map(lambda v: _name_matches(v, keys))
    hits = df[mask].copy()
    coverage = {
        "study": MOTRPAC_RAT_STUDY,
        "omics": "metabolomics",
        "endpoint": MOTRPAC_SEARCH,
        "query": {"study": MOTRPAC_RAT_STUDY, "omics": "metabolomics", "size": 200000},
        "timewise_rows_returned": int(len(df)),
        "unique_features": int(df[name_cols[0]].nunique()) if name_cols else 0,
        "tissues": sorted({str(v) for v in df.get("tissue", pd.Series(dtype=str)).unique()}),
        "comparison_groups": sorted({str(v) for v in df.get("comparison_group", pd.Series(dtype=str)).unique()}),
        "assays": sorted({str(v) for v in df.get("assay", pd.Series(dtype=str)).unique()}),
        "name_columns_scanned": name_cols,
        "queried_feature_hits": int(len(hits)),
    }
    print(f"[scan-rat] timewise rows={len(df)} | queried-name hits={len(hits)}")
    return df, hits, coverage


def run_metabolite_scan(query: str, variants: list[str], mw_studies: list[str], skip_rat: bool = False):
    keys = {_norm_name(query)} | {_norm_name(v) for v in variants}
    keys = {k for k in keys if k}
    slug = "".join(ch if ch.isalnum() else "_" for ch in query.lower()).strip("_")
    out_dir = SCAN_OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    mw_contexts, mw_queried, mw_volcanoes = [], [], []
    for study_id in mw_studies:
        try:
            volcano, queried, sample_level, context = scan_mw_study(study_id, keys)
        except Exception as exc:  # network/parse failure is recorded, not hidden
            mw_contexts.append({"study_id": study_id, "error": str(exc)})
            continue
        mw_contexts.append(context)
        if not volcano.empty:
            volcano.to_csv(out_dir / f"mw_{study_id}_volcano_pre_post.csv", index=False)
            mw_volcanoes.append(volcano)
        if not queried.empty:
            mw_queried.append(queried)
        if not sample_level.empty:
            sample_level.to_csv(out_dir / f"mw_{study_id}_queried_sample_level.csv", index=False)
    if mw_queried:
        pd.concat(mw_queried, ignore_index=True).to_csv(out_dir / "mw_queried_metabolite_effects.csv", index=False)

    if skip_rat:
        # Explicitly recorded so a partial scan can never be mistaken for a rat coverage result.
        rat_coverage = {"skipped": True,
                        "reason": "--scan-skip-rat requested; rat coverage NOT assessed in this run"}
    else:
        rat_all, rat_hits, rat_coverage = scan_rat_pass1b06(keys)
        rat_all.to_csv(out_dir / "rat_pass1b06_metabolomics_timewise_all_rows.csv", index=False)
        if not rat_hits.empty:
            rat_hits.to_csv(out_dir / "rat_pass1b06_queried_metabolite_rows.csv", index=False)

    provenance = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "query_original": query,
        "name_variants_searched": variants,
        "normalized_match_keys": sorted(keys),
        "match_basis": "normalized name containment across source name columns",
        "review_status": "requires_human_review",
        "decision_scope": "retrieval_and_effect_extraction_only",
        "harmonization_eligibility": "requires_assay_identity_review",
        "mw_studies": mw_contexts,
        "rat_motrpac": rat_coverage,
        "coverage_gap_semantics": (
            "A queried metabolite absent from a source feature space is an availability/coverage "
            "gap. It is not evidence of a null effect and must not be replaced by a synthetic row."
        ),
        "requests": PROVENANCE,
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2))
    print(f"[scan] wrote {out_dir}")
    return provenance


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["human", "rat"], default="human",
                    help="MoTrPAC comparison side: human acute exercise (default) or rat training.")
    ap.add_argument("--metabolite-scan", default="",
                    help="Run the single-metabolite cross-species scan lane for this metabolite name "
                         "instead of the paired volcano figure.")
    ap.add_argument("--name-variants", default="",
                    help="Semicolon-separated additional spellings to match for --metabolite-scan.")
    ap.add_argument("--mw-studies", default="",
                    help="Comma-separated MW study IDs to scan for --metabolite-scan.")
    ap.add_argument("--scan-skip-rat", action="store_true",
                    help="Skip the rat pass1b-06 coverage scan (recorded as not assessed).")
    args = ap.parse_args()

    if args.metabolite_scan:
        variants = [v.strip() for v in args.name_variants.split(";") if v.strip()]
        studies = [s.strip().upper() for s in args.mw_studies.split(",") if s.strip()]
        if not studies:
            raise SystemExit("--metabolite-scan requires --mw-studies")
        run_metabolite_scan(args.metabolite_scan, variants, studies, skip_rat=args.scan_skip_rat)
        return

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_REPORTS.mkdir(parents=True, exist_ok=True)

    human = compute_human_volcano()

    if args.source == "human":
        motrpac = fetch_motrpac_human_volcano()
        right_title = "MoTrPAC HUMAN plasma (precovid-sed-adu)\nendurance, post 3.5-4hr vs pre"
        suptitle = "Acute-exercise plasma metabolome: MW ST004303 vs MoTrPAC human"
        caption = ("Both panels: HUMAN plasma, acute exercise, post vs pre. Different cohorts/platforms/"
                   "models — MW: paired t-test on arbitrary MS intensities (266 named metabolites); "
                   "MoTrPAC: DREAM mixed-model logFC/p across 6 untargeted + 5 targeted plasma panels. "
                   f"Significance: p<{P_THRESH} & |log2FC|>{LOG2FC_THRESH}.")
        motrpac_csv = OUT_DATA / "volcano_motrpac_human_plasma_endur_post.csv"
        label_right = "MoTrPAC human plasma endur post"
    else:
        motrpac = fetch_motrpac_rat_volcano()
        right_title = (f"MoTrPAC {MOTRPAC_RAT_STUDY} — RAT plasma\n"
                       f"{MOTRPAC_RAT_GROUP} training vs sedentary control")
        suptitle = "Exercise-response metabolome: MW human acute vs MoTrPAC rat training"
        caption = ("CAVEAT: cross-species (human acute exercise vs rat training adaptation). "
                   "MW: paired t-test on arbitrary MS intensities; MoTrPAC: consortium precomputed "
                   f"timewise stats. Significance: p<{P_THRESH} & |log2FC|>{LOG2FC_THRESH}. Not a replication.")
        motrpac_csv = OUT_DATA / f"volcano_motrpac_{MOTRPAC_RAT_STUDY}_{MOTRPAC_RAT_TISSUE}_{MOTRPAC_RAT_GROUP}.csv"
        label_right = f"MoTrPAC rat {MOTRPAC_RAT_GROUP}"

    human_csv = OUT_DATA / "volcano_human_ST004303.csv"
    human.sort_values("p_value").to_csv(human_csv, index=False)
    motrpac.sort_values("p_value").to_csv(motrpac_csv, index=False)
    print(f"[csv] {human_csv}\n[csv] {motrpac_csv}")

    png = OUT_REPORTS / (f"volcano_human_vs_motrpac_{args.source}.png")
    plot_side_by_side(human, motrpac, png, right_title, suptitle, caption)

    (OUT_DATA / "volcano_provenance.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_mode": args.source,
        "human_mw": {"study": HUMAN_SID, "contrast": f"{HUMAN_POST} vs {HUMAN_PRE}",
                     "stat": "paired t-test on log2 abundance", "n_metabolites": int(len(human))},
        "motrpac": {"mode": args.source, "n_metabolites": int(len(motrpac)),
                    "human_contrast": MOTRPAC_HUMAN_CONTRAST if args.source == "human" else None},
        "thresholds": {"p": P_THRESH, "abs_log2fc": LOG2FC_THRESH},
        "requests": PROVENANCE,
    }, indent=2))

    def _summ(df, label):
        sig = df[(df["p_value"] < P_THRESH) & (df["log2fc"].abs() > LOG2FC_THRESH)]
        print(f"\n[{label}] {len(df)} metabolites | {len(sig)} significant")
        for _, r in sig.nlargest(6, "neg_log10_p").iterrows():
            print(f"    {str(r['refmet_name'])[:34]:34} log2fc={r['log2fc']:+.2f} p={r['p_value']:.2e}")

    _summ(human, "MW human ST004303")
    _summ(motrpac, label_right)
    print("\n[done] figure ->", png)


if __name__ == "__main__":
    main()

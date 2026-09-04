"""Live MW-vs-MoTrPAC volcano comparison workflow."""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# The incomplete beta lives in the offline analysis package so a statistical
# routine is never reachable only through a module that opens a socket. It is
# re-exported here because callers of this module import it by name.
from ..analysis.special_functions import regularized_beta
from ..io import ensure_dir, read_text, write_csv_rows, write_json, write_text

MW_BASE_URL = "https://www.metabolomicsworkbench.org/rest"
MOTRPAC_HOME_URL = "https://motrpac-data.org"
MOTRPAC_BUCKET = "motrpac-data-hub"
MOTRPAC_SERVICE_URL = "https://services.motrpac-data.org"
USER_AGENT = "metabotyping-agentic-workbench/0.1"
MIN_P_VALUE = 1e-300
PLOT_HELPER_PATH = Path(__file__).resolve().parents[1] / "plotting" / "motrpac_plot_helpers.R"
MOTRPAC_ACUTE_TIMEPOINTS = (
    "during_20_min",
    "during_40_min",
    "post_10_min",
    "post_15_30_45_min",
    "post_3.5_4_hr",
    "post_24_hr",
)
MOTRPAC_GROUP_CONTRASTS = (("EE", "CON"), ("RE", "CON"), ("EE", "RE"))
MOTRPAC_GROUP_CONTRAST_LABELS = tuple(f"{left}-{right}" for left, right in MOTRPAC_GROUP_CONTRASTS)
MOTRPAC_PLOT_CONTRAST_MODES = {"between-groups", "acute-pre"}
MOTRPAC_SCOPES = {"blood-plasma", "all-tissues"}
MOTRPAC_OMICS_ASSAY_FILTERS = {"all", "targeted", "untargeted"}


@dataclass(frozen=True)
class VolcanoComparisonResult:
    out_dir: Path
    mw_stats_path: Path
    motrpac_stats_path: Path
    similarity_path: Path
    report_path: Path
    plot_paths: list[Path]
    mw_row_count: int
    motrpac_row_count: int
    comparison_count: int
    mw_ambiguous_feature_key_count: int = 0
    motrpac_ambiguous_feature_key_count: int = 0


TextFetcher = Callable[[str], str]
JsonFetcher = Callable[[str], Any]


def fetch_text(url: str, timeout: int = 60) -> str:
    request = Request(url, headers={"Accept": "*/*", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit live data adapter
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"Request failed with HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {url}") from exc


def fetch_json(url: str, timeout: int = 60) -> Any:
    text = fetch_text(url, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        snippet = text[:160].replace("\n", " ")
        raise RuntimeError(f"Expected JSON from {url}, got: {snippet}") from exc


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    values = list(payload.values())
    if values and all(isinstance(item, dict) for item in values):
        return values
    return [payload]


def normalize_metabolite_name(value: str | None) -> str:
    """Conservative name key for exploratory overlap screening."""

    text = str(value or "").strip().lower()
    if not text or text in {"unknown", "not_reported", "na", "nan"}:
        return ""
    text = text.replace("α", "alpha").replace("β", "beta").replace("γ", "gamma")
    text = text.replace("Δ", "delta").replace("δ", "delta")
    key = re.sub(r"[^a-z0-9]+", "", text)
    return key if len(key) >= 3 else ""


# Fallback timepoint tokens are matched on alphanumeric-token boundaries only.
# A bare substring test classified ``Diagnosis:prediabetes``, ``Treatment:prednisone``
# and ``Sample source:Blood`` (via ``:b``) as pre-exercise samples and ``CTR2`` as a
# time-0 sample, which can pair samples into a contrast that the study never ran.
_MW_TIMEPOINT_PRE_FALLBACK = re.compile(
    r"(?<![a-z0-9])(?:pre[-_ ]?(?:exercise|ex|training)|pre|baseline|before|b)(?![a-z0-9])"
)
_MW_TIMEPOINT_TIME60_FALLBACK = re.compile(r"(?<![a-z0-9])(?:time[-_ ]?60|r3)(?![a-z0-9.])")
_MW_TIMEPOINT_TIME0_FALLBACK = re.compile(r"(?<![a-z0-9])(?:time[-_ ]?0|r2)(?![a-z0-9.])")


def classify_mw_timepoint(factors: str) -> str:
    """Classify one MW factor string or sample ID as ``pre``, ``time_<x>`` or ``unknown``.

    An explicit ``Time:`` factor is authoritative. The fallback conventions
    (``pre``/``baseline``/``before``/``b`` for the pre sample, ``time 0``/``r2``
    and ``time 60``/``r3`` for the post samples) are recognized only as whole
    tokens. Nothing here verifies that a label means exercise timing; that
    remains a review question recorded in provenance.
    """
    text = str(factors or "")
    normalized = text.lower()
    time_match = re.search(r"(?:^|\|)\s*time\s*:\s*([^|]+)", text, flags=re.IGNORECASE)
    if time_match:
        raw_time = time_match.group(1).strip()
        compact_time = re.sub(r"[^a-z0-9]+", "", raw_time.lower())
        if compact_time in {"1p", "pre", "baseline", "preexercise", "before", "b"}:
            return "pre"
        if compact_time not in {"", "blank", "qc", "unknown"}:
            return "time_" + compact_time
    if _MW_TIMEPOINT_TIME60_FALLBACK.search(normalized):
        return "time_60"
    if _MW_TIMEPOINT_TIME0_FALLBACK.search(normalized):
        return "time_0"
    if _MW_TIMEPOINT_PRE_FALLBACK.search(normalized):
        return "pre"
    return "unknown"


def participant_id_from_sample(sample_id: str) -> str:
    sample_id = str(sample_id)
    if "_plasma_" in sample_id:
        return sample_id.split("_plasma_", 1)[0]
    cleaned = re.sub(r"_(B|R2|R3|pre|time0|time60)(?:_|$).*", "", sample_id, flags=re.IGNORECASE)
    return cleaned or sample_id


def _label_has_standalone_token(text: str, token: str) -> bool:
    return re.search(rf"(^|[^A-Za-z0-9]){re.escape(token)}([^A-Za-z0-9]|$)", text, re.IGNORECASE) is not None


def normalize_exercise_group_label(value: Any) -> str:
    """Normalize explicit exercise-group labels to MoTrPAC EE/RE/CON categories."""

    text = str(value or "").strip()
    compact = re.sub(r"[^A-Za-z0-9]+", "", text).lower()
    if not compact:
        return ""
    if "aduendur" in compact or "endurance" in compact or _label_has_standalone_token(text, "EE"):
        return "EE"
    if "aduresist" in compact or "resistance" in compact or _label_has_standalone_token(text, "RE"):
        return "RE"
    if "aducontrol" in compact or "control" in compact or _label_has_standalone_token(text, "CON"):
        return "CON"
    return ""


def normalize_sex_label(value: Any) -> str:
    """Normalize explicit sex labels used in MoTrPAC-style plot metadata."""

    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"[^A-Za-z0-9]+", "", text).lower()
    if compact in {"female", "females"} or _label_has_standalone_token(text, "F"):
        return "female"
    if compact in {"male", "males"} or _label_has_standalone_token(text, "M"):
        return "male"
    if re.search(r"(^|[^a-z])female(s)?([^a-z]|$)", text, flags=re.IGNORECASE):
        return "female"
    if re.search(r"(^|[^a-z])male(s)?([^a-z]|$)", text, flags=re.IGNORECASE):
        return "male"
    return ""


def _factor_parts(factors: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for chunk in re.split(r"\s*\|\s*", str(factors or "")):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def _first_normalized(values: list[Any], normalizer: Callable[[Any], str]) -> str:
    for value in values:
        normalized = normalizer(value)
        if normalized:
            return normalized
    return ""


def parse_mw_factor_plot_metadata(record: dict[str, Any]) -> dict[str, str]:
    """Extract explicit MoTrPAC-style plot metadata from MW factor rows."""

    factors = str(record.get("factors") or "")
    factor_parts = _factor_parts(factors)
    group_candidates = [
        factor_parts.get("exercise_group"),
        factor_parts.get("exercise group"),
        factor_parts.get("treatment"),
        factor_parts.get("intervention"),
        factor_parts.get("arm"),
        factor_parts.get("group"),
    ]
    sex_candidates = [
        factor_parts.get("sex"),
        factor_parts.get("biological_sex"),
        factor_parts.get("biological sex"),
        factor_parts.get("gender"),
    ]
    exercise_group = _first_normalized(group_candidates, normalize_exercise_group_label)
    sex = _first_normalized(sex_candidates, normalize_sex_label)
    palette_source = "mw-explicit-factors" if exercise_group or sex else ""
    return {
        "exercise_group": exercise_group,
        "sex": sex,
        "palette_source": palette_source,
    }


def parse_motrpac_contrast_plot_metadata(contrast: str) -> dict[str, str]:
    """Extract explicit MoTrPAC plotting metadata from a DA contrast label."""

    exercise_group = normalize_exercise_group_label(contrast)
    sex = normalize_sex_label(contrast)
    palette_source = "motrpac-contrast" if exercise_group or sex else ""
    return {
        "exercise_group": exercise_group,
        "sex": sex,
        "timepoint": parse_motrpac_timepoint_label(contrast),
        "palette_source": palette_source,
    }


def parse_motrpac_timepoint_label(contrast: str) -> str:
    """Return the explicit non-pre acute MoTrPAC timepoint from a DA contrast."""

    text = str(contrast or "")
    for timepoint in MOTRPAC_ACUTE_TIMEPOINTS:
        if timepoint in text:
            return timepoint
    return ""


def is_motrpac_acute_pre_contrast(contrast: str) -> bool:
    """Accept all acute MoTrPAC contrasts that compare a sampled timepoint against pre-exercise."""

    text = str(contrast or "")
    return "pre_exercise" in text and bool(parse_motrpac_timepoint_label(text))


def normalize_motrpac_scope(scope: str) -> str:
    text = str(scope or "").strip().lower().replace("_", "-")
    aliases = {
        "": "blood-plasma",
        "blood": "blood-plasma",
        "plasma": "blood-plasma",
        "blood-plasma": "blood-plasma",
        "plasma-blood": "blood-plasma",
        "blood-or-plasma": "blood-plasma",
        "all": "all-tissues",
        "all-tissue": "all-tissues",
        "all-tissues": "all-tissues",
    }
    normalized = aliases.get(text, text)
    if normalized not in MOTRPAC_SCOPES:
        allowed = ", ".join(sorted(MOTRPAC_SCOPES))
        raise ValueError(f"Unsupported MoTrPAC scope {scope!r}; expected one of: {allowed}.")
    return normalized


def is_motrpac_blood_plasma_tissue(tissue: str) -> bool:
    text = str(tissue or "").lower()
    return "plasma" in text or "blood" in text


def filter_motrpac_objects_by_scope(objects: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    normalized_scope = normalize_motrpac_scope(scope)
    if normalized_scope == "all-tissues":
        return objects
    return [item for item in objects if is_motrpac_blood_plasma_tissue(str(item.get("tissue", "")))]


def filter_motrpac_rows_by_scope(rows: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    normalized_scope = normalize_motrpac_scope(scope)
    if normalized_scope == "all-tissues":
        return rows
    return [row for row in rows if is_motrpac_blood_plasma_tissue(str(row.get("tissue", "")))]


def normalize_motrpac_omics_assay_filter(value: str) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "": "all",
        "any": "all",
        "all": "all",
        "targeted": "targeted",
        "metabolomics-targeted": "targeted",
        "untargeted": "untargeted",
        "un-targeted": "untargeted",
        "metabolomics-untargeted": "untargeted",
    }
    normalized = aliases.get(text, text)
    if normalized not in MOTRPAC_OMICS_ASSAY_FILTERS:
        allowed = ", ".join(sorted(MOTRPAC_OMICS_ASSAY_FILTERS))
        raise ValueError(f"Unsupported MoTrPAC omics assay filter {value!r}; expected one of: {allowed}.")
    return normalized


def filter_motrpac_objects_by_omics_assay(objects: list[dict[str, Any]], value: str) -> list[dict[str, Any]]:
    normalized = normalize_motrpac_omics_assay_filter(value)
    if normalized == "all":
        return objects
    return [item for item in objects if str(item.get("omics_assay", "")) == normalized]


def parse_motrpac_group_contrast_filter(value: str) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text or text.lower() in {"all", "any"}:
        return ()
    requested = tuple(
        part.strip().upper().replace("_", "-")
        for part in re.split(r"[,;]", text)
        if part.strip()
    )
    invalid = [item for item in requested if item not in MOTRPAC_GROUP_CONTRAST_LABELS]
    if invalid:
        allowed = ", ".join(MOTRPAC_GROUP_CONTRAST_LABELS)
        raise ValueError(
            f"Unsupported MoTrPAC group contrast filter {', '.join(invalid)!r}; expected any of: {allowed}."
        )
    return requested


def filter_motrpac_rows_by_group_contrasts(rows: list[dict[str, Any]], value: str) -> list[dict[str, Any]]:
    requested = parse_motrpac_group_contrast_filter(value)
    if not requested:
        return rows
    allowed = set(requested)
    return [row for row in rows if str(row.get("group_contrast", "")) in allowed]


def _single_nonempty(values: list[str]) -> str:
    unique = sorted({value for value in values if value})
    return unique[0] if len(unique) == 1 else ""


def _mw_participant_id(record: dict[str, Any], sample_id: str) -> str:
    factor_parts = _factor_parts(str(record.get("factors") or ""))
    subject = factor_parts.get("subject", "").strip()
    treatment = factor_parts.get("treatment", "").strip()
    if subject and subject.lower() not in {"blank", "qc", "unknown"}:
        if treatment and treatment.lower() not in {"blank", "qc", "unknown"}:
            return f"{subject}|{treatment}"
        return subject
    return participant_id_from_sample(sample_id)


def _mw_timepoint_display(timepoint: str) -> str:
    if timepoint == "time_0":
        return "Time 0"
    if timepoint == "time_60":
        return "Time 60"
    if timepoint.startswith("time_"):
        return timepoint.removeprefix("time_").upper()
    return timepoint


def _mw_contrast_key(timepoint: str) -> str:
    display = _mw_timepoint_display(timepoint)
    safe = re.sub(r"[^A-Za-z0-9]+", "_", display).strip("_")
    return f"MW_{safe}_vs_Pre"


def _mw_timepoint_sort_key(timepoint: str) -> tuple[int, str]:
    if timepoint == "time_0":
        return (0, timepoint)
    if timepoint == "time_60":
        return (60, timepoint)
    match = re.fullmatch(r"time_(\d+)p", timepoint)
    if match:
        return (int(match.group(1)), timepoint)
    return (999, timepoint)


def mw_sample_map(factor_records: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    samples: dict[str, dict[str, str]] = {}
    for record in factor_records:
        sample_id = str(record.get("local_sample_id") or "").strip()
        if not sample_id:
            continue
        timepoint = classify_mw_timepoint(str(record.get("factors") or ""))
        if timepoint == "unknown":
            timepoint = classify_mw_timepoint(sample_id)
        samples[sample_id] = {
            "participant_id": _mw_participant_id(record, sample_id),
            "timepoint": timepoint,
            **parse_mw_factor_plot_metadata(record),
        }
    return samples


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def paired_ttest_p_value(differences: list[float]) -> float:
    n = len(differences)
    if n < 2:
        return 1.0
    mean_diff = _mean(differences)
    # fsum: this variance feeds a published paired t-statistic and p-value.
    variance = math.fsum((value - mean_diff) ** 2 for value in differences) / (n - 1)
    if variance <= 0:
        return 1.0 if abs(mean_diff) < 1e-15 else MIN_P_VALUE
    t_stat = abs(mean_diff) / math.sqrt(variance / n)
    df = n - 1
    x = df / (df + t_stat * t_stat)
    return max(min(regularized_beta(x, df / 2.0, 0.5), 1.0), MIN_P_VALUE)


def bh_adjust(p_values: list[float]) -> list[float]:
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * len(p_values)
    running = 1.0
    total = len(p_values)
    for rank, (index, p_value) in reversed(list(enumerate(indexed, start=1))):
        running = min(running, p_value * total / rank)
        adjusted[index] = min(max(running, MIN_P_VALUE), 1.0)
    return adjusted


def compute_mw_volcano_stats(
    data_records: list[dict[str, Any]],
    factor_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sample_map = mw_sample_map(factor_records)
    by_participant: dict[str, dict[str, str]] = {}
    for sample_id, sample in sample_map.items():
        if sample["timepoint"] != "unknown":
            by_participant.setdefault(sample["participant_id"], {})[sample["timepoint"]] = sample_id

    post_timepoints = sorted(
        {
            timepoint
            for samples in by_participant.values()
            for timepoint in samples
            if timepoint != "pre"
        },
        key=_mw_timepoint_sort_key,
    )
    contrast_specs = [
        (_mw_contrast_key(post_timepoint), post_timepoint, f"{_mw_timepoint_display(post_timepoint)} - Pre")
        for post_timepoint in post_timepoints
    ]
    rows_by_contrast: dict[str, list[dict[str, Any]]] = {key: [] for key, _, _ in contrast_specs}

    for record in data_records:
        data = record.get("DATA") or {}
        if not isinstance(data, dict):
            continue
        label = str(record.get("refmet_name") or record.get("metabolite_name") or "").strip()
        feature_key = normalize_metabolite_name(label)
        if not feature_key:
            continue
        for contrast_key, post_timepoint, contrast_label in contrast_specs:
            differences: list[float] = []
            row_groups: list[str] = []
            row_sexes: list[str] = []
            row_palette_sources: list[str] = []
            for samples in by_participant.values():
                pre_value = _to_float(data.get(samples.get("pre")))
                post_value = _to_float(data.get(samples.get(post_timepoint)))
                if pre_value is None or post_value is None or pre_value <= 0 or post_value <= 0:
                    continue
                differences.append(math.log2(post_value / pre_value))
                pre_meta = sample_map.get(samples.get("pre", ""), {})
                post_meta = sample_map.get(samples.get(post_timepoint, ""), {})
                row_groups.extend([pre_meta.get("exercise_group", ""), post_meta.get("exercise_group", "")])
                row_sexes.extend([pre_meta.get("sex", ""), post_meta.get("sex", "")])
                row_palette_sources.extend(
                    [pre_meta.get("palette_source", ""), post_meta.get("palette_source", "")]
                )
            if not differences:
                continue
            exercise_group = _single_nonempty(row_groups)
            sex = _single_nonempty(row_sexes)
            palette_source = _single_nonempty(row_palette_sources) if exercise_group or sex else ""
            log_fc = _mean(differences)
            p_value = paired_ttest_p_value(differences)
            rows_by_contrast[contrast_key].append(
                {
                    "source": "metabolomics_workbench",
                    "study_id": record.get("study_id") or "unknown",
                    "analysis_id": record.get("analysis_id") or "unknown",
                    "contrast_key": contrast_key,
                    "contrast": contrast_label,
                    "feature_id": record.get("metabolite_id") or label,
                    "feature_label": label,
                    "feature_key": feature_key,
                    "logFC": round(log_fc, 12),
                    "p_value": p_value,
                    "adj_p_value": 1.0,
                    "n_pairs": len(differences),
                    "assay": record.get("analysis_summary") or "unknown",
                    "tissue": "plasma",
                    "omics": "metabolomics",
                    "timepoint": post_timepoint,
                    "exercise_group": exercise_group,
                    "sex": sex,
                    "palette_source": palette_source,
                }
            )

    output: list[dict[str, Any]] = []
    for _contrast_key, rows in rows_by_contrast.items():
        adjusted = bh_adjust([float(row["p_value"]) for row in rows])
        for row, adj_p_value in zip(rows, adjusted, strict=True):
            row["adj_p_value"] = adj_p_value
            output.append(row)
    return output


def _motrpac_asset_url() -> str:
    home = fetch_text(MOTRPAC_HOME_URL)
    match = re.search(r'<script[^>]+src="(?P<src>/assets/[^"]+\.js)"', home)
    if not match:
        raise RuntimeError("Could not find MoTrPAC Data Hub JavaScript bundle.")
    return MOTRPAC_HOME_URL + match.group("src")


def fetch_motrpac_bundle() -> str:
    return fetch_text(_motrpac_asset_url())


def parse_motrpac_api_key(bundle_text: str) -> str:
    keys = re.findall(r"AIza[0-9A-Za-z_-]+", bundle_text)
    if not keys:
        raise RuntimeError("Could not find MoTrPAC signed-url API key in the Data Hub bundle.")
    return keys[0]


def discover_motrpac_da_objects_from_bundle(
    bundle_text: str,
    release: str = "human-precovid-sed-adu",
) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"\{(?P<body>[^{}]*object_size:(?P<size>\d+)[^{}]*object:"
        r'"(?P<object>analysis/'
        + re.escape(release)
        + r'/v1\.3/metabolomics-[^"]+/da/[^"]*acute[^"]*\.txt)"[^{}]*)\}'
    )
    objects: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in pattern.finditer(bundle_text):
        body = match.group("body")
        object_name = match.group("object")
        if "external_release:!0" not in body or object_name in seen:
            continue
        seen.add(object_name)
        objects.append(
            {
                "object": object_name,
                "object_size": int(match.group("size")),
                **parse_motrpac_object_metadata(object_name),
            }
        )
    return sorted(objects, key=lambda item: item["object"])


def parse_motrpac_object_metadata(object_name: str) -> dict[str, str]:
    filename = object_name.rsplit("/", 1)[-1]
    match = re.match(
        r"human-precovid-sed-adu_(?P<tissue>t\d+-[^_]+)_(?P<assay>[^_]+)_da_"
        r"(?P<method>[^_]+)-(?P<contrast_type>[^_]+)_v",
        filename,
    )
    parts = object_name.split("/")
    raw_omics = parts[3] if len(parts) > 3 else "metabolomics"
    omics = "metabolomics" if raw_omics.startswith("metabolomics") else raw_omics
    omics_assay = raw_omics.removeprefix("metabolomics-") if raw_omics.startswith("metabolomics-") else ""
    assay = match.group("assay") if match else "unknown"
    if not omics_assay:
        if assay.startswith("metab-u-"):
            omics_assay = "untargeted"
            raw_omics = "metabolomics-untargeted"
        elif assay.startswith("metab-t-"):
            omics_assay = "targeted"
            raw_omics = "metabolomics-targeted"
    return {
        "release": "human-precovid-sed-adu",
        "omics": omics,
        "omics_assay": omics_assay,
        "raw_omics": raw_omics,
        "tissue": match.group("tissue") if match else "unknown",
        "assay": assay,
        "assay_label": f"{omics}-{assay}" if assay != "unknown" else omics,
        "method": match.group("method") if match else "unknown",
        "contrast_type": match.group("contrast_type") if match else "acute",
    }


def signed_motrpac_url(object_name: str, api_key: str) -> str:
    query = urlencode({"bucket": MOTRPAC_BUCKET, "object": object_name, "key": api_key})
    response = fetch_json(f"{MOTRPAC_SERVICE_URL}/v1/signedurl?{query}")
    if not isinstance(response, dict) or not response.get("url"):
        raise RuntimeError(f"MoTrPAC signed-url service did not return a URL for {object_name}")
    return str(response["url"])


def parse_motrpac_da_tsv(text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    for row in reader:
        feature_label = str(row.get("feature_id") or "").strip()
        feature_key = normalize_metabolite_name(feature_label)
        if not feature_key:
            continue
        log_fc = _to_float(row.get("logFC"))
        p_value = _to_float(row.get("p_value"))
        adj_p_value = _to_float(row.get("adj_p_value"))
        if log_fc is None or p_value is None or adj_p_value is None:
            continue
        contrast = str(row.get("contrast") or "unknown").strip()
        if not is_motrpac_acute_pre_contrast(contrast):
            continue
        plot_metadata = parse_motrpac_contrast_plot_metadata(contrast)
        contrast_key = "|".join(
            [
                metadata.get("omics", "unknown"),
                metadata.get("omics_assay", "unknown"),
                metadata.get("tissue", "unknown"),
                metadata.get("assay", "unknown"),
                contrast,
            ]
        )
        rows.append(
            {
                "source": "motrpac",
                "release": metadata.get("release", "human-precovid-sed-adu"),
                "object": metadata.get("object", "unknown"),
                "contrast_key": contrast_key,
                "contrast": contrast,
                "feature_id": feature_label,
                "feature_label": feature_label,
                "feature_key": feature_key,
                "logFC": log_fc,
                "p_value": max(p_value, MIN_P_VALUE),
                "adj_p_value": max(adj_p_value, MIN_P_VALUE),
                "assay": metadata.get("assay", "unknown"),
                "assay_label": metadata.get("assay_label", metadata.get("assay", "unknown")),
                "tissue": metadata.get("tissue", "unknown"),
                "omics": metadata.get("omics", "unknown"),
                "omics_assay": metadata.get("omics_assay", ""),
                "raw_omics": metadata.get("raw_omics", metadata.get("omics", "unknown")),
                "method": metadata.get("method", "unknown"),
                "contrast_family": "acute_pre_exercise",
                "group_contrast": "",
                "group_a": "",
                "group_b": "",
                "p_value_source": "motrpac_summary",
                **plot_metadata,
            }
        )
    return rows


def _motrpac_between_group_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("object", "unknown")),
        str(row.get("release", "human-precovid-sed-adu")),
        str(row.get("tissue", "unknown")),
        str(row.get("assay", "unknown")),
        str(row.get("method", "unknown")),
        str(row.get("omics", "metabolomics")),
        str(row.get("omics_assay", "")),
        str(row.get("feature_key", "")),
        str(row.get("sex", "")),
        str(row.get("timepoint", "")),
    )


def derive_motrpac_between_group_contrasts(
    rows: list[dict[str, Any]],
    group_contrasts: tuple[tuple[str, str], ...] = MOTRPAC_GROUP_CONTRASTS,
) -> list[dict[str, Any]]:
    """Derive group-pair plot rows from within-group acute/pre MoTrPAC summary rows.

    The source DA rows provide within-group acute logFC values. Without model standard
    errors or covariance terms these derived rows are not formal between-group tests,
    so p-values are conservative component-support values rather than recomputed
    differential-abundance p-values.
    """

    grouped: dict[tuple[str, ...], dict[str, dict[str, Any]]] = {}
    for row in rows:
        group = str(row.get("exercise_group") or "")
        if row.get("contrast_family") != "acute_pre_exercise" or group not in {"EE", "RE", "CON"}:
            continue
        if not row.get("feature_key") or not row.get("timepoint"):
            continue
        grouped.setdefault(_motrpac_between_group_key(row), {})[group] = row

    derived: list[dict[str, Any]] = []
    for by_group in grouped.values():
        for group_a, group_b in group_contrasts:
            left = by_group.get(group_a)
            right = by_group.get(group_b)
            if left is None or right is None:
                continue
            log_fc = float(left["logFC"]) - float(right["logFC"])
            p_value = max(float(left["p_value"]), float(right["p_value"]))
            adj_p_value = max(float(left["adj_p_value"]), float(right["adj_p_value"]))
            group_contrast = f"{group_a}-{group_b}"
            timepoint = str(left.get("timepoint", ""))
            sex = str(left.get("sex", ""))
            contrast = (
                f"({group_a}.{timepoint} - {group_a}.pre_exercise) - "
                f"({group_b}.{timepoint} - {group_b}.pre_exercise)"
            )
            contrast_key_parts = [
                str(left.get("omics", "metabolomics")),
                str(left.get("omics_assay", "")),
                str(left.get("tissue", "unknown")),
                str(left.get("assay", "unknown")),
                str(left.get("method", "unknown")),
                group_contrast,
                sex,
                timepoint,
            ]
            output = dict(left)
            output.update(
                {
                    "contrast_key": "|".join(contrast_key_parts),
                    "contrast": contrast,
                    "logFC": round(log_fc, 12),
                    "p_value": max(p_value, MIN_P_VALUE),
                    "adj_p_value": max(adj_p_value, MIN_P_VALUE),
                    "contrast_family": "derived_between_group_from_pre_exercise_logFC",
                    "group_contrast": group_contrast,
                    "group_a": group_a,
                    "group_b": group_b,
                    "exercise_group": "",
                    "palette_source": "motrpac-derived-between-group",
                    "p_value_source": "max_component_pre_exercise_summary_p_value_not_between_group_inference",
                    "component_contrasts": f"{left.get('contrast', '')} || {right.get('contrast', '')}",
                    "component_logFC": f"{left.get('logFC', '')};{right.get('logFC', '')}",
                    "component_adj_p_value": f"{left.get('adj_p_value', '')};{right.get('adj_p_value', '')}",
                }
            )
            derived.append(output)
    return sorted(
        derived,
        key=lambda row: (
            str(row.get("contrast_key", "")),
            str(row.get("feature_key", "")),
            str(row.get("feature_id", "")),
        ),
    )


def prepare_motrpac_plot_rows(
    rows: list[dict[str, Any]],
    contrast_mode: str = "between-groups",
) -> list[dict[str, Any]]:
    if contrast_mode not in MOTRPAC_PLOT_CONTRAST_MODES:
        allowed = ", ".join(sorted(MOTRPAC_PLOT_CONTRAST_MODES))
        raise ValueError(f"Unsupported MoTrPAC plot contrast mode {contrast_mode!r}; expected one of: {allowed}.")
    if contrast_mode == "acute-pre":
        return rows
    derived = derive_motrpac_between_group_contrasts(rows)
    return derived or rows


def fetch_motrpac_volcano_stats(
    release: str = "human-precovid-sed-adu",
    bundle_text: str | None = None,
    local_da_dir: str | Path | None = None,
    scope: str = "blood-plasma",
    omics_assay_filter: str = "all",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_scope = normalize_motrpac_scope(scope)
    normalized_omics_assay = normalize_motrpac_omics_assay_filter(omics_assay_filter)
    if local_da_dir is not None:
        objects: list[dict[str, Any]] = []
        for path in sorted(Path(local_da_dir).glob("*.txt")):
            object_name = path.name
            metadata = parse_motrpac_object_metadata(object_name)
            metadata.update({"object": object_name, "local_path": str(path)})
            objects.append(metadata)
        objects = filter_motrpac_objects_by_scope(objects, normalized_scope)
        objects = filter_motrpac_objects_by_omics_assay(objects, normalized_omics_assay)
        rows = []
        for metadata in objects:
            rows.extend(parse_motrpac_da_tsv(read_text(metadata["local_path"]), metadata))
        return rows, objects

    bundle = bundle_text if bundle_text is not None else fetch_motrpac_bundle()
    api_key = parse_motrpac_api_key(bundle)
    objects = filter_motrpac_objects_by_scope(discover_motrpac_da_objects_from_bundle(bundle, release), normalized_scope)
    objects = filter_motrpac_objects_by_omics_assay(objects, normalized_omics_assay)
    rows = []
    for metadata in objects:
        url = signed_motrpac_url(metadata["object"], api_key)
        rows.extend(parse_motrpac_da_tsv(fetch_text(url), metadata))
    return rows, objects


def pearson_correlation(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 2:
        return 0.0
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    # fsum: this Pearson r is published (the Lac-Phe lactate-coupling result).
    numerator = math.fsum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator_x = math.sqrt(math.fsum((x - mean_x) ** 2 for x in xs))
    denominator_y = math.sqrt(math.fsum((y - mean_y) ** 2 for y in ys))
    if denominator_x == 0 or denominator_y == 0:
        return 0.0
    return numerator / (denominator_x * denominator_y)


def _unique_features_by_contrast(
    rows: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, dict[str, Any]]],
    dict[str, set[str]],
]:
    """Index only unambiguous feature keys and retain duplicate-key evidence.

    A normalized key is safe for exploratory overlap only when it occurs once
    within its contrast. Keeping grouped rows until cardinality is checked
    prevents the previous last-row-wins dictionary overwrite.
    """

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        contrast = str(row.get("contrast_key", ""))
        feature_key = str(row.get("feature_key", ""))
        if not contrast or not feature_key:
            continue
        grouped.setdefault(contrast, {}).setdefault(feature_key, []).append(row)

    unique: dict[str, dict[str, dict[str, Any]]] = {}
    ambiguous: dict[str, set[str]] = {}
    for contrast, feature_rows in grouped.items():
        unique[contrast] = {
            feature_key: matches[0]
            for feature_key, matches in feature_rows.items()
            if len(matches) == 1
        }
        ambiguous[contrast] = {
            feature_key for feature_key, matches in feature_rows.items() if len(matches) > 1
        }
    return unique, ambiguous


def ambiguous_feature_key_count(rows: list[dict[str, Any]]) -> int:
    """Count duplicate normalized keys as contrast-key ambiguity pairs."""

    _, ambiguous = _unique_features_by_contrast(rows)
    return sum(len(keys) for keys in ambiguous.values())


def rank_similarity(
    mw_rows: list[dict[str, Any]],
    motrpac_rows: list[dict[str, Any]],
    *,
    min_overlap: int = 5,
) -> list[dict[str, Any]]:
    mw_by_contrast, mw_ambiguous_by_contrast = _unique_features_by_contrast(mw_rows)
    motrpac_by_contrast, motrpac_ambiguous_by_contrast = _unique_features_by_contrast(motrpac_rows)

    comparisons: list[dict[str, Any]] = []
    for mw_contrast, mw_features in mw_by_contrast.items():
        for motrpac_contrast, motrpac_features in motrpac_by_contrast.items():
            mw_ambiguous = mw_ambiguous_by_contrast.get(mw_contrast, set())
            motrpac_ambiguous = motrpac_ambiguous_by_contrast.get(motrpac_contrast, set())
            mw_all_keys = set(mw_features) | mw_ambiguous
            motrpac_all_keys = set(motrpac_features) | motrpac_ambiguous
            excluded_ambiguous_overlap = sorted(
                (mw_all_keys & motrpac_all_keys) & (mw_ambiguous | motrpac_ambiguous)
            )
            overlap = sorted(set(mw_features).intersection(motrpac_features))
            if len(overlap) < min_overlap:
                continue
            pairs = [
                (float(mw_features[key]["logFC"]), float(motrpac_features[key]["logFC"]))
                for key in overlap
            ]
            correlation = pearson_correlation(pairs)
            concordant = sum(
                1
                for mw_log_fc, motrpac_log_fc in pairs
                if (mw_log_fc > 0 and motrpac_log_fc > 0) or (mw_log_fc < 0 and motrpac_log_fc < 0)
            )
            direction_concordance = concordant / len(pairs)
            score = (
                0.45 * max(correlation, 0.0)
                + 0.35 * direction_concordance
                + 0.20 * min(len(overlap) / 25.0, 1.0)
            )
            first_motrpac = next(iter(motrpac_features.values()))
            comparisons.append(
                {
                    "mw_contrast_key": mw_contrast,
                    "mw_contrast": next(iter(mw_features.values()))["contrast"],
                    "motrpac_contrast_key": motrpac_contrast,
                    "motrpac_contrast": first_motrpac["contrast"],
                    "motrpac_tissue": first_motrpac["tissue"],
                    "motrpac_assay": first_motrpac["assay"],
                    "motrpac_assay_label": first_motrpac.get("assay_label", first_motrpac["assay"]),
                    "motrpac_omics": first_motrpac["omics"],
                    "motrpac_omics_assay": first_motrpac.get("omics_assay", ""),
                    "motrpac_timepoint": first_motrpac.get("timepoint", ""),
                    "motrpac_group_contrast": first_motrpac.get("group_contrast", ""),
                    "motrpac_contrast_family": first_motrpac.get("contrast_family", ""),
                    "motrpac_p_value_source": first_motrpac.get("p_value_source", ""),
                    "overlap_n": len(overlap),
                    "mw_ambiguous_feature_key_n": len(mw_ambiguous),
                    "motrpac_ambiguous_feature_key_n": len(motrpac_ambiguous),
                    "excluded_ambiguous_overlap_n": len(excluded_ambiguous_overlap),
                    "excluded_ambiguous_overlap_feature_keys": ";".join(excluded_ambiguous_overlap),
                    "pearson_logFC_r": round(correlation, 6),
                    "direction_concordance": round(direction_concordance, 6),
                    "screening_similarity_score": round(score, 6),
                    "overlap_feature_keys": ";".join(overlap),
                }
            )
    return sorted(
        comparisons,
        key=lambda row: (
            float(row["screening_similarity_score"]),
            int(row["overlap_n"]),
            str(row["motrpac_contrast_key"]),
        ),
        reverse=True,
    )


def select_mw_reference_contrast_key(
    mw_rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    requested_key: str = "auto",
) -> str:
    mw_keys = sorted({str(row.get("contrast_key", "")) for row in mw_rows if row.get("contrast_key")})
    if not mw_keys:
        return ""
    requested = str(requested_key or "").strip()
    if requested and requested.lower() != "auto":
        if requested not in mw_keys:
            allowed = ", ".join(mw_keys)
            raise ValueError(f"MW reference contrast {requested!r} was not found; available contrasts: {allowed}.")
        return requested
    for comparison in comparisons:
        candidate = str(comparison.get("mw_contrast_key", ""))
        if candidate in mw_keys:
            return candidate
    return mw_keys[0]


def _csv_fieldnames(rows: list[dict[str, Any]], preferred: list[str]) -> list[str]:
    fields = list(preferred)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def _write_plot_script(path: Path) -> Path:
    script = r'''
args <- commandArgs(trailingOnly = TRUE)
mw_path <- args[[1]]
motrpac_path <- args[[2]]
similarity_path <- args[[3]]
plot_dir <- args[[4]]
top_n <- as.integer(args[[5]])
helper_path <- if (length(args) >= 6) args[[6]] else ""
mw_study_id <- if (length(args) >= 7) args[[7]] else "unknown"
motrpac_scope <- if (length(args) >= 8) args[[8]] else "blood-plasma"
motrpac_omics_assay_filter <- if (length(args) >= 9) args[[9]] else "all"
motrpac_group_contrast_filter <- if (length(args) >= 10) args[[10]] else "all"
mw_reference_contrast_key <- if (length(args) >= 11) args[[11]] else "auto"
dir.create(plot_dir, recursive = TRUE, showWarnings = FALSE)
if (!file.exists(helper_path)) {
  stop(paste("MoTrPAC plot helper not found:", helper_path))
}
source(helper_path)

read_csv <- function(path) {
  read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
}

cap_y <- function(values) {
  values[!is.finite(values)] <- NA
  if (all(is.na(values))) return(values)
  max_finite <- max(values[is.finite(values)], na.rm = TRUE)
  values[is.na(values)] <- max_finite
  values
}

wrapped_title <- function(title_text) {
  width <- ifelse(par("mfrow")[2] > 1, 44, 70)
  paste(strwrap(as.character(title_text), width = width), collapse = "\n")
}

plot_volcano <- function(data, title_text) {
  if (nrow(data) == 0) {
    plot.new()
    title(wrapped_title(title_text), cex.main = 0.9)
    text(0.5, 0.5, "No points")
    return()
  }
  p <- as.numeric(data$adj_p_value)
  p[is.na(p) | p <= 0] <- 1e-300
  x <- as.numeric(data$logFC)
  y <- cap_y(-log10(p))
  cols <- motrpac_significance_colors(x, p)
  plot(x, y, pch = 16, cex = 0.65, col = cols, xlab = "logFC", ylab = "-log10(adj p)",
       main = "")
  title(wrapped_title(title_text), cex.main = 0.9)
  abline(h = -log10(0.05), lty = 2, col = "#666666")
  abline(v = 0, lty = 3, col = "#666666")
  legend("bottomright",
         legend = c("adj p < 0.05, logFC > 0", "adj p < 0.05, logFC < 0", "not significant"),
         col = c("#b2182b", "#2166ac", "#80808055"), pch = 16, bty = "n", cex = 0.65)
  motrpac_draw_context(data)
  notes <- character()
  group_contrasts <- motrpac_unique_values(data, "group_contrast")
  if (length(group_contrasts) > 0) {
    notes <- c(notes, paste("Group contrast:", paste(group_contrasts, collapse = ", ")))
  }
  palette_sources <- motrpac_unique_values(data, "palette_source")
  if (length(palette_sources) > 0) {
    notes <- c(notes, paste("Palette metadata:", paste(palette_sources, collapse = ", ")))
  }
  if (length(notes) > 0) {
    mtext(paste(notes, collapse = " | "), side = 3, line = 0.1, adj = 0, cex = 0.55, col = "#555555")
  }
  ord <- order(p, decreasing = FALSE)
  if (length(ord) > 0) {
    lab_idx <- ord[seq_len(min(8, length(ord)))]
    text(x[lab_idx], y[lab_idx], labels = data$feature_label[lab_idx], pos = 3, cex = 0.55)
  }
}

plot_logfc_heatmap <- function(mat, title_text) {
  if (is.null(mat) || length(mat) == 0 || nrow(mat) == 0 || ncol(mat) == 0) {
    plot.new()
    title(title_text)
    text(0.5, 0.5, "No heatmap values")
    return()
  }
  mat <- as.matrix(mat)
  storage.mode(mat) <- "numeric"
  zlim <- max(abs(mat), na.rm = TRUE)
  if (!is.finite(zlim) || zlim == 0) zlim <- 1
  cols <- colorRampPalette(c("#2166ac", "#f7f7f7", "#b2182b"))(101)
  old_par <- par(no.readonly = TRUE)
  on.exit(par(old_par), add = TRUE)
  row_cex <- ifelse(nrow(mat) > 30, 0.42, 0.56)
  col_cex <- ifelse(ncol(mat) > 18, 0.52, 0.68)
  par(mar = c(9, 12, 4, 2))
  image(
    x = seq_len(ncol(mat)),
    y = seq_len(nrow(mat)),
    z = t(mat[nrow(mat):1, , drop = FALSE]),
    col = cols,
    zlim = c(-zlim, zlim),
    axes = FALSE,
    xlab = "",
    ylab = "",
    main = title_text
  )
  axis(1, at = seq_len(ncol(mat)), labels = colnames(mat), las = 2, cex.axis = col_cex)
  axis(2, at = seq_len(nrow(mat)), labels = rev(rownames(mat)), las = 2, cex.axis = row_cex)
  box()
  mtext(sprintf("logFC color scale capped at +/- %.2f", zlim), side = 3, line = 0.1, cex = 0.62, col = "#555555")
}

plot_overlap_heatmap <- function(mw_subset, motrpac_subset, title_text) {
  mw_counts <- table(as.character(mw_subset$feature_key))
  motrpac_counts <- table(as.character(motrpac_subset$feature_key))
  mw_unique <- names(mw_counts[mw_counts == 1])
  motrpac_unique <- names(motrpac_counts[motrpac_counts == 1])
  common <- intersect(mw_unique, motrpac_unique)
  common <- common[common != ""]
  if (length(common) == 0) {
    plot_logfc_heatmap(matrix(numeric(), nrow = 0), title_text)
    return()
  }
  rows <- list()
  scores <- c()
  for (key in common) {
    mw_row <- mw_subset[which(mw_subset$feature_key == key)[1], ]
    motrpac_row <- motrpac_subset[which(motrpac_subset$feature_key == key)[1], ]
    values <- c(as.numeric(mw_row$logFC), as.numeric(motrpac_row$logFC))
    label <- as.character(mw_row$feature_label)
    if (is.na(label) || label == "") label <- key
    rows[[label]] <- values
    scores[label] <- max(abs(values), na.rm = TRUE)
  }
  keep <- names(sort(scores, decreasing = TRUE))[seq_len(min(30, length(scores)))]
  mat <- do.call(rbind, rows[keep])
  colnames(mat) <- c("MW logFC", "MoTrPAC logFC")
  plot_logfc_heatmap(mat, title_text)
}

plot_motrpac_timepoint_heatmap <- function(data, title_text) {
  required <- c("feature_key", "feature_label", "logFC", "adj_p_value", "timepoint")
  if (!all(required %in% colnames(data))) {
    plot_logfc_heatmap(matrix(numeric(), nrow = 0), title_text)
    return()
  }
  d <- data[data$timepoint != "" & data$feature_key != "", ]
  if (nrow(d) == 0) {
    plot_logfc_heatmap(matrix(numeric(), nrow = 0), title_text)
    return()
  }
  d$adj_p_value <- as.numeric(d$adj_p_value)
  d$logFC <- as.numeric(d$logFC)
  d$feature_key <- as.character(d$feature_key)
  d$feature_label <- as.character(d$feature_label)
  d$exercise_group <- if ("exercise_group" %in% colnames(d)) as.character(d$exercise_group) else ""
  d$group_contrast <- if ("group_contrast" %in% colnames(d)) as.character(d$group_contrast) else ""
  d$sex <- if ("sex" %in% colnames(d)) as.character(d$sex) else ""
  d$exercise_group[is.na(d$exercise_group)] <- ""
  d$group_contrast[is.na(d$group_contrast)] <- ""
  d$plot_group <- ifelse(d$group_contrast != "", d$group_contrast, d$exercise_group)
  d$plot_group[is.na(d$plot_group)] <- ""
  d$plot_group[d$plot_group == ""] <- "group_unknown"
  d$sex[is.na(d$sex)] <- ""
  d$column_key <- ifelse(d$sex == "", paste(d$plot_group, d$timepoint, sep = ":"),
                         paste(d$plot_group, d$sex, d$timepoint, sep = ":"))
  feature_scores <- tapply(-log10(pmax(d$adj_p_value, 1e-300)), d$feature_key, max, na.rm = TRUE)
  feature_scores <- sort(feature_scores, decreasing = TRUE)
  top_features <- names(feature_scores)[seq_len(min(40, length(feature_scores)))]
  columns <- sort(unique(d$column_key))
  mat <- matrix(NA_real_, nrow = length(top_features), ncol = length(columns),
                dimnames = list(top_features, columns))
  labels <- setNames(top_features, top_features)
  for (feature in top_features) {
    feature_rows <- d[d$feature_key == feature, ]
    labels[feature] <- feature_rows$feature_label[which.max(-log10(pmax(feature_rows$adj_p_value, 1e-300)))]
    for (column in columns) {
      vals <- feature_rows$logFC[feature_rows$column_key == column]
      if (length(vals) > 0) {
        mat[feature, column] <- mean(vals, na.rm = TRUE)
      }
    }
  }
  rownames(mat) <- labels[rownames(mat)]
  mat[is.na(mat)] <- 0
  plot_logfc_heatmap(mat, title_text)
}

split_filter_values <- function(value) {
  value <- trimws(as.character(value))
  if (length(value) == 0 || value == "" || tolower(value) %in% c("all", "any")) {
    return(character())
  }
  parts <- trimws(unlist(strsplit(value, "[,;]")))
  parts[parts != ""]
}

safe_file_label <- function(value) {
  label <- gsub("[^A-Za-z0-9]+", "_", as.character(value))
  label <- gsub("^_+|_+$", "", label)
  if (label == "") "unknown" else label
}

first_value <- function(values, fallback = "") {
  values <- values[!is.na(values) & values != ""]
  if (length(values) == 0) fallback else as.character(values[1])
}

pick_mw_reference_key <- function(mw, similarity, requested_key) {
  requested_key <- as.character(requested_key)
  mw_keys <- unique(as.character(mw$contrast_key))
  if (!(tolower(requested_key) %in% c("", "auto")) && requested_key %in% mw_keys) {
    return(requested_key)
  }
  if (nrow(similarity) > 0 && "mw_contrast_key" %in% colnames(similarity)) {
    for (candidate in as.character(similarity$mw_contrast_key)) {
      if (candidate %in% mw_keys) return(candidate)
    }
  }
  sort(mw_keys)[1]
}

plot_mw_reference_vs_motrpac_timepoints <- function(
    mw, motrpac, similarity, plot_dir, mw_study_id,
    omics_assay_filter, group_contrast_filter, requested_mw_key) {
  if (!("group_contrast" %in% colnames(motrpac)) || !("timepoint" %in% colnames(motrpac))) {
    return(invisible(character()))
  }
  groups <- split_filter_values(group_contrast_filter)
  available_groups <- sort(unique(as.character(motrpac$group_contrast)))
  available_groups <- available_groups[!is.na(available_groups) & available_groups != ""]
  if (length(groups) == 0) groups <- available_groups
  groups <- groups[groups %in% available_groups]
  if (length(groups) == 0) return(invisible(character()))

  mw_key <- pick_mw_reference_key(mw, similarity, requested_mw_key)
  mw_subset <- mw[mw$contrast_key == mw_key, ]
  mw_label <- first_value(as.character(mw_subset$contrast), mw_key)
  timepoints <- c("during_20_min", "during_40_min", "post_10_min",
                  "post_15_30_45_min", "post_3.5_4_hr", "post_24_hr")
  written <- character()
  for (group in groups) {
    group_subset <- motrpac[as.character(motrpac$group_contrast) == group, ]
    if (nrow(group_subset) == 0) next
    out <- file.path(
      plot_dir,
      sprintf("mw_reference_vs_motrpac_%s_all_timepoints_volcano.png", safe_file_label(group))
    )
    png(out, width = 2400, height = 1600, res = 135)
    par(mfrow = c(2, 4), mar = c(5, 5, 4, 1), oma = c(0, 0, 2, 0))
    plot_volcano(mw_subset, paste("MW", mw_study_id, "reference:", mw_label))
    for (timepoint in timepoints) {
      subset <- group_subset[as.character(group_subset$timepoint) == timepoint, ]
      plot_volcano(subset, paste("MoTrPAC", group, timepoint, omics_assay_filter))
    }
    plot.new()
    title("Scope")
    text(0.5, 0.62, paste("MoTrPAC:", motrpac_scope_label), cex = 1.0)
    text(0.5, 0.50, paste("Assay:", omics_assay_filter), cex = 1.0)
    text(0.5, 0.38, "Derived group logFC; component p-values", cex = 0.8, col = "#555555")
    mtext(
      paste("One MW contrast vs MoTrPAC", group, "across all acute timepoints"),
      outer = TRUE,
      line = -1,
      cex = 1.05
    )
    dev.off()
    written <- c(written, out)
  }
  invisible(written)
}

mw <- read_csv(mw_path)
motrpac <- read_csv(motrpac_path)
similarity <- read_csv(similarity_path)
motrpac_scope_label <- ifelse(motrpac_scope == "all-tissues", "all tissues", "blood/plasma")
motrpac_overview_file <- ifelse(motrpac_scope == "all-tissues",
                                "motrpac_all_tissues_overview.png",
                                "motrpac_blood_plasma_overview.png")

png(file.path(plot_dir, "mw_all_acute_overview.png"), width = 1200, height = 900, res = 130)
plot_volcano(mw, paste("Metabolomics Workbench", mw_study_id, ": all acute contrasts"))
dev.off()

png(file.path(plot_dir, motrpac_overview_file), width = 1200, height = 900, res = 130)
plot_volcano(motrpac, paste("MoTrPAC human pre-COVID:", motrpac_scope_label, "acute contrasts"))
dev.off()
if (motrpac_scope != "all-tissues") {
  invisible(file.copy(file.path(plot_dir, motrpac_overview_file),
                      file.path(plot_dir, "motrpac_all_tissues_overview.png"),
                      overwrite = TRUE))
}

png(file.path(plot_dir, "motrpac_all_timepoints_heatmap.png"), width = 1500, height = 1200, res = 130)
plot_motrpac_timepoint_heatmap(motrpac, paste("MoTrPAC human pre-COVID:", motrpac_scope_label, "all acute timepoints"))
dev.off()

plot_mw_reference_vs_motrpac_timepoints(
  mw, motrpac, similarity, plot_dir, mw_study_id,
  motrpac_omics_assay_filter, motrpac_group_contrast_filter, mw_reference_contrast_key
)

if (nrow(similarity) > 0) {
  n <- min(top_n, nrow(similarity))
  for (i in seq_len(n)) {
    row <- similarity[i, ]
    mw_subset <- mw[mw$contrast_key == row$mw_contrast_key, ]
    motrpac_subset <- motrpac[motrpac$contrast_key == row$motrpac_contrast_key, ]
    out <- sprintf("side_by_side_top_%02d.png", i)
    png(file.path(plot_dir, out), width = 1800, height = 900, res = 130)
    par(mfrow = c(1, 2), mar = c(5, 5, 4, 1))
    plot_volcano(mw_subset, paste("MW:", row$mw_contrast))
    assay_text <- if ("motrpac_assay_label" %in% colnames(similarity)) as.character(row$motrpac_assay_label) else as.character(row$motrpac_assay)
    group_text <- if ("motrpac_group_contrast" %in% colnames(similarity)) as.character(row$motrpac_group_contrast) else ""
    time_text <- if ("motrpac_timepoint" %in% colnames(similarity)) as.character(row$motrpac_timepoint) else ""
    motrpac_title <- paste("MoTrPAC:", row$motrpac_tissue, assay_text)
    if (!is.na(group_text) && group_text != "") motrpac_title <- paste(motrpac_title, group_text)
    if (!is.na(time_text) && time_text != "") motrpac_title <- paste(motrpac_title, time_text)
    plot_volcano(motrpac_subset, motrpac_title)
    mtext(sprintf("Overlap n=%s | r=%s | score=%s", row$overlap_n, row$pearson_logFC_r,
                  row$screening_similarity_score), outer = TRUE, line = -1.5, cex = 0.9)
    dev.off()

    heatmap_out <- sprintf("side_by_side_top_%02d_heatmap.png", i)
    png(file.path(plot_dir, heatmap_out), width = 1200, height = 1100, res = 130)
    plot_overlap_heatmap(mw_subset, motrpac_subset,
                         sprintf("Overlap logFC heatmap: top %02d", i))
    dev.off()
  }
}
'''
    return write_text(path, script)


def render_volcano_pngs(
    mw_stats_path: Path,
    motrpac_stats_path: Path,
    similarity_path: Path,
    plot_dir: Path,
    top_n: int,
    mw_study_id: str,
    motrpac_scope: str,
    motrpac_omics_assay_filter: str,
    motrpac_group_contrast_filter: str,
    mw_reference_contrast_key: str,
) -> list[Path]:
    rscript = shutil.which("Rscript")
    if not rscript:
        raise RuntimeError("Rscript is required for PNG rendering but was not found on PATH.")
    script_path = _write_plot_script(plot_dir / "render_volcano_pngs.R")
    subprocess.run(
        [
            rscript,
            str(script_path),
            str(mw_stats_path),
            str(motrpac_stats_path),
            str(similarity_path),
            str(plot_dir),
            str(top_n),
            str(PLOT_HELPER_PATH),
            str(mw_study_id),
            str(motrpac_scope),
            str(motrpac_omics_assay_filter),
            str(motrpac_group_contrast_filter),
            str(mw_reference_contrast_key),
        ],
        check=True,
    )
    return sorted(plot_dir.glob("*.png"))


def _report_text(
    mw_study_id: str,
    mw_rows: list[dict[str, Any]],
    motrpac_rows: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    plot_paths: list[Path],
    plot_error: str | None,
    *,
    motrpac_source_row_count: int | None = None,
    motrpac_plot_contrast_mode: str = "between-groups",
    motrpac_scope: str = "blood-plasma",
    motrpac_omics_assay_filter: str = "all",
    motrpac_group_contrast_filter: str = "all",
    mw_reference_contrast_key: str = "auto",
    mw_ambiguous_feature_key_count: int | None = None,
    motrpac_ambiguous_feature_key_count: int | None = None,
) -> str:
    top_rows = comparisons[:6]
    source_row_count = len(motrpac_rows) if motrpac_source_row_count is None else motrpac_source_row_count
    normalized_scope = normalize_motrpac_scope(motrpac_scope)
    mw_ambiguous_count = (
        ambiguous_feature_key_count(mw_rows)
        if mw_ambiguous_feature_key_count is None
        else mw_ambiguous_feature_key_count
    )
    motrpac_ambiguous_count = (
        ambiguous_feature_key_count(motrpac_rows)
        if motrpac_ambiguous_feature_key_count is None
        else motrpac_ambiguous_feature_key_count
    )
    scope_text = (
        "blood/plasma only unless `--motrpac-scope all-tissues` is explicitly requested"
        if normalized_scope == "blood-plasma"
        else "all public human pre-COVID metabolomics tissues"
    )
    lines = [
        f"# MW {mw_study_id} vs MoTrPAC Volcano Comparison",
        "",
        "## Scope",
        "",
        f"- Metabolomics Workbench study: `{mw_study_id}`",
        "- MoTrPAC release: `human-precovid-sed-adu`",
        f"- MoTrPAC scope: `{normalized_scope}`; {scope_text}.",
        "- MoTrPAC acute sampled timepoints are discovered from public Data Hub DA files within the selected scope.",
        f"- MoTrPAC plot contrast mode: `{motrpac_plot_contrast_mode}`.",
        f"- MoTrPAC omics assay filter: `{motrpac_omics_assay_filter}`.",
        f"- MoTrPAC group contrast filter: `{motrpac_group_contrast_filter}`.",
        f"- MW reference contrast for all-timepoint panels: `{mw_reference_contrast_key}`.",
        "- Interpretation: exploratory screening only; name overlap is not a harmonized metabolite crosswalk.",
        "",
        "## Inputs",
        "",
        f"- MW volcano rows: {len(mw_rows)}",
        f"- MoTrPAC source acute/pre rows parsed: {source_row_count}",
        f"- MoTrPAC plot rows: {len(motrpac_rows)}",
        f"- MW ambiguous normalized feature keys excluded from similarity: {mw_ambiguous_count}",
        f"- MoTrPAC ambiguous normalized feature keys excluded from similarity: {motrpac_ambiguous_count}",
        f"- MoTrPAC DA files parsed: {len(objects)}",
        f"- Candidate contrast-pair comparisons with at least 5 unambiguous overlapping names: {len(comparisons)}",
        "",
        "## Top Exploratory Matches",
        "",
        "| rank | MW contrast | MoTrPAC tissue | MoTrPAC assay | MoTrPAC contrast | MoTrPAC timepoint | overlap | ambiguous overlap excluded | r | concordance | score |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(top_rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    str(row["mw_contrast"]),
                    str(row["motrpac_tissue"]),
                    str(row.get("motrpac_assay_label", row["motrpac_assay"])),
                    str(row.get("motrpac_group_contrast", "")) or str(row.get("motrpac_contrast", "")),
                    str(row.get("motrpac_timepoint", "")),
                    str(row["overlap_n"]),
                    str(row.get("excluded_ambiguous_overlap_n", 0)),
                    str(row["pearson_logFC_r"]),
                    str(row["direction_concordance"]),
                    str(row["screening_similarity_score"]),
                ]
            )
            + " |"
        )
    if not top_rows:
        lines.append("| _none_ | | | | | | | | | | |")
    lines.extend(["", "## PNG Outputs", ""])
    if plot_paths:
        for path in plot_paths:
            lines.append(f"- `{path.name}`")
    elif plot_error:
        lines.append(f"- PNG rendering did not complete: {plot_error}")
    else:
        lines.append("- PNG rendering was skipped.")
    lines.extend(
        [
            "",
            "## Methods Note",
            "",
            "MW logFC values are mean paired log2(post/pre) differences by participant prefix. "
            "MW p-values are paired t-tests with Benjamini-Hochberg adjustment per MW contrast. "
            "MoTrPAC source rows use published summary `logFC`, `p_value`, and `adj_p_value` values. "
            "When MoTrPAC plot rows are `EE-CON`, `RE-CON`, or `EE-RE`, `logFC` is a derived difference "
            "between within-group acute/pre logFC values. Its p-values are conservative component-support "
            "values from the paired source summaries, not formal between-group differential-abundance tests. "
            "Similarity scores combine positive Pearson correlation, directional concordance, and overlap count; "
            "they are screening metrics, not validation evidence. "
            "Normalized feature keys occurring more than once within either contrast are ambiguous and are "
            "excluded rather than selecting an arbitrary assay, isomer, adduct, or subgroup row. "
            "Plot palette metadata uses MoTrPAC group and sex colors only when normalized rows carry explicit "
            "`exercise_group` or `sex` evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def compare_mw_motrpac_volcano(
    mw_study_id: str = "ST001789",
    motrpac_release: str = "human-precovid-sed-adu",
    motrpac_scope: str = "blood-plasma",
    out: str | Path = "/private/tmp/metabotyping-live/comparisons/mw_ST001789_vs_motrpac_human_precovid",
    top_n: int = 6,
    *,
    mw_data_json: str | Path | None = None,
    mw_factors_json: str | Path | None = None,
    motrpac_da_dir: str | Path | None = None,
    motrpac_plot_contrast_mode: str = "between-groups",
    motrpac_omics_assay_filter: str = "all",
    motrpac_group_contrast_filter: str = "all",
    mw_reference_contrast_key: str = "auto",
    skip_plots: bool = False,
) -> VolcanoComparisonResult:
    normalized_motrpac_scope = normalize_motrpac_scope(motrpac_scope)
    normalized_omics_assay_filter = normalize_motrpac_omics_assay_filter(motrpac_omics_assay_filter)
    normalized_group_contrasts = parse_motrpac_group_contrast_filter(motrpac_group_contrast_filter)
    normalized_group_contrast_filter = ",".join(normalized_group_contrasts) if normalized_group_contrasts else "all"
    out_dir = ensure_dir(out)
    normalized_dir = ensure_dir(out_dir / "normalized")
    plot_dir = ensure_dir(out_dir / "plots")

    if mw_data_json is not None:
        mw_data = json.loads(Path(mw_data_json).read_text(encoding="utf-8"))
    else:
        mw_data = fetch_json(f"{MW_BASE_URL}/study/study_id/{mw_study_id}/data")
    if mw_factors_json is not None:
        mw_factors = json.loads(Path(mw_factors_json).read_text(encoding="utf-8"))
    else:
        mw_factors = fetch_json(f"{MW_BASE_URL}/study/study_id/{mw_study_id}/factors")

    mw_rows = compute_mw_volcano_stats(_records(mw_data), _records(mw_factors))
    motrpac_source_rows, motrpac_objects = fetch_motrpac_volcano_stats(
        release=motrpac_release,
        local_da_dir=motrpac_da_dir,
        scope=normalized_motrpac_scope,
        omics_assay_filter=normalized_omics_assay_filter,
    )
    motrpac_rows = prepare_motrpac_plot_rows(motrpac_source_rows, motrpac_plot_contrast_mode)
    motrpac_rows = filter_motrpac_rows_by_group_contrasts(motrpac_rows, normalized_group_contrast_filter)
    comparisons = rank_similarity(mw_rows, motrpac_rows)
    mw_ambiguous_key_count = ambiguous_feature_key_count(mw_rows)
    motrpac_ambiguous_key_count = ambiguous_feature_key_count(motrpac_rows)
    selected_mw_reference_contrast_key = select_mw_reference_contrast_key(
        mw_rows,
        comparisons,
        mw_reference_contrast_key,
    )

    mw_stats_path = write_csv_rows(
        normalized_dir / "mw_volcano_stats.csv",
        mw_rows,
        _csv_fieldnames(
            mw_rows,
            [
                "source",
                "study_id",
                "analysis_id",
                "contrast_key",
                "contrast",
                "feature_id",
                "feature_label",
                "feature_key",
                "logFC",
                "p_value",
                "adj_p_value",
                "n_pairs",
                "assay",
                "tissue",
                "omics",
                "timepoint",
                "exercise_group",
                "sex",
                "palette_source",
            ],
        ),
    )
    write_csv_rows(
        normalized_dir / "motrpac_pre_exercise_volcano_stats.csv",
        motrpac_source_rows,
        _csv_fieldnames(
            motrpac_source_rows,
            [
                "source",
                "release",
                "object",
                "contrast_key",
                "contrast",
                "feature_id",
                "feature_label",
                "feature_key",
                "logFC",
                "p_value",
                "adj_p_value",
                "assay",
                "assay_label",
                "tissue",
                "omics",
                "omics_assay",
                "raw_omics",
                "method",
                "contrast_family",
                "group_contrast",
                "group_a",
                "group_b",
                "timepoint",
                "exercise_group",
                "sex",
                "palette_source",
                "p_value_source",
            ],
        ),
    )
    motrpac_stats_path = write_csv_rows(
        normalized_dir / "motrpac_volcano_stats.csv",
        motrpac_rows,
        _csv_fieldnames(
            motrpac_rows,
            [
                "source",
                "release",
                "object",
                "contrast_key",
                "contrast",
                "feature_id",
                "feature_label",
                "feature_key",
                "logFC",
                "p_value",
                "adj_p_value",
                "assay",
                "assay_label",
                "tissue",
                "omics",
                "omics_assay",
                "raw_omics",
                "method",
                "contrast_family",
                "group_contrast",
                "group_a",
                "group_b",
                "timepoint",
                "exercise_group",
                "sex",
                "palette_source",
                "p_value_source",
            ],
        ),
    )
    similarity_path = write_csv_rows(
        normalized_dir / "comparison_similarity.csv",
        comparisons,
        _csv_fieldnames(
            comparisons,
            [
                "mw_contrast_key",
                "mw_contrast",
                "motrpac_contrast_key",
                "motrpac_contrast",
                "motrpac_tissue",
                "motrpac_assay",
                "motrpac_assay_label",
                "motrpac_omics",
                "motrpac_omics_assay",
                "motrpac_timepoint",
                "motrpac_group_contrast",
                "motrpac_contrast_family",
                "motrpac_p_value_source",
                "overlap_n",
                "mw_ambiguous_feature_key_n",
                "motrpac_ambiguous_feature_key_n",
                "excluded_ambiguous_overlap_n",
                "excluded_ambiguous_overlap_feature_keys",
                "pearson_logFC_r",
                "direction_concordance",
                "screening_similarity_score",
                "overlap_feature_keys",
            ],
        ),
    )
    write_json(normalized_dir / "motrpac_source_objects.json", motrpac_objects)

    plot_paths: list[Path] = []
    plot_error: str | None = None
    if not skip_plots:
        try:
            plot_paths = render_volcano_pngs(
                mw_stats_path,
                motrpac_stats_path,
                similarity_path,
                plot_dir,
                top_n,
                mw_study_id,
                normalized_motrpac_scope,
                normalized_omics_assay_filter,
                normalized_group_contrast_filter,
                selected_mw_reference_contrast_key,
            )
        except Exception as exc:
            plot_error = str(exc)

    report_path = write_text(
        out_dir / "comparison_report.md",
        _report_text(
            mw_study_id,
            mw_rows,
            motrpac_rows,
            motrpac_objects,
            comparisons,
            plot_paths,
            plot_error,
            motrpac_source_row_count=len(motrpac_source_rows),
            motrpac_plot_contrast_mode=motrpac_plot_contrast_mode,
            motrpac_scope=normalized_motrpac_scope,
            motrpac_omics_assay_filter=normalized_omics_assay_filter,
            motrpac_group_contrast_filter=normalized_group_contrast_filter,
            mw_reference_contrast_key=selected_mw_reference_contrast_key,
            mw_ambiguous_feature_key_count=mw_ambiguous_key_count,
            motrpac_ambiguous_feature_key_count=motrpac_ambiguous_key_count,
        ),
    )

    return VolcanoComparisonResult(
        out_dir=out_dir,
        mw_stats_path=mw_stats_path,
        motrpac_stats_path=motrpac_stats_path,
        similarity_path=similarity_path,
        report_path=report_path,
        plot_paths=plot_paths,
        mw_row_count=len(mw_rows),
        motrpac_row_count=len(motrpac_rows),
        comparison_count=len(comparisons),
        mw_ambiguous_feature_key_count=mw_ambiguous_key_count,
        motrpac_ambiguous_feature_key_count=motrpac_ambiguous_key_count,
    )

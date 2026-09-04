"""Deterministic, review-gated metabolomics plot preparation and rendering.

The public functions in this module deliberately separate scientific data
preparation from optional figure rendering.  Every prepared row carries the
contrast, direction, multiple-testing, quality, and palette semantics needed
to review a figure without reverse-engineering plotting code.

No function in this module performs metabolite identity harmonization.  A
cross-study heatmap or hierarchy view only displays rows whose mappings were
explicitly accepted; uncertain mappings remain in the exported table as
review-gated cells.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MIN_PROBABILITY = 1e-300
SCHEMA_VERSION = "metabotyping-plot-bundle/1.0"

# Direction colors use the color-vision-deficiency-friendly Okabe-Ito blue and
# vermillion.  MoTrPAC semantic palettes are retained for explicit study-group
# context and are never inferred from biological expectations.
SIGNIFICANCE_PALETTE = {
    "higher_in_numerator": "#D55E00",
    "lower_in_numerator": "#0072B2",
    "fdr_significant_below_effect_threshold": "#CC79A7",
    "not_selected": "#8C8C8C",
    "not_testable": "#3C3C3C",
}
SIGNIFICANCE_PALETTE_SOURCE = "Okabe-Ito (direction); repository plotting contract v1.0"
EFFECT_DIVERGING_COLORS = ("#0072B2", "#F7F7F7", "#D55E00")
EFFECT_PALETTE_SOURCE = "Okabe-Ito blue/neutral/vermillion diverging palette"

MOTRPAC_GROUP_COLORS = {
    "EE": "#d95f02",
    "RE": "#1b9e77",
    "CON": "#7570b3",
}
MOTRPAC_GROUP_MARKERS = {"EE": "o", "RE": "s", "CON": "^"}
MOTRPAC_GROUP_LINESTYLES = {"EE": "-", "RE": "--", "CON": ":"}
MOTRPAC_GROUP_PALETTE_SOURCE = (
    "MoTrPAC HUMAN_EXERCISE_GROUP_COLORS aliases in motrpac_plot_helpers.R"
)

ACCEPTED_MAPPING_STATUSES = frozenset(
    {"accepted", "reviewed_accepted", "exact_identity"}
)
ACCEPTED_ANNOTATION_STATUSES = frozenset(
    {"accepted", "reviewed_accepted", "curator_accepted", "accepted_curated"}
)
HIERARCHY_LEVELS = (
    "pathway",
    "sub_class",
    "main_class",
    "super_class",
)
HIERARCHY_COLUMN_ALIASES = {
    "pathway": ("pathway",),
    "sub_class": ("sub_class", "subclass"),
    "main_class": ("main_class", "class"),
    "super_class": ("super_class", "superclass"),
}
DEFAULT_MISSINGNESS_THRESHOLD = 0.20
DEFAULT_BELOW_LOD_THRESHOLD = 0.20
MISSING_TOKENS = frozenset({"", "na", "nan", "none", "null", "not_reported", "unknown"})


class PlotValidationError(ValueError):
    """Raised when plot semantics are ambiguous or scientifically unsafe."""


@dataclass(frozen=True)
class ContrastMetadata:
    """Explicit semantics for one differential-analysis contrast.

    ``effect_scale`` describes the numeric effect already present in the input;
    this module never silently converts between fold change, model coefficients,
    standardized effects, or other scales.
    """

    contrast_id: str
    numerator_label: str
    denominator_label: str
    effect_scale: str
    fdr_method: str
    fdr_scope: str
    source_study_id: str
    source_dataset_id: str
    alpha: float = 0.05
    effect_threshold: float = 0.0
    effect_column: str = "effect"
    p_value_column: str = "p_value"
    fdr_column: str = "fdr"
    feature_id_column: str = "feature_id"
    tissue: str = "not_reported"
    omics: str = "metabolomics"
    assay: str = "not_reported"
    platform: str = "not_reported"
    exercise_group: str = ""
    sex: str = ""
    display_order: int = 0

    def __post_init__(self) -> None:
        required = {
            "contrast_id": self.contrast_id,
            "numerator_label": self.numerator_label,
            "denominator_label": self.denominator_label,
            "effect_scale": self.effect_scale,
            "fdr_method": self.fdr_method,
            "fdr_scope": self.fdr_scope,
            "source_study_id": self.source_study_id,
            "source_dataset_id": self.source_dataset_id,
        }
        missing = [name for name, value in required.items() if not _text(value)]
        if missing:
            raise PlotValidationError(
                "Contrast metadata is missing explicit fields: " + ", ".join(missing)
            )
        if _text(self.numerator_label) == _text(self.denominator_label):
            raise PlotValidationError("Contrast numerator and denominator must differ.")
        if not 0 < float(self.alpha) < 1:
            raise PlotValidationError("alpha must be strictly between 0 and 1.")
        if float(self.effect_threshold) < 0:
            raise PlotValidationError("effect_threshold must be non-negative.")
        if self.exercise_group and self.exercise_group not in MOTRPAC_GROUP_COLORS:
            raise PlotValidationError(
                "exercise_group must be an explicit EE, RE, or CON mapping; "
                f"received {self.exercise_group!r}."
            )

    @property
    def direction_statement(self) -> str:
        return (
            f"positive {self.effect_scale} = {self.numerator_label} higher than "
            f"{self.denominator_label}; negative = lower"
        )

    @property
    def fdr_statement(self) -> str:
        return (
            f"selection uses {self.fdr_column} <= {self.alpha:g}; "
            f"{self.fdr_method} adjustment over {self.fdr_scope}; "
            f"{self.p_value_column} is unadjusted"
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["direction_statement"] = self.direction_statement
        value["fdr_statement"] = self.fdr_statement
        return value


@dataclass(frozen=True)
class TrajectoryMetadata:
    """Explicit design and summarization rules for a single-feature trajectory."""

    feature_id: str
    value_scale: str
    timepoint_order: tuple[str, ...]
    source_study_id: str
    source_dataset_id: str
    group_order: tuple[str, ...] = ()
    lod_policy: str = "exclude_flagged"
    missingness_threshold: float = DEFAULT_MISSINGNESS_THRESHOLD
    below_lod_threshold: float = DEFAULT_BELOW_LOD_THRESHOLD

    def __post_init__(self) -> None:
        if not all(
            _text(value)
            for value in (
                self.feature_id,
                self.value_scale,
                self.source_study_id,
                self.source_dataset_id,
            )
        ):
            raise PlotValidationError(
                "Trajectory metadata requires feature, scale, study, and dataset identifiers."
            )
        if not self.timepoint_order or any(not _text(value) for value in self.timepoint_order):
            raise PlotValidationError("timepoint_order must be explicit and non-empty.")
        if len(set(self.timepoint_order)) != len(self.timepoint_order):
            raise PlotValidationError("timepoint_order contains duplicate labels.")
        if self.group_order and len(set(self.group_order)) != len(self.group_order):
            raise PlotValidationError("group_order contains duplicate labels.")
        if self.lod_policy not in {"exclude_flagged", "as_reported"}:
            raise PlotValidationError("lod_policy must be 'exclude_flagged' or 'as_reported'.")
        _validate_fraction(self.missingness_threshold, "missingness_threshold")
        _validate_fraction(self.below_lod_threshold, "below_lod_threshold")


@dataclass(frozen=True)
class AggregationRules:
    """Coverage and quality gates for descriptive hierarchy summaries."""

    method: str = "median_unweighted_canonical_features"
    min_features: int = 3
    min_coverage: float = 0.50
    missingness_threshold: float = DEFAULT_MISSINGNESS_THRESHOLD
    below_lod_threshold: float = DEFAULT_BELOW_LOD_THRESHOLD

    def __post_init__(self) -> None:
        if self.method != "median_unweighted_canonical_features":
            raise PlotValidationError(
                "Only median_unweighted_canonical_features is supported; combining assay "
                "precision weights requires a reviewed model outside the plotting layer."
            )
        if self.min_features < 1:
            raise PlotValidationError("min_features must be at least one.")
        _validate_fraction(self.min_coverage, "min_coverage")
        _validate_fraction(self.missingness_threshold, "missingness_threshold")
        _validate_fraction(self.below_lod_threshold, "below_lod_threshold")


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in MISSING_TOKENS else text


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _probability(value: Any, field: str) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if not 0 <= number <= 1:
        raise PlotValidationError(f"{field} values must be between 0 and 1; received {value!r}.")
    return number


def _validate_fraction(value: float, field: str) -> None:
    if not 0 <= float(value) <= 1:
        raise PlotValidationError(f"{field} must be between 0 and 1.")


def _optional_fraction(value: Any, field: str) -> float | None:
    number = _float(value)
    if number is None:
        return None
    _validate_fraction(number, field)
    return number


def benjamini_hochberg(p_values: Sequence[float | None]) -> list[float | None]:
    """Return NaN-safe Benjamini-Hochberg adjusted p-values in input order."""

    valid = [(index, value) for index, value in enumerate(p_values) if value is not None]
    output: list[float | None] = [None] * len(p_values)
    if not valid:
        return output
    for _, value in valid:
        if value is None or not 0 <= value <= 1:
            raise PlotValidationError("BH input p-values must be between zero and one.")
    ranked = sorted(valid, key=lambda item: (item[1], item[0]))
    running = 1.0
    adjusted: dict[int, float] = {}
    total = len(ranked)
    for reverse_rank in range(total - 1, -1, -1):
        original_index, p_value = ranked[reverse_rank]
        rank = reverse_rank + 1
        running = min(running, float(p_value) * total / rank)
        adjusted[original_index] = min(1.0, running)
    for index, value in adjusted.items():
        output[index] = value
    return output


def _quality_flags(
    row: Mapping[str, Any],
    *,
    missingness_threshold: float = DEFAULT_MISSINGNESS_THRESHOLD,
    below_lod_threshold: float = DEFAULT_BELOW_LOD_THRESHOLD,
) -> tuple[list[str], float | None, float | None]:
    missing = _optional_fraction(row.get("missing_fraction"), "missing_fraction")
    below_lod = _optional_fraction(row.get("below_lod_fraction"), "below_lod_fraction")
    flags: list[str] = []
    if missing is None:
        flags.append("missingness_not_reported")
    elif missing > missingness_threshold:
        flags.append("high_missingness")
    if below_lod is None:
        flags.append("lod_not_reported")
    elif below_lod > below_lod_threshold:
        flags.append("high_below_lod")
    return flags, missing, below_lod


def _mapping_is_accepted(row: Mapping[str, Any]) -> bool:
    return _text(row.get("mapping_status")).lower() in ACCEPTED_MAPPING_STATUSES


def annotation_is_accepted(row: Mapping[str, Any]) -> bool:
    """Return whether a RefMet annotation row is accepted for hierarchy use."""

    status = _text(row.get("annotation_status")).lower()
    if status:
        return status in ACCEPTED_ANNOTATION_STATUSES
    # Compatibility with existing metabolite-effect-search plot-ready rows.
    # This fallback is deliberately narrow: accepted effect-name matching alone
    # is not treated as evidence for a RefMet hierarchy assignment.
    review_status = _text(row.get("review_status")).lower()
    match_basis = _text(row.get("match_basis")).lower()
    return review_status == "accepted_curated" or match_basis in {
        "refmet_curated_annotation",
        "refmet_hierarchy_annotation",
        "refmet_curated_class",
    }


def hierarchy_value(row: Mapping[str, Any], level: str) -> str:
    """Read one canonical RefMet level while rejecting conflicting aliases."""

    values = {
        _text(row.get(column))
        for column in HIERARCHY_COLUMN_ALIASES[level]
        if _text(row.get(column))
    }
    if len(values) > 1:
        raise PlotValidationError(
            f"Conflicting values supplied for canonical hierarchy field {level!r}: "
            + ", ".join(sorted(values))
        )
    return next(iter(values), "")


# Private aliases retained for existing call sites and tests. The public
# names above are what the analysis package imports.
_annotation_is_accepted = annotation_is_accepted
_hierarchy_value = hierarchy_value


def _normalise_contrasts(
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
) -> dict[str, ContrastMetadata]:
    values = list(contrasts.values()) if isinstance(contrasts, Mapping) else list(contrasts)
    by_id: dict[str, ContrastMetadata] = {}
    for metadata in values:
        if not isinstance(metadata, ContrastMetadata):
            raise PlotValidationError("contrasts must contain ContrastMetadata objects.")
        if metadata.contrast_id in by_id:
            raise PlotValidationError(f"Duplicate contrast metadata for {metadata.contrast_id!r}.")
        by_id[metadata.contrast_id] = metadata
    if not by_id:
        raise PlotValidationError("At least one contrast is required.")
    return by_id


def prepare_volcano_data(
    rows: Iterable[Mapping[str, Any]],
    metadata: ContrastMetadata,
    *,
    compute_missing_bh: bool = True,
    missingness_threshold: float = DEFAULT_MISSINGNESS_THRESHOLD,
    below_lod_threshold: float = DEFAULT_BELOW_LOD_THRESHOLD,
) -> list[dict[str, Any]]:
    """Prepare one reviewable volcano table with explicit FDR/direction semantics.

    If *all* adjusted values are absent and the declared adjustment is
    Benjamini-Hochberg, FDR is computed over exactly the supplied rows.  Partial
    adjusted-value columns are never filled because mixing adjustment scopes is
    unsafe.  A feature identifier may appear only once per contrast: duplicate
    rows are usually a second platform, sex stratum, or isomer that belongs in
    its own facet, and plotting them together double-counts the feature.
    """

    raw_rows = [dict(row) for row in rows]
    if not raw_rows:
        return []
    p_values = [
        _probability(row.get(metadata.p_value_column), metadata.p_value_column)
        for row in raw_rows
    ]
    supplied_fdr = [
        _probability(row.get(metadata.fdr_column), metadata.fdr_column)
        for row in raw_rows
    ]
    valid_fdr_count = sum(value is not None for value in supplied_fdr)
    fdr_source = "provided"
    if valid_fdr_count == 0 and compute_missing_bh:
        method_key = re.sub(r"[^a-z]", "", metadata.fdr_method.lower())
        if method_key not in {"bh", "benjaminihochberg"}:
            raise PlotValidationError(
                "Adjusted values are absent and automatic computation is limited to "
                "explicit Benjamini-Hochberg metadata."
            )
        supplied_fdr = benjamini_hochberg(p_values)
        fdr_source = "computed_bh_over_supplied_rows"
    elif 0 < valid_fdr_count < len(raw_rows):
        fdr_source = "provided_partial_no_imputation"

    prepared: list[dict[str, Any]] = []
    seen_feature_ids: set[str] = set()
    for input_order, (row, p_value, fdr) in enumerate(
        zip(raw_rows, p_values, supplied_fdr, strict=True), start=1
    ):
        feature_id = _text(row.get(metadata.feature_id_column))
        if not feature_id:
            raise PlotValidationError(
                f"Every volcano row requires {metadata.feature_id_column!r}; "
                f"row {input_order} is blank."
            )
        if feature_id in seen_feature_ids:
            raise PlotValidationError(
                f"Duplicate feature_id {feature_id!r} within contrast "
                f"{metadata.contrast_id!r}; facet by assay/platform, sex, or stratum, "
                "or disambiguate features before plotting."
            )
        seen_feature_ids.add(feature_id)
        row_contrast = _text(row.get("contrast_id"))
        if row_contrast and row_contrast != metadata.contrast_id:
            raise PlotValidationError(
                f"Row contrast {row_contrast!r} does not match {metadata.contrast_id!r}."
            )
        explicit_canonical_id = _text(row.get("canonical_feature_id"))
        effect = _float(row.get(metadata.effect_column))
        flags, missing_fraction, below_lod_fraction = _quality_flags(
            row,
            missingness_threshold=missingness_threshold,
            below_lod_threshold=below_lod_threshold,
        )
        if effect is None or fdr is None:
            selection = "not_testable"
        elif fdr <= metadata.alpha and effect >= metadata.effect_threshold and effect > 0:
            selection = "higher_in_numerator"
        elif fdr <= metadata.alpha and effect <= -metadata.effect_threshold and effect < 0:
            selection = "lower_in_numerator"
        elif fdr <= metadata.alpha:
            selection = "fdr_significant_below_effect_threshold"
        else:
            selection = "not_selected"
        if "high_missingness" in flags or "high_below_lod" in flags:
            flags.append("interpret_with_quality_caution")

        output = dict(row)
        output.update(
            {
                "feature_id": feature_id,
                "feature_label": _text(row.get("feature_label")) or feature_id,
                "canonical_feature_id": explicit_canonical_id or feature_id,
                "canonical_id_source": (
                    "explicit_reviewed_mapping"
                    if explicit_canonical_id
                    else "source_feature_id_fallback"
                ),
                "contrast_id": metadata.contrast_id,
                "numerator_label": metadata.numerator_label,
                "denominator_label": metadata.denominator_label,
                "effect": effect,
                "effect_scale": metadata.effect_scale,
                "direction_statement": metadata.direction_statement,
                "p_value": p_value,
                "fdr": fdr,
                "fdr_method": metadata.fdr_method,
                "fdr_scope": metadata.fdr_scope,
                "fdr_statement": metadata.fdr_statement,
                "fdr_source": fdr_source,
                "fdr_test_count": sum(value is not None for value in p_values),
                "neg_log10_p": (
                    -math.log10(max(p_value, MIN_PROBABILITY)) if p_value is not None else None
                ),
                "neg_log10_fdr": (
                    -math.log10(max(fdr, MIN_PROBABILITY)) if fdr is not None else None
                ),
                "alpha": metadata.alpha,
                "effect_threshold": metadata.effect_threshold,
                "selection_status": selection,
                "color_hex": SIGNIFICANCE_PALETTE[selection],
                "palette_source": SIGNIFICANCE_PALETTE_SOURCE,
                "missing_fraction": missing_fraction,
                "below_lod_fraction": below_lod_fraction,
                "quality_flags": ";".join(flags) if flags else "none",
                "source_study_id": _text(row.get("source_study_id")) or metadata.source_study_id,
                "source_dataset_id": (
                    _text(row.get("source_dataset_id")) or metadata.source_dataset_id
                ),
                "tissue": _text(row.get("tissue")) or metadata.tissue,
                "omics": _text(row.get("omics")) or metadata.omics,
                "assay": _text(row.get("assay")) or metadata.assay,
                "platform": _text(row.get("platform")) or metadata.platform,
                "exercise_group": _text(row.get("exercise_group")) or metadata.exercise_group,
                "sex": _text(row.get("sex")) or metadata.sex,
                "input_order": input_order,
            }
        )
        prepared.append(output)

    priority = {
        "higher_in_numerator": 0,
        "lower_in_numerator": 1,
        "fdr_significant_below_effect_threshold": 2,
        "not_selected": 3,
        "not_testable": 4,
    }
    prepared.sort(
        key=lambda row: (
            priority[row["selection_status"]],
            row["fdr"] if row["fdr"] is not None else math.inf,
            -(abs(row["effect"]) if row["effect"] is not None else -1),
            row["feature_id"].casefold(),
            row["input_order"],
        )
    )
    for display_order, row in enumerate(prepared, start=1):
        row["display_order"] = display_order
    return prepared


def _prepare_effect_rows(
    rows: Iterable[Mapping[str, Any]],
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
) -> tuple[list[dict[str, Any]], dict[str, ContrastMetadata]]:
    by_id = _normalise_contrasts(contrasts)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        contrast_id = _text(row.get("contrast_id"))
        if not contrast_id:
            raise PlotValidationError("Every multi-contrast effect row requires contrast_id.")
        if contrast_id not in by_id:
            raise PlotValidationError(f"No contrast metadata supplied for {contrast_id!r}.")
        grouped[contrast_id].append(row)
    prepared: list[dict[str, Any]] = []
    for contrast_id in sorted(grouped, key=lambda value: (by_id[value].display_order, value)):
        prepared.extend(prepare_volcano_data(grouped[contrast_id], by_id[contrast_id]))
    return prepared, by_id


def prepare_effect_heatmap_data(
    rows: Iterable[Mapping[str, Any]],
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
    *,
    feature_order: Sequence[str] | None = None,
    contrast_order: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Create a complete, stably ordered feature-by-contrast effect grid.

    Cross-dataset cells require both a canonical identifier and an accepted
    mapping status.  Unreviewed cells are exported with ``heatmap_value=None``
    instead of being visually presented as harmonized evidence.
    """

    prepared, by_id = _prepare_effect_rows(rows, contrasts)
    effect_scales = {row["effect_scale"] for row in prepared}
    if len(effect_scales) > 1:
        raise PlotValidationError(
            "One heatmap cannot mix effect scales without an explicit reviewed standardization."
        )
    dataset_ids = {row["source_dataset_id"] for row in prepared if row["source_dataset_id"]}
    cross_dataset = len(dataset_ids) > 1
    if contrast_order is None:
        ordered_contrasts = sorted(by_id, key=lambda value: (by_id[value].display_order, value))
    else:
        ordered_contrasts = list(contrast_order)
        if len(set(ordered_contrasts)) != len(ordered_contrasts):
            raise PlotValidationError("contrast_order contains duplicates.")
        if set(ordered_contrasts) != set(by_id):
            raise PlotValidationError(
                "contrast_order must contain every supplied contrast exactly once."
            )

    observed_features = {
        _text(row.get("canonical_feature_id")) or row["feature_id"] for row in prepared
    }
    if feature_order is None:
        ordered_features = sorted(observed_features, key=str.casefold)
    else:
        ordered_features = list(feature_order)
        if len(set(ordered_features)) != len(ordered_features):
            raise PlotValidationError("feature_order contains duplicates.")
        missing_features = observed_features - set(ordered_features)
        if missing_features:
            raise PlotValidationError(
                "feature_order omits observed canonical features: "
                + ", ".join(sorted(missing_features))
            )

    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for row in prepared:
        canonical = _text(row.get("canonical_feature_id")) or row["feature_id"]
        key = (canonical, row["contrast_id"])
        if key in cells:
            raise PlotValidationError(
                "Duplicate heatmap cell for canonical feature and contrast "
                f"{key}; facet by assay/platform or resolve duplicates before plotting."
            )
        mapping_ok = not cross_dataset or (
            row.get("canonical_id_source") == "explicit_reviewed_mapping"
            and _mapping_is_accepted(row)
        )
        if not mapping_ok:
            status = "unreviewed_harmonization"
            heatmap_value = None
        elif row["effect"] is None:
            status = "effect_not_reported"
            heatmap_value = None
        elif "high_missingness" in row["quality_flags"]:
            status = "high_missingness"
            heatmap_value = row["effect"]
        elif "high_below_lod" in row["quality_flags"]:
            status = "high_below_lod"
            heatmap_value = row["effect"]
        else:
            status = "observed"
            heatmap_value = row["effect"]
        cell = dict(row)
        cell.update(
            {
                "canonical_feature_id": canonical,
                "heatmap_value": heatmap_value,
                "cell_status": status,
                "cross_dataset_view": cross_dataset,
                "harmonization_statement": (
                    "cross-dataset cells require an accepted canonical mapping"
                    if cross_dataset
                    else "single-dataset identity; no cross-study harmonization claimed"
                ),
                "effect_palette_source": EFFECT_PALETTE_SOURCE,
            }
        )
        cells[key] = cell

    output: list[dict[str, Any]] = []
    for feature_index, feature_id in enumerate(ordered_features, start=1):
        for contrast_index, contrast_id in enumerate(ordered_contrasts, start=1):
            key = (feature_id, contrast_id)
            if key in cells:
                cell = cells[key]
            else:
                metadata = by_id[contrast_id]
                cell = {
                    "feature_id": feature_id,
                    "feature_label": feature_id,
                    "canonical_feature_id": feature_id,
                    "contrast_id": contrast_id,
                    "numerator_label": metadata.numerator_label,
                    "denominator_label": metadata.denominator_label,
                    "effect": None,
                    "effect_scale": metadata.effect_scale,
                    "direction_statement": metadata.direction_statement,
                    "p_value": None,
                    "fdr": None,
                    "heatmap_value": None,
                    "cell_status": "not_reported",
                    "quality_flags": "not_reported",
                    "source_study_id": metadata.source_study_id,
                    "source_dataset_id": metadata.source_dataset_id,
                    "cross_dataset_view": cross_dataset,
                    "harmonization_statement": (
                        "cross-dataset cells require an accepted canonical mapping"
                        if cross_dataset
                        else "single-dataset identity; no cross-study harmonization claimed"
                    ),
                    "effect_palette_source": EFFECT_PALETTE_SOURCE,
                }
            cell["feature_order"] = feature_index
            cell["contrast_order"] = contrast_index
            output.append(cell)
    return output


def prepare_single_feature_effect_data(
    rows: Iterable[Mapping[str, Any]],
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
    canonical_feature_id: str,
) -> list[dict[str, Any]]:
    """Return stably ordered effect/CI rows for one reviewed canonical feature."""

    prepared, by_id = _prepare_effect_rows(rows, contrasts)
    selected = [
        row
        for row in prepared
        if (_text(row.get("canonical_feature_id")) or row["feature_id"]) == canonical_feature_id
    ]
    for row in selected:
        ci_low = _float(row.get("ci_low"))
        ci_high = _float(row.get("ci_high"))
        if (ci_low is None) != (ci_high is None):
            raise PlotValidationError(
                "Both ci_low and ci_high are required when either is supplied."
            )
        if ci_low is not None and ci_high is not None and ci_low > ci_high:
            raise PlotValidationError("ci_low cannot exceed ci_high.")
        row["ci_low"] = ci_low
        row["ci_high"] = ci_high
        row["ci_semantics"] = (
            _text(row.get("ci_semantics")) or "not_reported; no interval inferred by plotting layer"
        )
        row["single_feature_inference"] = "feature-level source model; no cross-contrast pooling"
    selected.sort(key=lambda row: (by_id[row["contrast_id"]].display_order, row["contrast_id"]))
    for order, row in enumerate(selected, start=1):
        row["contrast_order"] = order
    return selected


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def prepare_single_feature_trajectory_data(
    observations: Iterable[Mapping[str, Any]],
    metadata: TrajectoryMetadata,
) -> list[dict[str, Any]]:
    """Summarize one feature by explicit group/timepoint without imputation.

    Missingness denominators are the explicit input rows in each cell.  Planned
    samples absent from the input cannot be counted and this limitation is
    retained in ``missingness_denominator``.
    """

    selected: list[dict[str, Any]] = []
    seen_subject_cells: set[tuple[str, str, str]] = set()
    for row in observations:
        row_feature = _text(row.get("canonical_feature_id")) or _text(row.get("feature_id"))
        if row_feature != metadata.feature_id:
            continue
        timepoint = _text(row.get("timepoint"))
        if timepoint not in metadata.timepoint_order:
            raise PlotValidationError(
                f"Trajectory row has timepoint {timepoint!r} outside the explicit order."
            )
        group = _text(row.get("exercise_group")) or "all_participants"
        if metadata.group_order and group not in metadata.group_order:
            raise PlotValidationError(
                f"Trajectory row has group {group!r} outside the explicit group order."
            )
        participant_id = _text(row.get("participant_id"))
        if participant_id:
            key = (participant_id, group, timepoint)
            if key in seen_subject_cells:
                raise PlotValidationError(
                    "Duplicate participant/group/timepoint trajectory observation; summarize "
                    "technical replicates before plotting."
                )
            seen_subject_cells.add(key)
        selected.append(dict(row, _timepoint=timepoint, _group=group))

    groups = list(metadata.group_order) if metadata.group_order else sorted(
        {_text(row["_group"]) for row in selected}, key=str.casefold
    )
    if not groups:
        groups = ["all_participants"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        grouped[(row["_group"], row["_timepoint"])].append(row)

    output: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups, start=1):
        for time_index, timepoint in enumerate(metadata.timepoint_order, start=1):
            cell = grouped.get((group, timepoint), [])
            values: list[float] = []
            missing_count = 0
            below_lod_count = 0
            for row in cell:
                value = _float(row.get("value"))
                lod = _float(row.get("lod"))
                below_lod = _parse_bool(row.get("below_lod")) or (
                    value is not None and lod is not None and value < lod
                )
                if below_lod:
                    below_lod_count += 1
                if value is None:
                    missing_count += 1
                elif below_lod and metadata.lod_policy == "exclude_flagged":
                    continue
                else:
                    values.append(value)
            n_total = len(cell)
            n_observed = len(values)
            missing_fraction = missing_count / n_total if n_total else None
            below_lod_fraction = below_lod_count / n_total if n_total else None
            flags: list[str] = []
            if n_total == 0:
                flags.append("not_reported")
            if missing_fraction is not None and missing_fraction > metadata.missingness_threshold:
                flags.append("high_missingness")
            if below_lod_fraction is not None and below_lod_fraction > metadata.below_lod_threshold:
                flags.append("high_below_lod")
            if not any(_float(row.get("lod")) is not None for row in cell):
                flags.append("lod_not_reported")
            mean = statistics.fmean(values) if values else None
            sd = statistics.stdev(values) if len(values) > 1 else None
            se = sd / math.sqrt(len(values)) if sd is not None else None
            palette_source = (
                MOTRPAC_GROUP_PALETTE_SOURCE
                if group in MOTRPAC_GROUP_COLORS
                else "neutral; no explicit MoTrPAC group mapping"
            )
            output.append(
                {
                    "feature_id": metadata.feature_id,
                    "canonical_feature_id": metadata.feature_id,
                    "exercise_group": group,
                    "timepoint": timepoint,
                    "group_order": group_index,
                    "timepoint_order": time_index,
                    "n_input_rows": n_total,
                    "n_observed": n_observed,
                    "n_missing": missing_count,
                    "n_below_lod": below_lod_count,
                    "missing_fraction": missing_fraction,
                    "below_lod_fraction": below_lod_fraction,
                    "mean": mean,
                    "sd": sd,
                    "se": se,
                    "median": statistics.median(values) if values else None,
                    "q1": _quantile(values, 0.25),
                    "q3": _quantile(values, 0.75),
                    "value_scale": metadata.value_scale,
                    "lod_policy": metadata.lod_policy,
                    "summary_rule": "arithmetic mean and SE plus median/IQR; no imputation",
                    "trajectory_inference": "descriptive; no longitudinal model fitted",
                    "missingness_denominator": (
                        "explicit input rows in group/timepoint; absent planned samples not counted"
                    ),
                    "quality_flags": ";".join(flags) if flags else "none",
                    "color_hex": MOTRPAC_GROUP_COLORS.get(group, "#666666"),
                    "marker": MOTRPAC_GROUP_MARKERS.get(group, "o"),
                    "line_style": MOTRPAC_GROUP_LINESTYLES.get(group, "-"),
                    "palette_source": palette_source,
                    "source_study_id": metadata.source_study_id,
                    "source_dataset_id": metadata.source_dataset_id,
                }
            )
    return output


def prepare_hierarchy_aggregate_data(
    rows: Iterable[Mapping[str, Any]],
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
    level: str,
    *,
    expected_members: Mapping[str, Sequence[str]] | None,
    rules: AggregationRules | None = None,
) -> list[dict[str, Any]]:
    """Create descriptive pathway/class aggregates with explicit coverage gates.

    The aggregation unit is one accepted canonical metabolite per contrast.
    Feature p-values/FDR values are summarized as proportions only; no category
    p-value is invented because metabolites are dependent and assay/platform
    effects are not modeled by this plotting layer.
    """

    if level not in HIERARCHY_LEVELS:
        raise PlotValidationError(
            f"Unsupported hierarchy level {level!r}; expected one of {HIERARCHY_LEVELS}."
        )
    rules = rules or AggregationRules()
    prepared, by_id = _prepare_effect_rows(rows, contrasts)
    source_datasets = {
        row["source_dataset_id"] for row in prepared if _text(row.get("source_dataset_id"))
    }
    cross_dataset = len(source_datasets) > 1
    expected: dict[str, set[str]] | None = None
    if expected_members is not None:
        expected = {}
        for category, members in expected_members.items():
            if isinstance(members, (str, bytes)):
                raise PlotValidationError(
                    "Expected hierarchy members must be a sequence of feature identifiers, "
                    "not one string."
                )
            clean_category = _text(category)
            clean_members = {_text(member) for member in members if _text(member)}
            if not clean_category or not clean_members:
                raise PlotValidationError("Expected hierarchy membership cannot contain blanks.")
            expected[clean_category] = clean_members

    categories = set(expected or {})
    categories.update(
        _hierarchy_value(row, level)
        for row in prepared
        if _hierarchy_value(row, level)
    )
    if not categories:
        return []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    exclusion_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    seen: set[tuple[str, str, str]] = set()
    for row in prepared:
        category = _hierarchy_value(row, level)
        if not category:
            continue
        key = (row["contrast_id"], category)
        if cross_dataset and (
            row.get("canonical_id_source") != "explicit_reviewed_mapping"
            or not _mapping_is_accepted(row)
        ):
            exclusion_counts[key]["unreviewed_mapping"] += 1
            continue
        if not _annotation_is_accepted(row):
            exclusion_counts[key]["unreviewed_annotation"] += 1
            continue
        canonical = _text(row.get("canonical_feature_id")) or row["feature_id"]
        if expected is not None and category in expected and canonical not in expected[category]:
            raise PlotValidationError(
                f"Accepted feature {canonical!r} is absent from the expected universe for "
                f"{level}={category!r}."
            )
        dedupe_key = (row["contrast_id"], category, canonical)
        if dedupe_key in seen:
            raise PlotValidationError(
                "Duplicate canonical metabolite within a hierarchy/contrast; resolve assay "
                "duplicates before descriptive aggregation."
            )
        seen.add(dedupe_key)
        quality = row["quality_flags"]
        if "high_missingness" in quality:
            exclusion_counts[key]["high_missingness"] += 1
            continue
        if "high_below_lod" in quality:
            exclusion_counts[key]["high_below_lod"] += 1
            continue
        if row["effect"] is None:
            exclusion_counts[key]["effect_not_reported"] += 1
            continue
        grouped[key].append(dict(row, _canonical=canonical))

    ordered_contrasts = sorted(by_id, key=lambda value: (by_id[value].display_order, value))
    output: list[dict[str, Any]] = []
    for category_index, category in enumerate(sorted(categories, key=str.casefold), start=1):
        for contrast_index, contrast_id in enumerate(ordered_contrasts, start=1):
            cell = grouped.get((contrast_id, category), [])
            scales = {row["effect_scale"] for row in cell}
            if len(scales) > 1:
                raise PlotValidationError(
                    f"Cannot aggregate mixed effect scales in {level}={category!r}."
                )
            values = [float(row["effect"]) for row in cell]
            observed = {row["_canonical"] for row in cell}
            expected_set = expected.get(category) if expected is not None else None
            expected_count = len(expected_set) if expected_set is not None else None
            coverage = len(observed) / expected_count if expected_count else None
            if len(observed) < rules.min_features:
                status = "insufficient_feature_count"
            elif expected_count is None:
                status = "coverage_denominator_unknown"
            elif coverage is not None and coverage < rules.min_coverage:
                status = "insufficient_coverage"
            else:
                status = "eligible_descriptive_summary"
            up_count = sum(value > 0 for value in values)
            down_count = sum(value < 0 for value in values)
            nonzero_count = up_count + down_count
            significant_count = sum(
                row["fdr"] is not None and row["fdr"] <= by_id[contrast_id].alpha for row in cell
            )
            assays = sorted({_text(row.get("assay")) for row in cell if _text(row.get("assay"))})
            platforms = sorted(
                {_text(row.get("platform")) for row in cell if _text(row.get("platform"))}
            )
            exclusions = exclusion_counts[(contrast_id, category)]
            output.append(
                {
                    "hierarchy_level": level,
                    "category": category,
                    "category_order": category_index,
                    "contrast_id": contrast_id,
                    "contrast_order": contrast_index,
                    "aggregate_effect": statistics.median(values) if values else None,
                    "q1_effect": _quantile(values, 0.25),
                    "q3_effect": _quantile(values, 0.75),
                    "effect_scale": (
                        next(iter(scales)) if scales else by_id[contrast_id].effect_scale
                    ),
                    "observed_feature_count": len(observed),
                    "expected_feature_count": expected_count,
                    "coverage_fraction": coverage,
                    "coverage_rule": (
                        f">={rules.min_features} accepted canonical features and coverage "
                        f">={rules.min_coverage:g} against an explicit expected universe"
                    ),
                    "aggregate_status": status,
                    "up_feature_count": up_count,
                    "down_feature_count": down_count,
                    "sign_concordance": (
                        max(up_count, down_count) / nonzero_count if nonzero_count else None
                    ),
                    "fdr_significant_feature_count": significant_count,
                    "fdr_significant_fraction": (
                        significant_count / len(cell) if cell else None
                    ),
                    "excluded_unreviewed_annotation_count": exclusions.get(
                        "unreviewed_annotation", 0
                    ),
                    "excluded_unreviewed_mapping_count": exclusions.get(
                        "unreviewed_mapping", 0
                    ),
                    "excluded_high_missingness_count": exclusions.get("high_missingness", 0),
                    "excluded_high_below_lod_count": exclusions.get("high_below_lod", 0),
                    "excluded_missing_effect_count": exclusions.get("effect_not_reported", 0),
                    "aggregation_rule": rules.method,
                    "assays": ";".join(assays),
                    "assay_count": len(assays),
                    "platforms": ";".join(platforms),
                    "platform_count": len(platforms),
                    "cross_platform_summary": len(assays) > 1 or len(platforms) > 1,
                    "aggregate_inference": (
                        "descriptive median across accepted canonical features; dependence and "
                        "platform effects not modeled; no aggregate p-value or FDR; this is not "
                        "the RefMet over-representation enrichment analysis"
                    ),
                    "direction_statement": by_id[contrast_id].direction_statement,
                    "effect_palette_source": EFFECT_PALETTE_SOURCE,
                    "source_study_id": by_id[contrast_id].source_study_id,
                    "source_dataset_id": by_id[contrast_id].source_dataset_id,
                }
            )
    return output


def prepare_all_hierarchy_views(
    rows: Iterable[Mapping[str, Any]],
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
    *,
    expected_members: Mapping[str, Mapping[str, Sequence[str]]] | None,
    rules: AggregationRules | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Prepare pathway, class, subclass, and superclass tables using one rule set."""

    materialized = [dict(row) for row in rows]
    return {
        level: prepare_hierarchy_aggregate_data(
            materialized,
            contrasts,
            level,
            expected_members=(expected_members or {}).get(level),
            rules=rules,
        )
        for level in HIERARCHY_LEVELS
    }


def _stable_fieldnames(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    priority = [
        "feature_id",
        "feature_label",
        "canonical_feature_id",
        "contrast_id",
        "hierarchy_level",
        "category",
        "exercise_group",
        "timepoint",
        "effect",
        "aggregate_effect",
        "p_value",
        "fdr",
        "source_study_id",
        "source_dataset_id",
    ]
    keys = {key for row in rows for key in row}
    return [key for key in priority if key in keys] + sorted(keys - set(priority))


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple, set)):
        return ";".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_plot_bundle(
    tables: Mapping[str, Sequence[Mapping[str, Any]]],
    output_dir: str | Path,
    provenance: Mapping[str, Any],
    *,
    figure_paths: Mapping[str, str | Path] | None = None,
) -> dict[str, Path]:
    """Write stable plot-ready CSV tables plus a checksummed provenance manifest."""

    required_provenance = {"analysis_id", "input_artifacts", "synthetic_data", "software_version"}
    missing = sorted(key for key in required_provenance if key not in provenance)
    if missing:
        raise PlotValidationError(
            "Plot bundle provenance is missing required fields: " + ", ".join(missing)
        )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for name in sorted(tables):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise PlotValidationError(f"Unsafe plot table name {name!r}.")
        rows = [dict(row) for row in tables[name]]
        path = output_path / f"{name}.csv"
        fieldnames = _stable_fieldnames(rows)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
        paths[name] = path
        artifacts[name] = {
            "path": path.name,
            "artifact_kind": "plot_ready_data",
            "media_type": "text/csv",
            "row_count": len(rows),
            "columns": fieldnames,
            "sha256": _sha256(path),
        }

    for name, figure_path in sorted((figure_paths or {}).items()):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise PlotValidationError(f"Unsafe figure artifact name {name!r}.")
        path = Path(figure_path)
        if not path.exists() or path.stat().st_size == 0:
            raise PlotValidationError(f"Figure artifact is missing or empty: {path}.")
        try:
            relative_path = path.resolve().relative_to(output_path.resolve())
        except ValueError as exc:
            raise PlotValidationError(
                "Figure artifacts must be inside the plot bundle output directory."
            ) from exc
        artifact_name = f"figure_{name}"
        if artifact_name in artifacts:
            raise PlotValidationError(f"Duplicate artifact name {artifact_name!r}.")
        media_types = {".png": "image/png", ".svg": "image/svg+xml", ".pdf": "application/pdf"}
        artifacts[artifact_name] = {
            "path": relative_path.as_posix(),
            "artifact_kind": "figure",
            "media_type": media_types.get(path.suffix.lower(), "application/octet-stream"),
            "byte_count": path.stat().st_size,
            "sha256": _sha256(path),
        }
        paths[artifact_name] = path

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": provenance["analysis_id"],
        "synthetic_data": bool(provenance["synthetic_data"]),
        "software_version": provenance["software_version"],
        "input_artifacts": provenance["input_artifacts"],
        "notes": provenance.get("notes", []),
        "palette_provenance": {
            "direction": SIGNIFICANCE_PALETTE_SOURCE,
            "effect": EFFECT_PALETTE_SOURCE,
            "exercise_group": MOTRPAC_GROUP_PALETTE_SOURCE,
        },
        "artifacts": artifacts,
    }
    manifest_path = output_path / "plot_bundle_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    paths["manifest"] = manifest_path
    return paths


def _artifact_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not slug:
        raise PlotValidationError(f"Cannot create an artifact name from {value!r}.")
    return slug


def run_metabolomics_plot_workflow(
    effect_rows: Iterable[Mapping[str, Any]],
    contrasts: Mapping[str, ContrastMetadata] | Sequence[ContrastMetadata],
    output_dir: str | Path,
    provenance: Mapping[str, Any],
    *,
    expected_members: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    aggregation_rules: AggregationRules | None = None,
    single_feature_id: str | None = None,
    trajectory_observations: Iterable[Mapping[str, Any]] | None = None,
    trajectory_metadata: TrajectoryMetadata | None = None,
    render: bool = True,
) -> dict[str, Path]:
    """Run the complete offline plotting workflow and export one audit bundle.

    Plot-ready data are written before optional rendering starts.  Therefore, a
    missing matplotlib installation fails clearly while leaving the scientific
    tables and provisional manifest available for review.
    """

    materialized = [dict(row) for row in effect_rows]
    by_id = _normalise_contrasts(contrasts)
    ordered_contrasts = sorted(by_id, key=lambda value: (by_id[value].display_order, value))
    tables: dict[str, list[dict[str, Any]]] = {}
    volcano_tables: dict[str, list[dict[str, Any]]] = {}
    for contrast_id in ordered_contrasts:
        selected = [row for row in materialized if _text(row.get("contrast_id")) == contrast_id]
        table_name = f"volcano_{_artifact_slug(contrast_id)}"
        volcano_tables[contrast_id] = prepare_volcano_data(selected, by_id[contrast_id])
        tables[table_name] = volcano_tables[contrast_id]

    heatmap = prepare_effect_heatmap_data(materialized, by_id)
    tables["effect_heatmap"] = heatmap
    hierarchy_views = prepare_all_hierarchy_views(
        materialized,
        by_id,
        expected_members=expected_members,
        rules=aggregation_rules,
    )
    for level, rows in hierarchy_views.items():
        tables[f"hierarchy_{level}"] = rows

    single_effect: list[dict[str, Any]] = []
    if single_feature_id:
        single_effect = prepare_single_feature_effect_data(
            materialized, by_id, single_feature_id
        )
        tables[f"single_effect_{_artifact_slug(single_feature_id)}"] = single_effect

    if (trajectory_observations is None) != (trajectory_metadata is None):
        raise PlotValidationError(
            "trajectory_observations and trajectory_metadata must be supplied together."
        )
    trajectory: list[dict[str, Any]] = []
    if trajectory_observations is not None and trajectory_metadata is not None:
        trajectory = prepare_single_feature_trajectory_data(
            trajectory_observations, trajectory_metadata
        )
        tables[f"trajectory_{_artifact_slug(trajectory_metadata.feature_id)}"] = trajectory

    output_path = Path(output_dir)
    paths = export_plot_bundle(tables, output_path, provenance)
    if not render:
        return paths

    figure_dir = output_path / "figures"
    figure_paths: dict[str, Path] = {}
    for contrast_id in ordered_contrasts:
        slug = _artifact_slug(contrast_id)
        figure_paths[f"volcano_{slug}"] = render_volcano_plot(
            volcano_tables[contrast_id],
            by_id[contrast_id],
            figure_dir / f"volcano_{slug}.png",
        )
    if heatmap:
        figure_paths["effect_heatmap"] = render_effect_heatmap(
            heatmap, figure_dir / "effect_heatmap.png"
        )
    for level, rows in hierarchy_views.items():
        if rows:
            figure_paths[f"hierarchy_{level}"] = render_hierarchy_heatmap(
                rows, figure_dir / f"hierarchy_{level}.png"
            )
    if single_effect:
        figure_paths[f"single_effect_{_artifact_slug(single_feature_id or '')}"] = (
            render_single_feature_effect(
                single_effect,
                figure_dir / f"single_effect_{_artifact_slug(single_feature_id or '')}.png",
            )
        )
    if trajectory and trajectory_metadata is not None:
        figure_paths[f"trajectory_{_artifact_slug(trajectory_metadata.feature_id)}"] = (
            render_single_feature_trajectory(
                trajectory,
                figure_dir / f"trajectory_{_artifact_slug(trajectory_metadata.feature_id)}.png",
            )
        )
    return export_plot_bundle(
        tables,
        output_path,
        provenance,
        figure_paths=figure_paths,
    )


def _load_matplotlib() -> tuple[Any, Any, Any]:
    """Load the optional rendering stack only when a figure is requested."""

    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.colors import LinearSegmentedColormap
    except ImportError as exc:  # pragma: no cover - depends on optional local stack
        raise RuntimeError(
            "Figure rendering requires matplotlib and numpy. Plot-ready CSV/provenance "
            "exports do not require them."
        ) from exc
    return plt, np, LinearSegmentedColormap


def _save_figure(fig: Any, output_path: str | Path) -> Path:
    path = Path(output_path)
    if path.suffix.lower() not in {".png", ".svg", ".pdf"}:
        raise PlotValidationError("Figure output must use a .png, .svg, or .pdf suffix.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".pdf":
        metadata = {
            "Creator": "metabotyping-agentic-workbench",
            "CreationDate": None,
            "ModDate": None,
        }
    elif path.suffix.lower() == ".svg":
        metadata = {"Creator": "metabotyping-agentic-workbench", "Date": None}
    else:
        metadata = {"Software": "metabotyping-agentic-workbench"}
    fig.savefig(path, dpi=180, bbox_inches="tight", metadata=metadata)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Figure rendering failed for {path}.")
    return path


def render_volcano_plot(
    rows: Sequence[Mapping[str, Any]],
    metadata: ContrastMetadata,
    output_path: str | Path,
    *,
    title: str | None = None,
    label_count: int = 8,
) -> Path:
    """Render an accessible FDR-based volcano from prepared volcano rows."""

    plt, _, _ = _load_matplotlib()
    data = [dict(row) for row in rows]
    if any(row.get("contrast_id") != metadata.contrast_id for row in data):
        raise PlotValidationError("Volcano rows do not match the supplied contrast metadata.")
    fig, axis = plt.subplots(figsize=(7.4, 5.7))
    draw_order = (
        "not_selected",
        "fdr_significant_below_effect_threshold",
        "lower_in_numerator",
        "higher_in_numerator",
        "not_testable",
    )
    labels = {
        "higher_in_numerator": "FDR-selected; higher in numerator",
        "lower_in_numerator": "FDR-selected; lower in numerator",
        "fdr_significant_below_effect_threshold": "FDR-selected; below effect threshold",
        "not_selected": "Not FDR/effect selected",
        "not_testable": "Not testable",
    }
    markers = {
        "higher_in_numerator": "^",
        "lower_in_numerator": "v",
        "fdr_significant_below_effect_threshold": "D",
        "not_selected": "o",
        "not_testable": "x",
    }
    for status in draw_order:
        subset = [
            row
            for row in data
            if row.get("selection_status") == status
            and _float(row.get("effect")) is not None
            and _float(row.get("neg_log10_fdr")) is not None
        ]
        if not subset:
            continue
        axis.scatter(
            [float(row["effect"]) for row in subset],
            [float(row["neg_log10_fdr"]) for row in subset],
            c=SIGNIFICANCE_PALETTE[status],
            marker=markers[status],
            s=34 if status != "not_selected" else 24,
            alpha=0.9 if status != "not_selected" else 0.55,
            linewidths=0.5,
            edgecolors="white" if markers[status] not in {"x"} else None,
            label=labels[status],
        )
    axis.axhline(-math.log10(metadata.alpha), color="#444444", linestyle="--", linewidth=0.9)
    if metadata.effect_threshold > 0:
        axis.axvline(metadata.effect_threshold, color="#555555", linestyle=":", linewidth=0.9)
        axis.axvline(-metadata.effect_threshold, color="#555555", linestyle=":", linewidth=0.9)
    axis.axvline(0, color="#777777", linewidth=0.7)
    candidates = [
        row
        for row in data
        if row.get("selection_status")
        in {"higher_in_numerator", "lower_in_numerator"}
        and _float(row.get("effect")) is not None
        and _float(row.get("neg_log10_fdr")) is not None
    ][: max(0, label_count)]
    for label_index, row in enumerate(candidates):
        effect = float(row["effect"])
        axis.annotate(
            str(row.get("feature_label") or row["feature_id"]),
            (effect, float(row["neg_log10_fdr"])),
            xytext=(5 if effect >= 0 else -5, 4 + (label_index % 3) * 7),
            textcoords="offset points",
            ha="left" if effect >= 0 else "right",
            fontsize=7,
        )
    axis.set_xlabel(metadata.effect_scale)
    axis.set_ylabel("−log10 FDR")
    axis.set_title(title or f"{metadata.numerator_label} vs {metadata.denominator_label}")
    # Matplotlib does not include annotation extents in its default data limits.
    # Explicit margins keep labels for extreme effects inside the plotting area.
    axis.margins(x=0.16, y=0.12)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E5E5", linewidth=0.6)
    handles, legend_labels = axis.get_legend_handles_labels()
    if handles:
        axis.legend(handles, legend_labels, frameon=False, fontsize=7, loc="lower left")
    fig.text(
        0.01,
        0.005,
        f"{metadata.direction_statement}. {metadata.fdr_statement}. "
        f"Palette: {SIGNIFICANCE_PALETTE_SOURCE}.",
        ha="left",
        va="bottom",
        fontsize=6.5,
        color="#333333",
        wrap=True,
    )
    fig.subplots_adjust(bottom=0.18)
    path = _save_figure(fig, output_path)
    plt.close(fig)
    return path


def _matrix_from_grid(
    rows: Sequence[Mapping[str, Any]],
    *,
    row_key: str,
    row_order_key: str,
    column_key: str,
    column_order_key: str,
    value_key: str,
) -> tuple[
    list[str],
    list[str],
    list[list[float | None]],
    dict[tuple[str, str], Mapping[str, Any]],
]:
    row_values = sorted(
        {_text(row.get(row_key)) for row in rows if _text(row.get(row_key))},
        key=lambda value: min(
            int(row.get(row_order_key, 10**9))
            for row in rows
            if _text(row.get(row_key)) == value
        ),
    )
    column_values = sorted(
        {_text(row.get(column_key)) for row in rows if _text(row.get(column_key))},
        key=lambda value: min(
            int(row.get(column_order_key, 10**9))
            for row in rows
            if _text(row.get(column_key)) == value
        ),
    )
    lookup: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (_text(row.get(row_key)), _text(row.get(column_key)))
        if key in lookup:
            raise PlotValidationError(f"Duplicate rendered grid cell {key}.")
        lookup[key] = row
    matrix = [
        [
            _float(lookup.get((row_value, column_value), {}).get(value_key))
            for column_value in column_values
        ]
        for row_value in row_values
    ]
    return row_values, column_values, matrix, lookup


def _draw_effect_grid(
    rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    row_key: str,
    row_order_key: str,
    column_key: str,
    column_order_key: str,
    value_key: str,
    title: str,
    footer: str,
    annotation: Any | None = None,
    row_label_key: str | None = None,
) -> Path:
    plt, np, LinearSegmentedColormap = _load_matplotlib()
    row_values, column_values, matrix, lookup = _matrix_from_grid(
        rows,
        row_key=row_key,
        row_order_key=row_order_key,
        column_key=column_key,
        column_order_key=column_order_key,
        value_key=value_key,
    )
    if not row_values or not column_values:
        raise PlotValidationError("Cannot render an empty effect grid.")
    numeric = [value for row in matrix for value in row if value is not None]
    limit = max((abs(value) for value in numeric), default=1.0)
    limit = limit if limit > 0 else 1.0
    array = np.array(
        [[value if value is not None else np.nan for value in matrix_row] for matrix_row in matrix],
        dtype=float,
    )
    cmap = LinearSegmentedColormap.from_list("motrpac_effect", EFFECT_DIVERGING_COLORS)
    cmap.set_bad("#ECECEC")
    width = max(6.4, 1.05 * len(column_values) + 2.8)
    height = max(4.2, 0.38 * len(row_values) + 2.2)
    fig, axis = plt.subplots(figsize=(width, height))
    image = axis.imshow(array, cmap=cmap, vmin=-limit, vmax=limit, aspect="auto")
    axis.set_xticks(range(len(column_values)), labels=column_values, rotation=40, ha="right")
    row_labels = []
    for row_value in row_values:
        representative = next(
            (
                lookup[(row_value, column)]
                for column in column_values
                if (row_value, column) in lookup
            ),
            {},
        )
        label = _text(representative.get(row_label_key)) if row_label_key else ""
        row_labels.append(label or row_value)
    axis.set_yticks(range(len(row_values)), labels=row_labels)
    axis.tick_params(labelsize=8)
    axis.set_xticks(np.arange(-0.5, len(column_values), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(row_values), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=1.0)
    axis.tick_params(which="minor", bottom=False, left=False)
    for row_index, row_value in enumerate(row_values):
        for column_index, column_value in enumerate(column_values):
            row = lookup.get((row_value, column_value), {})
            value = _float(row.get(value_key))
            if annotation is not None:
                label = annotation(row)
            elif value is None:
                label = "×" if row.get("cell_status") == "unreviewed_harmonization" else "·"
            else:
                label = f"{value:.2g}"
                if row.get("cell_status") in {"high_missingness", "high_below_lod"}:
                    label += "!"
            color = "white" if value is not None and abs(value) > limit * 0.58 else "#222222"
            axis.text(
                column_index,
                row_index,
                label,
                ha="center",
                va="center",
                fontsize=7,
                color=color,
            )
    colorbar = fig.colorbar(image, ax=axis, shrink=0.82)
    colorbar.set_label("Effect", fontsize=8)
    axis.set_title(title)
    fig.text(0.01, 0.005, footer, fontsize=6.5, ha="left", va="bottom", wrap=True)
    fig.subplots_adjust(bottom=0.34)
    path = _save_figure(fig, output_path)
    plt.close(fig)
    return path


def render_effect_heatmap(
    rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    title: str = "Reviewed metabolite effects across contrasts",
) -> Path:
    """Render a complete effect heatmap; review-gated cells remain visibly blank."""

    data = [dict(row) for row in rows]
    scales = {_text(row.get("effect_scale")) for row in data if _text(row.get("effect_scale"))}
    if len(scales) > 1:
        raise PlotValidationError("Heatmap rendering cannot mix effect scales.")
    return _draw_effect_grid(
        data,
        output_path,
        row_key="canonical_feature_id",
        row_order_key="feature_order",
        column_key="contrast_id",
        column_order_key="contrast_order",
        value_key="heatmap_value",
        title=title,
        footer=(
            f"Scale: {next(iter(scales), 'not reported')}. Palette: {EFFECT_PALETTE_SOURCE}. "
            "× = unreviewed harmonization; · = not reported; ! = missingness/LOD caution. "
            "Visual similarity is not evidence of biological replication."
        ),
        row_label_key="feature_label",
    )


def render_single_feature_trajectory(
    rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Render descriptive mean±SE trajectories with redundant group encodings."""

    plt, _, _ = _load_matplotlib()
    data = [dict(row) for row in rows]
    if not data:
        raise PlotValidationError("Cannot render an empty trajectory.")
    feature_ids = {_text(row.get("canonical_feature_id")) for row in data}
    scales = {_text(row.get("value_scale")) for row in data}
    if len(feature_ids) != 1 or len(scales) != 1:
        raise PlotValidationError("Trajectory rows must represent one feature on one value scale.")
    fig, axis = plt.subplots(figsize=(7.4, 5.0))
    groups = sorted(
        {_text(row.get("exercise_group")) for row in data},
        key=lambda group: min(
            int(row.get("group_order", 10**9))
            for row in data
            if _text(row.get("exercise_group")) == group
        ),
    )
    timepoints = sorted(
        {_text(row.get("timepoint")) for row in data},
        key=lambda timepoint: min(
            int(row.get("timepoint_order", 10**9))
            for row in data
            if _text(row.get("timepoint")) == timepoint
        ),
    )
    lookup = {
        (_text(row.get("exercise_group")), _text(row.get("timepoint"))): row for row in data
    }
    for group in groups:
        group_rows = [lookup[(group, timepoint)] for timepoint in timepoints]
        x_values = [
            index
            for index, row in enumerate(group_rows)
            if _float(row.get("mean")) is not None
        ]
        y_values = [float(group_rows[index]["mean"]) for index in x_values]
        errors = [
            _float(group_rows[index].get("se")) or 0.0
            for index in x_values
        ]
        source = group_rows[0]
        axis.errorbar(
            x_values,
            y_values,
            yerr=errors,
            color=source.get("color_hex", "#666666"),
            marker=source.get("marker", "o"),
            linestyle=source.get("line_style", "-"),
            linewidth=1.5,
            markersize=5,
            capsize=3,
            label=group,
        )
        for x_value in x_values:
            flags = str(group_rows[x_value].get("quality_flags", ""))
            if "high_" in flags:
                axis.scatter(
                    [x_value],
                    [float(group_rows[x_value]["mean"])],
                    facecolors="none",
                    edgecolors="#111111",
                    s=72,
                    linewidths=0.9,
                    zorder=5,
                )
    axis.set_xticks(range(len(timepoints)), labels=timepoints, rotation=30, ha="right")
    axis.set_ylabel(next(iter(scales)))
    feature_id = next(iter(feature_ids))
    axis.set_title(title or f"{feature_id} trajectory")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E5E5", linewidth=0.6)
    axis.legend(frameon=False, title="Explicit group")
    fig.text(
        0.01,
        0.005,
        "Mean ± SE of observed values; no imputation or longitudinal model. Hollow rings mark "
        "high missingness/LOD caution. Group colors are MoTrPAC aliases only for explicit "
        f"EE/RE/CON metadata. Palette source: {MOTRPAC_GROUP_PALETTE_SOURCE}.",
        fontsize=6.5,
        ha="left",
        va="bottom",
        wrap=True,
    )
    fig.subplots_adjust(bottom=0.25)
    path = _save_figure(fig, output_path)
    plt.close(fig)
    return path


def render_single_feature_effect(
    rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Render a non-pooled single-feature forest view across explicit contrasts."""

    plt, _, _ = _load_matplotlib()
    data = [dict(row) for row in rows]
    if not data:
        raise PlotValidationError("Cannot render an empty single-feature effect view.")
    scales = {_text(row.get("effect_scale")) for row in data}
    features = {_text(row.get("canonical_feature_id")) for row in data}
    if len(scales) != 1 or len(features) != 1:
        raise PlotValidationError(
            "Single-feature effect rows require one feature and effect scale."
        )
    data.sort(key=lambda row: int(row.get("contrast_order", 10**9)))
    fig, axis = plt.subplots(figsize=(7.4, max(3.8, 0.48 * len(data) + 2.3)))
    y_positions = list(reversed(range(len(data))))
    for y_position, row in zip(y_positions, data, strict=True):
        effect = _float(row.get("effect"))
        if effect is None:
            continue
        low = _float(row.get("ci_low"))
        high = _float(row.get("ci_high"))
        xerr = None
        if low is not None and high is not None:
            xerr = [[effect - low], [high - effect]]
        axis.errorbar(
            [effect],
            [y_position],
            xerr=xerr,
            marker="o",
            color=row.get("color_hex", SIGNIFICANCE_PALETTE["not_selected"]),
            capsize=3,
            linestyle="none",
        )
    axis.axvline(0, color="#555555", linestyle="--", linewidth=0.9)
    axis.set_yticks(y_positions, labels=[row["contrast_id"] for row in data])
    axis.set_xlabel(next(iter(scales)))
    feature = next(iter(features))
    axis.set_title(title or f"{feature}: contrast-specific effects")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="x", color="#E5E5E5", linewidth=0.6)
    fig.text(
        0.01,
        0.005,
        "Intervals are shown only when supplied with explicit source semantics; no interval or "
        "cross-contrast pooled estimate is inferred by the plotting layer.",
        fontsize=6.5,
        ha="left",
        va="bottom",
        wrap=True,
    )
    fig.subplots_adjust(bottom=0.15)
    path = _save_figure(fig, output_path)
    plt.close(fig)
    return path


def render_hierarchy_heatmap(
    rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Render coverage-gated descriptive pathway/RefMet hierarchy effects."""

    data = [dict(row) for row in rows]
    levels = {_text(row.get("hierarchy_level")) for row in data}
    scales = {_text(row.get("effect_scale")) for row in data}
    if len(levels) != 1 or len(scales) != 1:
        raise PlotValidationError("Hierarchy heatmap rows require one level and one effect scale.")
    for row in data:
        row["render_effect"] = (
            row.get("aggregate_effect")
            if row.get("aggregate_status") == "eligible_descriptive_summary"
            else None
        )

    def coverage_label(row: Mapping[str, Any]) -> str:
        value = _float(row.get("render_effect"))
        observed = int(row.get("observed_feature_count", 0))
        coverage = _float(row.get("coverage_fraction"))
        if value is None:
            return f"×\nn={observed}"
        denominator = f"{coverage:.0%}" if coverage is not None else "cov?"
        return f"{value:.2g}\nn={observed}; {denominator}"

    level = next(iter(levels))
    return _draw_effect_grid(
        data,
        output_path,
        row_key="category",
        row_order_key="category_order",
        column_key="contrast_id",
        column_order_key="contrast_order",
        value_key="render_effect",
        title=title or f"Coverage-gated descriptive {level.replace('_', ' ')} effects",
        footer=(
            f"Scale: {next(iter(scales))}. Palette: {EFFECT_PALETTE_SOURCE}. Only cells passing "
            "the declared feature-count and expected-universe coverage gates are colored; × "
            "marks gated cells. Medians are descriptive, not pathway activity or RefMet "
            "over-representation enrichment, and have no aggregate p-value/FDR."
        ),
        annotation=coverage_label,
    )

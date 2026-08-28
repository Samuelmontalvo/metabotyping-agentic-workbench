#!/usr/bin/env python3
"""Generate the deterministic cold split for the synthetic statin classifier."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "examples" / "medication_classifier"
FEATURE_NAMES = (
    "ldl_particle_signal",
    "cholesteryl_ester_signal",
    "mevalonate_pathway_proxy",
    "apo_b_proxy",
    "triglyceride_proxy",
    "neutral_reference_signal",
)
FIELDNAMES = ("sample_id", "cohort_id", "statin_exposure", *FEATURE_NAMES)


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(_json_bytes(value))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wave(index: int, multiplier: int, modulus: int, scale: float) -> float:
    midpoint = (modulus - 1) / 2
    return (((index * multiplier) % modulus) - midpoint) * scale


def _cohort_rows(
    cohort_id: str,
    sample_prefix: str,
    sample_count: int,
    cohort_shift: float,
    label_offset: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(sample_count):
        exposed = (index + label_offset) % 2
        values = {
            "ldl_particle_signal": (
                1.20 - 0.70 * exposed + 0.55 * cohort_shift
                + _wave(index, 3, 11, 0.018)
            ),
            "cholesteryl_ester_signal": (
                0.95 - 0.50 * exposed + 0.30 * cohort_shift
                + _wave(index, 5, 13, 0.016)
            ),
            "mevalonate_pathway_proxy": (
                1.10 - 0.60 * exposed + 0.15 * cohort_shift
                + _wave(index, 7, 17, 0.012)
            ),
            "apo_b_proxy": (
                0.80 - 0.42 * exposed + 0.50 * cohort_shift
                + _wave(index, 2, 9, 0.022)
            ),
            "triglyceride_proxy": (
                0.75 - 0.20 * exposed + 0.25 * cohort_shift
                + _wave(index, 4, 15, 0.025)
            ),
            "neutral_reference_signal": (
                0.50 + 0.60 * cohort_shift + _wave(index, 6, 19, 0.020)
            ),
        }
        rows.append(
            {
                "sample_id": f"{sample_prefix}_{index + 1:03d}",
                "cohort_id": cohort_id,
                "statin_exposure": str(exposed),
                **{name: f"{values[name]:.6f}" for name in FEATURE_NAMES},
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(FIELDNAMES),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "sample_count": len(rows),
        "cohort_ids": sorted({row["cohort_id"] for row in rows}),
        "class_counts": {
            "0": sum(row["statin_exposure"] == "0" for row in rows),
            "1": sum(row["statin_exposure"] == "1" for row in rows),
        },
    }


def generate(out_dir: Path) -> None:
    """Write byte-stable feature metadata, labeled splits, and hash manifest."""

    out_dir.mkdir(parents=True, exist_ok=True)
    feature_catalog = {
        "schema_version": "1.0.0",
        "catalog_id": "synthetic_statin_signals_v1",
        "status": "synthetic_only_not_clinically_validated",
        "target_column": "statin_exposure",
        "id_columns": ["sample_id", "cohort_id"],
        "negative_label": "0",
        "positive_label": "1",
        "minimum_feature_count": 4,
        "features": [
            {
                "name": "ldl_particle_signal",
                "description": "Synthetic lipid-particle signal; not a measured biomarker.",
                "unit": "synthetic_standardized_abundance",
                "synthetic_expected_direction": "decrease",
            },
            {
                "name": "cholesteryl_ester_signal",
                "description": "Synthetic cholesteryl-ester signal; not a measured biomarker.",
                "unit": "synthetic_standardized_abundance",
                "synthetic_expected_direction": "decrease",
            },
            {
                "name": "mevalonate_pathway_proxy",
                "description": "Synthetic pathway proxy with no clinical interpretation.",
                "unit": "synthetic_standardized_abundance",
                "synthetic_expected_direction": "decrease",
            },
            {
                "name": "apo_b_proxy",
                "description": "Synthetic apolipoprotein-associated proxy; not an assay result.",
                "unit": "synthetic_standardized_abundance",
                "synthetic_expected_direction": "decrease",
            },
            {
                "name": "triglyceride_proxy",
                "description": "Synthetic weak-effect lipid proxy; not an assay result.",
                "unit": "synthetic_standardized_abundance",
                "synthetic_expected_direction": "decrease",
            },
            {
                "name": "neutral_reference_signal",
                "description": "Synthetic cohort-shift control without an exposure effect.",
                "unit": "synthetic_standardized_abundance",
                "synthetic_expected_direction": "noise_control",
            },
        ],
        "limitations": [
            "Feature names describe synthetic signals and do not assert clinical biomarkers.",
            "The catalog is suitable only for deterministic offline evaluation.",
        ],
    }

    train_rows = [
        *_cohort_rows("SYN_TRAIN_ALPHA", "STA", 24, -0.12, 0),
        *_cohort_rows("SYN_TRAIN_BETA", "STB", 24, 0.14, 1),
    ]
    test_rows = _cohort_rows("SYN_TEST_GAMMA", "STG", 24, 0.28, 0)

    feature_catalog_path = out_dir / "feature_catalog.json"
    train_path = out_dir / "train.csv"
    test_path = out_dir / "test.csv"
    split_manifest_path = out_dir / "split_manifest.json"
    _write_json(feature_catalog_path, feature_catalog)
    _write_csv(train_path, train_rows)
    _write_csv(test_path, test_rows)

    split_manifest = {
        "schema_version": "1.0.0",
        "split_id": "synthetic_statin_cold_split_v1",
        "status": "synthetic_only_not_clinically_validated",
        "target_column": "statin_exposure",
        "artifacts": {
            "feature_catalog": {
                "path": feature_catalog_path.name,
                "sha256": _sha256(feature_catalog_path),
            },
            "train": {
                "path": train_path.name,
                "sha256": _sha256(train_path),
                **_summary(train_rows),
            },
            "test": {
                "path": test_path.name,
                "sha256": _sha256(test_path),
                **_summary(test_rows),
            },
        },
        "constraints": {
            "sample_id_disjoint": True,
            "cohort_id_disjoint": True,
            "declared_feature_vectors_disjoint": True,
            "test_labels_excluded_from_model_fitting": True,
            "test_labels_excluded_from_scoring": True,
        },
    }
    _write_json(split_manifest_path, split_manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()
    generate(args.out)


if __name__ == "__main__":
    main()

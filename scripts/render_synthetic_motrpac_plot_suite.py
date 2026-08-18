#!/usr/bin/env python3
"""Render the deterministic offline MoTrPAC-style metabolomics example bundle.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python scripts/render_synthetic_motrpac_plot_suite.py

All inputs are synthetic fixtures committed under ``tests/fixtures/plotting``.
The command performs no network access and writes plot-ready CSVs, PNG figures,
and a checksummed provenance manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from metabotyping_agentic.plotting import (
    AggregationRules,
    ContrastMetadata,
    TrajectoryMetadata,
    run_metabolomics_plot_workflow,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "plotting"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "reports" / "synthetic_motrpac_plot_suite",
        help="Output bundle directory.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Export plot-ready data and provenance without optional matplotlib rendering.",
    )
    args = parser.parse_args()

    effect_path = FIXTURE_DIR / "synthetic_effects.csv"
    contrast_path = FIXTURE_DIR / "contrast_metadata.json"
    expected_path = FIXTURE_DIR / "expected_members.json"
    trajectory_path = FIXTURE_DIR / "synthetic_trajectory.csv"
    contrasts = [ContrastMetadata(**row) for row in _read_json(contrast_path)]
    trajectory_metadata = TrajectoryMetadata(
        feature_id="RM0136379",
        value_scale="synthetic concentration (µmol/L)",
        timepoint_order=("pre_exercise", "post_10_min", "post_24_hr"),
        group_order=("EE", "RE"),
        source_study_id="SYN-MOTRPAC",
        source_dataset_id="SYN-MOTRPAC-A",
    )
    input_paths = [effect_path, contrast_path, expected_path, trajectory_path]
    provenance = {
        "analysis_id": "synthetic-motrpac-metabolomics-plot-suite-v1",
        "synthetic_data": True,
        "software_version": "0.2.0",
        "input_artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(path),
                "synthetic": True,
            }
            for path in input_paths
        ],
        "notes": [
            "Synthetic values demonstrate plot and provenance semantics only.",
            "Visual similarity is not evidence of harmonized cohorts or biological replication.",
        ],
    }
    paths = run_metabolomics_plot_workflow(
        _read_csv(effect_path),
        contrasts,
        args.out,
        provenance,
        expected_members=_read_json(expected_path),
        aggregation_rules=AggregationRules(min_features=3, min_coverage=0.75),
        single_feature_id="RM0136379",
        trajectory_observations=_read_csv(trajectory_path),
        trajectory_metadata=trajectory_metadata,
        render=not args.skip_plots,
    )
    print(f"Wrote {len(paths)} audited artifacts to {args.out.resolve()}")
    print(f"Manifest: {paths['manifest'].resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

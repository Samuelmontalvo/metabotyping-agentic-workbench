#!/usr/bin/env python3
"""Build deterministic synthetic assay harmonization and audit artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from metabotyping_agentic.harmonization.assay_harmonization import (  # noqa: E402
    write_assay_harmonization_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "data/examples/mock_metabolite_assays.json",
        help="Local synthetic assay fixture JSON.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
        help="Root under which reports/, data/review/, and data/harmonized/ are written.",
    )
    args = parser.parse_args()
    paths = write_assay_harmonization_artifacts(args.fixture, args.project_root)
    for label, path in sorted(paths.items()):
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

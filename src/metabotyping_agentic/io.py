"""File IO helpers for deterministic offline workflows."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .models import Modality


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    return path


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> Path:
    path = Path(path)
    rows = list(rows)
    ensure_dir(path.parent)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_json(path: str | Path, value: Any) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(to_plain(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    return value


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_int(value: Any) -> int | None:
    value = str(value).strip()
    if not value or value.lower() in {"unknown", "not_reported", "not_available"}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_modalities(value: str | list[str]) -> list[Modality]:
    if isinstance(value, list):
        parts = value
    else:
        parts = [part.strip() for part in str(value).replace(",", ";").split(";")]
    modalities: list[Modality] = []
    for part in parts:
        if not part:
            continue
        normalized = part.strip().lower().replace(" ", "_").replace("-", "_")
        try:
            modalities.append(Modality(normalized))
        except ValueError:
            modalities.append(Modality.UNKNOWN)
    return modalities or [Modality.UNKNOWN]


def validate_required_keys(value: dict[str, Any], required: list[str]) -> list[str]:
    return [key for key in required if key not in value or value[key] in {None, ""}]


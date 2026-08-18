"""Schema helpers."""

from __future__ import annotations

import sysconfig
from pathlib import Path
from typing import Any

from .io import read_json


REPOSITORY_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
INSTALLED_SCHEMA_DIR = (
    Path(sysconfig.get_path("data"))
    / "share"
    / "metabotyping-agentic-workbench"
    / "schemas"
)
SCHEMA_DIR = (
    REPOSITORY_SCHEMA_DIR
    if REPOSITORY_SCHEMA_DIR.is_dir()
    else INSTALLED_SCHEMA_DIR
)


def project_schema_path(filename: str) -> Path:
    """Return a schema path from a checkout or an installed wheel."""

    path = SCHEMA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return path


def validate_against_schema(instance: dict[str, Any], schema_path: str | Path) -> list[str]:
    """Validate with jsonschema when available; otherwise perform required-key checks."""
    schema = read_json(schema_path)
    try:  # pragma: no cover - optional dependency path
        import jsonschema

        jsonschema.validate(instance=instance, schema=schema)
        return []
    except ModuleNotFoundError:
        missing = [key for key in schema.get("required", []) if key not in instance]
        return [f"Missing required key: {key}" for key in missing]
    except Exception as exc:  # pragma: no cover - exact jsonschema error class varies
        return [str(exc)]


def validate_or_raise(
    instance: dict[str, Any],
    schema_path: str | Path,
    *,
    label: str = "artifact",
) -> None:
    """Raise a clear error when a generated artifact violates its JSON Schema."""
    errors = validate_against_schema(instance, schema_path)
    if errors:
        joined = "; ".join(errors)
        raise ValueError(f"{label} failed schema validation: {joined}")

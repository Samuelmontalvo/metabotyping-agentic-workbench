"""Create variable inventory cards."""

from __future__ import annotations

from pathlib import Path

from ..io import parse_modalities, read_csv_rows, to_plain, write_csv_rows, write_json
from ..models import Modality, VariableCard
from ..schemas import project_schema_path, validate_or_raise


def load_variable_cards(
    path: str | Path,
    *,
    provenance_source: str | None = None,
) -> list[VariableCard]:
    cards: list[VariableCard] = []
    source = provenance_source or str(path)
    for row in read_csv_rows(path):
        modalities = parse_modalities(row.get("modality", "unknown"))
        modality = modalities[0] if modalities else Modality.UNKNOWN
        cards.append(
            VariableCard(
                study_id=row["study_id"],
                source_variable=row["source_variable"],
                label=row.get("label") or row["source_variable"],
                unit=row.get("unit") or "unknown",
                timing=row.get("timing") or "unknown",
                modality=modality,
                description=row.get("description") or "",
                provenance={"source": source, "row_key": f"{row['study_id']}::{row['source_variable']}"},
            )
        )
    return cards


def extract_variable_inventory(
    path: str | Path,
    out_dir: str | Path,
    *,
    provenance_source: str | None = None,
) -> list[VariableCard]:
    cards = load_variable_cards(path, provenance_source=provenance_source)
    rows = [to_plain(card) for card in cards]
    schema_path = project_schema_path("variable_card.schema.json")
    for row in rows:
        validate_or_raise(
            row,
            schema_path,
            label=f"variable card {row['study_id']}::{row['source_variable']}",
        )
    flat_rows = []
    for row in rows:
        flat_rows.append(
            {
                "study_id": row["study_id"],
                "source_variable": row["source_variable"],
                "label": row["label"],
                "unit": row["unit"],
                "timing": row["timing"],
                "modality": row["modality"],
                "description": row["description"],
            }
        )
    out_dir = Path(out_dir)
    write_csv_rows(out_dir / "variable_inventory.csv", flat_rows)
    write_json(out_dir / "variable_cards.json", rows)
    return cards

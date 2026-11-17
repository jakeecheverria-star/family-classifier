"""Read Revit exports and write classified output."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_COLUMNS = ("category", "family", "type")

OUTPUT_COLUMNS = (
    "uniclass_code",
    "uniclass_title",
    "ifc_entity",
    "confidence",
    "source",
    "reason",
    "approved",
    "reviewed_uniclass_code",
    "reviewed_ifc_entity",
)


@dataclass
class FamilyRow:
    """One family type from a Revit export."""

    category: str
    family: str
    type: str
    params: dict[str, str] = field(default_factory=dict)

    # Filled in by the pipeline.
    uniclass_code: str = ""
    uniclass_title: str = ""
    ifc_entity: str = ""
    confidence: str = ""
    source: str = ""
    reason: str = ""

    # Filled in by the reviewer.
    approved: str = ""
    reviewed_uniclass_code: str = ""
    reviewed_ifc_entity: str = ""

    @property
    def is_approved(self) -> bool:
        return self.approved.strip().lower() in {"y", "yes", "x", "1", "true"}

    @property
    def final_uniclass(self) -> str:
        """The code to write back, or an empty string if the row isn't reviewed."""
        if self.reviewed_uniclass_code.strip():
            return self.reviewed_uniclass_code.strip()
        return self.uniclass_code if self.is_approved else ""

    @property
    def final_ifc(self) -> str:
        if self.reviewed_ifc_entity.strip():
            return self.reviewed_ifc_entity.strip()
        return self.ifc_entity if self.is_approved else ""

    @property
    def was_reviewed(self) -> bool:
        return bool(self.final_uniclass or self.final_ifc)

    def describe(self) -> str:
        """Short text for the prompt."""
        extras = ", ".join(f"{k}={v}" for k, v in self.params.items() if v)
        text = f"category={self.category}; family={self.family}; type={self.type}"
        return f"{text}; {extras}" if extras else text


def read_export(path: str | Path) -> list[FamilyRow]:
    """Read a CSV export. Columns other than the required ones become params."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")
        rows = []
        for raw in reader:
            known = {k: (raw.get(k) or "").strip() for k in REQUIRED_COLUMNS + OUTPUT_COLUMNS}
            params = {
                k: (v or "").strip()
                for k, v in raw.items()
                if k and k not in REQUIRED_COLUMNS and k not in OUTPUT_COLUMNS
            }
            rows.append(FamilyRow(params=params, **known))
    return rows


def write_output(rows: list[FamilyRow], path: str | Path) -> None:
    """Write rows with the input columns first and the classification columns after."""
    param_cols: list[str] = []
    for row in rows:
        for key in row.params:
            if key not in param_cols:
                param_cols.append(key)
    header = list(REQUIRED_COLUMNS) + param_cols + list(OUTPUT_COLUMNS)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(
                [row.category, row.family, row.type]
                + [row.params.get(c, "") for c in param_cols]
                + [getattr(row, c) for c in OUTPUT_COLUMNS]
            )

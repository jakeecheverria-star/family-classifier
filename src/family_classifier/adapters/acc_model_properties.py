"""Convert ACC Model Properties API results into family-classifier rows.

The Model Properties API returns two line-delimited JSON files for an index
or a diff: a fields file that maps short keys (such as "p5eddc473") to
property names, and a properties file with one object per element.

This adapter reads both, picks out category, family, type, and the parameters
you ask for, and collapses elements to one row per family type. One row per
type is what the classifier needs: a new instance of a known type costs nothing.

DRAFT: the property names below are defaults to verify against a real fields
file from your hub. Override them with the `names` argument.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from ..io import FamilyRow


@dataclass
class PropertyNames:
    """Which Model Properties fields hold the values the classifier needs."""

    category: str = "Category"
    family: str = "Family Name"
    type: str = "Type Name"
    # Viewer categories are prefixed, for example "Revit Doors".
    category_prefix: str = "Revit "
    params: list[str] = field(default_factory=lambda: ["Width", "Height", "Description", "Type Mark"])


def read_ldjson(path: str | Path) -> Iterator[dict]:
    """Read line-delimited JSON, gzipped or plain."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def field_keys(fields: Iterable[dict]) -> dict[str, str]:
    """Map property name to key. If a name repeats, the first one wins."""
    keys: dict[str, str] = {}
    for item in fields:
        name, key = item.get("name"), item.get("key")
        if name and key and name not in keys:
            keys[name] = key
    return keys


def rows_from_properties(
    fields: Iterable[dict],
    elements: Iterable[dict],
    names: PropertyNames | None = None,
    change_types: set[str] | None = None,
) -> list[FamilyRow]:
    """Build one FamilyRow per distinct (category, family, type).

    For diff results, pass `change_types` (for example {"ADDED", "CHANGED"})
    to keep only those elements. Elements without a change type are kept.
    """
    names = names or PropertyNames()
    keys = field_keys(fields)
    missing = [n for n in (names.category, names.family, names.type) if n not in keys]
    if missing:
        raise ValueError(
            "fields file has no property named: " + ", ".join(missing)
            + ". Check the names in PropertyNames against your fields file."
        )

    seen: dict[tuple[str, str, str], FamilyRow] = {}
    for element in elements:
        change = element.get("type") or element.get("changeType")
        if change_types and change and change not in change_types:
            continue
        props = element.get("props") or element.get("properties") or {}

        def get(name: str) -> str:
            key = keys.get(name)
            value = props.get(key) if key else None
            return "" if value is None else str(value).strip()

        family, type_name = get(names.family), get(names.type)
        if not family or not type_name:
            continue  # Not a family instance, for example a view or a room.
        category = get(names.category)
        if names.category_prefix and category.startswith(names.category_prefix):
            category = category[len(names.category_prefix):]

        ident = (category, family, type_name)
        if ident not in seen:
            seen[ident] = FamilyRow(
                category, family, type_name,
                params={p: get(p) for p in names.params},
            )
    return sorted(seen.values(), key=lambda r: (r.category, r.family, r.type))


def load(fields_path: str | Path, properties_path: str | Path, **kwargs) -> list[FamilyRow]:
    return rows_from_properties(read_ldjson(fields_path), read_ldjson(properties_path), **kwargs)

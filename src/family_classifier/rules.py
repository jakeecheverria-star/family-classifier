"""Office rules: abbreviations and learned mappings, stored in a YAML file."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .io import FamilyRow


@dataclass
class Rule:
    """Map families that match `category` and `family` patterns to fixed codes.

    Patterns are regular expressions, matched case-insensitively against the
    whole value. An empty pattern matches anything.
    """

    category: str = ""
    family: str = ""
    type: str = ""
    uniclass_code: str = ""
    ifc_entity: str = ""
    note: str = ""
    learned: str = ""

    def matches(self, row: FamilyRow) -> bool:
        for pattern, value in (
            (self.category, row.category),
            (self.family, row.family),
            (self.type, row.type),
        ):
            if pattern and not re.fullmatch(pattern, value, flags=re.IGNORECASE):
                return False
        return True

    def to_dict(self) -> dict:
        match = {k: v for k, v in (("category", self.category), ("family", self.family), ("type", self.type)) if v}
        out: dict = {"match": match}
        for key in ("uniclass_code", "ifc_entity", "note", "learned"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


@dataclass
class OfficeRules:
    abbreviations: dict[str, str] = field(default_factory=dict)
    rules: list[Rule] = field(default_factory=list)
    uniclass_version: str = ""

    def find(self, row: FamilyRow) -> Rule | None:
        """Return the first matching rule. Rules earlier in the file win."""
        for rule in self.rules:
            if rule.matches(row):
                return rule
        return None

    @classmethod
    def load(cls, path: str | Path) -> "OfficeRules":
        path = Path(path)
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rules = []
        for item in data.get("rules") or []:
            match = item.get("match") or {}
            rules.append(
                Rule(
                    category=str(match.get("category", "")),
                    family=str(match.get("family", "")),
                    type=str(match.get("type", "")),
                    uniclass_code=str(item.get("uniclass_code", "")),
                    ifc_entity=str(item.get("ifc_entity", "")),
                    note=str(item.get("note", "")),
                    learned=str(item.get("learned", "")),
                )
            )
        return cls(
            abbreviations={str(k): str(v) for k, v in (data.get("abbreviations") or {}).items()},
            rules=rules,
            uniclass_version=str(data.get("uniclass_version", "")),
        )

    def save(self, path: str | Path) -> None:
        data = {
            "uniclass_version": self.uniclass_version,
            "abbreviations": self.abbreviations,
            "rules": [r.to_dict() for r in self.rules],
        }
        Path(path).write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )

    def learn(self, rows: list[FamilyRow]) -> int:
        """Add or update an exact rule for every reviewed row.

        A reviewed row is one with a correction or with `approved` set. Rules
        that came from an earlier review of the same family are updated in
        place. Hand-written rules aren't changed. Returns the number of rules
        added or changed.
        """
        today = date.today().isoformat()
        changed = 0
        for row in rows:
            # Approving a rule's own output teaches nothing new.
            if not row.was_reviewed or (row.source == "rule" and not _is_correction(row)):
                continue
            category = re.escape(row.category)
            family = re.escape(row.family)
            existing = next(
                (r for r in self.rules if r.learned and r.category == category and r.family == family and not r.type),
                None,
            )
            uniclass = row.final_uniclass or row.uniclass_code
            ifc = row.final_ifc or row.ifc_entity
            if existing:
                if (existing.uniclass_code, existing.ifc_entity) != (uniclass, ifc):
                    existing.uniclass_code, existing.ifc_entity, existing.learned = uniclass, ifc, today
                    changed += 1
                continue
            # Learned rules go first so they override broader hand-written rules.
            self.rules.insert(
                0,
                Rule(category=category, family=family, uniclass_code=uniclass, ifc_entity=ifc, learned=today),
            )
            changed += 1
        return changed


def _is_correction(row: FamilyRow) -> bool:
    return bool(row.reviewed_uniclass_code.strip() or row.reviewed_ifc_entity.strip())

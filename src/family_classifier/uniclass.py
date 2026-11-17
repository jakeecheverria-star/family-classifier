"""Load Uniclass tables and find candidate codes for a family."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

CODE_PATTERN = re.compile(r"^[A-Z][a-zA-Z]_\d{2}(_\d{2}){0,3}$")

STOPWORDS = {"and", "or", "the", "of", "for", "with", "to", "in", "a", "an"}


@dataclass(frozen=True)
class UniclassItem:
    code: str
    title: str


class UniclassTable:
    """A Uniclass table, such as Products (Pr), loaded from an NBS download."""

    def __init__(self, items: list[UniclassItem], version: str = "unknown"):
        self.items = items
        self.version = version
        self._by_code = {item.code: item for item in items}
        self._tokens = {item.code: tokenize(item.title) for item in items}

    def __len__(self) -> int:
        return len(self.items)

    def get(self, code: str) -> UniclassItem | None:
        return self._by_code.get(code.strip())

    def candidates(self, words: set[str], limit: int = 25) -> list[UniclassItem]:
        """Return the items whose titles share the most words with `words`.

        Deeper codes win ties, because they're more specific.
        """
        if not words:
            return []
        scored = []
        for item in self.items:
            overlap = len(words & self._tokens[item.code])
            if overlap:
                depth = item.code.count("_")
                scored.append((overlap, depth, item))
        scored.sort(key=lambda s: (-s[0], -s[1], s[2].code))
        return [s[2] for s in scored[:limit]]

    @classmethod
    def load(cls, path: str | Path, version: str | None = None) -> "UniclassTable":
        """Load a CSV or Excel file that has `Code` and `Title` columns.

        NBS downloads often have title rows above the header, so the loader
        searches the first 20 rows for the header.
        """
        path = Path(path)
        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            rows = _read_xlsx(path)
        else:
            with open(path, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
        code_i, title_i, start = _find_header(rows, path)
        items = []
        for row in rows[start:]:
            if len(row) <= max(code_i, title_i):
                continue
            code, title = str(row[code_i] or "").strip(), str(row[title_i] or "").strip()
            if CODE_PATTERN.match(code) and title:
                items.append(UniclassItem(code, title))
        if not items:
            raise ValueError(f"{path}: no Uniclass codes found")
        return cls(items, version or path.stem)


def _read_xlsx(path: Path) -> list[list]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _find_header(rows: list[list], path: Path) -> tuple[int, int, int]:
    for i, row in enumerate(rows[:20]):
        cells = [str(c or "").strip().lower() for c in row]
        if "code" in cells and "title" in cells:
            return cells.index("code"), cells.index("title"), i + 1
    raise ValueError(f"{path}: no header row with 'Code' and 'Title' columns")


_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
_SPLIT = re.compile(r"[^A-Za-z0-9]+")


def tokenize(text: str, abbreviations: dict[str, str] | None = None) -> set[str]:
    """Split a name into lowercase words and expand office abbreviations.

    Numbers are dropped, because sizes don't help find a classification.

    >>> sorted(tokenize("DR_SingleFlush-900", {"DR": "door"}))
    ['door', 'flush', 'single']
    """
    abbreviations = {k.lower(): v for k, v in (abbreviations or {}).items()}
    words: set[str] = set()
    for part in _SPLIT.split(_CAMEL.sub(" ", text)):
        if not part:
            continue
        low = part.lower()
        expanded = abbreviations.get(low, low)
        for w in expanded.lower().split():
            if w in STOPWORDS or any(ch.isdigit() for ch in w):
                continue
            words.add(w)
            if w.endswith("s") and len(w) > 3:
                words.add(w[:-1])
    return words

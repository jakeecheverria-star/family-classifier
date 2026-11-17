"""Classify rows: office rules first, then Claude, then the category map."""

from __future__ import annotations

from pathlib import Path

import yaml

from .io import FamilyRow
from .llm import CONFIDENCE_LEVELS, Completer, build_prompt, parse_response
from .rules import OfficeRules
from .uniclass import UniclassTable, tokenize

FALLBACK_IFC = "IfcBuildingElementProxy"


def load_category_map() -> dict[str, str]:
    path = Path(__file__).parent / "ifc_category_map.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def classify(
    rows: list[FamilyRow],
    table: UniclassTable | None,
    rules: OfficeRules,
    completer: Completer | None,
    batch_size: int = 20,
    candidate_limit: int = 25,
    progress=None,
) -> list[FamilyRow]:
    """Fill in the classification fields of each row in place and return the rows.

    With no completer (offline mode), rows that no rule covers get only the
    default IFC entity and are marked for review.
    """
    category_map = load_category_map()
    pending: list[FamilyRow] = []

    for row in rows:
        rule = rules.find(row)
        if rule:
            row.uniclass_code = rule.uniclass_code
            row.ifc_entity = rule.ifc_entity or category_map.get(row.category, FALLBACK_IFC)
            row.confidence = "high"
            row.source = "rule"
            row.reason = rule.note or ("learned " + rule.learned if rule.learned else "office rule")
        else:
            row.ifc_entity = category_map.get(row.category, FALLBACK_IFC)
            row.confidence = "low"
            row.source = "category_map"
            missing = rules.missing_params(row)
            if missing:
                # Don't let the model guess from partial data.
                row.reason = "needs_review: missing " + ", ".join(missing)
            else:
                row.reason = "needs_review: no rule matched"
                pending.append(row)

    if table is not None:
        for row in rows:
            if row.uniclass_code and (item := table.get(row.uniclass_code)):
                row.uniclass_title = item.title

    if completer is None or table is None or not pending:
        return rows

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        candidates = [
            table.candidates(
                tokenize(f"{r.category} {r.family} {r.type} {' '.join(r.params.values())}", rules.abbreviations),
                limit=candidate_limit,
            )
            for r in batch
        ]
        prompt = build_prompt(batch, candidates, [r.ifc_entity for r in batch], rules.abbreviations)
        answers = parse_response(completer(prompt), len(batch))
        for row, cands, answer in zip(batch, candidates, answers):
            _apply_answer(row, answer, {c.code for c in cands}, table)
        if progress:
            progress(min(start + batch_size, len(pending)), len(pending))

    return rows


def _apply_answer(row: FamilyRow, answer: dict, allowed: set[str], table: UniclassTable) -> None:
    if not answer:
        row.reason = "needs_review: no answer from model"
        return
    code = str(answer.get("uniclass_code") or "").strip()
    confidence = str(answer.get("confidence") or "low").lower()
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "low"
    reason = str(answer.get("reason") or "").strip()

    # Guard against invented codes: the code must be one we offered.
    if code and code not in allowed:
        reason = f"model proposed {code}, which wasn't a candidate; {reason}"
        code, confidence = "", "low"

    row.uniclass_code = code
    row.uniclass_title = item.title if code and (item := table.get(code)) else ""
    ifc = str(answer.get("ifc_entity") or "").strip()
    if ifc.startswith("Ifc"):
        row.ifc_entity = ifc
    row.confidence = confidence
    row.source = "llm"
    row.reason = reason

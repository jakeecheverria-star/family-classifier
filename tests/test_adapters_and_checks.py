import gzip
import json

import pytest

from family_classifier.adapters.acc_model_properties import PropertyNames, load, rows_from_properties
from family_classifier.cli import main
from family_classifier.io import FamilyRow, read_export
from family_classifier.llm import make_completer
from family_classifier.pipeline import classify
from family_classifier.rules import OfficeRules

FIELDS = [
    {"key": "p1", "name": "Category"},
    {"key": "p2", "name": "Family Name"},
    {"key": "p3", "name": "Type Name"},
    {"key": "p4", "name": "Width"},
]
ELEMENTS = [
    {"type": "ADDED", "props": {"p1": "Revit Doors", "p2": "DR_SGL_FL", "p3": "900", "p4": "900"}},
    {"type": "ADDED", "props": {"p1": "Revit Doors", "p2": "DR_SGL_FL", "p3": "900", "p4": "900"}},
    {"type": "REMOVED", "props": {"p1": "Revit Walls", "p2": "Basic Wall", "p3": "W1"}},
    {"type": "CHANGED", "props": {"p1": "Revit Windows", "p2": "WIN_CSMT", "p3": "1200"}},
    {"props": {"p1": "Revit Rooms"}},
]


def test_acc_rows_collapse_to_types_and_filter_changes():
    rows = rows_from_properties(FIELDS, ELEMENTS, PropertyNames(params=["Width"]), {"ADDED", "CHANGED"})
    assert [(r.category, r.family, r.type) for r in rows] == [
        ("Doors", "DR_SGL_FL", "900"),
        ("Windows", "WIN_CSMT", "1200"),
    ]
    assert rows[0].params == {"Width": "900"}


def test_acc_missing_field_names_fail_clearly():
    with pytest.raises(ValueError, match="Family Name"):
        rows_from_properties(FIELDS[:1], ELEMENTS)


def test_from_acc_cli_reads_gzip(tmp_path):
    fields, props = tmp_path / "fields.ldjson.gz", tmp_path / "props.ldjson.gz"
    for path, items in ((fields, FIELDS), (props, ELEMENTS)):
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(i) for i in items))
    out = tmp_path / "export.csv"
    assert main(["from-acc", str(fields), str(props), "--out", str(out), "--params", "Width"]) == 0
    assert len(read_export(out)) == 3
    assert len(load(fields, props, change_types={"ADDED"})) == 1


def test_missing_required_params_skip_the_model():
    rules = OfficeRules(required_params={"Doors": ["Width"]})
    row = FamilyRow("Doors", "DR_X", "1", params={"Width": ""})
    calls = []
    classify([row], None, rules, lambda p: calls.append(p) or "[]")
    assert row.reason == "needs_review: missing Width"
    assert calls == []


def test_required_params_round_trip(tmp_path):
    path = tmp_path / "rules.yaml"
    OfficeRules(required_params={"*": ["Description"]}).save(path)
    assert OfficeRules.load(path).missing_params(FamilyRow("Walls", "W", "1")) == ["Description"]


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="azure-openai"):
        make_completer("copilot", "x")

import json
from pathlib import Path

from family_classifier.cli import main
from family_classifier.io import FamilyRow, read_export, write_output
from family_classifier.llm import parse_response
from family_classifier.pipeline import classify
from family_classifier.rules import OfficeRules, Rule
from family_classifier.uniclass import UniclassTable, tokenize

HERE = Path(__file__).parent
ROOT = HERE.parent
TABLE = UniclassTable.load(HERE / "fixtures_uniclass.csv", "test")


class FakeCompleter:
    """Returns a scripted answer and records the prompts it receives."""

    def __init__(self, answers):
        self.answers = answers
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return "Here you go:\n" + json.dumps(self.answers)


def test_table_skips_title_rows():
    assert len(TABLE) == 9
    assert TABLE.get("Pr_10_10_10_20").title == "Test double glazed doorsets"


def test_tokenize_expands_abbreviations_and_drops_numbers():
    assert tokenize("DR_DBL_GLZ 1800x2100", {"DR": "door", "DBL": "double", "GLZ": "glazed"}) == {
        "door", "double", "glazed",
    }


def test_candidates_prefer_overlap_then_depth():
    cands = TABLE.candidates({"double", "glazed", "doorset"})
    assert cands[0].code == "Pr_10_10_10_20"


def test_rule_wins_over_model():
    rules = OfficeRules(rules=[Rule(category="Doors", family="DR_SGL_.*", uniclass_code="Pr_10_10_10_10")])
    row = FamilyRow("Doors", "DR_SGL_FL", "900x2100")
    fake = FakeCompleter([])
    classify([row], TABLE, rules, fake)
    assert (row.source, row.confidence, row.uniclass_code, row.ifc_entity) == (
        "rule", "high", "Pr_10_10_10_10", "IfcDoor",
    )
    assert row.uniclass_title == "Test single flush doorsets"
    assert fake.prompts == []


def test_model_answer_applied_and_invented_code_rejected():
    rows = [FamilyRow("Doors", "DR_DBL_GLZ", "1800"), FamilyRow("Generic Models", "GM_BOLLARD", "Fixed")]
    rules = OfficeRules(abbreviations={"DR": "door", "DBL": "double", "GLZ": "glazed"})
    fake = FakeCompleter([
        {"id": 0, "uniclass_code": "Pr_10_10_10_20", "ifc_entity": "IfcDoor", "confidence": "high", "reason": "ok"},
        {"id": 1, "uniclass_code": "Pr_99_99_99_99", "ifc_entity": "IfcElement", "confidence": "high", "reason": "x"},
    ])
    classify(rows, TABLE, rules, fake)
    assert rows[0].uniclass_code == "Pr_10_10_10_20" and rows[0].confidence == "high"
    assert rows[1].uniclass_code == "" and rows[1].confidence == "low"
    assert "wasn't a candidate" in rows[1].reason
    assert "Pr_10_10_10_20" in fake.prompts[0]


def test_parse_response_tolerates_garbage():
    assert parse_response("no json here", 2) == [{}, {}]
    assert parse_response('[{"id": 1, "uniclass_code": "A"}]', 2) == [{}, {"id": 1, "uniclass_code": "A"}]


def test_offline_marks_rows_for_review():
    row = FamilyRow("Lighting Fixtures", "LT_LED_PNL", "600x600")
    classify([row], None, OfficeRules(), None)
    assert (row.ifc_entity, row.confidence, row.source) == ("IfcLightFixture", "low", "category_map")


def test_learn_adds_and_updates_rules(tmp_path):
    rules = OfficeRules()
    row = FamilyRow("Doors", "DR_DBL_GLZ", "1800", uniclass_code="Pr_10_10_10_10", ifc_entity="IfcDoor",
                    source="llm", reviewed_uniclass_code="Pr_10_10_10_20")
    assert rules.learn([row]) == 1
    assert rules.find(FamilyRow("Doors", "DR_DBL_GLZ", "2000")).uniclass_code == "Pr_10_10_10_20"

    row.reviewed_uniclass_code = "Pr_10_10_10"
    assert rules.learn([row]) == 1
    assert len(rules.rules) == 1

    path = tmp_path / "rules.yaml"
    rules.save(path)
    assert OfficeRules.load(path).rules[0].uniclass_code == "Pr_10_10_10"


def test_learn_skips_unreviewed_and_approved_rule_rows():
    rows = [
        FamilyRow("Doors", "A", "1", uniclass_code="Pr_10_10", source="llm"),
        FamilyRow("Doors", "B", "1", uniclass_code="Pr_10_10", source="rule", approved="y"),
    ]
    assert OfficeRules().learn(rows) == 0


def test_cli_offline_round_trip(tmp_path):
    out = tmp_path / "mapped.csv"
    code = main([
        "classify", str(ROOT / "examples" / "sample_export.csv"),
        "--rules", str(ROOT / "examples" / "rules.yaml"),
        "--out", str(out), "--offline",
    ])
    assert code == 0
    rows = read_export(out)
    assert len(rows) == 10
    assert rows[0].source == "rule"
    assert rows[0].params["element_id"] == "1001"

    # Simulate a review, then learn.
    rows[1].reviewed_uniclass_code = "Pr_10_10_10_20"
    write_output(rows, out)
    rules_path = tmp_path / "rules.yaml"
    assert main(["learn", str(out), "--rules", str(rules_path)]) == 0
    assert OfficeRules.load(rules_path).rules[0].family == "DR_DBL_GLZ"

# -*- coding: utf-8 -*-
"""Write reviewed Uniclass codes and IFC entities back to family types."""
# Written for IronPython 2.7 and CPython 3, so no f-strings.

__title__ = "Write\nBack"
__doc__ = (
    "Read a reviewed family-classifier CSV and write approved codes to type "
    "parameters. Only rows with approved=y or a reviewed_* value are written."
)

import csv
import io

from pyrevit import revit, DB, forms, script

# Type parameters to write. Both must exist as shared or project parameters,
# bound to the categories you classify, before you run this button.
# The Revit IFC exporter reads ClassificationCode in the form
# "[Uniclass]Pr_xx_xx_xx_xx:Title" and IfcExportAs as an IFC entity name.
CLASSIFICATION_PARAM = "ClassificationCode"
IFC_PARAM = "IfcExportAs"
CLASSIFICATION_NAME = "Uniclass"

APPROVED_VALUES = ("y", "yes", "x", "1", "true")

output = script.get_output()


def read_rows(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    try:
        # CPython 3
        return list(csv.DictReader(io.StringIO(text)))
    except TypeError:
        # IronPython 2.7: csv needs byte strings.
        data = text.encode("utf-8").splitlines()
        rows = []
        for r in csv.DictReader(data):
            rows.append(dict((k.decode("utf-8"), (v or "").decode("utf-8")) for k, v in r.items()))
        return rows


def final_values(row):
    approved = (row.get("approved") or "").strip().lower() in APPROVED_VALUES
    code = (row.get("reviewed_uniclass_code") or "").strip()
    ifc = (row.get("reviewed_ifc_entity") or "").strip()
    if not code and approved:
        code = (row.get("uniclass_code") or "").strip()
    if not ifc and approved:
        ifc = (row.get("ifc_entity") or "").strip()
    title = (row.get("uniclass_title") or "").strip() if code == row.get("uniclass_code") else ""
    return code, title, ifc


def set_text(element, name, value):
    p = element.LookupParameter(name)
    if p is None:
        return "missing"
    if p.IsReadOnly or p.StorageType != DB.StorageType.String:
        return "not writable"
    p.Set(value)
    return "ok"


path = forms.pick_file(file_ext="csv")
if not path:
    script.exit()

rows = read_rows(path)
doc = revit.doc
written, skipped, problems = 0, 0, []

with revit.Transaction("Write classification"):
    for row in rows:
        code, title, ifc = final_values(row)
        if not code and not ifc:
            skipped += 1
            continue
        try:
            element = doc.GetElement(DB.ElementId(int(row["element_id"])))
        except Exception:
            element = None
        if element is None:
            problems.append((row.get("family"), row.get("type"), "element not found"))
            continue
        if code:
            value = u"[{}]{}".format(CLASSIFICATION_NAME, code)
            if title:
                value += u":" + title
            status = set_text(element, CLASSIFICATION_PARAM, value)
            if status != "ok":
                problems.append((row.get("family"), row.get("type"), CLASSIFICATION_PARAM + " " + status))
        if ifc:
            status = set_text(element, IFC_PARAM, ifc)
            if status != "ok":
                problems.append((row.get("family"), row.get("type"), IFC_PARAM + " " + status))
        written += 1

output.print_md("Wrote **{}** types. Skipped **{}** unreviewed rows.".format(written, skipped))
if problems:
    output.print_md("**{} problems:**".format(len(problems)))
    output.print_table([list(p) for p in problems], columns=["Family", "Type", "Problem"])

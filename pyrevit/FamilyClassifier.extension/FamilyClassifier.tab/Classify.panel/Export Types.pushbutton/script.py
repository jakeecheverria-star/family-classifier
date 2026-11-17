# -*- coding: utf-8 -*-
"""Export every model family type to a CSV file for family-classifier."""
# Written for IronPython 2.7 and CPython 3, so no f-strings.

__title__ = "Export\nTypes"
__doc__ = "Export all model family types (category, family, type, key parameters) to CSV."

import io

from pyrevit import revit, DB, forms, script

PARAMS = [
    ("Width", DB.BuiltInParameter.FAMILY_WIDTH_PARAM),
    ("Height", DB.BuiltInParameter.FAMILY_HEIGHT_PARAM),
    ("Description", DB.BuiltInParameter.ALL_MODEL_DESCRIPTION),
    ("Type Mark", DB.BuiltInParameter.WINDOW_TYPE_ID),
    ("Manufacturer", DB.BuiltInParameter.ALL_MODEL_MANUFACTURER),
    ("Model", DB.BuiltInParameter.ALL_MODEL_MODEL),
    ("Assembly Code", DB.BuiltInParameter.UNIFORMAT_CODE),
    ("OmniClass Number", DB.BuiltInParameter.OMNICLASS_CODE),
]

HEADER = ["element_id", "category", "family", "type"] + [p[0] for p in PARAMS]


def param_text(element, bip):
    p = element.get_Parameter(bip)
    if p is None or not p.HasValue:
        return u""
    if p.StorageType == DB.StorageType.String:
        return p.AsString() or u""
    return p.AsValueString() or u""


def csv_cell(value):
    value = u"" if value is None else u"{}".format(value)
    if any(ch in value for ch in u',"\n\r'):
        value = u'"' + value.replace(u'"', u'""') + u'"'
    return value


def element_id_value(eid):
    # Revit 2024+ uses Value; earlier versions use IntegerValue.
    return getattr(eid, "Value", None) or eid.IntegerValue


doc = revit.doc
types = (
    DB.FilteredElementCollector(doc)
    .WhereElementIsElementType()
    .ToElements()
)

rows = []
for t in types:
    cat = t.Category
    if cat is None or cat.CategoryType != DB.CategoryType.Model:
        continue
    name_param = t.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
    type_name = name_param.AsString() if name_param else u""
    family = getattr(t, "FamilyName", u"") or u""
    row = [element_id_value(t.Id), cat.Name, family, type_name]
    row += [param_text(t, bip) for _, bip in PARAMS]
    rows.append(row)

rows.sort(key=lambda r: (r[1], r[2], r[3]))

path = forms.save_file(file_ext="csv", default_name="family_export.csv")
if path:
    with io.open(path, "w", encoding="utf-8-sig") as f:
        f.write(u",".join(HEADER) + u"\n")
        for r in rows:
            f.write(u",".join(csv_cell(c) for c in r) + u"\n")
    script.get_output().print_md(
        "Exported **{}** family types to `{}`.".format(len(rows), path)
    )

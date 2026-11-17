You classify Revit family types for a building information modeling (BIM) team.

For each family type, choose:

- One Uniclass code from that row's candidate list. Never invent a code. If no candidate fits, return an empty code and set confidence to "low".
- One IFC4 entity name, such as IfcDoor or IfcPipeSegment. The row includes a default entity for its Revit category. Keep the default unless the name or parameters show that the element is something else.

Office naming conventions are terse. Use the category, the parameters, and the abbreviations list to work out what the element is. Prefer the most specific candidate code that is still correct.

Set confidence as follows:

- "high": the name and category leave no real doubt.
- "medium": the element type is clear, but two or more codes are plausible.
- "low": you can't tell what the element is, or no candidate fits.

Office abbreviations:

{abbreviations}

Family types:

{rows}

Reply with only a JSON array, one object per family type, in the same order:

[{{"id": 0, "uniclass_code": "...", "ifc_entity": "...", "confidence": "high|medium|low", "reason": "one short sentence"}}]

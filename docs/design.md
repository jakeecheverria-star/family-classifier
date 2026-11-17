# Design notes

## Goals

- Map any office's Revit naming convention to Uniclass and IFC, without the office renaming its families.
- Make review fast. Offices won't put unreviewed codes in a deliverable, so the review step matters more than raw accuracy.
- Learn from every review, so each run on the same library needs less review.

## Non-goals

- Renaming families.
- Editing geometry.
- Holding client or project data.

## Pipeline

Each row passes through three sources, in order:

| Order | Source | Confidence | When it applies |
|---|---|---|---|
| 1 | Office rule | `high` | A rule in `rules.yaml` matches the category, family, and type. |
| 2 | Claude | from the model | No rule matches, and the run isn't offline. |
| 3 | Category map | `low` | Offline runs, or the model returned nothing for the row. |

## Why candidates are prefiltered

The Products table has thousands of codes. Sending all of them in every prompt is slow and costly, and it invites the model to pick a plausible code from the wrong group. The pipeline instead expands office abbreviations, scores each Uniclass title by shared words, and sends the top 25 as that row's candidates. The model must pick from that list, and the pipeline rejects any code that wasn't offered.

The trade-off: if the right code isn't in the top 25, the model can't pick it. The fix is better abbreviations in `rules.yaml`, not a larger list.

## Learning loop

`family-classifier learn` reads the reviewed CSV. For each row with a correction or with `approved` set, it adds a rule that matches that exact category and family. Learned rules go at the top of the file, so they override broader hand-written rules. A repeat review of the same family updates the existing learned rule instead of adding a new one.

Learned rules are plain YAML, so you can generalize one by hand. For example, change `family: DR_SGL_FL` to `family: DR_SGL_.*` to cover every single door.

## Write-back

The Revit IFC exporter reads a type parameter named `ClassificationCode` in the form `[Uniclass]Code:Title`, and `IfcExportAs` for the entity. The Write Back button writes both. It doesn't create the parameters; they must already exist in the project.

## Open questions

- Should rules match on parameters such as width, not only names?
- Should the review step be a small web page instead of a CSV?
- How should the tool handle one family type that needs two Uniclass codes, such as a product code and a system code?

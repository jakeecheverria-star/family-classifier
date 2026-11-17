# Family classifier

Family classifier reads the Revit family and type names that an office already uses and proposes a Uniclass code and an Industry Foundation Classes (IFC) entity for each one. You review the proposals, and the tool learns your corrections as office rules, so each run needs less review than the last.

## Status

Early prototype. The command-line tool runs end to end on a CSV export. The pyRevit buttons are drafts that haven't been tested in Revit yet.

## How it works

The tool runs in five stages:

1. **Export.** A pyRevit button exports every loaded family type to a CSV file, with its Revit category and key parameters.
2. **Classify.** The `classify` command checks each row against your office rules first. Rows that no rule covers go to Claude, which picks from a short list of candidate Uniclass codes and returns a code, an IFC entity, a confidence level, and a one-line reason.
3. **Review.** You open the output CSV, type `y` in the `approved` column for rows that look right, and type corrections into the `reviewed_*` columns.
4. **Learn.** The `learn` command turns your corrections into office rules in `rules.yaml`.
5. **Write back.** A pyRevit button writes the approved codes into the `ClassificationCode` and `IfcExportAs` type parameters, which the Revit IFC exporter reads.

For the reasoning behind each stage, see [Design notes](docs/design.md).

## Before you begin

You need the following:

- Python 3.10 or later.
- An Anthropic API key in `ANTHROPIC_API_KEY`, or an approved Azure OpenAI deployment. Neither is needed for rules-only runs.
- The Uniclass Products (Pr) table, downloaded from NBS as a CSV or Excel file. This repo doesn't include the Uniclass tables. See [Uniclass data](docs/uniclass-data.md).
- For the Revit side: Revit 2022 or later and pyRevit.

## Install

To install the tool, run the following from the repo folder:

```
pip install -e ".[anthropic,dev]"
```

For Azure OpenAI instead, install `.[azure]`. For rules-only use, install the base package with no extras.

To install the Revit buttons, add the `pyrevit` folder of this repo as a custom extension path in pyRevit settings, and then reload pyRevit. A **FamilyClassifier** tab appears with **Export Types** and **Write Back** buttons.

Before you use **Write Back**, add two text type parameters to the project, named `ClassificationCode` and `IfcExportAs`, and bind them to the categories that you classify.

## Usage

To classify an export, run the following:

```
family-classifier classify examples/sample_export.csv \
    --uniclass data/Uniclass2015_Pr.csv \
    --rules examples/rules.yaml \
    --out mapped.csv
```

To try the pipeline without an API key, add `--offline`. Offline mode uses rules and the IFC category map only, and marks every other row as `needs_review`.

To learn from a reviewed file, run the following:

```
family-classifier learn mapped.csv --rules examples/rules.yaml
```

To build the export from ACC instead of Revit, download the fields and properties files of a Model Properties index or diff, and then run the following:

```
family-classifier from-acc fields.ldjson.gz properties.ldjson.gz \
    --changes ADDED,CHANGED --params Width,Height --out export.csv
```

The adapter keeps one row per family type. Its default property names are a draft; check them against a real fields file.

To run in an organization with approved services only, see [Deployment](docs/deployment.md).

## Output columns

The output CSV adds these columns to each input row:

| Column | Meaning |
|---|---|
| `uniclass_code` | Proposed Uniclass code, in the form `Pr_xx_xx_xx_xx`. |
| `uniclass_title` | Title of that code in the Uniclass table. |
| `ifc_entity` | Proposed IFC entity, for example `IfcDoor`. |
| `confidence` | `high`, `medium`, or `low`. |
| `source` | `rule`, `llm`, or `category_map`. |
| `reason` | One-line explanation. |
| `approved` | Empty. Type `y` to accept the proposal as is. |
| `reviewed_uniclass_code` | Empty. Fill it in to correct the code. |
| `reviewed_ifc_entity` | Empty. Fill it in to correct the IFC entity. |

## Repo layout

| Path | Contents |
|---|---|
| `src/family_classifier/` | Python package and command-line tool. |
| `src/family_classifier/prompts/` | Prompt text sent to Claude. Edit prompts here, not in code. |
| `pyrevit/` | pyRevit extension with the export and write-back buttons. |
| `examples/` | Sample export and sample office rules. |
| `docs/` | Design notes and data sources. |
| `tests/` | Tests. They run without an API key. |

## Scope and data

This tool maps to public classification systems only. Don't commit client data, project-specific breakdown structures, or Revit models to this repo.

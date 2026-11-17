# Deployment

The tool is built from swappable parts, so one codebase can run in a personal environment and inside an organization with stricter rules.

## Parts

| Part | Options | Choose with |
|---|---|---|
| Input | Revit CSV export (pyRevit), ACC Model Properties results | `family-classifier from-acc`, or the **Export Types** button |
| Model | Anthropic, Azure OpenAI, or none | `--provider`, or `--offline` |
| Output | CSV | Read it from Power BI, or upload it to a SharePoint list |

## Personal environment

Use this to develop and test the tool on sample models that you own.

- Input: CSV export or sample ACC data from your own APS account.
- Model: `--provider anthropic`.

## Organization environment

Use this when the organization allows only approved services.

- Input: ACC Model Properties results for the project, through `from-acc`.
- Model: `--provider azure-openai` with the organization's approved deployment, or `--offline` to use office rules only.
- Output: CSV into SharePoint and Power BI.

Before you run the tool on project data, confirm with the organization's IT and information-security owners which model provider, if any, is approved.

## Keep the environments separate

Data flows one way: from the generic repo into the organization, never back.

- Don't commit project data, project rules, or reviewed CSV files from an organization to the personal repo.
- Keep each organization's `rules.yaml` in that organization's storage. The learned rules describe its naming convention, which is its data.
- Changes to the generic code go back to the personal repo only if they contain no project data.

## Incremental runs on ACC

To classify only what changed since the last published version, do the following:

1. Run a Model Properties diff between the previous and the new version.
2. Download the diff's fields and properties files.
3. Run `family-classifier from-acc fields.ldjson.gz properties.ldjson.gz --changes ADDED,CHANGED --out export.csv`.
4. Run `classify` on `export.csv`. Types already covered by office rules need no model call.

Automating steps 1 and 2 with a webhook is a separate service. See the open issue for change-triggered runs.

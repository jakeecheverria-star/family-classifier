# Uniclass data

This tool needs the Uniclass Products (Pr) table. The repo doesn't include it.

## Get the table

1. Go to the [Uniclass download page](https://uniclass.thenbs.com/download).
2. Download the Products (Pr) table as Excel.
3. Save it in the `data/` folder, with the release in the file name, for example `data/Uniclass2015_Pr_2026-07.xlsx`.

The loader finds the `Code` and `Title` columns on its own, including when the file has title rows above the header.

## Versions

NBS updates the tables quarterly. Codes are sometimes added, retitled, or withdrawn. To keep results traceable, do the following:

- Pass `--uniclass-version` on each run, for example `--uniclass-version "2026-07"`.
- Set `uniclass_version` in your `rules.yaml` to the release your rules were learned against.

If the two don't match, the tool prints a warning so that you can check learned rules against the new table.

## License

NBS publishes Uniclass under the Creative Commons Attribution-NoDerivatives 4.0 license (CC BY-ND 4.0). That allows use on personal and commercial projects, but NBS asks users not to adapt the tables or add their own codes.

For this repo, that means:

- Don't add invented codes to a Uniclass table or to `rules.yaml`. To request a missing code, contact NBS.
- Keep the tables out of the repo until you have confirmed that redistributing them inside a tool meets the license terms, including attribution.

## Other classification systems

The pipeline is written around Uniclass Pr. To add another table, such as Uniclass Systems (Ss) or OmniClass, see the open issue for multiple classification tables.

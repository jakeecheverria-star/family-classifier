"""Command-line entry point: `family-classifier classify` and `family-classifier learn`."""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from .io import read_export, write_output
from .llm import DEFAULT_MODEL
from .pipeline import classify
from .rules import OfficeRules
from .uniclass import UniclassTable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="family-classifier")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("classify", help="Propose Uniclass and IFC for an export CSV.")
    c.add_argument("export", help="CSV exported from Revit.")
    c.add_argument("--uniclass", help="Uniclass Pr table (CSV or XLSX) from NBS.")
    c.add_argument("--uniclass-version", help="Version label to record, for example 'Pr v1.32'.")
    c.add_argument("--rules", default="rules.yaml", help="Office rules file.")
    c.add_argument("--out", default="mapped.csv", help="Output CSV.")
    c.add_argument("--offline", action="store_true", help="Use rules and the category map only.")
    c.add_argument("--provider", default="anthropic", help="anthropic or azure-openai.")
    c.add_argument("--model", default=DEFAULT_MODEL, help="Model name, or Azure deployment name.")
    c.add_argument("--batch-size", type=int, default=20)

    l = sub.add_parser("learn", help="Turn reviewed rows into office rules.")
    l.add_argument("reviewed", help="Output CSV after review.")
    l.add_argument("--rules", default="rules.yaml")

    a = sub.add_parser("from-acc", help="Convert ACC Model Properties results to an export CSV.")
    a.add_argument("fields", help="Fields file (.ldjson or .ldjson.gz).")
    a.add_argument("properties", help="Properties file (.ldjson or .ldjson.gz).")
    a.add_argument("--out", default="export.csv")
    a.add_argument("--changes", default="", help="For diff results, for example ADDED,CHANGED.")
    a.add_argument("--params", default="", help="Comma-separated parameter names to keep.")

    args = parser.parse_args(argv)
    handlers = {"classify": _classify, "learn": _learn, "from-acc": _from_acc}
    return handlers[args.command](args)


def _from_acc(args) -> int:
    from .adapters.acc_model_properties import PropertyNames, load

    names = PropertyNames()
    if args.params:
        names.params = [p.strip() for p in args.params.split(",") if p.strip()]
    changes = {c.strip().upper() for c in args.changes.split(",") if c.strip()} or None
    rows = load(args.fields, args.properties, names=names, change_types=changes)
    write_output(rows, args.out)
    print(f"Wrote {len(rows)} distinct family types to {args.out}.")
    return 0


def _classify(args) -> int:
    rows = read_export(args.export)
    rules = OfficeRules.load(args.rules)
    table = UniclassTable.load(args.uniclass, args.uniclass_version) if args.uniclass else None

    if table and rules.uniclass_version and rules.uniclass_version != table.version:
        print(
            f"Warning: rules were learned against Uniclass '{rules.uniclass_version}', "
            f"but this run uses '{table.version}'. Check learned codes still exist.",
            file=sys.stderr,
        )

    completer = None
    if not args.offline:
        if table is None:
            print("Error: --uniclass is required unless you use --offline.", file=sys.stderr)
            return 2
        from .llm import make_completer

        completer = make_completer(args.provider, args.model)

    def progress(done: int, total: int) -> None:
        print(f"  classified {done}/{total}", file=sys.stderr)

    classify(rows, table, rules, completer, batch_size=args.batch_size, progress=progress)
    write_output(rows, args.out)

    counts = Counter(r.confidence for r in rows)
    print(
        f"Wrote {len(rows)} rows to {args.out}: "
        f"{counts['high']} high, {counts['medium']} medium, {counts['low']} low confidence."
    )
    return 0


def _learn(args) -> int:
    rows = read_export(args.reviewed)
    rules = OfficeRules.load(args.rules)
    changed = rules.learn(rows)
    rules.save(args.rules)
    print(f"Updated {changed} rules in {args.rules}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

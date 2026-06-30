"""gw graph domain-refs <name> — D-13 3-column bubble-up of package references."""

from __future__ import annotations

import json as _json
import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        records = reader.domain_references(domain_name=args.name)
    finally:
        reader.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print(
                f"Domain '{args.name}' has no incoming references.",
                file=sys.stderr,
            )
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(
            _json.dumps(
                [
                    {
                        "package": pkg,
                        "total_usage_count": usage,
                        "distinct_domain_count": doms,
                    }
                    for pkg, usage, doms in records
                ]
            )
        )
    else:
        rows = [(pkg, str(usage), str(doms)) for pkg, usage, doms in records]
        keys = ["package", "usage", "domains"]
        widths = {
            "package": max(len("package"), max(len(r[0]) for r in rows)),
            "usage": max(len("usage"), max(len(r[1]) for r in rows)),
            "domains": max(len("domains"), max(len(r[2]) for r in rows)),
        }
        print("  ".join(k.ljust(widths[k]) for k in keys))
        for pkg, usage, doms in rows:
            print(f"{pkg.ljust(widths['package'])}  {usage.ljust(widths['usage'])}  {doms.ljust(widths['domains'])}")
    return exit_codes.SUCCESS

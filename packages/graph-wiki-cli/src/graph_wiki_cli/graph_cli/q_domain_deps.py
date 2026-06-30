"""gw graph domain-deps <name> — D-14 2-column bubble-up of outgoing domain dependencies."""

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
        records = reader.domain_depends_on(domain_name=args.name)
    finally:
        reader.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print(
                f"Domain '{args.name}' has no outgoing dependencies.",
                file=sys.stderr,
            )
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(_json.dumps([{"domain": d, "total_usage_count": u} for d, u in records]))
    else:
        rows = [(d, str(u)) for d, u in records]
        keys = ["domain", "usage"]
        widths = {
            "domain": max(len("domain"), max(len(r[0]) for r in rows)),
            "usage": max(len("usage"), max(len(r[1]) for r in rows)),
        }
        print("  ".join(k.ljust(widths[k]) for k in keys))
        for d, u in rows:
            print(f"{d.ljust(widths['domain'])}  {u.ljust(widths['usage'])}")
    return exit_codes.SUCCESS

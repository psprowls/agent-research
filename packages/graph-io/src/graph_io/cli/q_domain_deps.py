"""cg domain-deps <name> — D-14 2-column bubble-up of outgoing domain dependencies."""

from __future__ import annotations

import argparse
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")


def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        records = queries.domain_depends_on(conn, domain_name=args.name)
    finally:
        conn.close()
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
        print(
            _json.dumps(
                [{"domain": d, "total_usage_count": u} for d, u in records]
            )
        )
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

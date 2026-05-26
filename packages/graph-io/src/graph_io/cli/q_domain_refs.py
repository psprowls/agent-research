"""cg domain-refs <name> — D-13 3-column bubble-up of package references."""

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
        records = queries.domain_references(conn, domain_name=args.name)
    finally:
        conn.close()
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
            print(
                f"{pkg.ljust(widths['package'])}  "
                f"{usage.ljust(widths['usage'])}  "
                f"{doms.ljust(widths['domains'])}"
            )
    return exit_codes.SUCCESS

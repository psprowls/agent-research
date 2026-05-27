"""cg describe-dependency <name> [--ecosystem pypi]"""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument(
        "--ecosystem",
        default="pypi",
        help="package ecosystem (default: pypi)",
    )


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
        desc = queries.describe_dependency(
            conn, ecosystem=args.ecosystem, name=args.name
        )
    finally:
        conn.close()
    if desc is None:
        print(
            f"error: dependency not found: {args.ecosystem}/{args.name}",
            file=sys.stderr,
        )
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"name:             {desc.name}")
        print(f"ecosystem:        {desc.ecosystem}")
        print(f"uri:              {desc.uri}")
        versions = ", ".join(desc.versions_in_use) or "(none)"
        used_by = ", ".join(desc.used_by) or "(none)"
        print(f"versions_in_use:  {versions}")
        print(f"used_by:          {used_by}")
    return exit_codes.SUCCESS

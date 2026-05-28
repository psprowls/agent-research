"""cg describe-package <name>"""

from __future__ import annotations

import argparse
import dataclasses
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
        desc = queries.describe_package(conn, name=args.name)
    finally:
        conn.close()
    if desc is None:
        print(f"error: package not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"package: {desc.name}")
        print(f"language: {desc.language}")
        print(f"version:  {desc.version}")
        print(f"files:    {len(desc.files)}")
        print(f"counts:   {desc.counts}")
        # Phase 55 D-08: both directions of the depends_on_package edge.
        print(f"internal deps:       {', '.join(desc.internal_dependencies) or '-'}")
        print(f"internal dependents: {', '.join(desc.internal_dependents) or '-'}")
    return exit_codes.SUCCESS

"""cg describe-path <path>"""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")


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
        desc = queries.describe_path(conn, path=args.path)
    finally:
        conn.close()
    if desc is None:
        print(f"error: path not found in graph: {args.path}", file=sys.stderr)
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"path: {desc.path}")
        print("children:")
        for c in desc.children:
            print(f"  {c.kind}  {c.name}  line {c.line}")
        print("imports:")
        for i in desc.imports:
            print(f"  {i.path}")
    return exit_codes.SUCCESS

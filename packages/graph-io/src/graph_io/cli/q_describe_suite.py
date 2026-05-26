"""cg describe-suite <name> — compact key-value for a TestSuite.

SuiteDescription lacks a `framework` field as of Phase 32 — re-add when
the helper grows it.
"""

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
        desc = queries.describe_test_suite(conn, suite_name=args.name)
    finally:
        conn.close()
    if desc is None:
        print(f"error: not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"suite:  {desc.name}")
        print(f"uri:    {desc.uri}")
        print(f"kind:   {desc.kind}")
        print(f"files:  {desc.file_count}")
    return exit_codes.SUCCESS

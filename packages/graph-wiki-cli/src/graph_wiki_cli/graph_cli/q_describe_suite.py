"""gw graph describe-suite <name> — compact key-value for a TestSuite.

SuiteDescription lacks a `framework` field as of Phase 32 — re-add when
the helper grows it.
"""

from __future__ import annotations

import sys

from graph_io import exit_codes, queries, store
from graph_io import render as _render
from workspace_io.paths import graph_dir

from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
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
        if desc is None:
            print(f"error: not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = queries.children_for(
            conn, kind="test_suite", name=desc.name, depth=getattr(args, "depth", None)
        )
    finally:
        conn.close()
    print(_render.format_suite(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

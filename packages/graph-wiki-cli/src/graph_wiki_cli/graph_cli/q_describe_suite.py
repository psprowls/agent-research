"""gw graph describe-suite <name> — compact key-value for a TestSuite.

SuiteDescription lacks a `framework` field as of Phase 32 — re-add when
the helper grows it.
"""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_io import render as _render

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
        desc = reader.describe_test_suite(suite_name=args.name)
        if desc is None:
            print(f"error: not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = reader.children_for(kind="test_suite", name=desc.name, depth=getattr(args, "depth", None))
    finally:
        reader.close()
    print(_render.format_suite(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

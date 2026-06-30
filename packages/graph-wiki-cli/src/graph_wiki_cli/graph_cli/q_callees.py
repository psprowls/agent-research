"""gw graph callees <name> [--depth N]"""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli import _format
from graph_wiki_cli.graph_cli._args import DepthNameArgs


def run(args: DepthNameArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        records = reader.callees(name=args.name, depth=args.depth, include_test_files=args.include_tests)
    finally:
        reader.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS

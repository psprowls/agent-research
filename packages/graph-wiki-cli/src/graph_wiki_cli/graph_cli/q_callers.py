"""gw graph callers <name> [--depth N]"""

from __future__ import annotations

import sys

from graph_io import exit_codes, queries, store
from workspace_io.paths import graph_dir

from graph_wiki_cli.graph_cli import _format
from graph_wiki_cli.graph_cli._args import DepthNameArgs


def run(args: DepthNameArgs) -> int:
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
        records = queries.callers(conn, name=args.name, depth=args.depth, include_test_files=args.include_tests)
    finally:
        conn.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS

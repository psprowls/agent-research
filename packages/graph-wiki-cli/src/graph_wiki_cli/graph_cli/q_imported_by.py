"""gw graph imported-by <path> [--symbol NAME] [--depth N]"""

from __future__ import annotations

import sys
from typing import Protocol

from graph_io import exit_codes, queries, store
from workspace_io.paths import graph_dir

from graph_wiki_cli.graph_cli import _format
from graph_wiki_cli.graph_cli._args import PathDescribeArgs


class ImportedByArgs(PathDescribeArgs, Protocol):
    symbol: str | None
    depth: int


def run(args: ImportedByArgs) -> int:
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
        records = queries.imported_by(conn, path=args.path, symbol=args.symbol, depth=args.depth)
    finally:
        conn.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS

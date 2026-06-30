"""gw graph imported-by <path> [--symbol NAME] [--depth N]"""

from __future__ import annotations

import sys
from typing import Protocol

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli import _format
from graph_wiki_cli.graph_cli._args import PathDescribeArgs


class ImportedByArgs(PathDescribeArgs, Protocol):
    symbol: str | None
    depth: int


def run(args: ImportedByArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        records = reader.imported_by(path=args.path, symbol=args.symbol, depth=args.depth)
    finally:
        reader.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS

"""gw graph imported-by <path> [--symbol NAME] [--depth N]"""

from __future__ import annotations

import sys
from typing import Protocol

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes

from graph_wiki_cli.graph_cli import _format
from graph_wiki_cli.graph_cli._args import PathDescribeArgs


class ImportedByArgs(PathDescribeArgs, Protocol):
    symbol: str | None
    depth: int


def run(args: ImportedByArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        records = reader.imported_by(path=args.path, symbol=args.symbol, depth=args.depth)
    finally:
        reader.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS

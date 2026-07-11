"""gw graph find --name X [--kind KIND] [--in-package PKG]"""

from __future__ import annotations

import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes
from graph_wiki_core.commands.graph_query import render as _render

from graph_wiki_cli.graph_cli._args import FindArgs


def run(args: FindArgs) -> int:
    # D-01: at least one filter required.
    if args.name is None and args.kind is None and args.in_package is None:
        return exit_codes.GENERIC

    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        records = reader.find(
            name=args.name,
            kind=args.kind,
            in_package=args.in_package,
        )
    finally:
        reader.close()

    # D-07: --in-package non-match → exit 1 (silent zero-result distinct from
    # name/kind zero, which preserves historical SUCCESS for those filters).
    if args.in_package is not None and not records:
        return exit_codes.GENERIC

    def _notice(shown: int, total: int) -> None:
        print(f"... showing {shown} of {total} (truncated)", file=sys.stderr)

    print(_render.render(records, fmt=args.fmt, cap=50, on_truncate=_notice))
    return exit_codes.SUCCESS

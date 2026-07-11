"""gw graph describe-dependency <name> [--ecosystem pypi]"""

from __future__ import annotations

import sys
from typing import cast

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes
from graph_wiki_core.commands.graph_query import render as _render

from graph_wiki_cli.graph_cli._args import DependencyDescribeArgs


def run(args: DependencyDescribeArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        desc = reader.describe_dependency(ecosystem=cast(str, args.ecosystem), name=args.name)
    finally:
        reader.close()
    if desc is None:
        print(
            f"error: dependency not found: {args.ecosystem}/{args.name}",
            file=sys.stderr,
        )
        return exit_codes.GENERIC
    print(_render.format_dependency(desc, fmt=args.fmt))
    return exit_codes.SUCCESS

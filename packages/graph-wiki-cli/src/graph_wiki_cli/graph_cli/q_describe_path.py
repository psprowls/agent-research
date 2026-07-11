"""gw graph describe-path <path>"""

from __future__ import annotations

import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes
from graph_wiki_core.commands.graph_query import render as _render

from graph_wiki_cli.graph_cli._args import PathDescribeArgs


def run(args: PathDescribeArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        desc = reader.describe_path(path=args.path)
        if desc is None:
            print(f"error: path not found in graph: {args.path}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = reader.children_for(kind="file", path=desc.path, depth=getattr(args, "depth", None))
    finally:
        reader.close()
    print(_render.format_path(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

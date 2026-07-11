"""gw graph describe-package <name>"""

from __future__ import annotations

import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes
from graph_wiki_core.commands.graph_query import render as _render

from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        desc = reader.describe_package(name=args.name)
        if desc is None:
            print(f"error: package not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = reader.children_for(kind="package", name=desc.name, depth=getattr(args, "depth", None))
    finally:
        reader.close()
    print(_render.format_package(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

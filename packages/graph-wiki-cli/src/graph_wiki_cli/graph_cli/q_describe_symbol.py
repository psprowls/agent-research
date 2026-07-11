"""gw graph describe <name> --kind function|class|method|type"""

from __future__ import annotations

import sys
from typing import cast

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes
from graph_wiki_core.commands.graph_query import render as _render

from graph_wiki_cli.graph_cli._args import MutableDescribeArgs

# DB node kinds this module describes; the CLI --kind value equals the DB kind.
CODE_KINDS = ("function", "class", "method", "type")


def run(args: MutableDescribeArgs) -> int:
    """Describe a single code symbol. `args.kind` is the DB kind, `args.selector`
    the name; `args.in_package` optionally narrows via `describe_symbol`. If
    multiple nodes still match, the first (ORDER BY path, line) is described.
    """
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        desc = reader.describe_symbol(
            kind=cast(str, args.kind),
            name=cast(str, args.selector),
            in_package=args.in_package,
            path=getattr(args, "path", None),
            line=getattr(args, "line", None),
        )
        if desc is None:
            print(f"error: {args.kind} not found: {args.selector}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = reader.children_for(
            kind=desc.kind, name=desc.name, path=desc.path, line=desc.line, depth=getattr(args, "depth", None)
        )
    finally:
        reader.close()
    print(_render.format_symbol(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

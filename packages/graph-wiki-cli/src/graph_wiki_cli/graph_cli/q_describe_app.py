"""gw graph describe-app <name> (Phase 50 APP-05 / D-10 / D-11).

Looks up an App node by name and prints its attributes plus joined
counts/files/domains/entry_points/test_suites. Mirrors
`gw graph describe-package` with two added lines for `app_kind` and `signals`.
"""

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
        desc = reader.describe_app(name=args.name)
        if desc is None:
            print(f"error: app not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = reader.children_for(kind="app", name=desc.name, depth=getattr(args, "depth", None))
    finally:
        reader.close()
    print(_render.format_app(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

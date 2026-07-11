"""gw graph describe-domain <name> — D-11 extended human format with nested sub-blocks."""

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
        desc = reader.describe_domain(name=args.name)
        if desc is None:
            print(f"error: not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        packages, subdomains = reader.domain_members(args.name)
        children, eff = reader.children_for(kind="domain", name=desc.name, depth=getattr(args, "depth", None))
    finally:
        reader.close()

    print(_render.format_domain(desc, packages, subdomains, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS

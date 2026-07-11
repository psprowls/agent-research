"""gw graph describe-agent-plugin <name>"""

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
        desc = reader.describe_agent_plugin(name=args.name)
    finally:
        reader.close()
    if desc is None:
        print(f"error: agent_plugin not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_agent_plugin(desc, fmt=args.fmt))
    return exit_codes.SUCCESS

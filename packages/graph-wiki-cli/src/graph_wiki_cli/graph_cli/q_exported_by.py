"""gw graph exported-by <name>"""

from __future__ import annotations

import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes

from graph_wiki_cli.graph_cli import _format
from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        records = reader.exported_by(name=args.name)
    finally:
        reader.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS

"""gw graph dump — raw SQL dump for debugging."""

from __future__ import annotations

import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes

from graph_wiki_cli.graph_cli._args import WorkspaceArgs


def run(args: WorkspaceArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        for line in reader.dump_sql():
            print(line)
    finally:
        reader.close()
    return exit_codes.SUCCESS

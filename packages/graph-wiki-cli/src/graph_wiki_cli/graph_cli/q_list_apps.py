"""gw graph list-apps — list all App nodes alphabetically (Phase 50 APP-05 / D-09)."""

from __future__ import annotations

import dataclasses
import json as _json
import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs


def run(args: FormatArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        records = reader.list_apps()
    finally:
        reader.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print("No apps in graph.", file=sys.stderr)
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(r) for r in records], default=str))
    else:
        for r in records:
            print(r.name)
    return exit_codes.SUCCESS

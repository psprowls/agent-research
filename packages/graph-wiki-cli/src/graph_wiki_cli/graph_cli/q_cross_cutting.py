"""gw graph cross-cutting — D-12 cross-cutting packages ranked by SUM(usage_count)."""

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
        records = reader.cross_cutting_packages()
    finally:
        reader.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print("No zero-domain packages in graph.", file=sys.stderr)
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(
            _json.dumps(
                [
                    {
                        "name": desc.name,
                        "score": score,
                        "package": dataclasses.asdict(desc),
                    }
                    for desc, score in records
                ],
                default=str,
            )
        )
    else:
        name_w = max(len(desc.name) for desc, _ in records)
        for desc, score in records:
            print(f"{desc.name.ljust(name_w)}  score={score}")
    return exit_codes.SUCCESS

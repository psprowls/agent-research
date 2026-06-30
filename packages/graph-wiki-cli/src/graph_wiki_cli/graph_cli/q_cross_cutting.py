"""gw graph cross-cutting — D-12 cross-cutting packages ranked by SUM(usage_count)."""

from __future__ import annotations

import dataclasses
import json as _json
import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs


def run(args: FormatArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
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

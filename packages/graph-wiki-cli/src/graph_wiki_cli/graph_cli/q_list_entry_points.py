"""gw graph list-entry-points <package> [--kind {executable,library}]"""

from __future__ import annotations

import dataclasses
import json as _json
import sys
from typing import Protocol

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs


class ListEntryPointsArgs(FormatArgs, Protocol):
    package: str
    kind: str | None


def run(args: ListEntryPointsArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        entries = reader.entry_points_for_package(package_name=args.package)
    finally:
        reader.close()

    if args.kind is not None:
        entries = [d for d in entries if d.kind == args.kind]

    if not entries:
        if args.fmt == "json":
            print("[]")
        else:
            print(
                f"Package '{args.package}' has no declared entry points.",
                file=sys.stderr,
            )
        return exit_codes.SUCCESS

    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(d) for d in entries], default=str))
    else:
        if args.kind is not None:
            for d in entries:
                print(d.name)
        else:
            for d in entries:
                impl = d.implemented_by_path if d.implemented_by_path else "(unresolved)"
                print(f"{d.name}  [{d.kind}]  -> {impl}")
    return exit_codes.SUCCESS

"""gw graph list-entry-points <package> [--kind {executable,library}]"""

from __future__ import annotations

import dataclasses
import json as _json
import sys
from typing import Protocol

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs


class ListEntryPointsArgs(FormatArgs, Protocol):
    package: str
    kind: str | None


def run(args: ListEntryPointsArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
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

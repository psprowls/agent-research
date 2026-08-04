"""gw graph what-tests <name> -- tests covering a package."""

from __future__ import annotations

import dataclasses
import json as _json
import sys

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import exit_codes

from graph_wiki_cli.graph_cli._args import WhatTestsArgs


def run(args: WhatTestsArgs) -> int:
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code

    try:
        if not reader.node_exists(kind="package", name=args.name):
            print(f"error: no Package named '{args.name}'", file=sys.stderr)
            return exit_codes.GENERIC
        results = reader.tests_for_package(package_name=args.name)
        kind_label = "package"
    finally:
        reader.close()

    if not results:
        if args.fmt == "json":
            print("[]")
        else:
            print(
                f"No TestSuites cover {kind_label} '{args.name}'.",
                file=sys.stderr,
            )
        return exit_codes.SUCCESS

    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(r) for r in results], default=str))
    else:
        for r in results:
            print(r.name)
    return exit_codes.SUCCESS

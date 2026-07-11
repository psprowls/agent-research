"""gw graph what-tests <name> [--kind {package,domain}] — probe-both dispatch (D-01/D-02)."""

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
        if args.kind == "package":
            results = reader.tests_for_package(package_name=args.name)
            kind_label = "package"
        elif args.kind == "domain":
            results = reader.tests_for_domain(domain_name=args.name)
            kind_label = "domain"
        else:
            pkg_exists = reader.node_exists(kind="package", name=args.name)
            dom_exists = reader.node_exists(kind="domain", name=args.name)
            if pkg_exists and dom_exists:
                print(
                    f"error: ambiguous: '{args.name}' is both a Package and a Domain. "
                    "Use --kind package or --kind domain.",
                    file=sys.stderr,
                )
                return exit_codes.AMBIGUOUS
            if not pkg_exists and not dom_exists:
                print(
                    f"error: no Package or Domain named '{args.name}'",
                    file=sys.stderr,
                )
                return exit_codes.GENERIC
            if pkg_exists:
                results = reader.tests_for_package(package_name=args.name)
                kind_label = "package"
            else:
                results = reader.tests_for_domain(domain_name=args.name)
                kind_label = "domain"
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

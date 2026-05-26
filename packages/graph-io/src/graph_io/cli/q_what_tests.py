"""cg what-tests <name> [--kind {package,domain}] — probe-both dispatch (D-01/D-02)."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")
    parser.add_argument("--kind", choices=("package", "domain"), default=None)


def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH

    try:
        if args.kind == "package":
            results = queries.tests_for_package(conn, package_name=args.name)
            kind_label = "package"
        elif args.kind == "domain":
            results = queries.tests_for_domain(conn, domain_name=args.name)
            kind_label = "domain"
        else:
            pkg_exists = bool(
                conn.execute(
                    "SELECT 1 FROM nodes WHERE kind='package' AND name = ? LIMIT 1",
                    (args.name,),
                ).fetchone()
            )
            dom_exists = bool(
                conn.execute(
                    "SELECT 1 FROM nodes WHERE kind='domain' AND name = ? LIMIT 1",
                    (args.name,),
                ).fetchone()
            )
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
                results = queries.tests_for_package(conn, package_name=args.name)
                kind_label = "package"
            else:
                results = queries.tests_for_domain(conn, domain_name=args.name)
                kind_label = "domain"
    finally:
        conn.close()

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

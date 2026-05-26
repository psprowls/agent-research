"""cg describe-domain <name> — D-11 extended human format with nested sub-blocks."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")


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
        desc = queries.describe_domain(conn, name=args.name)
        if desc is None:
            print(f"error: not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        pkg_rows = conn.execute(
            "SELECT p.name FROM edges e "
            "JOIN nodes p ON e.src = p.id "
            "JOIN nodes d ON e.dst = d.id "
            "WHERE e.kind='belongs_to_domain' AND d.kind='domain' AND d.name = ? "
            "ORDER BY p.name",
            (args.name,),
        ).fetchall()
        packages = [r[0] for r in pkg_rows]
        sub_rows = conn.execute(
            "SELECT c.name FROM edges e "
            "JOIN nodes c ON e.dst = c.id "
            "JOIN nodes p ON e.src = p.id "
            "WHERE e.kind='domain_contains_domain' AND p.kind='domain' AND p.name = ? "
            "ORDER BY c.name",
            (args.name,),
        ).fetchall()
        subdomains = [r[0] for r in sub_rows]
    finally:
        conn.close()

    if args.fmt == "json":
        payload = {
            **dataclasses.asdict(desc),
            "packages": packages,
            "subdomains": subdomains,
        }
        print(_json.dumps(payload, default=str))
    else:
        parent = desc.parent if desc.parent else "(none)"
        description = desc.description if desc.description else "(none)"
        print(f"domain:        {desc.name}")
        print(f"uri:           {desc.uri}")
        print(f"parent:        {parent}")
        print(f"description:   {description}")
        print("packages:")
        if packages:
            for name in packages:
                print(f"  - {name}")
        else:
            print("  (none)")
        print("subdomains:")
        if subdomains:
            for name in subdomains:
                print(f"  - {name}")
        else:
            print("  (none)")
    return exit_codes.SUCCESS

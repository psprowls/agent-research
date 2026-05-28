"""cg describe-builtin <uri> — describe a Builtin node by URI (Phase 49 BUILTIN-06)."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("uri", help="builtin URI, e.g. builtin:python/pathlib")


def run(args: argparse.Namespace) -> int:
    # URI parse — fail fast on malformed input with exit_codes.GENERIC.
    if not args.uri.startswith("builtin:"):
        print(f"error: not a builtin URI: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    rest = args.uri.removeprefix("builtin:")
    if "/" not in rest:
        print(f"error: malformed builtin URI: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    language, module_name = rest.split("/", 1)

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
        desc = queries.describe_builtin(conn, language=language, module_name=module_name)
    finally:
        conn.close()
    if desc is None:
        print(f"error: builtin not found: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"language:         {desc.language}")
        print(f"module_name:      {desc.module_name}")
        print(f"uri:              {desc.uri}")
        used_by = ", ".join(desc.used_by) or "(none)"
        print(f"used_by:          {used_by}")
    return exit_codes.SUCCESS

"""cg describe-repo — describe the single Repository node in the graph."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


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
        desc = queries.describe_repository(conn)
    finally:
        conn.close()
    if desc is None:
        print("error: not found: repository", file=sys.stderr)
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        url = desc.url if desc.url else "(none)"
        default_branch = desc.default_branch if desc.default_branch else "(none)"
        print(f"repository:     {desc.name}")
        print(f"uri:            {desc.uri}")
        print(f"url:            {url}")
        print(f"default_branch: {default_branch}")
        print(f"package_count:  {desc.package_count}")
    return exit_codes.SUCCESS

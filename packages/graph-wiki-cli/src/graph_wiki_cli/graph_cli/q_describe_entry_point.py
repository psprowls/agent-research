"""gw graph describe-entry-point <name>

Looks up an EntryPoint by name. Accepts either a bare entry-point name
(unique across all packages) or a qualified ``package:entry`` form. Bare-name
resolution and ambiguity detection are handled by ``queries.resolve_entry_point``:
it scans all packages declaring an EntryPoint with that name and, if multiple
matches are found, returns the candidates so this module can report AMBIGUOUS.
"""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_io import render as _render

from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc, ambiguous = reader.resolve_entry_point(args.name)
    finally:
        reader.close()
    if ambiguous:
        packages = ", ".join(ambiguous)
        print(
            f"error: entry point not found: {args.name} (ambiguous across packages: {packages}; use 'package:entry')",
            file=sys.stderr,
        )
        return exit_codes.AMBIGUOUS
    if desc is None:
        print(f"error: entry point not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_entry_point(desc, fmt=args.fmt))
    return exit_codes.SUCCESS

"""cg CLI entry point — argparse dispatch over 9 subcommands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from workspace_io.config import resolve

from graph_io.cli import (
    ops_dump,
    ops_status,
    ops_sync_wiki,
    ops_update,
    q_callees,
    q_callers,
    q_describe_package,
    q_describe_path,
    q_exported_by,
    q_exports,
    q_find,
    q_imported_by,
    q_imports,
)

_SUBCOMMANDS = {
    "update": ops_update,
    "sync-wiki": ops_sync_wiki,
    "status": ops_status,
    "dump": ops_dump,
    "find": q_find,
    "callers": q_callers,
    "callees": q_callees,
    "imports": q_imports,
    "imported-by": q_imported_by,
    "exports": q_exports,
    "exported-by": q_exported_by,
    "describe-package": q_describe_package,
    "describe-path": q_describe_path,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg", description="lattice code graph CLI")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repo root (defaults to current dir)",
    )
    parser.add_argument(
        "--fmt",
        choices=("human", "json"),
        default="human",
        help="output format for query results",
    )
    parser.add_argument(
        "--mode",
        choices=("test", "workspace"),
        default="workspace",
        help="run in test mode",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, mod in _SUBCOMMANDS.items():
        sp = sub.add_parser(name)
        mod.add_arguments(sp)
        sp.set_defaults(_module=mod)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    require_manifest: bool = True if args.mode == "workspace" else False
    args.workspace = resolve(args.repo, require_manifest).workspace
    return args._module.run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

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
    q_cross_cutting,
    q_describe_app,
    q_describe_builtin,
    q_describe_dependency,
    q_describe_domain,
    q_describe_entry_point,
    q_describe_package,
    q_describe_path,
    q_describe_plugin,
    q_describe_repo,
    q_describe_suite,
    q_domain_clusters,
    q_domain_deps,
    q_domain_refs,
    q_exported_by,
    q_exports,
    q_find,
    q_imported_by,
    q_imports,
    q_list_apps,
    q_list_builtins,
    q_list_domains,
    q_list_entry_points,
    q_list_packages,
    q_list_scripts,
    q_list_suites,
    q_what_tests,
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
    "describe-app": q_describe_app,
    "describe-builtin": q_describe_builtin,
    "describe-dependency": q_describe_dependency,
    "describe-package": q_describe_package,
    "describe-path": q_describe_path,
    "describe-plugin": q_describe_plugin,
    "describe-repo": q_describe_repo,
    "list-apps": q_list_apps,
    "list-builtins": q_list_builtins,
    "list-packages": q_list_packages,
    "list-entry-points": q_list_entry_points,
    "list-scripts": q_list_scripts,
    "list-suites": q_list_suites,
    "describe-suite": q_describe_suite,
    "what-tests": q_what_tests,
    "list-domains": q_list_domains,
    "describe-domain": q_describe_domain,
    "describe-entry-point": q_describe_entry_point,
    "domain-clusters": q_domain_clusters,
    "domain-refs": q_domain_refs,
    "domain-deps": q_domain_deps,
    "cross-cutting": q_cross_cutting,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg", description="graph-wiki code graph CLI")
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
        sp.set_defaults(_module=mod, _parser=sp)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    require_manifest: bool = True if args.mode == "workspace" else False
    args.workspace = resolve(args.repo, require_manifest).workspace
    return args._module.run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Native Typer command surface for `gw graph`.

The code-graph implementation lives in graph_io. This package owns only the
unified graph-wiki CLI presentation layer.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import typer
from workspace_io.config import resolve

from graph_wiki_cli.graph_cli import (
    ops_dump,
    ops_status,
    ops_sync_wiki,
    ops_update,
    q_callees,
    q_callers,
    q_cross_cutting,
    q_describe_agent_plugin,
    q_describe_app,
    q_describe_builtin,
    q_describe_dependency,
    q_describe_domain,
    q_describe_entry_point,
    q_describe_package,
    q_describe_path,
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
    q_list,
    q_list_entry_points,
    q_what_tests,
)
from graph_io.queries import _VALID_KINDS

OUTPUT_FORMATS = ["human", "json"]
RUN_MODES = ["workspace", "test"]
ENTRY_POINT_KINDS = ["executable", "library"]
TEST_TARGET_KINDS = ["package", "domain"]


graph_app = typer.Typer(
    name="graph",
    help="Code graph operations.",
    no_args_is_help=True,
)


def _ctx_args(ctx: typer.Context) -> SimpleNamespace:
    params = ctx.obj or {}
    repo = params.get("repo") or Path.cwd()
    mode = params.get("mode") or "workspace"
    require_manifest = mode == "workspace"
    workspace = resolve(repo, require_manifest).workspace
    return SimpleNamespace(
        repo=repo,
        fmt=params.get("fmt") or "human",
        mode=mode,
        workspace=workspace,
    )


def _run(module, ctx: typer.Context, **kwargs) -> None:
    args = _ctx_args(ctx)
    for key, value in kwargs.items():
        setattr(args, key, value)
    raise typer.Exit(code=module.run(args))


@graph_app.callback()
def graph_options(
    ctx: typer.Context,
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Repo root (defaults to current dir)."),
    fmt: str = typer.Option("human", "--fmt", help="Output format for query results."),
    mode: str = typer.Option("workspace", "--mode", help="Workspace resolution mode."),
) -> None:
    """Code graph operations."""
    if fmt not in OUTPUT_FORMATS:
        raise typer.BadParameter(f"fmt must be one of: {', '.join(OUTPUT_FORMATS)}")
    if mode not in RUN_MODES:
        raise typer.BadParameter(f"mode must be one of: {', '.join(RUN_MODES)}")
    ctx.obj = {"repo": repo, "fmt": fmt, "mode": mode}


@graph_app.command(name="update")
def update_cmd(ctx: typer.Context, full: bool = typer.Option(False, "--full", help="Full rebuild from scratch.")) -> None:
    """Refresh the code graph."""
    _run(ops_update, ctx, full=full)


@graph_app.command(name="sync-wiki")
def sync_wiki_cmd(ctx: typer.Context) -> None:
    """Link package nodes to wiki overview pages."""
    _run(ops_sync_wiki, ctx)


@graph_app.command(name="status")
def status_cmd(ctx: typer.Context) -> None:
    """Print schema version, indexed commit, and counts."""
    _run(ops_status, ctx)


@graph_app.command(name="dump")
def dump_cmd(ctx: typer.Context) -> None:
    """Emit raw SQLite contents for debugging."""
    _run(ops_dump, ctx)


@graph_app.command(name="find")
def find_cmd(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", help="Filter by node name."),
    kind: Optional[str] = typer.Option(None, "--kind", help="Filter by node kind."),
    in_package: Optional[str] = typer.Option(None, "--in-package", help="Filter by containing package."),
) -> None:
    """Find graph nodes. At least one filter is required."""
    if name is None and kind is None and in_package is None:
        typer.echo("Error: at least one of --name, --kind, --in-package is required", err=True)
        raise typer.Exit(code=2)
    if kind is not None and kind not in _VALID_KINDS:
        raise typer.BadParameter(f"invalid choice: {kind} (choose from: {', '.join(sorted(_VALID_KINDS))})")
    _run(q_find, ctx, name=name, kind=kind, in_package=in_package)


@graph_app.command(name="callers")
def callers_cmd(ctx: typer.Context, name: str, depth: int = typer.Option(3, "--depth")) -> None:
    """Show callers of a symbol."""
    _run(q_callers, ctx, name=name, depth=depth)


@graph_app.command(name="callees")
def callees_cmd(ctx: typer.Context, name: str, depth: int = typer.Option(3, "--depth")) -> None:
    """Show callees of a symbol."""
    _run(q_callees, ctx, name=name, depth=depth)


@graph_app.command(name="imports")
def imports_cmd(ctx: typer.Context, path: str) -> None:
    """Show imports for a path."""
    _run(q_imports, ctx, path=path)


@graph_app.command(name="imported-by")
def imported_by_cmd(
    ctx: typer.Context,
    path: str,
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    depth: int = typer.Option(1, "--depth"),
) -> None:
    """Show files that import a path."""
    _run(q_imported_by, ctx, path=path, symbol=symbol, depth=depth)


@graph_app.command(name="exports")
def exports_cmd(ctx: typer.Context, path: str) -> None:
    """Show exports from a path."""
    _run(q_exports, ctx, path=path)


@graph_app.command(name="exported-by")
def exported_by_cmd(ctx: typer.Context, name: str) -> None:
    """Show files exporting a symbol."""
    _run(q_exported_by, ctx, name=name)


@graph_app.command(name="describe-agent-plugin")
def describe_agent_plugin_cmd(ctx: typer.Context, name: str) -> None:
    """Describe an agent plugin (claude-code plugin under development)."""
    _run(q_describe_agent_plugin, ctx, name=name)


@graph_app.command(name="describe-app")
def describe_app_cmd(ctx: typer.Context, name: str) -> None:
    """Describe an app node."""
    _run(q_describe_app, ctx, name=name)


@graph_app.command(name="describe-builtin")
def describe_builtin_cmd(ctx: typer.Context, uri: str) -> None:
    """Describe a builtin node by URI."""
    _run(q_describe_builtin, ctx, uri=uri)


@graph_app.command(name="describe-dependency")
def describe_dependency_cmd(
    ctx: typer.Context,
    name: str,
    ecosystem: Optional[str] = typer.Option(None, "--ecosystem"),
) -> None:
    """Describe a dependency."""
    _run(q_describe_dependency, ctx, name=name, ecosystem=ecosystem)


@graph_app.command(name="describe-package")
def describe_package_cmd(ctx: typer.Context, name: str) -> None:
    """Describe a package."""
    _run(q_describe_package, ctx, name=name)


@graph_app.command(name="describe-path")
def describe_path_cmd(ctx: typer.Context, path: str) -> None:
    """Describe a file or directory path."""
    _run(q_describe_path, ctx, path=path)


@graph_app.command(name="describe-repo")
def describe_repo_cmd(ctx: typer.Context) -> None:
    """Describe the repository node."""
    _run(q_describe_repo, ctx)


@graph_app.command(name="list")
def list_cmd(
    ctx: typer.Context,
    kind: str = typer.Option(..., "--kind", "-k", help=f"Entity kind: {', '.join(q_list.LIST_KINDS)}."),
) -> None:
    """List graph entities of a given kind."""
    if kind not in q_list.LIST_KINDS:
        raise typer.BadParameter(f"kind must be one of: {', '.join(q_list.LIST_KINDS)}")
    _run(q_list, ctx, kind=kind)


@graph_app.command(name="list-entry-points")
def list_entry_points_cmd(
    ctx: typer.Context,
    package: str,
    kind: Optional[str] = typer.Option(None, "--kind"),
) -> None:
    """List entry points declared by a package."""
    if kind is not None and kind not in ENTRY_POINT_KINDS:
        raise typer.BadParameter(f"kind must be one of: {', '.join(ENTRY_POINT_KINDS)}")
    _run(q_list_entry_points, ctx, package=package, kind=kind)


@graph_app.command(name="describe-suite")
def describe_suite_cmd(ctx: typer.Context, name: str) -> None:
    """Describe a test suite."""
    _run(q_describe_suite, ctx, name=name)


@graph_app.command(name="what-tests")
def what_tests_cmd(
    ctx: typer.Context,
    name: str,
    kind: Optional[str] = typer.Option(None, "--kind"),
) -> None:
    """Show tests for a package or domain."""
    if kind is not None and kind not in TEST_TARGET_KINDS:
        raise typer.BadParameter(f"kind must be one of: {', '.join(TEST_TARGET_KINDS)}")
    _run(q_what_tests, ctx, name=name, kind=kind)


@graph_app.command(name="describe-domain")
def describe_domain_cmd(ctx: typer.Context, name: str) -> None:
    """Describe a domain."""
    _run(q_describe_domain, ctx, name=name)


@graph_app.command(name="describe-entry-point")
def describe_entry_point_cmd(ctx: typer.Context, name: str) -> None:
    """Describe an entry point."""
    _run(q_describe_entry_point, ctx, name=name)


@graph_app.command(name="domain-clusters")
def domain_clusters_cmd(
    ctx: typer.Context,
    hub_threshold: float = typer.Option(0.5, "--hub-threshold"),
) -> None:
    """Compute domain clusters over package references."""
    _run(q_domain_clusters, ctx, hub_threshold=hub_threshold)


@graph_app.command(name="domain-refs")
def domain_refs_cmd(ctx: typer.Context, name: str) -> None:
    """Show package references for a domain."""
    _run(q_domain_refs, ctx, name=name)


@graph_app.command(name="domain-deps")
def domain_deps_cmd(ctx: typer.Context, name: str) -> None:
    """Show outgoing domain dependencies."""
    _run(q_domain_deps, ctx, name=name)


@graph_app.command(name="cross-cutting")
def cross_cutting_cmd(ctx: typer.Context) -> None:
    """Show cross-cutting packages."""
    _run(q_cross_cutting, ctx)


def main() -> None:
    graph_app()


if __name__ == "__main__":
    main()

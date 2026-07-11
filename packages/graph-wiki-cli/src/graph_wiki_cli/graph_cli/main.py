"""Native Typer command surface for `gw graph`.

The code-graph implementation lives in graph_io. This package owns only the
unified graph-wiki CLI presentation layer.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import typer
from graph_wiki_core.commands.graph_query import VALID_KINDS
from workspace_io.config import resolve

from graph_wiki_cli.graph_cli import (
    ops_dump,
    ops_status,
    ops_sync_wiki,
    ops_update,
    q_callees,
    q_callers,
    q_cross_cutting,
    q_describe,
    q_domain_clusters,
    q_domain_deps,
    q_domain_refs,
    q_exported_by,
    q_find,
    q_imported_by,
    q_list,
    q_list_entry_points,
    q_what_tests,
)

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
def update_cmd(
    ctx: typer.Context, full: bool = typer.Option(False, "--full", help="Full rebuild from scratch.")
) -> None:
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
    if kind is not None and kind not in VALID_KINDS:
        raise typer.BadParameter(f"invalid choice: {kind} (choose from: {', '.join(sorted(VALID_KINDS))})")
    _run(q_find, ctx, name=name, kind=kind, in_package=in_package)


@graph_app.command(name="callers")
def callers_cmd(
    ctx: typer.Context,
    name: str,
    depth: int = typer.Option(3, "--depth"),
    include_tests: bool = typer.Option(False, "--include-tests", help="Include callers defined in test files."),
) -> None:
    """Show callers of a symbol."""
    _run(q_callers, ctx, name=name, depth=depth, include_tests=include_tests)


@graph_app.command(name="callees")
def callees_cmd(
    ctx: typer.Context,
    name: str,
    depth: int = typer.Option(3, "--depth"),
    include_tests: bool = typer.Option(False, "--include-tests", help="Include callees defined in test files."),
) -> None:
    """Show callees of a symbol."""
    _run(q_callees, ctx, name=name, depth=depth, include_tests=include_tests)


@graph_app.command(name="imported-by")
def imported_by_cmd(
    ctx: typer.Context,
    path: str,
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    depth: int = typer.Option(1, "--depth"),
) -> None:
    """Show files that import a path."""
    _run(q_imported_by, ctx, path=path, symbol=symbol, depth=depth)


@graph_app.command(name="exported-by")
def exported_by_cmd(ctx: typer.Context, name: str) -> None:
    """Show files exporting a symbol."""
    _run(q_exported_by, ctx, name=name)


@graph_app.command(name="describe")
def describe_cmd(
    ctx: typer.Context,
    selector: Optional[str] = typer.Argument(None, help="Name / path / URI of the entity (omit only for --kind repo)."),
    kind: Optional[str] = typer.Option(
        None,
        "--kind",
        "-k",
        help=f"Entity kind: {', '.join(q_describe.DESCRIBE_KINDS)}. Inferred from the selector when omitted.",
    ),
    ecosystem: Optional[str] = typer.Option(
        None, "--ecosystem", help="Dependency ecosystem (use with --kind dependency)."
    ),
    in_package: Optional[str] = typer.Option(
        None, "--in-package", help="Narrow resolution to a containing package (mirrors find)."
    ),
    depth: Optional[int] = typer.Option(None, "--depth", help="children-tree depth (>=1). Default: per-kind."),
) -> None:
    """Describe a graph entity. Kind is inferred from the selector when --kind is omitted."""
    if kind is not None and kind not in q_describe.DESCRIBE_KINDS:
        raise typer.BadParameter(f"kind must be one of: {', '.join(q_describe.DESCRIBE_KINDS)}")
    if depth is not None and depth < 1:
        raise typer.BadParameter("depth must be >= 1")
    _run(q_describe, ctx, selector=selector, kind=kind, ecosystem=ecosystem, in_package=in_package, depth=depth)


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


# --------------------------------------------------------------------------- #
# Core-owned commands re-exposed on the CLI graph surface. These live on the
# core graph_app (commands/graph.py) but the gw CLI mounts this separate
# graph_app, so they must be wired here too to be reachable via `gw graph`.
# They resolve the workspace from --workspace / GRAPH_WIKI_WORKSPACE and ignore
# the group --repo/--fmt/--mode options.
# --------------------------------------------------------------------------- #

# suggest-resources is Bedrock-free, so register the core function directly.
from graph_wiki_core.commands.suggest_resources import (  # noqa: E402
    suggest_resources_cmd as _suggest_resources_cmd,
)

graph_app.command(name="suggest-resources")(_suggest_resources_cmd)

# export is Bedrock-free, so register the core function directly.
from graph_wiki_core.commands.graph import (  # noqa: E402
    export_graph_cmd as _export_graph_cmd,
)

graph_app.command(name="export")(_export_graph_cmd)


# propose-domains pulls the Bedrock stack (model_adapter / subagent_runtime) at
# import. Wrap it so the import stays inside the command body — keeping this
# module (invoked per-command in the smoke suite) lightweight to import.
@graph_app.command(name="propose-domains")
def propose_domains_cmd(
    workspace: str = typer.Option("", "--workspace", help="Workspace root (defaults to GRAPH_WIKI_WORKSPACE)"),
    hub_threshold: float = typer.Option(
        0.5, "--hub-threshold", help="Fraction-of-packages threshold for cross-cutting hub detection"
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Override domain_proposer model_id"),
) -> None:
    """Propose candidate domains from domain-clusters via an LLM fan-out."""
    from graph_wiki_core.commands.propose_domains import propose_domains_cmd as _core

    _core(workspace=workspace, hub_threshold=hub_threshold, model=model)


def main() -> None:
    graph_app()


if __name__ == "__main__":
    main()

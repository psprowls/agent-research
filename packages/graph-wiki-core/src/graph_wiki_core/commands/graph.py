"""graph-wiki-core graph subcommands — typed graph_io API.

Phase 59 (Plan 02): migrated off the legacy cli wrappers onto the typed
library API. All read access now routes through the `graph_io` handle API
(`graph_io.open_reader(...)` → `GraphReader`); builds use `graph_io.update.run`
(D-04..D-07).

Trace records (when `--trace` is passed) reuse the Phase 9 OBS-04 schema
(D-01, D-02: schema_version=1, NO bump) with the same `event` values:
  * `graph_build_start`, `graph_build_complete`
  * `graph_describe`
  * `graph_query`

Proxy commands (`describe`, `query`) OMIT cost fields per D-03's honest-omission
rule — those commands invoke no LLM, so `model_id`, `tokens_in`, `tokens_out`,
`cost_usd` are absent from the record.

Decision references:
  D-01 trace file naming `<ISO-Z>-<command>.jsonl`
  D-02 schema_version reuse (do NOT bump to 2)
  D-03 honest-omission of cost fields on proxy commands
  D-04 shared connect+map helper (_open_graph_reader) reused by all describe + query
  D-05 exit-code contract preserved exactly incl. AMBIGUOUS(7) for entry-point
  D-06 graph build uses update.run (raises on error)
  D-07 trace schema unchanged; exit_code from agent's own exception mapping
  D-08 describe is a Typer subapp with 6 sub-sub-commands
  D-09 kebab-case CLI names ↔ snake_case dispatch keys

Pattern template: open_reader + except GraphNotInitializedError/SchemaMismatchError.
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Any, Optional

import graph_io
import typer
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes, update
from graph_io import render as _render
from graph_io.handle import GraphReader
from workspace_io.config import resolve
from workspace_io.paths import graph_dir

from graph_wiki_core.commands._paths import _resolve_paths

_SCHEMA_VERSION = 1  # Phase 9 OBS-04 — D-02: do NOT bump


def _iso_utc_timestamp() -> str:
    """Filename-safe ISO-Z timestamp (colons replaced with hyphens)."""
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _iso_utc_record_timestamp() -> str:
    """ISO-Z timestamp for the trace record `timestamp` field (colons KEPT)."""
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _connect_or_error(
    workspace: Path,
) -> tuple[GraphReader | None, int, str]:
    """Open a read-only GraphReader, returning (reader, exit_code, stderr).

    No printing, no typer.Exit. On success returns (reader, SUCCESS, ""). On a
    store error returns (None, NOT_INITIALIZED|SCHEMA_MISMATCH, "error: ...").
    Used by the printing-free core functions (run_describe/run_query). The
    Typer-facing `_open_graph_reader` wraps this and raises typer.Exit.

    Does NOT close the reader on success — callers use try/finally: reader.close().
    """
    try:
        return graph_io.open_reader(workspace), exit_codes.SUCCESS, ""
    except GraphNotInitializedError as exc:
        return None, exit_codes.NOT_INITIALIZED, f"error: {exc}"
    except SchemaMismatchError as exc:
        return None, exit_codes.SCHEMA_MISMATCH, f"error: {exc}"


def _open_graph_reader(workspace: Path) -> GraphReader:
    """Open a read-only GraphReader, raising typer.Exit on store errors.

    Thin Typer-facing wrapper over `_connect_or_error` (preserves the original
    CLI behavior: echo to stderr + raise typer.Exit with the mapped code).
    Does NOT close the reader — callers use try/finally: reader.close().
    """
    reader, exit_code, stderr = _connect_or_error(workspace)
    if reader is None:
        typer.echo(stderr, err=True)
        raise typer.Exit(code=exit_code)
    return reader


def _trace_path(workspace: Path, command: str, shared_stamp: str) -> Path:
    """Compute the per-invocation trace JSONL path under <workspace>/.graph-wiki/traces/."""
    trace_dir = graph_dir(workspace) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir / f"{shared_stamp}-{command}.jsonl"


def _write_trace_record(
    trace_path: Path,
    event: str,
    command: str,
    args_dict: dict,
    exit_code: Optional[int],
    duration_ms: int,
    *,
    model_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Append one JSONL record to the trace file.

    For proxy commands (`model_id is None` AND event != 'graph_build_*'), OMIT
    cost fields per D-03 honest-omission. For `graph_build_*` events, include
    `model_id` (may be None) but still omit token/cost fields because v1.7's
    `graph build` does not invoke an LLM.
    """
    record: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "timestamp": _iso_utc_record_timestamp(),
        "event": event,
        "command": command,
        "args": args_dict,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
    }
    # Include model_id ONLY for graph_build events (D-04) or when an explicit
    # model_id was passed (kept for forward-compatibility).
    if model_id is not None or event.startswith("graph_build"):
        record["model_id"] = model_id
    if extra:
        record.update(extra)
    try:
        with trace_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        typer.echo(f"warning: trace write failed: {exc}", err=True)


# --------------------------------------------------------------------------- #
# Core functions — printing-free, exit-code-returning (D-02 single source of
# truth). Shared by the Typer commands below AND the MCP server / scan.py.
# Each returns (exit_code, stdout, stderr); NO printing, NO typer.Exit, NO
# trace writes (trace + printing stay the caller's job).
# --------------------------------------------------------------------------- #


# kind -> requires-identifier. repository needs none; all others require one.
# Exposed publicly so the MCP server can enforce identifier-required semantics
# (replaces the old _DESCRIBE_DISPATCH[kind] -> (module, id_attr) lookup).
DESCRIBE_REQUIRES_IDENTIFIER: dict[str, bool] = {
    "package": True,
    "path": True,
    "repository": False,
    "domain": True,
    "entry_point": True,
    "test_suite": True,
    "app": True,
    "dependency": True,
    "agent_plugin": True,
    "builtin": True,
}


def run_build(repo: Path, workspace: Path, *, full: bool, scope_to_repo: bool = True) -> tuple[int, str, str]:
    """Build/refresh the code graph via the typed `update.run` (D-06).

    Multi-repo: when the workspace config declares members, drives
    `update.run_workspace`. `scope_to_repo` controls member selection:
      * ``True`` (default — the explicit ``gw graph --repo <member>`` path):
        if `repo` names one of the members, scopes the build to that single
        member (deliberate per-member update).
      * ``False`` (scan / whole-monorepo build): builds ALL members regardless
        of whether `repo` happens to name one. `gw scan` must build the whole
        monorepo so the wiki index renders one ``## Repository:`` section per
        member.
    Single-repo workspaces unchanged (empty members → existing `update.run`
    path, taken regardless of `scope_to_repo`).

    Returns (exit_code, stdout, stderr). `update.run`/`run_workspace` are silent
    on success (sanctioned by D-06), so stdout is always "". On error, stderr
    carries `error: <exc>` and the exit code mirrors `graph_build_cmd`'s mapping.
    Does NOT emit the CLI-only `--model` note.
    """
    try:
        cfg = resolve(repo, require_manifest=False)
        members = list(cfg.members)
        if members:
            if scope_to_repo:
                repo_resolved = Path(repo).resolve()
                scoped = [m for m in members if m == repo_resolved]
                update.run_workspace(scoped or members, workspace=workspace, full=full)
            else:
                update.run_workspace(members, workspace=workspace, full=full)
        else:
            update.run(repo, workspace=workspace, full=full)
    except update.NotInGitRepoError as exc:
        return exit_codes.NOT_IN_GIT_REPO, "", f"error: {exc}"
    except update.UpdateInProgressError as exc:
        return exit_codes.UPDATE_IN_PROGRESS, "", f"error: {exc}"
    except SchemaMismatchError as exc:
        return exit_codes.SCHEMA_MISMATCH, "", f"error: {exc}"
    except Exception as exc:  # noqa: BLE001 — mirror CLI's catch-all → GENERIC
        return exit_codes.GENERIC, "", f"error: {exc}"
    return exit_codes.SUCCESS, "", ""


def run_describe(
    kind: str, identifier: str | None, repo: Path, workspace: Path, depth: int | None = None
) -> tuple[int, str, str]:
    """Describe a graph entity (full describable set), printing-free (D-04).

    Dispatches over the shared `_render.format_<kind>` spine formatters using
    the `GraphReader` describe/resolve methods. Covers package/app/path/repository/
    domain/dependency/agent_plugin/builtin/entry_point/test_suite.

    Returns (exit_code, stdout, stderr). On success stdout is exactly the
    `_render.format_<kind>(...)` human string (byte-identical). not-found →
    GENERIC; ambiguous bare entry-point → AMBIGUOUS(7); store errors →
    NOT_INITIALIZED|SCHEMA_MISMATCH (via `_connect_or_error`).

    `depth` controls the children-tree depth (per-kind default when None).
    Existing callers that omit `depth` are unaffected.
    """
    reader, exit_code, stderr = _connect_or_error(workspace)
    if reader is None:
        return exit_code, "", stderr

    try:
        if kind == "repository":
            desc = reader.describe_repository()
            if desc is None:
                return exit_codes.GENERIC, "", "error: not found: repository"
            children, eff = reader.children_for(kind="repository", name=desc.name, depth=depth)
            out = _render.format_repo(desc, fmt="human", children=children, effective_depth=eff)
            return exit_codes.SUCCESS, out, ""

        # Defensive guard: every other kind requires an identifier. Real callers
        # already prevent None reaching here; this keeps the public core safe.
        if identifier is None:
            return exit_codes.GENERIC, "", "error: identifier required"

        if kind == "package":
            desc = reader.describe_package(name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: package not found: {identifier}"
            children, eff = reader.children_for(kind="package", name=desc.name, depth=depth)
            out = _render.format_package(desc, fmt="human", children=children, effective_depth=eff)
            return exit_codes.SUCCESS, out, ""

        if kind == "path":
            desc = reader.describe_path(path=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: path not found in graph: {identifier}"
            children, eff = reader.children_for(kind="file", path=desc.path, depth=depth)
            out = _render.format_path(desc, fmt="human", children=children, effective_depth=eff)
            return exit_codes.SUCCESS, out, ""

        if kind == "domain":
            desc = reader.describe_domain(name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: not found: {identifier}"
            packages, subdomains = reader.domain_members(identifier)
            children, eff = reader.children_for(kind="domain", name=desc.name, depth=depth)
            out = _render.format_domain(desc, packages, subdomains, fmt="human", children=children, effective_depth=eff)
            return exit_codes.SUCCESS, out, ""

        if kind == "entry_point":
            desc, ambiguous = reader.resolve_entry_point(identifier)
            if ambiguous:
                packages = ", ".join(ambiguous)
                return (
                    exit_codes.AMBIGUOUS,
                    "",
                    f"error: entry point not found: {identifier} "
                    f"(ambiguous across packages: {packages}; use 'package:entry')",
                )
            if desc is None:
                return exit_codes.GENERIC, "", f"error: entry point not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_entry_point(desc, fmt="human"), ""

        if kind == "test_suite":
            desc = reader.describe_test_suite(suite_name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: not found: {identifier}"
            children, eff = reader.children_for(kind="test_suite", name=desc.name, depth=depth)
            out = _render.format_suite(desc, fmt="human", children=children, effective_depth=eff)
            return exit_codes.SUCCESS, out, ""

        if kind == "app":
            desc = reader.describe_app(name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: app not found: {identifier}"
            children, eff = reader.children_for(kind="app", name=desc.name, depth=depth)
            out = _render.format_app(desc, fmt="human", children=children, effective_depth=eff)
            return exit_codes.SUCCESS, out, ""

        if kind == "dependency":
            # Core receives no ecosystem arg, so it uses the "ecosystem/name" prefix
            # convention (e.g. "npm/react"); bare names default to "pypi". MCP/CLI
            # callers should pass the qualified form for non-pypi dependencies.
            if "/" in identifier:
                ecosystem, _, dep_name = identifier.partition("/")
            else:
                ecosystem, dep_name = "pypi", identifier
            desc = reader.describe_dependency(ecosystem=ecosystem, name=dep_name)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: dependency not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_dependency(desc, fmt="human"), ""

        if kind == "agent_plugin":
            desc = reader.describe_agent_plugin(name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: agent_plugin not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_agent_plugin(desc, fmt="human"), ""

        if kind == "builtin":
            rest = identifier.removeprefix("builtin:")
            if "/" not in rest:
                return exit_codes.GENERIC, "", f"error: malformed builtin URI: {identifier}"
            language, module_name = rest.split("/", 1)
            desc = reader.describe_builtin(language=language, module_name=module_name)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: builtin not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_builtin(desc, fmt="human"), ""

        # Unknown kind — caller should have validated; treat defensively.
        raise KeyError(kind)
    finally:
        reader.close()


def run_query(
    repo: Path,
    workspace: Path,
    *,
    name: str | None,
    kind: str | None,
    in_package: str | None,
) -> tuple[int, str, str]:
    """Query the code graph, printing-free (D-04/D-05/D-07).

    Returns (exit_code, stdout, stderr). stdout is the rendered human table;
    stderr carries the truncation notice "... showing N of M (truncated)" (if
    any) — matching where the CLI's `_notice` writes it. Preserves the D-07
    `--in-package` no-match → GENERIC(1) quirk (distinct from name/kind
    zero-result = SUCCESS). Does NOT enforce the missing-filter exit-2 guard
    (that is a CLI-arg concern handled by the caller).
    """
    reader, exit_code, stderr = _connect_or_error(workspace)
    if reader is None:
        return exit_code, "", stderr

    try:
        records = reader.find(name=name, kind=kind, in_package=in_package)
    finally:
        reader.close()

    # D-07 quirk: --in-package non-match → exit 1 (distinct from name/kind
    # zero-result which stays SUCCESS). Source: q_find.py:66-68.
    if in_package is not None and not records:
        return exit_codes.GENERIC, "", ""

    truncation: dict[str, str] = {}

    def _capture_notice(shown: int, total: int) -> None:
        truncation["msg"] = f"... showing {shown} of {total} (truncated)"

    rendered = _render.render(records, fmt="human", cap=50, on_truncate=_capture_notice)
    return exit_codes.SUCCESS, rendered, truncation.get("msg", "")


def run_export(workspace: Path, out_path: Path) -> tuple[int, str, str]:
    """Export the full code graph to GraphML.

    Returns (exit_code, stdout, stderr). When out_path is Path("-"), stdout is
    the full XML string. Otherwise stdout is a one-line summary and the file is
    written to out_path.
    """
    reader, exit_code, stderr = _connect_or_error(workspace)
    if reader is None:
        return exit_code, "", stderr

    try:
        xml_str = reader.to_graphml()
        n_nodes = reader.node_count()
        n_edges = sum(reader.edge_counts_by_kind().values())
    finally:
        reader.close()

    if str(out_path) == "-":
        return exit_codes.SUCCESS, xml_str, ""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml_str, encoding="utf-8")
    return exit_codes.SUCCESS, f"wrote {n_nodes} nodes, {n_edges} edges → {out_path}", ""


# --------------------------------------------------------------------------- #
# Typer apps
# --------------------------------------------------------------------------- #

graph_app = typer.Typer(
    name="graph",
    help="Code graph operations (build/describe/query).",
    no_args_is_help=True,
)

graph_describe_app = typer.Typer(
    help="Describe a graph entity (6 kinds: package, path, repository, domain, entry-point, test-suite).",
    no_args_is_help=True,
)
graph_app.add_typer(graph_describe_app, name="describe")


# --------------------------------------------------------------------------- #
# Shared Typer-facing describe wrapper: calls run_describe(), echoes stdout/
# stderr, writes the trace record with the mapped exit code, raises on nonzero.
# CLI output stays byte-identical (Wave 3 snapshots verify).
# --------------------------------------------------------------------------- #


def _describe_cli(
    *,
    kind: str,
    identifier: Optional[str],
    command: str,
    trace: bool,
    workspace: str,
) -> None:
    repo, workspace_path = _resolve_paths(workspace)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    t0 = time.monotonic()
    exit_code, stdout, stderr = run_describe(kind, identifier, repo, workspace_path)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if stdout:
        typer.echo(stdout)
    if stderr:
        typer.echo(stderr, err=True)

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command=command,
            args_dict={"kind": kind, "identifier": identifier},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=None,
        )

    if exit_code != exit_codes.SUCCESS:
        raise typer.Exit(code=exit_code)


# --------------------------------------------------------------------------- #
# graph build
# --------------------------------------------------------------------------- #


@graph_app.command(name="build")
def graph_build_cmd(
    full: bool = typer.Option(False, "--full", help="Full rebuild from scratch (else incremental)"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace to .graph-wiki/traces/"),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Model ID — recorded in trace; NOT invoked in v1.7 (graph build does not call an LLM).",
    ),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
) -> None:
    """Build or refresh the code graph."""
    repo, workspace_path = _resolve_paths(workspace)

    if model is not None:
        typer.echo(
            "note: --model is recorded in the trace but not invoked in v1.7 — graph build does not call an LLM.",
            err=True,
        )

    shared_stamp = _iso_utc_timestamp()
    trace_file = _trace_path(workspace_path, "graph-build", shared_stamp) if trace else None

    args_dict = {"full": full, "model": model}

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_build_start",
            command="graph build",
            args_dict=args_dict,
            exit_code=None,
            duration_ms=0,
            model_id=model,
        )

    t0 = time.monotonic()
    exit_code, stdout, stderr = run_build(repo, workspace_path, full=full)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if stdout:
        typer.echo(stdout)
    if stderr:
        typer.echo(stderr, err=True)

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_build_complete",
            command="graph build",
            args_dict=args_dict,
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=model,
        )

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# --------------------------------------------------------------------------- #
# graph describe (6 sub-sub-commands)
# --------------------------------------------------------------------------- #


@graph_describe_app.command(name="package")
def describe_package_cmd(
    name: str = typer.Argument(..., help="Package name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a package."""
    _describe_cli(
        kind="package",
        identifier=name,
        command="graph describe package",
        trace=trace,
        workspace=workspace,
    )


@graph_describe_app.command(name="path")
def describe_path_cmd(
    path: str = typer.Argument(..., help="File or directory path"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a path (file or directory)."""
    _describe_cli(
        kind="path",
        identifier=path,
        command="graph describe path",
        trace=trace,
        workspace=workspace,
    )


@graph_describe_app.command(name="repository")
def describe_repository_cmd(
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe the repository (no identifier required)."""
    _describe_cli(
        kind="repository",
        identifier=None,
        command="graph describe repository",
        trace=trace,
        workspace=workspace,
    )


@graph_describe_app.command(name="domain")
def describe_domain_cmd(
    name: str = typer.Argument(..., help="Domain name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a domain."""
    _describe_cli(
        kind="domain",
        identifier=name,
        command="graph describe domain",
        trace=trace,
        workspace=workspace,
    )


@graph_describe_app.command(name="entry-point")
def describe_entry_point_cmd(
    name: str = typer.Argument(..., help="Entry-point name (use 'package:entry' to disambiguate)"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe an entry-point."""
    _describe_cli(
        kind="entry_point",
        identifier=name,
        command="graph describe entry-point",
        trace=trace,
        workspace=workspace,
    )


@graph_describe_app.command(name="test-suite")
def describe_test_suite_cmd(
    name: str = typer.Argument(..., help="Test-suite name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a test-suite."""
    _describe_cli(
        kind="test_suite",
        identifier=name,
        command="graph describe test-suite",
        trace=trace,
        workspace=workspace,
    )


# --------------------------------------------------------------------------- #
# graph query
# --------------------------------------------------------------------------- #


@graph_app.command(name="query")
def graph_query_cmd(
    name: Optional[str] = typer.Option(None, "--name", help="Filter by node name"),
    kind: Optional[str] = typer.Option(None, "--kind", help="Filter by node kind"),
    in_package: Optional[str] = typer.Option(None, "--in-package", help="Filter by containing package"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Query the code graph. At least one of --name/--kind/--in-package required."""
    if name is None and kind is None and in_package is None:
        typer.echo(
            "Error: at least one of --name, --kind, --in-package is required",
            err=True,
        )
        raise typer.Exit(code=2)

    repo, workspace_path = _resolve_paths(workspace)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-query", shared_stamp)

    t0 = time.monotonic()
    exit_code, stdout, stderr = run_query(repo, workspace_path, name=name, kind=kind, in_package=in_package)
    dur_ms = int((time.monotonic() - t0) * 1000)

    # Echo render output (stdout) on success; truncation notice / store-error
    # message goes to stderr. The D-07 --in-package no-match path returns
    # GENERIC with empty stdout/stderr (nothing to echo) — matching the old
    # CLI which printed nothing before raising typer.Exit(GENERIC).
    if exit_code == exit_codes.SUCCESS:
        typer.echo(stdout)
        if stderr:
            typer.echo(stderr, err=True)
    elif stderr:
        typer.echo(stderr, err=True)

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_query",
            command="graph query",
            args_dict={"name": name, "kind": kind, "in_package": in_package},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=None,
        )

    if exit_code != exit_codes.SUCCESS:
        raise typer.Exit(code=exit_code)


# --------------------------------------------------------------------------- #
# graph propose-domains  (Phase 48 D-22)
# --------------------------------------------------------------------------- #
# Registered here (instead of in propose_domains.py) so the registration runs
# whenever this module is imported — and avoids a circular `commands/graph.py`
# ↔ `commands/propose_domains.py` import. The function body (with all
# orchestration logic, dataclasses, helpers) lives in `propose_domains.py`.


@graph_app.command(name="export")
def export_graph_cmd(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    out: Optional[str] = typer.Option(
        None,
        "--out",
        help="Output file (default: <workspace>/.graph-wiki/graph.graphml). Use '-' for stdout.",
    ),
) -> None:
    """Export the code graph to GraphML for visualization in Gephi/Cytoscape."""
    _, workspace_path = _resolve_paths(workspace)
    out_path = Path("-") if out == "-" else (Path(out) if out else graph_dir(workspace_path) / "graph.graphml")
    exit_code, stdout, stderr = run_export(workspace_path, out_path)
    if stdout:
        typer.echo(stdout)
    if stderr:
        typer.echo(stderr, err=True)
    if exit_code != exit_codes.SUCCESS:
        raise typer.Exit(code=exit_code)


from graph_wiki_core.commands.propose_domains import (  # noqa: E402
    propose_domains_cmd as _propose_domains_cmd,
)

graph_app.command(name="propose-domains")(_propose_domains_cmd)

from graph_wiki_core.commands.suggest_resources import (  # noqa: E402
    suggest_resources_cmd as _suggest_resources_cmd,
)

graph_app.command(name="suggest-resources")(_suggest_resources_cmd)

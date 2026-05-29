"""graph-wiki-agent graph subcommands — typed graph_io API.

Phase 59 (Plan 02): migrated off the legacy cli wrappers onto the typed
library API. Replaces the Phase 38 namespace-construction + stdout-capture
shim with direct calls to `graph_io.queries.*`, `graph_io.update.run`, and
`graph_io.store.read_only_connect` (D-04..D-07).

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
  D-04 shared connect+map helper (_open_graph_conn) reused by all describe + query
  D-05 exit-code contract preserved exactly incl. AMBIGUOUS(7) for entry-point
  D-06 graph build uses update.run (raises on error)
  D-07 trace schema unchanged; exit_code from agent's own exception mapping
  D-08 describe is a Typer subapp with 6 sub-sub-commands
  D-09 kebab-case CLI names ↔ snake_case dispatch keys

Pattern template: scan.py:540-558 (read_only_connect + except GraphNotInitializedError).
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import typer

from graph_io import exit_codes, queries, render as _render, update
from graph_io.store import GraphNotInitializedError, SchemaMismatchError, read_only_connect
from workspace_io.config import resolve as resolve_config
from workspace_io.paths import graph_dir

_SCHEMA_VERSION = 1  # Phase 9 OBS-04 — D-02: do NOT bump


def _iso_utc_timestamp() -> str:
    """Filename-safe ISO-Z timestamp (colons replaced with hyphens)."""
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _iso_utc_record_timestamp() -> str:
    """ISO-Z timestamp for the trace record `timestamp` field (colons KEPT)."""
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_paths(workspace_arg: str) -> tuple[Path, Path]:
    """Resolve (repo_root, workspace) from --workspace arg or GRAPH_WIKI_WORKSPACE env."""
    if workspace_arg:
        cfg = resolve_config(Path(workspace_arg).resolve(), require_manifest=False)
    else:
        cfg = resolve_config(None, require_manifest=False)
    return cfg.repo_root, cfg.workspace


def _connect_or_error(
    workspace: Path,
) -> tuple[sqlite3.Connection | None, int, str]:
    """Open a read-only graph connection, returning (conn, exit_code, stderr).

    No printing, no typer.Exit. On success returns (conn, SUCCESS, ""). On a
    store error returns (None, NOT_INITIALIZED|SCHEMA_MISMATCH, "error: ...").
    Used by the printing-free core functions (run_describe/run_query). The
    Typer-facing `_open_graph_conn` wraps this and raises typer.Exit.

    Source pattern: scan.py:540-558 (read_only_connect + except GraphNotInitializedError).
    Does NOT close the connection on success — callers use try/finally: conn.close().
    """
    db = graph_dir(workspace) / "code.db"
    try:
        return read_only_connect(db), exit_codes.SUCCESS, ""
    except GraphNotInitializedError as exc:
        return None, exit_codes.NOT_INITIALIZED, f"error: {exc}"
    except SchemaMismatchError as exc:
        return None, exit_codes.SCHEMA_MISMATCH, f"error: {exc}"


def _open_graph_conn(workspace: Path) -> sqlite3.Connection:
    """Open a read-only graph connection, raising typer.Exit on store errors.

    Thin Typer-facing wrapper over `_connect_or_error` (preserves the original
    CLI behavior: echo to stderr + raise typer.Exit with the mapped code).
    Does NOT close the connection — callers use try/finally: conn.close().
    """
    conn, exit_code, stderr = _connect_or_error(workspace)
    if conn is None:
        typer.echo(stderr, err=True)
        raise typer.Exit(code=exit_code)
    return conn


def _trace_path(workspace: Path, command: str, shared_stamp: str) -> Path:
    """Compute the per-invocation trace JSONL path under <workspace>/.graph-wiki/traces/."""
    trace_dir = workspace / ".graph-wiki" / "traces"
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
}


def run_build(repo: Path, workspace: Path, *, full: bool) -> tuple[int, str, str]:
    """Build/refresh the code graph via the typed `update.run` (D-06).

    Returns (exit_code, stdout, stderr). `update.run` is silent on success
    (sanctioned by D-06), so stdout is always "". On error, stderr carries
    `error: <exc>` and the exit code mirrors `graph_build_cmd`'s mapping.
    Does NOT emit the CLI-only `--model` note.
    """
    try:
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
    kind: str, identifier: str | None, repo: Path, workspace: Path
) -> tuple[int, str, str]:
    """Describe a graph entity (all 6 kinds), printing-free (D-04).

    Returns (exit_code, stdout, stderr). On success stdout is exactly the
    `_render.format_<kind>(...)` human string (byte-identical). not-found →
    GENERIC; ambiguous bare entry-point → AMBIGUOUS(7); store errors →
    NOT_INITIALIZED|SCHEMA_MISMATCH (via `_connect_or_error`).
    """
    conn, exit_code, stderr = _connect_or_error(workspace)
    if conn is None:
        return exit_code, "", stderr

    try:
        # Defensive guard: every kind except repository requires an identifier.
        # Real callers (the Typer Argument and the MCP identifier-required check)
        # already prevent None reaching here; this stops a latent TypeError if the
        # public core is called directly with identifier=None (e.g. entry_point's
        # `":" in raw`).
        if identifier is None and kind != "repository":
            return exit_codes.GENERIC, "", "error: identifier required"

        if kind == "package":
            desc = queries.describe_package(conn, name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: package not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_package(desc, fmt="human"), ""

        if kind == "path":
            desc = queries.describe_path(conn, path=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: path not found in graph: {identifier}"
            return exit_codes.SUCCESS, _render.format_path(desc, fmt="human"), ""

        if kind == "repository":
            desc = queries.describe_repository(conn)
            if desc is None:
                return exit_codes.GENERIC, "", "error: not found: repository"
            return exit_codes.SUCCESS, _render.format_repo(desc, fmt="human"), ""

        if kind == "domain":
            desc = queries.describe_domain(conn, name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: not found: {identifier}"
            pkg_rows = conn.execute(
                "SELECT p.name FROM edges e "
                "JOIN nodes p ON e.src = p.id "
                "JOIN nodes d ON e.dst = d.id "
                "WHERE e.kind='belongs_to_domain' AND d.kind='domain' AND d.name = ? "
                "ORDER BY p.name",
                (identifier,),
            ).fetchall()
            packages = [r[0] for r in pkg_rows]
            sub_rows = conn.execute(
                "SELECT c.name FROM edges e "
                "JOIN nodes c ON e.dst = c.id "
                "JOIN nodes p ON e.src = p.id "
                "WHERE e.kind='domain_contains_domain' AND p.kind='domain' AND p.name = ? "
                "ORDER BY c.name",
                (identifier,),
            ).fetchall()
            subdomains = [r[0] for r in sub_rows]
            return (
                exit_codes.SUCCESS,
                _render.format_domain(desc, packages, subdomains, fmt="human"),
                "",
            )

        if kind == "entry_point":
            raw = identifier
            if ":" in raw:
                package_name, entry_name = raw.split(":", 1)
                desc = queries.describe_entry_point(
                    conn, package_name=package_name, entry_name=entry_name
                )
            else:
                # Bare entry name: scan all packages that declare an EntryPoint by this name.
                rows = conn.execute(
                    "SELECT pkg.name "
                    "FROM nodes pkg "
                    "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
                    "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
                    # Phase 50 D-04: include apps too — apps declare entry points
                    # via the same manifest fields as packages.
                    "WHERE pkg.kind IN ('package', 'app') AND ep.name = ?",
                    (raw,),
                ).fetchall()
                if not rows:
                    desc = None
                elif len(rows) > 1:
                    packages = ", ".join(r[0] for r in rows)
                    return (
                        exit_codes.AMBIGUOUS,
                        "",
                        f"error: entry point not found: {raw} "
                        f"(ambiguous across packages: {packages}; use 'package:entry')",
                    )
                else:
                    desc = queries.describe_entry_point(
                        conn, package_name=rows[0][0], entry_name=raw
                    )
            if desc is None:
                return exit_codes.GENERIC, "", f"error: entry point not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_entry_point(desc, fmt="human"), ""

        if kind == "test_suite":
            desc = queries.describe_test_suite(conn, suite_name=identifier)
            if desc is None:
                return exit_codes.GENERIC, "", f"error: not found: {identifier}"
            return exit_codes.SUCCESS, _render.format_suite(desc, fmt="human"), ""

        # Unknown kind — caller should have validated; treat defensively.
        raise KeyError(kind)
    finally:
        conn.close()


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
    conn, exit_code, stderr = _connect_or_error(workspace)
    if conn is None:
        return exit_code, "", stderr

    try:
        records = queries.find(conn, name=name, kind=kind, in_package=in_package)
    finally:
        conn.close()

    # D-07 quirk: --in-package non-match → exit 1 (distinct from name/kind
    # zero-result which stays SUCCESS). Source: q_find.py:66-68.
    if in_package is not None and not records:
        return exit_codes.GENERIC, "", ""

    truncation: dict[str, str] = {}

    def _capture_notice(shown: int, total: int) -> None:
        truncation["msg"] = f"... showing {shown} of {total} (truncated)"

    rendered = _render.render(records, fmt="human", cap=50, on_truncate=_capture_notice)
    return exit_codes.SUCCESS, rendered, truncation.get("msg", "")


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
    workspace: str = typer.Option(
        "", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"
    ),
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
    exit_code, stdout, stderr = run_query(
        repo, workspace_path, name=name, kind=kind, in_package=in_package
    )
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

from graph_wiki_agent.commands.propose_domains import (  # noqa: E402
    propose_domains_cmd as _propose_domains_cmd,
)

graph_app.command(name="propose-domains")(_propose_domains_cmd)

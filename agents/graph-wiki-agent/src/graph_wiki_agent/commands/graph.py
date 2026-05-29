"""graph-wiki-agent graph subcommands — typed graph_io API.

Phase 59 (Plan 02): migrated off `graph_io.cli` onto the typed library API.
Replaces the Phase 38 `_build_namespace`/`_capture_run`/argparse shim with
direct calls to `graph_io.queries.*`, `graph_io.update.run`, and
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


def _open_graph_conn(workspace: Path) -> sqlite3.Connection:
    """Open a read-only graph connection, raising typer.Exit on store errors.

    Source pattern: scan.py:540-558 (read_only_connect + except GraphNotInitializedError).
    Does NOT close the connection — callers use try/finally: conn.close().
    """
    db = graph_dir(workspace) / "code.db"
    try:
        return read_only_connect(db)
    except GraphNotInitializedError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=exit_codes.NOT_INITIALIZED)
    except SchemaMismatchError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=exit_codes.SCHEMA_MISMATCH)


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

    exit_code = exit_codes.SUCCESS
    t0 = time.monotonic()
    try:
        update.run(repo, workspace=workspace_path, full=full)
    except update.NotInGitRepoError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.NOT_IN_GIT_REPO
    except update.UpdateInProgressError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.UPDATE_IN_PROGRESS
    except SchemaMismatchError as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.SCHEMA_MISMATCH
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        exit_code = exit_codes.GENERIC
    dur_ms = int((time.monotonic() - t0) * 1000)

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
    repo, workspace_path = _resolve_paths(workspace)
    conn = _open_graph_conn(workspace_path)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    t0 = time.monotonic()
    try:
        desc = queries.describe_package(conn, name=name)
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    if desc is None:
        typer.echo(f"error: package not found: {name}", err=True)
        if trace_file is not None:
            _write_trace_record(
                trace_file,
                event="graph_describe",
                command="graph describe package",
                args_dict={"kind": "package", "identifier": name},
                exit_code=exit_codes.GENERIC,
                duration_ms=dur_ms,
                model_id=None,
            )
        raise typer.Exit(code=exit_codes.GENERIC)

    typer.echo(_render.format_package(desc, fmt="human"))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command="graph describe package",
            args_dict={"kind": "package", "identifier": name},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
        )


@graph_describe_app.command(name="path")
def describe_path_cmd(
    path: str = typer.Argument(..., help="File or directory path"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a path (file or directory)."""
    repo, workspace_path = _resolve_paths(workspace)
    conn = _open_graph_conn(workspace_path)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    t0 = time.monotonic()
    try:
        desc = queries.describe_path(conn, path=path)
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    if desc is None:
        typer.echo(f"error: path not found: {path}", err=True)
        if trace_file is not None:
            _write_trace_record(
                trace_file,
                event="graph_describe",
                command="graph describe path",
                args_dict={"kind": "path", "identifier": path},
                exit_code=exit_codes.GENERIC,
                duration_ms=dur_ms,
                model_id=None,
            )
        raise typer.Exit(code=exit_codes.GENERIC)

    typer.echo(_render.format_path(desc, fmt="human"))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command="graph describe path",
            args_dict={"kind": "path", "identifier": path},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
        )


@graph_describe_app.command(name="repository")
def describe_repository_cmd(
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe the repository (no identifier required)."""
    repo, workspace_path = _resolve_paths(workspace)
    conn = _open_graph_conn(workspace_path)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    t0 = time.monotonic()
    try:
        desc = queries.describe_repository(conn)
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    if desc is None:
        typer.echo("error: repository not found", err=True)
        if trace_file is not None:
            _write_trace_record(
                trace_file,
                event="graph_describe",
                command="graph describe repository",
                args_dict={"kind": "repository", "identifier": None},
                exit_code=exit_codes.GENERIC,
                duration_ms=dur_ms,
                model_id=None,
            )
        raise typer.Exit(code=exit_codes.GENERIC)

    typer.echo(_render.format_repo(desc, fmt="human"))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command="graph describe repository",
            args_dict={"kind": "repository", "identifier": None},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
        )


@graph_describe_app.command(name="domain")
def describe_domain_cmd(
    name: str = typer.Argument(..., help="Domain name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a domain."""
    repo, workspace_path = _resolve_paths(workspace)
    conn = _open_graph_conn(workspace_path)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    t0 = time.monotonic()
    try:
        desc = queries.describe_domain(conn, name=name)
        if desc is None:
            dur_ms = int((time.monotonic() - t0) * 1000)
            typer.echo(f"error: not found: {name}", err=True)
            if trace_file is not None:
                _write_trace_record(
                    trace_file,
                    event="graph_describe",
                    command="graph describe domain",
                    args_dict={"kind": "domain", "identifier": name},
                    exit_code=exit_codes.GENERIC,
                    duration_ms=dur_ms,
                    model_id=None,
                )
            raise typer.Exit(code=exit_codes.GENERIC)
        pkg_rows = conn.execute(
            "SELECT p.name FROM edges e "
            "JOIN nodes p ON e.src = p.id "
            "JOIN nodes d ON e.dst = d.id "
            "WHERE e.kind='belongs_to_domain' AND d.kind='domain' AND d.name = ? "
            "ORDER BY p.name",
            (name,),
        ).fetchall()
        packages = [r[0] for r in pkg_rows]
        sub_rows = conn.execute(
            "SELECT c.name FROM edges e "
            "JOIN nodes c ON e.dst = c.id "
            "JOIN nodes p ON e.src = p.id "
            "WHERE e.kind='domain_contains_domain' AND p.kind='domain' AND p.name = ? "
            "ORDER BY c.name",
            (name,),
        ).fetchall()
        subdomains = [r[0] for r in sub_rows]
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    typer.echo(_render.format_domain(desc, packages, subdomains, fmt="human"))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command="graph describe domain",
            args_dict={"kind": "domain", "identifier": name},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
        )


@graph_describe_app.command(name="entry-point")
def describe_entry_point_cmd(
    name: str = typer.Argument(..., help="Entry-point name (use 'package:entry' to disambiguate)"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe an entry-point."""
    repo, workspace_path = _resolve_paths(workspace)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    conn = _open_graph_conn(workspace_path)
    t0 = time.monotonic()
    try:
        raw = name
        if ":" in raw:
            package_name, entry_name = raw.split(":", 1)
            desc = queries.describe_entry_point(conn, package_name=package_name, entry_name=entry_name)
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
                typer.echo(
                    f"error: entry point not found: {raw} "
                    f"(ambiguous across packages: {packages}; use 'package:entry')",
                    err=True,
                )
                dur_ms = int((time.monotonic() - t0) * 1000)
                if trace_file is not None:
                    _write_trace_record(
                        trace_file,
                        event="graph_describe",
                        command="graph describe entry-point",
                        args_dict={"kind": "entry_point", "identifier": name},
                        exit_code=exit_codes.AMBIGUOUS,
                        duration_ms=dur_ms,
                        model_id=None,
                    )
                raise typer.Exit(code=exit_codes.AMBIGUOUS)
            else:
                desc = queries.describe_entry_point(conn, package_name=rows[0][0], entry_name=raw)
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    if desc is None:
        typer.echo(f"error: entry point not found: {name}", err=True)
        if trace_file is not None:
            _write_trace_record(
                trace_file,
                event="graph_describe",
                command="graph describe entry-point",
                args_dict={"kind": "entry_point", "identifier": name},
                exit_code=exit_codes.GENERIC,
                duration_ms=dur_ms,
                model_id=None,
            )
        raise typer.Exit(code=exit_codes.GENERIC)

    typer.echo(_render.format_entry_point(desc, fmt="human"))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command="graph describe entry-point",
            args_dict={"kind": "entry_point", "identifier": name},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
        )


@graph_describe_app.command(name="test-suite")
def describe_test_suite_cmd(
    name: str = typer.Argument(..., help="Test-suite name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a test-suite."""
    repo, workspace_path = _resolve_paths(workspace)
    conn = _open_graph_conn(workspace_path)

    trace_file = None
    if trace:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    t0 = time.monotonic()
    try:
        desc = queries.describe_test_suite(conn, suite_name=name)
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    if desc is None:
        typer.echo(f"error: test-suite not found: {name}", err=True)
        if trace_file is not None:
            _write_trace_record(
                trace_file,
                event="graph_describe",
                command="graph describe test-suite",
                args_dict={"kind": "test_suite", "identifier": name},
                exit_code=exit_codes.GENERIC,
                duration_ms=dur_ms,
                model_id=None,
            )
        raise typer.Exit(code=exit_codes.GENERIC)

    typer.echo(_render.format_suite(desc, fmt="human"))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command="graph describe test-suite",
            args_dict={"kind": "test_suite", "identifier": name},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
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

    conn = _open_graph_conn(workspace_path)
    t0 = time.monotonic()
    try:
        records = queries.find(conn, name=name, kind=kind, in_package=in_package)
    finally:
        conn.close()
    dur_ms = int((time.monotonic() - t0) * 1000)

    # D-07 quirk: --in-package non-match → exit 1 (distinct from name/kind
    # zero-result which stays SUCCESS). Source: q_find.py:66-68.
    if in_package is not None and not records:
        if trace_file is not None:
            _write_trace_record(
                trace_file,
                event="graph_query",
                command="graph query",
                args_dict={"name": name, "kind": kind, "in_package": in_package},
                exit_code=exit_codes.GENERIC,
                duration_ms=dur_ms,
                model_id=None,
            )
        raise typer.Exit(code=exit_codes.GENERIC)

    def _notice(shown: int, total: int) -> None:
        typer.echo(f"... showing {shown} of {total} (truncated)", err=True)

    typer.echo(_render.render(records, fmt="human", cap=50, on_truncate=_notice))

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_query",
            command="graph query",
            args_dict={"name": name, "kind": kind, "in_package": in_package},
            exit_code=exit_codes.SUCCESS,
            duration_ms=dur_ms,
            model_id=None,
        )


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

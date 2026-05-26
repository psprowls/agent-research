"""graph-wiki-agent graph subcommands — in-process cg dispatch.

Phase 38: exposes `graph build|describe|query` Typer commands that wrap the
`graph_io.cli.*` modules via direct in-process import (D-06/D-07). Each command
constructs an `argparse.Namespace` matching the shape cg's argparse produces
and calls `<module>.run(args)` under `contextlib.redirect_stdout/stderr` so
the captured stdout/stderr can be forwarded to the typer layer without
tripping MCP's _StdoutGuard (Plan 02).

Trace records (when `--trace` is passed) reuse the Phase 9 OBS-04 schema
(D-01, D-02: schema_version=1, NO bump) with new `event` values:
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
  D-04 `--model` only applies to `graph build`, not describe/query
  D-06 in-process import (no subprocess)
  D-07 manual argparse.Namespace construction
  D-08 `describe` is itself a Typer subapp with 6 sub-sub-commands
  D-09 kebab-case CLI names ↔ snake_case dispatch keys

Pattern template: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py`.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import time
from pathlib import Path
from typing import Any, Optional

import typer

from graph_io.cli import (
    ops_update,
    q_describe_domain,
    q_describe_entry_point,
    q_describe_package,
    q_describe_path,
    q_describe_repo,
    q_describe_suite,
    q_find,
)
from workspace_io.config import resolve as resolve_config

_SCHEMA_VERSION = 1  # Phase 9 OBS-04 — D-02: do NOT bump

# Dispatch table: snake_case kind → (cg_module, identifier_attr_name on the Namespace)
# identifier_attr_name is None for `repository` (no identifier needed).
_DESCRIBE_DISPATCH: dict[str, tuple[Any, Optional[str]]] = {
    "package": (q_describe_package, "name"),
    "path": (q_describe_path, "path"),
    "repository": (q_describe_repo, None),
    "domain": (q_describe_domain, "name"),
    "entry_point": (q_describe_entry_point, "name"),
    "test_suite": (q_describe_suite, "name"),
}


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


def _build_namespace(module, *, repo: Path, workspace: Path, **extras) -> argparse.Namespace:
    """Build the argparse.Namespace shape that cg modules' `run()` expect."""
    ns = argparse.Namespace(
        repo=repo,
        workspace=workspace,
        fmt="human",
        mode="workspace",
        _module=module,
        _parser=None,
    )
    for key, value in extras.items():
        setattr(ns, key, value)
    return ns


def _capture_run(module, args: argparse.Namespace) -> tuple[int, str, str]:
    """Run module.run(args) with stdout/stderr captured. Returns (exit_code, stdout, stderr).

    Catches SystemExit defensively (RESEARCH §6) — some cg modules call
    args._parser.error(...) which raises SystemExit. The agent pre-validates
    args at the Typer layer to avoid that path, but the catch keeps things
    robust if a cg module ever raises SystemExit for another reason.
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code = 0
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exit_code = module.run(args)
    except SystemExit as exc:
        exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


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
    help="Code graph operations (build/describe/query) via in-process cg dispatch.",
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
    """Build or refresh the code graph (wraps `cg update`)."""
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

    args = _build_namespace(ops_update, repo=repo, workspace=workspace_path, full=full)
    t0 = time.monotonic()
    exit_code, stdout, stderr = _capture_run(ops_update, args)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True, nl=False)

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


def _run_describe(
    kind: str,
    identifier: Optional[str],
    workspace_arg: str,
    trace_flag: bool,
) -> None:
    """Shared implementation for the 6 describe sub-sub-commands."""
    repo, workspace_path = _resolve_paths(workspace_arg)
    module, id_attr = _DESCRIBE_DISPATCH[kind]
    extras: dict = {} if id_attr is None else {id_attr: identifier}

    trace_file = None
    if trace_flag:
        shared_stamp = _iso_utc_timestamp()
        trace_file = _trace_path(workspace_path, "graph-describe", shared_stamp)

    args = _build_namespace(module, repo=repo, workspace=workspace_path, **extras)
    t0 = time.monotonic()
    exit_code, stdout, stderr = _capture_run(module, args)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True, nl=False)

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_describe",
            command=f"graph describe {kind.replace('_', '-')}",
            args_dict={"kind": kind, "identifier": identifier},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=None,  # proxy: cost fields omitted per D-03
        )

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@graph_describe_app.command(name="package")
def describe_package_cmd(
    name: str = typer.Argument(..., help="Package name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a package."""
    _run_describe(kind="package", identifier=name, workspace_arg=workspace, trace_flag=trace)


@graph_describe_app.command(name="path")
def describe_path_cmd(
    path: str = typer.Argument(..., help="File or directory path"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a path (file or directory)."""
    _run_describe(kind="path", identifier=path, workspace_arg=workspace, trace_flag=trace)


@graph_describe_app.command(name="repository")
def describe_repository_cmd(
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe the repository (no identifier required)."""
    _run_describe(kind="repository", identifier=None, workspace_arg=workspace, trace_flag=trace)


@graph_describe_app.command(name="domain")
def describe_domain_cmd(
    name: str = typer.Argument(..., help="Domain name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a domain."""
    _run_describe(kind="domain", identifier=name, workspace_arg=workspace, trace_flag=trace)


@graph_describe_app.command(name="entry-point")
def describe_entry_point_cmd(
    name: str = typer.Argument(..., help="Entry-point name (use 'package:entry' to disambiguate)"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe an entry-point."""
    _run_describe(kind="entry_point", identifier=name, workspace_arg=workspace, trace_flag=trace)


@graph_describe_app.command(name="test-suite")
def describe_test_suite_cmd(
    name: str = typer.Argument(..., help="Test-suite name"),
    trace: bool = typer.Option(False, "--trace", help="Write JSONL trace"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Describe a test-suite."""
    _run_describe(kind="test_suite", identifier=name, workspace_arg=workspace, trace_flag=trace)


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
    """Query the code graph (wraps `cg find`). At least one of --name/--kind/--in-package required."""
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

    args = _build_namespace(
        q_find,
        repo=repo,
        workspace=workspace_path,
        name=name,
        kind=kind,
        in_package=in_package,
    )
    t0 = time.monotonic()
    exit_code, stdout, stderr = _capture_run(q_find, args)
    dur_ms = int((time.monotonic() - t0) * 1000)

    if stdout:
        typer.echo(stdout, nl=False)
    if stderr:
        typer.echo(stderr, err=True, nl=False)

    if trace_file is not None:
        _write_trace_record(
            trace_file,
            event="graph_query",
            command="graph query",
            args_dict={"name": name, "kind": kind, "in_package": in_package},
            exit_code=exit_code,
            duration_ms=dur_ms,
            model_id=None,  # proxy: cost fields omitted per D-03
        )

    if exit_code != 0:
        raise typer.Exit(code=exit_code)

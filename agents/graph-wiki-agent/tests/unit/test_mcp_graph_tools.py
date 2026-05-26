"""Unit tests for the 3 graph_* MCP tools (Phase 38-02 Task 2).

Covers GRAPHCMD-04, D-04, D-09:
  * Three tools registered (graph_build, graph_describe, graph_query)
  * Pydantic Input shape: extra='forbid', Literal kind enum
  * MCP dispatch reuses Plan 01's _DESCRIBE_DISPATCH and _capture_run
  * _StdoutGuard never tripped (cg's print() is absorbed by _capture_run)
  * Errors returned as GraphCommandOutput(status='error', ...) — no raises
  * Existing wiki_* tools remain registered (regression guard)
  * Trace files written and trace_path returned in output

asyncio_mode='auto' in agents/graph-wiki-agent/pyproject.toml means `async def
test_*` functions are auto-detected — no @pytest.mark.asyncio decorator needed.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# Importing the server module installs _StdoutGuard at module-init time.
from graph_wiki_agent.mcp.server import (  # noqa: F401  (mcp imported for tool registry inspection)
    GraphBuildInput,
    GraphCommandOutput,
    GraphDescribeInput,
    GraphQueryInput,
    graph_build,
    graph_describe,
    graph_query,
    mcp,
)
from graph_wiki_agent.commands import graph as graph_module
from graph_io import exit_codes


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    ws.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(ws))
    return ws


@pytest.fixture
def fake_ctx():
    """A minimal stand-in for FastMCP's Context.

    The graph_* tools don't call ctx.report_progress, so a MagicMock suffices.
    """
    ctx = MagicMock()
    ctx.report_progress = MagicMock(return_value=None)
    return ctx


# --------------------------------------------------------------------------- #
# Tool registration
# --------------------------------------------------------------------------- #


def test_three_graph_tools_registered():
    """The 3 graph_* coroutines are importable and async."""
    assert callable(graph_build)
    assert callable(graph_describe)
    assert callable(graph_query)
    assert inspect.iscoroutinefunction(graph_build)
    assert inspect.iscoroutinefunction(graph_describe)
    assert inspect.iscoroutinefunction(graph_query)


def test_wiki_tools_still_registered():
    """Regression guard: Phase 38 did not break existing wiki_* tools."""
    from graph_wiki_agent.mcp.server import (
        wiki_bootstrap,
        wiki_ingest,
        wiki_lint,
        wiki_log,
        wiki_ping,
        wiki_query,
        wiki_scan,
    )
    for tool in [wiki_ping, wiki_query, wiki_log, wiki_bootstrap, wiki_scan, wiki_ingest, wiki_lint]:
        assert callable(tool)


# --------------------------------------------------------------------------- #
# Pydantic Input shape
# --------------------------------------------------------------------------- #


def test_graph_build_input_shape():
    GraphBuildInput(full=True, trace=False, model="x", workspace_path="/tmp")
    GraphBuildInput()  # all defaults
    with pytest.raises(ValidationError):
        GraphBuildInput(unknown_field=1)  # type: ignore[call-arg]


def test_graph_describe_input_kind_enum():
    with pytest.raises(ValidationError):
        GraphDescribeInput(kind="bogus", identifier="x")  # type: ignore[arg-type]
    GraphDescribeInput(kind="repository")
    GraphDescribeInput(kind="package", identifier="foo")
    # Pydantic accepts identifier=None for non-repository kinds; the adapter rejects at dispatch.
    GraphDescribeInput(kind="package")


# --------------------------------------------------------------------------- #
# MCP dispatch
# --------------------------------------------------------------------------- #


async def test_graph_describe_mcp_dispatch(tmp_workspace, fake_ctx):
    recorder_pkg = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.q_describe_package, "run", recorder_pkg):
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="foo"), fake_ctx)
    assert out.status == "success"
    assert out.exit_code == 0
    assert recorder_pkg.call_count == 1
    args_ns = recorder_pkg.call_args.args[0]
    assert args_ns.name == "foo"

    recorder_repo = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.q_describe_repo, "run", recorder_repo):
        out = await graph_describe(GraphDescribeInput(kind="repository"), fake_ctx)
    assert out.status == "success"
    assert recorder_repo.call_count == 1


async def test_describe_missing_identifier_returns_error(tmp_workspace, fake_ctx):
    """Adapter-layer check: kind='package' with identifier=None returns exit_code=2."""
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.q_describe_package, "run", recorder):
        out = await graph_describe(GraphDescribeInput(kind="package"), fake_ctx)
    assert out.status == "error"
    assert out.exit_code == 2
    assert "identifier required for kind=package" in out.stderr
    assert recorder.call_count == 0


# --------------------------------------------------------------------------- #
# _StdoutGuard safety
# --------------------------------------------------------------------------- #


async def test_stdout_guard_not_tripped(tmp_workspace, fake_ctx):
    """cg's print() output is captured by _capture_run, never reaches _StdoutGuard."""

    def fake_print_then_succeed(args):
        print("hello from cg")  # must be captured
        return exit_codes.SUCCESS

    with patch.object(graph_module.q_describe_package, "run", side_effect=fake_print_then_succeed):
        # If _StdoutGuard fires, RuntimeError("Illegal stdout write") propagates.
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="foo"), fake_ctx)

    assert out.status == "success"
    assert "hello from cg" in out.stdout


# --------------------------------------------------------------------------- #
# Output shape
# --------------------------------------------------------------------------- #


async def test_output_shape_per_tool(tmp_workspace, fake_ctx):
    def succeed_with_output(args):
        print("captured")
        return exit_codes.SUCCESS

    with patch.object(graph_module.ops_update, "run", side_effect=succeed_with_output):
        out = await graph_build(GraphBuildInput(), fake_ctx)
    assert out.status == "success"
    assert out.exit_code == 0
    assert "captured" in out.stdout
    assert out.stderr == ""
    assert out.trace_path is None

    with patch.object(graph_module.q_describe_package, "run", side_effect=succeed_with_output):
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="foo"), fake_ctx)
    assert out.status == "success"
    assert "captured" in out.stdout

    with patch.object(graph_module.q_find, "run", side_effect=succeed_with_output):
        out = await graph_query(GraphQueryInput(name="x"), fake_ctx)
    assert out.status == "success"
    assert "captured" in out.stdout


# --------------------------------------------------------------------------- #
# Error packaging
# --------------------------------------------------------------------------- #


async def test_describe_missing_entity(tmp_workspace, fake_ctx):
    import sys as _sys

    def not_found(args):
        print("error: package not found: nonexistent", file=_sys.stderr)
        return exit_codes.GENERIC

    with patch.object(graph_module.q_describe_package, "run", side_effect=not_found):
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="nonexistent"), fake_ctx)

    assert out.status == "error"
    assert out.exit_code == exit_codes.GENERIC
    assert "package not found" in out.stderr


async def test_graph_build_uninitialized_returns_error(tmp_workspace, fake_ctx):
    with patch.object(graph_module.ops_update, "run", return_value=exit_codes.NOT_IN_GIT_REPO):
        out = await graph_build(GraphBuildInput(), fake_ctx)
    assert out.status == "error"
    assert out.exit_code == exit_codes.NOT_IN_GIT_REPO


async def test_graph_query_no_filters_returns_error(tmp_workspace, fake_ctx):
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.q_find, "run", recorder):
        out = await graph_query(GraphQueryInput(), fake_ctx)
    assert out.status == "error"
    assert out.exit_code == 2
    assert "at least one of name, kind, in_package required" in out.stderr
    assert recorder.call_count == 0


# --------------------------------------------------------------------------- #
# Trace writes
# --------------------------------------------------------------------------- #


async def test_graph_build_trace_writes_file(tmp_workspace, fake_ctx):
    with patch.object(graph_module.ops_update, "run", return_value=exit_codes.SUCCESS):
        out = await graph_build(GraphBuildInput(trace=True), fake_ctx)
    assert out.trace_path is not None
    p = Path(out.trace_path)
    assert p.exists(), f"trace file {p} should exist"
    records = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    events = [r.get("event") for r in records]
    assert "graph_build_start" in events
    assert "graph_build_complete" in events

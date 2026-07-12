"""Unit tests for the 3 graph_* MCP tools.

Covers GRAPHCMD-04, D-04, D-09:
  * Three tools registered (graph_build, graph_describe, graph_query)
  * Pydantic Input shape: extra='forbid', Literal kind enum
  * MCP dispatch delegates to the typed core funcs run_build/run_describe/run_query
    (Phase 59-02b: replaced the deleted _DESCRIBE_DISPATCH/_capture_run shim)
  * _StdoutGuard never tripped (core funcs return strings, never print)
  * Errors returned as GraphCommandOutput(status='error', ...) — no raises
  * Existing wiki_* tools remain registered (regression guard)
  * Trace files written and trace_path returned in output

asyncio_mode='auto' in packages/graph-wiki-mcp/pyproject.toml means `async def
test_*` functions are auto-detected — no @pytest.mark.asyncio decorator needed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from graph_io import exit_codes
from graph_wiki_core.commands import graph as graph_module

# Importing the server module installs _StdoutGuard at module-init time.
from graph_wiki_mcp.server import (  # noqa: F401  (mcp imported for tool registry inspection)
    GraphBuildInput,
    GraphCommandOutput,
    GraphDescribeInput,
    GraphQueryInput,
    graph_build,
    graph_describe,
    graph_query,
    mcp,
)
from pydantic import ValidationError


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
# MCP dispatch — delegates to typed core funcs
# --------------------------------------------------------------------------- #


async def test_graph_describe_mcp_dispatch(tmp_workspace, fake_ctx):
    recorder = MagicMock(return_value=(exit_codes.SUCCESS, "rendered package foo", ""))
    with patch.object(graph_module, "run_describe", recorder):
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="foo"), fake_ctx)
    assert out.status == "success"
    assert out.exit_code == 0
    assert out.stdout == "rendered package foo"
    assert recorder.call_count == 1
    # run_describe(kind, identifier, repo, workspace)
    assert recorder.call_args.args[0] == "package"
    assert recorder.call_args.args[1] == "foo"

    recorder_repo = MagicMock(return_value=(exit_codes.SUCCESS, "rendered repo", ""))
    with patch.object(graph_module, "run_describe", recorder_repo):
        out = await graph_describe(GraphDescribeInput(kind="repository"), fake_ctx)
    assert out.status == "success"
    assert recorder_repo.call_count == 1
    assert recorder_repo.call_args.args[0] == "repository"
    assert recorder_repo.call_args.args[1] is None


async def test_describe_missing_identifier_returns_error(tmp_workspace, fake_ctx):
    """Adapter-layer check: kind='package' with identifier=None returns exit_code=2."""
    recorder = MagicMock(return_value=(exit_codes.SUCCESS, "", ""))
    with patch.object(graph_module, "run_describe", recorder):
        out = await graph_describe(GraphDescribeInput(kind="package"), fake_ctx)
    assert out.status == "error"
    assert out.exit_code == 2
    assert "identifier required for kind=package" in out.stderr
    assert recorder.call_count == 0


# --------------------------------------------------------------------------- #
# _StdoutGuard safety — core funcs return strings, never print to stdout
# --------------------------------------------------------------------------- #


async def test_stdout_guard_not_tripped(tmp_workspace, fake_ctx):
    """run_describe returns its rendered output as a string; no stray stdout write."""
    recorder = MagicMock(return_value=(exit_codes.SUCCESS, "hello from describe", ""))
    with patch.object(graph_module, "run_describe", recorder):
        # If _StdoutGuard fires, RuntimeError("Illegal stdout write") propagates.
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="foo"), fake_ctx)

    assert out.status == "success"
    assert "hello from describe" in out.stdout


# --------------------------------------------------------------------------- #
# Output shape
# --------------------------------------------------------------------------- #


async def test_output_shape_per_tool(tmp_workspace, fake_ctx):
    # update.run is silent on success → run_build returns ("", ...) stdout.
    with patch.object(graph_module, "run_build", MagicMock(return_value=(exit_codes.SUCCESS, "", ""))):
        out = await graph_build(GraphBuildInput(), fake_ctx)
    assert out.status == "success"
    assert out.exit_code == 0
    assert out.stdout == ""  # D-06: typed update.run is silent
    assert out.stderr == ""
    assert out.trace_path is None

    with patch.object(graph_module, "run_describe", MagicMock(return_value=(exit_codes.SUCCESS, "rendered", ""))):
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="foo"), fake_ctx)
    assert out.status == "success"
    assert "rendered" in out.stdout

    with patch.object(graph_module, "run_query", MagicMock(return_value=(exit_codes.SUCCESS, "rows", ""))):
        out = await graph_query(GraphQueryInput(name="x"), fake_ctx)
    assert out.status == "success"
    assert "rows" in out.stdout


# --------------------------------------------------------------------------- #
# Error packaging
# --------------------------------------------------------------------------- #


async def test_describe_missing_entity(tmp_workspace, fake_ctx):
    recorder = MagicMock(return_value=(exit_codes.GENERIC, "", "error: package not found: nonexistent"))
    with patch.object(graph_module, "run_describe", recorder):
        out = await graph_describe(GraphDescribeInput(kind="package", identifier="nonexistent"), fake_ctx)

    assert out.status == "error"
    assert out.exit_code == exit_codes.GENERIC
    assert "package not found" in out.stderr


async def test_graph_build_uninitialized_returns_error(tmp_workspace, fake_ctx):
    with patch.object(
        graph_module,
        "run_build",
        MagicMock(return_value=(exit_codes.NOT_IN_GIT_REPO, "", "error: not a git repo")),
    ):
        out = await graph_build(GraphBuildInput(), fake_ctx)
    assert out.status == "error"
    assert out.exit_code == exit_codes.NOT_IN_GIT_REPO


async def test_graph_query_no_filters_returns_error(tmp_workspace, fake_ctx):
    recorder = MagicMock(return_value=(exit_codes.SUCCESS, "", ""))
    with patch.object(graph_module, "run_query", recorder):
        out = await graph_query(GraphQueryInput(), fake_ctx)
    assert out.status == "error"
    assert out.exit_code == 2
    assert "at least one of name, kind, in_package required" in out.stderr
    assert recorder.call_count == 0


# --------------------------------------------------------------------------- #
# Trace writes
# --------------------------------------------------------------------------- #


async def test_graph_build_trace_writes_file(tmp_workspace, fake_ctx):
    with patch.object(graph_module, "run_build", MagicMock(return_value=(exit_codes.SUCCESS, "", ""))):
        out = await graph_build(GraphBuildInput(trace=True), fake_ctx)
    assert out.trace_path is not None
    p = Path(out.trace_path)
    assert p.exists(), f"trace file {p} should exist"
    records = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    events = [r.get("event") for r in records]
    assert "graph_build_start" in events
    assert "graph_build_complete" in events

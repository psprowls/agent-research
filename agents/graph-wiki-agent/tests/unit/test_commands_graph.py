"""Unit tests for the graph subapp (Phase 38-01 Task 5).

Covers GRAPHCMD-01..GRAPHCMD-03 and D-01..D-09:
  * CLI shape (3 top-level subcommands, 6 describe sub-sub-commands)
  * graph build dispatches to ops_update; --full toggles correctly
  * --trace writes JSONL files with schema_version=1 and correct event names
  * --model is recorded but not invoked (v1.7); stderr note emitted
  * Proxy commands (describe/query) omit cost fields (D-03)
  * graph query pre-validates at Typer layer (no AttributeError on _parser=None)
  * cg exit codes propagate as typer.Exit codes
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from graph_io import exit_codes
from graph_wiki_agent.cli import app
from graph_wiki_agent.commands import graph as graph_module


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """A tmp workspace + GRAPH_WIKI_WORKSPACE env var.

    The cg modules are mocked, so we don't need a real .graph-wiki.yaml or DB —
    workspace_io.config.resolve(None, require_manifest=False) accepts any path.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(ws))
    return ws


# --------------------------------------------------------------------------- #
# CLI shape
# --------------------------------------------------------------------------- #


def test_graph_help_lists_exactly_three_subcommands(runner):
    result = runner.invoke(app, ["graph", "--help"])
    assert result.exit_code == 0, result.output
    assert "build" in result.output
    assert "describe" in result.output
    assert "query" in result.output


def test_graph_build_help_flags(runner):
    result = runner.invoke(app, ["graph", "build", "--help"])
    assert result.exit_code == 0, result.output
    for flag in ["--full", "--trace", "--model", "--workspace"]:
        assert flag in result.output, f"missing flag {flag} in:\n{result.output}"
    # cg flags should NOT be advertised on graph build
    assert "--repo" not in result.output
    assert "--fmt" not in result.output


def test_graph_describe_help_lists_six_kinds(runner):
    result = runner.invoke(app, ["graph", "describe", "--help"])
    assert result.exit_code == 0, result.output
    for kind in ["package", "path", "repository", "domain", "entry-point", "test-suite"]:
        assert kind in result.output, f"missing kind {kind} in:\n{result.output}"


# --------------------------------------------------------------------------- #
# graph build
# --------------------------------------------------------------------------- #


def test_graph_build_dispatches_to_ops_update(runner, tmp_workspace):
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.ops_update, "run", recorder):
        result = runner.invoke(app, ["graph", "build"])
        assert result.exit_code == 0, result.output
        assert recorder.call_count == 1
        args = recorder.call_args.args[0]
        assert args.full is False
        assert args._module is graph_module.ops_update

        result_full = runner.invoke(app, ["graph", "build", "--full"])
        assert result_full.exit_code == 0, result_full.output
        assert recorder.call_count == 2
        assert recorder.call_args.args[0].full is True


def test_graph_build_writes_trace(runner, tmp_workspace):
    with patch.object(graph_module.ops_update, "run", return_value=exit_codes.SUCCESS):
        result = runner.invoke(app, ["graph", "build", "--trace"])
        assert result.exit_code == 0, result.output

    trace_files = list((tmp_workspace / ".graph-wiki" / "traces").glob("*-graph-build.jsonl"))
    assert len(trace_files) == 1, [p.name for p in trace_files]

    records = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
        if line.strip()
    ]
    events = [r.get("event") for r in records]
    assert "graph_build_start" in events
    assert "graph_build_complete" in events
    complete = next(r for r in records if r["event"] == "graph_build_complete")
    assert complete["schema_version"] == 1
    assert complete["exit_code"] == 0
    assert complete["duration_ms"] >= 0
    assert "args" in complete


def test_graph_build_model_recorded_not_invoked(runner, tmp_workspace):
    with patch.object(graph_module.ops_update, "run", return_value=exit_codes.SUCCESS):
        result = runner.invoke(app, ["graph", "build", "--trace", "--model", "my-model-id"])
        assert result.exit_code == 0, result.output
        assert "not invoked in v1.7" in result.stderr

    trace_files = list((tmp_workspace / ".graph-wiki" / "traces").glob("*-graph-build.jsonl"))
    records = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
        if line.strip()
    ]
    complete = next(r for r in records if r["event"] == "graph_build_complete")
    assert complete.get("model_id") == "my-model-id"


# --------------------------------------------------------------------------- #
# graph describe (dispatch parametrized over 6 kinds)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kind_kebab, kind_snake, cg_attr, identifier, id_attr",
    [
        ("package", "package", "q_describe_package", "my-pkg", "name"),
        ("path", "path", "q_describe_path", "src/foo.py", "path"),
        ("repository", "repository", "q_describe_repo", None, None),
        ("domain", "domain", "q_describe_domain", "my-domain", "name"),
        ("entry-point", "entry_point", "q_describe_entry_point", "my-ep", "name"),
        ("test-suite", "test_suite", "q_describe_suite", "my-suite", "name"),
    ],
)
def test_graph_describe_dispatch_all_six_kinds(
    runner, tmp_workspace, kind_kebab, kind_snake, cg_attr, identifier, id_attr
):
    cg_module = getattr(graph_module, cg_attr)
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    argv = ["graph", "describe", kind_kebab]
    if identifier is not None:
        argv.append(identifier)
    with patch.object(cg_module, "run", recorder):
        result = runner.invoke(app, argv)
    assert result.exit_code == 0, result.output
    assert recorder.call_count == 1
    args = recorder.call_args.args[0]
    if id_attr is not None:
        assert getattr(args, id_attr) == identifier
    assert args._module is cg_module


def test_graph_describe_trace_omits_cost_fields(runner, tmp_workspace):
    with patch.object(graph_module.q_describe_package, "run", return_value=exit_codes.SUCCESS):
        result = runner.invoke(app, ["graph", "describe", "package", "my-pkg", "--trace"])
        assert result.exit_code == 0, result.output

    trace_files = list((tmp_workspace / ".graph-wiki" / "traces").glob("*-graph-describe.jsonl"))
    assert len(trace_files) == 1, [p.name for p in trace_files]
    records = [
        json.loads(line)
        for line in trace_files[0].read_text().splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec["event"] == "graph_describe"
    assert rec["schema_version"] == 1
    # D-03 honest-omission
    assert "model_id" not in rec, rec
    assert "tokens_in" not in rec, rec
    assert "tokens_out" not in rec, rec
    assert "cost_usd" not in rec, rec
    # Required fields
    assert "command" in rec
    assert "args" in rec
    assert "exit_code" in rec
    assert "duration_ms" in rec
    assert "timestamp" in rec


# --------------------------------------------------------------------------- #
# graph query
# --------------------------------------------------------------------------- #


def test_graph_query_dispatch(runner, tmp_workspace):
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.q_find, "run", recorder):
        result = runner.invoke(
            app,
            ["graph", "query", "--name", "foo", "--kind", "class", "--in-package", "pkg"],
        )
    assert result.exit_code == 0, result.output
    args = recorder.call_args.args[0]
    assert args.name == "foo"
    assert args.kind == "class"
    assert args.in_package == "pkg"


def test_graph_query_no_filters_fails_fast(runner, tmp_workspace):
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.q_find, "run", recorder):
        result = runner.invoke(app, ["graph", "query"])
    assert result.exit_code == 2, result.output
    assert "at least one of --name, --kind, --in-package is required" in result.stderr
    assert recorder.call_count == 0, "q_find.run must NOT be called when Typer-layer pre-validation fails"


# --------------------------------------------------------------------------- #
# exit code propagation
# --------------------------------------------------------------------------- #


def test_cg_exit_codes_propagate(runner, tmp_workspace):
    with patch.object(graph_module.ops_update, "run", return_value=exit_codes.NOT_IN_GIT_REPO):
        result = runner.invoke(app, ["graph", "build"])
    assert result.exit_code == exit_codes.NOT_IN_GIT_REPO

    with patch.object(graph_module.ops_update, "run", return_value=exit_codes.SUCCESS):
        result = runner.invoke(app, ["graph", "build"])
    assert result.exit_code == 0

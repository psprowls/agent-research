"""Unit tests for the graph subapp (Phase 38-01 Task 5, rebuilt Phase 59 Wave 3).

Covers GRAPHCMD-01..GRAPHCMD-03 and D-01..D-09:
  * CLI shape (3 top-level subcommands, 6 describe sub-sub-commands)
  * graph build dispatches to update.run; --full toggles correctly
  * --trace writes JSONL files with schema_version=1 and correct event names
  * --model is recorded but not invoked (v1.7); stderr note emitted
  * Proxy commands (describe/query) omit cost fields (D-03)
  * graph query pre-validates at Typer layer (no-filter → exit 2)
  * Real-DB syrupy snapshots verify byte-identical output for all 6 describe kinds + query
  * Exit-code branches (NOT_INITIALIZED, SCHEMA_MISMATCH, --in-package no-match,
    ambiguous entry-point, NOT_IN_GIT_REPO) covered
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from graph_io import exit_codes, update
from graph_io.store import GraphNotInitializedError, SchemaMismatchError
from graph_wiki_agent.cli import app
from graph_wiki_agent.commands import graph as graph_module


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_workspace(tmp_path):
    """A minimal tmp workspace dir (no DB) for mock-based tests."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


# --------------------------------------------------------------------------- #
# CLI shape (kept verbatim from pre-refactor — do not depend on deleted mech)
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


def test_graph_query_no_filters_fails_fast(runner, tmp_workspace):
    result = runner.invoke(
        app,
        ["graph", "query"],
        env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
    )
    assert result.exit_code == 2, result.output
    assert "at least one of --name, --kind, --in-package is required" in result.stderr


# --------------------------------------------------------------------------- #
# graph build — monkeypatched update.run (D-06)
# --------------------------------------------------------------------------- #


def test_graph_build_invokes_update_run(runner, tmp_workspace):
    """graph build calls update.run; --full propagates."""
    with patch.object(update, "run", return_value=None) as mock_run:
        result = runner.invoke(
            app, ["graph", "build"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
        assert result.exit_code == 0, result.output
        assert mock_run.call_count == 1
        # Verify full=False default
        _, kwargs = mock_run.call_args
        assert kwargs.get("full") is False

    with patch.object(update, "run", return_value=None) as mock_run:
        result = runner.invoke(
            app, ["graph", "build", "--full"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_run.call_args
        assert kwargs.get("full") is True


def test_graph_build_writes_trace(runner, tmp_workspace):
    """--trace writes JSONL with start+complete events, schema_version=1, exit_code=0."""
    with patch.object(update, "run", return_value=None):
        result = runner.invoke(
            app, ["graph", "build", "--trace"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
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
    """--model is recorded in trace; stderr note 'not invoked in v1.7' is emitted."""
    with patch.object(update, "run", return_value=None):
        result = runner.invoke(
            app, ["graph", "build", "--trace", "--model", "my-model-id"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
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


def test_graph_build_not_in_git_repo(runner, tmp_workspace):
    """update.run raising NotInGitRepoError → exit NOT_IN_GIT_REPO."""
    with patch.object(update, "run", side_effect=update.NotInGitRepoError("not a repo")):
        result = runner.invoke(
            app, ["graph", "build"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
    assert result.exit_code == exit_codes.NOT_IN_GIT_REPO


# --------------------------------------------------------------------------- #
# graph describe — real-DB syrupy snapshots (6 kinds, D-08/D-09)
# --------------------------------------------------------------------------- #


def test_describe_package_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """describe package commonlib → byte-identical snapshot."""
    result = runner.invoke(
        app,
        ["graph", "describe", "package", "commonlib"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


def test_describe_path_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """describe path packages/commonlib/src/commonlib/__init__.py → byte-identical snapshot."""
    result = runner.invoke(
        app,
        ["graph", "describe", "path", "packages/commonlib/src/commonlib/__init__.py"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


def test_describe_repository_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """describe repository (no identifier) → snapshot (url: line normalized — path is tmp)."""
    result = runner.invoke(
        app,
        ["graph", "describe", "repository"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    # Normalize the `url:` line — it contains the tmp_path_factory path which
    # differs between test sessions. Replace everything after "url:" up to the
    # next newline with a stable placeholder.
    normalized = re.sub(r"(url:\s+).*", r"\1<normalized>", result.output)
    assert normalized == snapshot


def test_describe_domain_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """describe domain core → byte-identical snapshot."""
    result = runner.invoke(
        app,
        ["graph", "describe", "domain", "core"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


def test_describe_entry_point_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """describe entry-point mypkg-run → byte-identical snapshot."""
    result = runner.invoke(
        app,
        ["graph", "describe", "entry-point", "mypkg-run"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


def test_describe_test_suite_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """describe test-suite mypkg-unit-tests → byte-identical snapshot."""
    result = runner.invoke(
        app,
        ["graph", "describe", "test-suite", "mypkg-unit-tests"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


# --------------------------------------------------------------------------- #
# graph query — real-DB syrupy snapshot (D-08/D-09)
# --------------------------------------------------------------------------- #


def test_graph_query_output(
    runner: CliRunner,
    seeded_graph_workspace: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """graph query --kind package → byte-identical snapshot."""
    result = runner.invoke(
        app,
        ["graph", "query", "--kind", "package"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output
    assert result.output == snapshot


# --------------------------------------------------------------------------- #
# describe trace omits cost fields (D-03)
# --------------------------------------------------------------------------- #


def test_graph_describe_trace_omits_cost_fields(
    runner: CliRunner,
    seeded_graph_workspace: Path,
) -> None:
    """describe package with --trace: trace record omits model/cost fields (D-03)."""
    result = runner.invoke(
        app,
        ["graph", "describe", "package", "commonlib", "--trace"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == 0, result.output

    trace_files = list(
        (seeded_graph_workspace / ".graph-wiki" / "traces").glob("*-graph-describe.jsonl")
    )
    assert len(trace_files) >= 1, "no trace file found"
    records = [
        json.loads(line)
        for line in trace_files[-1].read_text().splitlines()
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
# Exit-code branches
# --------------------------------------------------------------------------- #


def test_describe_package_not_found_exits_generic(
    runner: CliRunner,
    seeded_graph_workspace: Path,
) -> None:
    """describe package with non-existent name → GENERIC(1)."""
    result = runner.invoke(
        app,
        ["graph", "describe", "package", "nonexistent-pkg-xyz"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == exit_codes.GENERIC
    # SC#3 byte-identical: not-found stderr must match the cg message exactly.
    assert "error: package not found: nonexistent-pkg-xyz" in result.stderr


def test_describe_path_not_found_stderr_byte_identical(
    runner: CliRunner,
    seeded_graph_workspace: Path,
) -> None:
    """describe path not-found stderr matches cg's `path not found in graph` (SC#3)."""
    result = runner.invoke(
        app,
        ["graph", "describe", "path", "no/such/path.xyz"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == exit_codes.GENERIC
    assert "error: path not found in graph: no/such/path.xyz" in result.stderr


def test_describe_test_suite_not_found_stderr_byte_identical(
    runner: CliRunner,
    seeded_graph_workspace: Path,
) -> None:
    """describe test-suite not-found stderr matches cg's `not found: <name>` (SC#3)."""
    result = runner.invoke(
        app,
        ["graph", "describe", "test-suite", "no-such-suite-xyz"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == exit_codes.GENERIC
    assert "error: not found: no-such-suite-xyz" in result.stderr


def test_describe_repository_not_found_stderr_byte_identical(
    runner: CliRunner,
    seeded_graph_workspace: Path,
) -> None:
    """describe repository not-found stderr matches cg's `not found: repository` (SC#3).

    A seeded graph always has a repository node, so force the None branch by
    patching the typed query.
    """
    with patch.object(graph_module.queries, "describe_repository", return_value=None):
        result = runner.invoke(
            app,
            ["graph", "describe", "repository"],
            env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
        )
    assert result.exit_code == exit_codes.GENERIC
    assert "error: not found: repository" in result.stderr


def test_query_in_package_no_match_exits_generic(
    runner: CliRunner,
    seeded_graph_workspace: Path,
) -> None:
    """graph query --kind package --in-package nonexistent → GENERIC(1) (D-07 quirk)."""
    result = runner.invoke(
        app,
        ["graph", "query", "--kind", "function", "--in-package", "nonexistent-pkg-xyz"],
        env={"GRAPH_WIKI_WORKSPACE": str(seeded_graph_workspace)},
    )
    assert result.exit_code == exit_codes.GENERIC


def test_describe_entry_point_ambiguous_exits_ambiguous(
    runner: CliRunner,
    tmp_workspace: Path,
) -> None:
    """Ambiguous bare entry-point name → AMBIGUOUS(7). Mock conn.execute to return >1 row."""
    import sqlite3

    fake_conn = MagicMock(spec=sqlite3.Connection)
    fake_conn.execute.return_value.fetchall.return_value = [("pkg1",), ("pkg2",)]

    with patch.object(graph_module, "_connect_or_error", return_value=(fake_conn, exit_codes.SUCCESS, "")):
        result = runner.invoke(
            app,
            ["graph", "describe", "entry-point", "ambiguous-ep"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
    assert result.exit_code == exit_codes.AMBIGUOUS


def test_describe_not_initialized_exits_not_initialized(
    runner: CliRunner,
    tmp_workspace: Path,
) -> None:
    """Graph DB not initialized → NOT_INITIALIZED(3)."""
    with patch.object(
        graph_module,
        "_connect_or_error",
        return_value=(None, exit_codes.NOT_INITIALIZED, "error: not initialized"),
    ):
        result = runner.invoke(
            app,
            ["graph", "describe", "package", "mypkg"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
    assert result.exit_code == exit_codes.NOT_INITIALIZED


def test_describe_schema_mismatch_exits_schema_mismatch(
    runner: CliRunner,
    tmp_workspace: Path,
) -> None:
    """Schema mismatch → SCHEMA_MISMATCH(4)."""
    with patch.object(
        graph_module,
        "_connect_or_error",
        return_value=(None, exit_codes.SCHEMA_MISMATCH, "error: schema mismatch"),
    ):
        result = runner.invoke(
            app,
            ["graph", "describe", "package", "mypkg"],
            env={"GRAPH_WIKI_WORKSPACE": str(tmp_workspace)},
        )
    assert result.exit_code == exit_codes.SCHEMA_MISMATCH

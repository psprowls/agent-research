from __future__ import annotations

"""Unit tests for Phase 39 scan→graph integration.

Covers D-01..D-08 of the scanner-consumes-graph-io plan:
  - D-01: scan calls cg update before fan-out (via graph helper surface)
  - D-02: cg update precedes discover_workspaces and SubagentPool.run_all
  - D-03: decoration step adds pkg['uri'] and overwrites pkg['domain']
          when graph carries belongs_to_domain; wiki_relative_path
          is recomputed when domain changes
  - D-04: wiki-io's _wiki_relative_path_for is reused (not reimplemented)
  - D-05: a single read-only conn is opened on success and closed in finally
  - D-06: cg update is incremental (full=False) with no trace, no model
  - D-07: hard abort on non-recoverable runtime failure (no fallback line)
  - D-08: graceful fallback on filesystem init failure (one stderr line)

The scanner fan-out (LLM dispatch) is short-circuited in every test via a
stubbed SubagentPool.run_all that returns an empty FanOutResult — no Bedrock.
"""

import asyncio
import json
import re
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from graph_io import exit_codes
from graph_io.store import GraphNotInitializedError
from graph_wiki_agent.commands import graph as graph_module
from graph_wiki_agent.commands import scan as scan_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_not_initialized_fallback_line(stderr: str) -> bool:
    """Return True iff stderr contains EXACTLY ONE NOT_INITIALIZED fallback line."""
    pattern = r"\[NOT_INITIALIZED fallback: graph could not be initialized \(.+\); using path-based slugs\]"
    matches = re.findall(pattern, stderr)
    return len(matches) == 1


def _seed_minimal_graph(db_path: Path) -> None:
    """Create a minimal sqlite DB with two packages and one belongs_to_domain edge.

    Layout:
      package nodes: pkg-a, pkg-b
      domain node:   my-domain
      edges:         pkg-a -[belongs_to_domain]-> my-domain
      uri values:    pkg-a -> pkg:org/repo/pkg-a
                     pkg-b -> pkg:org/repo/pkg-b
    """
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        # Insert two package nodes (uri stored in `nodes.uri` column per upsert.py)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', 'pkg:org/repo/pkg-a')"
        )
        pkg_a_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-b', 'packages/pkg-b', NULL, '{\"language\": \"python\"}', 'pkg:org/repo/pkg-b')"
        )
        # Domain node
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('domain', 'my-domain', NULL, NULL, '{}', 'domain:org/repo/my-domain')"
        )
        dom_id = conn.execute(
            "SELECT id FROM nodes WHERE kind='domain' AND name='my-domain'"
        ).fetchone()[0]
        # belongs_to_domain edge: pkg-a -> my-domain
        conn.execute(
            "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?, ?, 'belongs_to_domain', NULL)",
            (pkg_a_id, dom_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """Build a minimal workspace + wiki + repo skeleton on disk.

    Layout:
      tmp_path/workspace/
        wiki/
          CLAUDE.md      # empty layout block (heuristic discovery)
          .graph-wiki/   # created — graph DB lives at graph/code.db
        repo/            # minimal monorepo
    """
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n\nNo pinned containers.\n")
    # append_log validates the wiki by checking for log.md at the wiki root.
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    return workspace


@pytest.fixture
def tmp_workspace_with_packages(tmp_workspace):
    """Extend tmp_workspace with two minimal python packages in repo/packages/."""
    repo = tmp_workspace / "repo"
    for name in ("pkg-a", "pkg-b"):
        pdir = repo / "packages" / name / "src" / name.replace("-", "_")
        pdir.mkdir(parents=True)
        (pdir / "__init__.py").write_text('"""pkg."""\n')
        (repo / "packages" / name / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
        )
    return tmp_workspace


@pytest.fixture(autouse=True)
def stub_pool_run_all(monkeypatch):
    """Short-circuit the scanner fan-out — no Bedrock calls in unit tests."""
    from subagent_runtime.pool import FanOutResult

    async def _stub(self, *, items, task, role, model_id, max_concurrency):
        result = FanOutResult()
        return result

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _stub)


@pytest.fixture(autouse=True)
def stub_make_llm(monkeypatch):
    """Replace make_llm so no Bedrock-credential lookup happens during run_scan."""
    monkeypatch.setattr(scan_module, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_module,
        "load_role_config",
        lambda role: {
            "model_id": "fake-model",
            "max_concurrency": 1,
            "region": "us-east-1",
            "max_tokens": 100,
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cg_update_dispatched_before_fanout(tmp_workspace_with_packages, monkeypatch):
    """SC#1 / D-01 / D-02: scan calls run_build(...) once BEFORE any
    SubagentPool.run_all invocation, with full=False.

    Phase 59-02b: migrated off the deleted _capture_run(ops_update, ...) shim
    onto the typed run_build core (scan binds it as `_cg_run_build`).
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    order: list[str] = []
    captured_call: dict = {}

    def _recorder_run_build(repo_arg, workspace_arg, *, full):
        order.append("cg_update")
        captured_call["repo"] = repo_arg
        captured_call["workspace"] = workspace_arg
        captured_call["full"] = full
        return (exit_codes.SUCCESS, "", "")

    monkeypatch.setattr(scan_module, "_cg_run_build", _recorder_run_build)

    from subagent_runtime.pool import FanOutResult

    async def _track_run_all(self, *, items, task, role, model_id, max_concurrency):
        order.append("fanout")
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _track_run_all)

    # Pretend cg succeeded but no DB on disk → conn open should fail with
    # GraphNotInitializedError; scan should still complete via fallback.
    asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    assert order, "expected at least the cg_update step to run"
    assert order[0] == "cg_update", f"cg update must run first; got order={order}"
    # Verify the call shape — full=False, workspace is the ROOT (wiki.parent),
    # which run_build writes `.graph/code.db` under. Mirrors commands/graph.py
    # and the librarian's read path (commands/query.py uses graph_dir(wiki.parent)).
    assert captured_call["full"] is False, f"expected full=False; got {captured_call['full']}"
    assert captured_call["workspace"] == workspace, (
        f"expected workspace root; got {captured_call['workspace']}"
    )
    assert captured_call["repo"] == repo


def test_cg_update_logs_success(tmp_workspace_with_packages, monkeypatch):
    """SC#1: scan log records 'cg update complete: exit_code=0' after success."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    log_path = wiki / "log.md"
    assert log_path.exists(), f"scan log not written at {log_path}"
    log_text = log_path.read_text(encoding="utf-8")
    assert "cg update complete: exit_code=0" in log_text


def test_decoration_adds_uri_and_domain(tmp_workspace_with_packages, monkeypatch):
    """D-03 / D-04: after a successful cg update, every workspace dict whose
    unscope(name) matches a graph package gets `pkg['uri']` from the graph
    and `pkg['domain']` from belongs_to_domain (when present).
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    # Seed the graph DB at the expected path so read_only_connect succeeds.
    db = workspace / ".graph" / "code.db"
    _seed_minimal_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Capture the decorated workspaces by patching the fan-out to inspect items.
    captured: dict = {}
    from subagent_runtime.pool import FanOutResult

    async def _capture_fanout(self, *, items, task, role, model_id, max_concurrency):
        captured["items"] = list(items)
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _capture_fanout)

    # Also intercept the workspace list directly via discover_workspaces wrapper,
    # because fan-out only sees diffed items. Easier: patch discover_workspaces
    # to inject a known minimal list that matches our seeded graph names.
    fake_workspaces = [
        {
            "name": "pkg-a",
            "path": "packages/pkg-a",
            "wiki_relative_path": "packages/pkg-a/overview.md",
            "type": "library",
            "language": "python",
            "changed_files": None,
        },
        {
            "name": "pkg-b",
            "path": "packages/pkg-b",
            "wiki_relative_path": "packages/pkg-b/overview.md",
            "type": "library",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_workspaces)
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["pkg-a", "pkg-b"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    # Inspect the decorated workspaces (mutated in place by the decoration step).
    pkg_a = next(w for w in fake_workspaces if w["name"] == "pkg-a")
    pkg_b = next(w for w in fake_workspaces if w["name"] == "pkg-b")

    assert pkg_a.get("uri") == "pkg:org/repo/pkg-a", f"pkg-a uri not decorated: {pkg_a}"
    assert pkg_b.get("uri") == "pkg:org/repo/pkg-b", f"pkg-b uri not decorated: {pkg_b}"
    # pkg-a has belongs_to_domain → my-domain; pkg-b has none
    assert pkg_a.get("domain") == "my-domain", f"pkg-a domain not decorated: {pkg_a}"
    assert pkg_b.get("domain") is None or pkg_b.get("domain") == "", \
        f"pkg-b has unexpected domain: {pkg_b}"


def test_slug_recomputed_on_domain_change(tmp_workspace_with_packages, monkeypatch):
    """SC#2 / D-03: a package whose graph domain differs from its filesystem
    domain has its `wiki_relative_path` recomputed to the domain-scoped slug.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_minimal_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # pkg-a starts at packages/pkg-a/overview.md; after graph decoration
    # gives it domain=my-domain, slug should become
    # domains/my-domain/packages/pkg-a/overview.md.
    pkg_a = {
        "name": "pkg-a",
        "path": "packages/pkg-a",
        "wiki_relative_path": "packages/pkg-a/overview.md",
        "type": "library",
        "language": "python",
        "changed_files": None,
    }
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: [pkg_a])
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["pkg-a"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    assert pkg_a["domain"] == "my-domain"
    assert (
        pkg_a["wiki_relative_path"] == "domains/my-domain/packages/pkg-a/overview.md"
    ), f"slug not recomputed: {pkg_a['wiki_relative_path']}"


@pytest.mark.parametrize(
    "exit_code,stderr",
    [
        (exit_codes.NOT_IN_GIT_REPO, "fatal: not a git repository"),
        (exit_codes.UPDATE_IN_PROGRESS, "another update is in progress"),
        (exit_codes.SCHEMA_MISMATCH, "schema version mismatch"),
        (exit_codes.GENERIC, "sqlite3.OperationalError: database is locked"),
    ],
)
def test_hard_abort_on_runtime_failure(
    tmp_workspace_with_packages, monkeypatch, capsys, exit_code, stderr
):
    """D-07: non-recoverable runtime failures hard-abort with ScanAbortedError;
    fan-out NEVER runs; no NOT_INITIALIZED fallback line is emitted.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_code, "", stderr)
    )

    # Stub the pool with a recorder that proves it was NEVER called.
    pool_calls: list[int] = []
    from subagent_runtime.pool import FanOutResult

    async def _track(self, *, items, task, role, model_id, max_concurrency):
        pool_calls.append(1)
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _track)

    with pytest.raises(scan_module.ScanAbortedError) as excinfo:
        asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    assert excinfo.value.exit_code == exit_code
    assert str(exit_code) in str(excinfo.value)
    assert pool_calls == [], f"fan-out should not have run; pool_calls={pool_calls}"

    captured = capsys.readouterr()
    assert "[NOT_INITIALIZED fallback:" not in captured.err, (
        f"NOT_INITIALIZED fallback should NOT be emitted on hard abort; stderr={captured.err}"
    )


def test_hard_abort_on_generic_runtime_failure(tmp_workspace_with_packages, monkeypatch, capsys):
    """D-07: GENERIC exit with non-init-pattern stderr is a hard abort (no fallback)."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    monkeypatch.setattr(
        scan_module,
        "_cg_run_build",
        lambda repo, workspace, *, full: (
            exit_codes.GENERIC,
            "",
            "sqlite3.OperationalError: database is locked",
        ),
    )

    with pytest.raises(scan_module.ScanAbortedError):
        asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    captured = capsys.readouterr()
    assert "[NOT_INITIALIZED fallback:" not in captured.err


@pytest.mark.parametrize(
    "init_stderr",
    [
        "PermissionError: [Errno 13] Permission denied",
        "OSError: [Errno 28] No space left on device",
        "OSError: [Errno 30] Read-only file system",
        "Permission denied: cannot create .graph-wiki/graph/",
    ],
)
def test_graceful_fallback_on_init_failure(
    tmp_workspace_with_packages, monkeypatch, capsys, init_stderr
):
    """D-08: GENERIC exit with init-pattern stderr emits exactly one fallback line,
    skips decoration, and lets the scan complete without raising.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    monkeypatch.setattr(
        scan_module,
        "_cg_run_build",
        lambda repo, workspace, *, full: (exit_codes.GENERIC, "", init_stderr),
    )

    # read_only_connect should NEVER be called when init fallback fired.
    conn_calls: list[Path] = []
    real_read_only_connect = scan_module.read_only_connect

    def _record_conn(db_path):
        conn_calls.append(db_path)
        return real_read_only_connect(db_path)

    monkeypatch.setattr(scan_module, "read_only_connect", _record_conn)

    # Scan should complete without raising.
    result = asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True)
    )
    assert result is not None  # ScanResult returned

    captured = capsys.readouterr()
    assert _has_not_initialized_fallback_line(captured.err), (
        f"expected exactly one NOT_INITIALIZED fallback line in stderr; got: {captured.err!r}"
    )
    assert conn_calls == [], (
        f"read_only_connect should not be called on init fallback; calls={conn_calls}"
    )


def test_conn_closed_on_exception(tmp_workspace_with_packages, monkeypatch):
    """D-05 / Pitfall 4: read-only conn opened after successful cg update is
    closed in finally even when fan-out raises.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_minimal_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Substitute read_only_connect with a MagicMock so we can assert close().
    mock_conn = MagicMock()
    # Mock execute() to return an object with fetchall() so domain query works.
    mock_conn.execute.return_value.fetchall.return_value = []
    monkeypatch.setattr(scan_module, "read_only_connect", lambda db_path: mock_conn)

    # Make list_packages return [] so decoration is a no-op (graph query phase).
    monkeypatch.setattr(scan_module.queries, "list_packages", lambda conn: [])

    # Phase 45 D-04/D-08: legacy scanner fan-out is removed. To exercise the
    # conn-closure-on-exception path we now raise from write_entities (Step 9a),
    # which runs inside the same `try` block as the conn lifecycle.
    def _boom_write(*a, **kw):
        raise RuntimeError("simulated fan-out crash")

    monkeypatch.setattr(scan_module, "write_entities", _boom_write)

    # Patch discover_workspaces so we actually reach the fan-out step.
    monkeypatch.setattr(
        scan_module,
        "discover_workspaces",
        lambda *a, **kw: [
            {
                "name": "pkg-a",
                "path": "packages/pkg-a",
                "wiki_relative_path": "packages/pkg-a/overview.md",
                "type": "library",
                "language": "python",
                "changed_files": None,
            }
        ],
    )
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["pkg-a"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    with pytest.raises(RuntimeError, match="simulated fan-out crash"):
        asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    mock_conn.close.assert_called(), "read-only conn must be closed in finally"


def test_phase35_regression_test_path_exists():
    """SC#3 sanity guard: Phase 35 bootstrap test file is still in the repo.

    Phase 39 does not modify wiki-io, so this test's continued presence on
    disk is the structural pre-condition for SC#3 — Task 5 actually re-runs it.
    """
    repo_root = Path(__file__).resolve().parents[4]
    bootstrap_test = (
        repo_root
        / "packages"
        / "wiki-io"
        / "tests"
        / "test_bootstrap_e2e_no_broken_links.py"
    )
    assert bootstrap_test.exists(), (
        f"Phase 35 regression test missing at {bootstrap_test}; SC#3 cannot be evaluated."
    )

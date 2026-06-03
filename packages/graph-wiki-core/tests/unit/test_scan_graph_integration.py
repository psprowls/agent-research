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
from graph_wiki_core.commands import graph as graph_module
from graph_wiki_core.commands import scan as scan_module


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


def _seed_app_graph(db_path: Path) -> None:
    """Create a minimal sqlite DB with one `app` kind node.

    Layout:
      app node: app-x  (uri app:org/repo/app-x, path apps/app-x)

    Mirrors _seed_minimal_graph but seeds an app instead of packages. The
    `app:` uri scheme matches graph_io/uri.py:app_uri. No domain/repo nodes
    are needed — write_entities renders any admitted kind that has nodes.
    """
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('app', 'app-x', 'apps/app-x', NULL, '{\"language\": \"python\"}', 'app:org/repo/app-x')"
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
            f'[project]\nname = "{name}"\nversion = "0.1.1"\n'
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

    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    with pytest.raises(RuntimeError, match="simulated fan-out crash"):
        asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=True))

    mock_conn.close.assert_called(), "read-only conn must be closed in finally"


def test_file_map_injected_into_package_entity_page(
    tmp_workspace_with_packages, monkeypatch
):
    """File-map injection: after write_entities creates a package entity page,
    run_scan replaces its `## File map` section with the deterministic
    `w["file_map"]` block (path + kind rows). Verified end-to-end against the
    real write_entities + packaged entity-package.md template.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_minimal_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Deterministic file-map block as build_file_map would emit it for pkg-a.
    pkg_a_block = (
        "## File map - pkg-a\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### pkg-a/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/pkg_a/__init__.py` | file | — TODO |\n"
    )

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
            # No file_map → injection is skipped for pkg-b.
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for pkg-a,
    # None for pkg-b (so pkg-b injection is still skipped).
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: pkg_a_block if str(path).endswith("pkg-a") else None,
    )

    result = asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)
    )

    # pkg-a was created this scan → its file map should be injected.
    assert "pkg:org/repo/pkg-a" in result.entities_created

    # Find the entity page for pkg-a by its frontmatter uri.
    import frontmatter

    entities = sorted((wiki / "entities").glob("*.md"))
    assert entities, "no entity pages written"
    pkg_a_page = next(
        p for p in entities if frontmatter.load(p).metadata.get("uri") == "pkg:org/repo/pkg-a"
    )
    text = pkg_a_page.read_text(encoding="utf-8")

    # Deterministic rows landed; the empty template placeholder rows are gone.
    assert "| `pyproject.toml` | file | — TODO |" in text
    assert "| `src/pkg_a/__init__.py` | file | — TODO |" in text
    assert "<Short description of file contents.>" not in text
    assert text.count("## File map - pkg-a") == 1
    # Neighboring sections preserved.
    assert "## Purpose" in text
    assert "## Public API" in text


@pytest.mark.asyncio
async def test_file_map_injected_into_app_entity_page(
    tmp_workspace_with_packages, monkeypatch
):
    """File-map injection (apps): after write_entities creates an app entity
    page, run_scan replaces its `## File map` section with the deterministic
    `w["file_map"]` block (path + kind rows). Verified end-to-end against the
    real write_entities + packaged entity-app.md template. App parity with
    test_file_map_injected_into_package_entity_page.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Deterministic file-map block as build_file_map would emit it for app-x.
    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/app_x/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for app-x.
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: app_x_block if str(path).endswith("app-x") else None,
    )

    result = await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    # app-x was created this scan → its file map should be injected.
    assert "app:org/repo/app-x" in result.entities_created

    # Find the entity page for app-x by its frontmatter uri.
    import frontmatter

    entities = sorted((wiki / "entities").glob("*.md"))
    assert entities, "no entity pages written"
    app_x_page = next(
        p for p in entities if frontmatter.load(p).metadata.get("uri") == "app:org/repo/app-x"
    )
    text = app_x_page.read_text(encoding="utf-8")

    # Deterministic rows landed; the empty template placeholder rows are gone.
    assert "| `pyproject.toml` | file | — TODO |" in text
    assert "| `src/app_x/__init__.py` | file | — TODO |" in text
    assert "<Short description of file contents.>" not in text
    assert text.count("## File map - app-x") == 1
    # Neighboring sections survive injection (only the File map block is replaced).
    assert "## Provider chain" in text
    assert "## Concepts" in text


def test_file_map_descriptions_survive_rescan(
    tmp_workspace_with_packages, monkeypatch
):
    """Durability: a Description filled into a package's File-map table survives
    a rescan, even though write_entities re-renders the page body from template.

    The snapshot-before-write_entities pass captures the filled description; the
    Step 10b inject_file_map(preserved=...) merge restores it for the path that
    is still on disk. Unfilled (— TODO) rows stay TODO.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_minimal_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    pkg_a_block = (
        "## File map - pkg-a\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### pkg-a/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/pkg_a/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "pkg-a",
            "path": "packages/pkg-a",
            "wiki_relative_path": "packages/pkg-a/overview.md",
            "type": "library",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for pkg-a.
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: pkg_a_block if str(path).endswith("pkg-a") else None,
    )

    import frontmatter

    # Scan 1: page created, File map injected with — TODO rows.
    asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)
    )
    pkg_a_page = next(
        p
        for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "pkg:org/repo/pkg-a"
    )

    # Human/ingest fills one description (the other stays — TODO).
    filled = pkg_a_page.read_text(encoding="utf-8").replace(
        "| `src/pkg_a/__init__.py` | file | — TODO |",
        "| `src/pkg_a/__init__.py` | file | the package entrypoint |",
    )
    pkg_a_page.write_text(filled, encoding="utf-8")

    # Scan 2: write_entities re-renders the page body from template (wiping the
    # injected File map); the snapshot+merge must restore the filled cell.
    asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)
    )

    text2 = pkg_a_page.read_text(encoding="utf-8")
    assert "| `src/pkg_a/__init__.py` | file | the package entrypoint |" in text2, (
        f"filled description was wiped on rescan; page:\n{text2}"
    )
    # The un-filled row remains a — TODO placeholder.
    assert "| `pyproject.toml` | file | — TODO |" in text2


def test_code_reader_fanout_fills_todo_descriptions(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c: after the deterministic File map is injected with — TODO rows,
    the code_reader fan-out fills the Description cells from the model's
    {path: description} JSON. Verified end-to-end with a stubbed describer pool.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_minimal_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    pkg_a_block = (
        "## File map - pkg-a\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### pkg-a/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/pkg_a/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "pkg-a",
            "path": "packages/pkg-a",
            "wiki_relative_path": "packages/pkg-a/overview.md",
            "type": "library",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for pkg-a.
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: pkg_a_block if str(path).endswith("pkg-a") else None,
    )

    # Override the autouse empty-pool stub: the code_reader pool returns a
    # {path: description} JSON for each item's todo paths; the narrator pool
    # (role != code_reader) stays empty.
    from subagent_runtime.pool import FanOutResult

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                _uri, _ws, _page, todo_paths = it
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    import frontmatter

    asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)
    )

    pkg_a_page = next(
        p
        for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "pkg:org/repo/pkg-a"
    )
    text = pkg_a_page.read_text(encoding="utf-8")

    # The — TODO placeholders were replaced by the model's descriptions.
    assert "| `pyproject.toml` | file | desc for pyproject.toml |" in text
    assert (
        "| `src/pkg_a/__init__.py` | file | desc for src/pkg_a/__init__.py |"
        in text
    )
    assert "— TODO" not in text


@pytest.mark.asyncio
async def test_code_reader_fanout_fills_app_todo_descriptions(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c (apps): after the deterministic File map is injected with — TODO
    rows on an app page, the code_reader fan-out fills the Description cells from
    the model's {path: description} JSON. Proves Step 10c is kind-agnostic once
    Task 1 lands apps in file_mapped_pages.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/app_x/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for app-x.
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: app_x_block if str(path).endswith("app-x") else None,
    )

    # Override the autouse empty-pool stub: the code_reader pool returns a
    # {path: description} JSON for each item's todo paths; the narrator pool
    # (role != code_reader) stays empty.
    from subagent_runtime.pool import FanOutResult

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                _uri, _ws, _page, todo_paths = it
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    import frontmatter

    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    app_x_page = next(
        p
        for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "app:org/repo/app-x"
    )
    text = app_x_page.read_text(encoding="utf-8")

    # The — TODO placeholders were replaced by the model's descriptions.
    assert "| `pyproject.toml` | file | desc for pyproject.toml |" in text
    assert (
        "| `src/app_x/__init__.py` | file | desc for src/app_x/__init__.py |"
        in text
    )
    assert "— TODO" not in text


@pytest.mark.asyncio
async def test_app_file_map_descriptions_survive_rescan(
    tmp_workspace_with_packages, monkeypatch
):
    """Durability (apps): a Description filled into an app's File-map table
    survives a rescan, even though write_entities re-renders the page body from
    template. The snapshot-before-write_entities pass captures the filled cell;
    Step 10b inject_file_map(preserved=...) restores it. App parity with
    test_file_map_descriptions_survive_rescan.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/app_x/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for app-x.
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: app_x_block if str(path).endswith("app-x") else None,
    )

    import frontmatter

    # Scan 1: page created, File map injected with — TODO rows.
    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )
    app_x_page = next(
        p
        for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "app:org/repo/app-x"
    )

    # Human/ingest fills one description (the other stays — TODO).
    filled = app_x_page.read_text(encoding="utf-8").replace(
        "| `src/app_x/__init__.py` | file | — TODO |",
        "| `src/app_x/__init__.py` | file | the app entrypoint |",
    )
    app_x_page.write_text(filled, encoding="utf-8")

    # Scan 2: write_entities re-renders the page body from template (wiping the
    # injected File map); the snapshot+merge must restore the filled cell.
    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    text2 = app_x_page.read_text(encoding="utf-8")
    assert "| `src/app_x/__init__.py` | file | the app entrypoint |" in text2, (
        f"filled description was wiped on rescan; page:\n{text2}"
    )
    # The un-filled row remains a — TODO placeholder.
    assert "| `pyproject.toml` | file | — TODO |" in text2


@pytest.mark.asyncio
async def test_description_fill_log_uses_entity_noun(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c log wording: the `file descriptions filled` line must read
    `entity(s)`, not `package(s)`, now that apps share the path. Asserts against
    the real log.md (append_log is unpatched in this module).
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
        },
    ]
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Step 10b now sources file-map text via build_file_map(repo / node.path).
    # No real git repo in this fixture — mock returns the expected block for app-x.
    monkeypatch.setattr(
        scan_module,
        "build_file_map",
        lambda path, **kw: app_x_block if str(path).endswith("app-x") else None,
    )

    from subagent_runtime.pool import FanOutResult

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                _uri, _ws, _page, todo_paths = it
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    log_text = (wiki / "log.md").read_text(encoding="utf-8")
    assert "file descriptions filled:" in log_text, (
        f"description-fill log line missing; log:\n{log_text}"
    )
    fill_line = next(
        line for line in log_text.splitlines() if "file descriptions filled:" in line
    )
    assert "entity(s)" in fill_line, f"expected 'entity(s)' noun; got: {fill_line!r}"
    assert "package(s)" not in fill_line, f"stale 'package(s)' noun; got: {fill_line!r}"


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


def _seed_test_suite_graph(db_path: Path) -> None:
    """Seed a minimal DB with one test_suite node owned by pkg-a.

    Layout:
      test_suite node: name 'pkg-a-unit-tests', path 'packages/pkg-a/tests',
        uri 'test_suite:org/repo/pkg-a/tests', attrs {suite_kind: unit,
        path: packages/pkg-a/tests, language: python}
    """
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('test_suite', 'pkg-a-unit-tests', 'packages/pkg-a/tests', NULL, "
            "'{\"suite_kind\": \"unit\", \"path\": \"packages/pkg-a/tests\", \"language\": \"python\"}', "
            "'test_suite:org/repo/pkg-a/tests')"
        )
        conn.commit()
    finally:
        conn.close()


def test_entity_page_path_suite_aware_slug():
    """Module-level _entity_page_path applies the suite-aware slug for
    test_suite kinds (suite_kind + pkg_for_suite derived from attrs['path'])."""
    from types import SimpleNamespace

    wiki = Path("/fake/wiki")
    node = SimpleNamespace(
        kind="test_suite",
        name="pkg-a-unit-tests",
        attrs={
            "uri": "test_suite:org/repo/pkg-a/tests",
            "suite_kind": "unit",
            "path": "packages/pkg-a/tests",
        },
    )
    page = scan_module._entity_page_path(
        wiki, "test_suite", node, "test_suite:org/repo/pkg-a/tests", frozenset()
    )
    assert page == wiki / "entities" / "unit_tests_pkg-a.md"

    # A package node uses the plain kind prefix (no suite logic).
    pkg_node = SimpleNamespace(
        kind="package", name="pkg-a", attrs={"uri": "pkg:org/repo/pkg-a"}
    )
    pkg_page = scan_module._entity_page_path(
        wiki, "package", pkg_node, "pkg:org/repo/pkg-a", frozenset()
    )
    assert pkg_page == wiki / "entities" / "pkg_pkg-a.md"


@pytest.mark.asyncio
async def test_file_map_injected_into_test_suite_entity_page(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10b-ts: after write_entities creates a test_suite entity page,
    run_scan replaces its `## File map` section with the deterministic
    build_dir_file_map block rooted at the suite path (path + kind rows)."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_test_suite_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Deterministic suite block as build_dir_file_map would emit it. The heading
    # label is the suite-root basename ("tests").
    suite_block = (
        "## File map - tests\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### tests/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `conftest.py` | file | — TODO |\n"
        "| `test_pkg_a.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(
        scan_module, "build_dir_file_map", lambda *a, **kw: suite_block
    )
    # No package/app workspaces — only the seeded test_suite drives this scan.
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    result = await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    # The test_suite page was created this scan → file map injected.
    assert "test_suite:org/repo/pkg-a/tests" in result.entities_created

    suite_page = wiki / "entities" / "unit_tests_pkg-a.md"
    assert suite_page.exists(), f"suite page not written; entities: {list((wiki / 'entities').glob('*.md'))}"
    text = suite_page.read_text(encoding="utf-8")

    assert "## File map - tests" in text
    assert "| `conftest.py` | file | — TODO |" in text
    assert "| `test_pkg_a.py` | file | — TODO |" in text
    # The template's placeholder file row is gone.
    assert "| `<file>` | file | — TODO |" not in text
    # Neighboring template sections survive injection.
    assert "## Test conventions" in text


@pytest.mark.asyncio
async def test_code_reader_fills_test_suite_todo_descriptions(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c: after the suite File map is injected with — TODO rows, the
    code_reader fan-out fills the Description cells from the model's
    {path: description} JSON. Proves the synthesized test_suite describer dict
    routes the suite into the describer pool."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_test_suite_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    suite_block = (
        "## File map - tests\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### tests/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `conftest.py` | file | — TODO |\n"
        "| `test_pkg_a.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(scan_module, "build_dir_file_map", lambda *a, **kw: suite_block)
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    from subagent_runtime.pool import FanOutResult

    captured_paths: dict = {}

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                uri_inner, ws_dict, _page, todo_paths = it
                captured_paths[uri_inner] = (ws_dict, list(todo_paths))
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    # The suite was routed into the code_reader pool with a synthesized dict.
    suite_uri = "test_suite:org/repo/pkg-a/tests"
    assert suite_uri in captured_paths, f"suite not dispatched to describer; got {captured_paths}"
    ws_dict, todo = captured_paths[suite_uri]
    assert ws_dict["type"] == "test_suite"
    assert ws_dict["path"] == "packages/pkg-a/tests"
    assert ws_dict["language"] == "python"
    assert set(todo) == {"conftest.py", "test_pkg_a.py"}

    text = (wiki / "entities" / "unit_tests_pkg-a.md").read_text(encoding="utf-8")
    assert "| `conftest.py` | file | desc for conftest.py |" in text
    assert "| `test_pkg_a.py` | file | desc for test_pkg_a.py |" in text
    assert "— TODO" not in text
    assert "## Coverage" in text


@pytest.mark.asyncio
async def test_test_suite_file_map_descriptions_survive_rescan(
    tmp_workspace_with_packages, monkeypatch
):
    """Durability: descriptions filled into a suite's File map survive a rescan
    (write_entities re-renders the body; snapshot+merge restores them). A fully
    described suite triggers NO code_reader call on the second scan."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_test_suite_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    suite_block = (
        "## File map - tests\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### tests/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `conftest.py` | file | — TODO |\n"
        "| `test_pkg_a.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(scan_module, "build_dir_file_map", lambda *a, **kw: suite_block)
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    from subagent_runtime.pool import FanOutResult

    code_reader_dispatches: list[list] = []

    async def _recording_run_all(self, *, items, task, role, model_id, max_concurrency):
        if role == "code_reader":
            code_reader_dispatches.append([it[0] for it in items])
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _recording_run_all)

    # Scan 1: suite page created, File map injected with — TODO rows.
    await scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)
    suite_page = wiki / "entities" / "unit_tests_pkg-a.md"
    assert suite_page.exists()

    # Injection actually landed the TODO rows before the human edit (guards
    # against a vacuous pass if injection ever silently no-ops).
    text1 = suite_page.read_text(encoding="utf-8")
    assert "| `conftest.py` | file | — TODO |" in text1
    assert "| `test_pkg_a.py` | file | — TODO |" in text1

    # Human fills BOTH descriptions.
    filled = text1.replace(
        "| `conftest.py` | file | — TODO |",
        "| `conftest.py` | file | shared pytest fixtures |",
    ).replace(
        "| `test_pkg_a.py` | file | — TODO |",
        "| `test_pkg_a.py` | file | unit tests for pkg-a |",
    )
    suite_page.write_text(filled, encoding="utf-8")

    code_reader_dispatches.clear()

    # Scan 2: write_entities re-renders the body; snapshot+merge must restore both.
    await scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)

    text2 = suite_page.read_text(encoding="utf-8")
    assert "| `conftest.py` | file | shared pytest fixtures |" in text2, (
        f"filled description wiped on rescan; page:\n{text2}"
    )
    assert "| `test_pkg_a.py` | file | unit tests for pkg-a |" in text2, (
        f"filled description wiped on rescan; page:\n{text2}"
    )
    assert "— TODO" not in text2

    # A fully-described suite has no TODO paths → no code_reader dispatch at all.
    flat = [uri for batch in code_reader_dispatches for uri in batch]
    assert "test_suite:org/repo/pkg-a/tests" not in flat, (
        f"fully-described suite should trigger no describer call; dispatches={code_reader_dispatches}"
    )

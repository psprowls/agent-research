"""Phase 43 integration tests — wave-1 ingestion + wave-2 entity writing round-trip.

These tests build a real workspace fixture (`tmp_path`), invoke graph-io's
ingestion pipeline against it, then invoke wiki-io's `write_entities` and
assert the on-disk state. Unlike the unit tests in `test_entity_writer.py`
(which use `MockGraphConn`), these tests use a real `sqlite3.Connection`
+ real graph-io code.

# integration-gate-allow
These tests do NOT call any external network service (no Bedrock, no API)
— they run entirely against an in-memory sqlite + real graph-io ingestion
modules + tmp_path filesystem. They are <1s each and safe to run on every
PR. The `# integration-gate-allow` marker above opts them out of the
canonical `GRAPH_WIKI_RUN_INTEGRATION` gate (see docs/testing.md).
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import pytest

from graph_io import packages, plugins, structural_nodes
from graph_io.schema import apply_schema
from graph_io.uri import RepoContext
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    WriteLockHeldError,
    _acquire_scan_lock,
    write_entities,
)

CTX = RepoContext(org="local", repo="fixture")


def _init_git_repo(root: Path) -> None:
    """Initialize a git repo so structural_nodes._tracked_files has something to read."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=root, check=True
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture init"], cwd=root, check=True
    )


def _build_fixture_workspace(root: Path) -> None:
    """Write a small synthetic workspace under `root`:

    - pkg-a/pyproject.toml with deps [boto3>=1.38, pyyaml>=6]
    - pkg-b/pyproject.toml with deps [boto3==1.40, click>=8]
    - .graph-wiki.yaml v2 with plugins: [graph-wiki]
    - pkg-a/src/pkg_a/__init__.py + pkg-a/src/pkg_a/sub/__init__.py (subpkg test)
    """
    (root / "pkg-a" / "src" / "pkg_a" / "sub").mkdir(parents=True)
    (root / "pkg-a" / "src" / "pkg_a" / "__init__.py").write_text("")
    (root / "pkg-a" / "src" / "pkg_a" / "sub" / "__init__.py").write_text("")
    (root / "pkg-a" / "pyproject.toml").write_text(
        '[project]\n'
        'name = "pkg-a"\n'
        'version = "0.1.0"\n'
        'dependencies = ["boto3>=1.38", "pyyaml>=6"]\n'
    )
    (root / "pkg-b").mkdir(parents=True)
    (root / "pkg-b" / "pyproject.toml").write_text(
        '[project]\n'
        'name = "pkg-b"\n'
        'version = "0.1.0"\n'
        'dependencies = ["boto3==1.40", "click>=8"]\n'
    )
    (root / ".graph-wiki.yaml").write_text(
        'version: 2\n'
        'initialized_at: "2026-05-26"\n'
        'plugins:\n'
        '  - name: graph-wiki\n'
        '    installed_version: "0.1.0"\n'
        '    applied_version: "0.1.0"\n'
    )


def _ingest(workspace: Path) -> sqlite3.Connection:
    """Build an in-memory graph from the fixture workspace."""
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    packages.refresh(conn, repo_root=workspace, ctx=CTX)
    structural_nodes.emit(
        conn, repo_root=workspace, ctx=CTX, skip_dirs=frozenset()
    )
    plugins.emit(conn, workspace_root=workspace, ctx=CTX)
    return conn


def test_write_entities_round_trip_on_synthetic_workspace(tmp_path):
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"
    result = write_entities(conn, wiki_root, ADMITTED_KINDS)

    # Expected pages: 1 repo + 2 packages + 3 unique deps (boto3, pyyaml, click) + 1 plugin = 7
    assert len(result.created) >= 7, (
        f"expected >=7 created, got {len(result.created)}: {result.created}"
    )
    assert result.errors == [], f"unexpected errors: {result.errors}"
    assert result.needs_narrative == set(result.created)

    entities = wiki_root / "entities"
    # Phase 52: short-form filenames via `short_filename`.
    assert (entities / "pkg_pkg-a.md").exists()
    assert (entities / "pkg_pkg-b.md").exists()
    assert (entities / "dep_boto3.md").exists()
    assert (entities / "plugin_graph-wiki.md").exists()
    assert (entities / "repo_fixture.md").exists()


def test_status_deprecated_preserved_after_rewrite(tmp_path):
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"
    write_entities(conn, wiki_root, ADMITTED_KINDS)
    pkg_a_path = wiki_root / "entities" / "pkg_pkg-a.md"
    raw = pkg_a_path.read_text()
    raw_new = raw.replace("kind: package\n", "kind: package\nstatus: deprecated\n", 1)
    pkg_a_path.write_text(raw_new)
    write_entities(conn, wiki_root, ADMITTED_KINDS)
    final = pkg_a_path.read_text()
    assert "status: deprecated" in final


def test_hard_delete_logs_to_deletions_log(tmp_path):
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"
    write_entities(conn, wiki_root, ADMITTED_KINDS)
    pkg_a_path = wiki_root / "entities" / "pkg_pkg-a.md"
    assert pkg_a_path.exists()

    # Remove pkg-a from the graph: delete its edges, then its node.
    conn.execute(
        "DELETE FROM edges WHERE src IN ("
        "  SELECT id FROM nodes WHERE kind='package' AND name='pkg-a'"
        ") OR dst IN ("
        "  SELECT id FROM nodes WHERE kind='package' AND name='pkg-a'"
        ")"
    )
    conn.execute(
        "DELETE FROM nodes WHERE kind='package' AND name='pkg-a'"
    )

    result = write_entities(conn, wiki_root, ADMITTED_KINDS)
    assert any("pkg-a" in uri for uri in result.deleted)
    assert not pkg_a_path.exists()
    log_path = tmp_path / ".graph-wiki" / "deletions.log"
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    pkg_a_entries = [json.loads(line) for line in lines if "pkg-a" in line]
    assert len(pkg_a_entries) == 1
    entry = pkg_a_entries[0]
    for field in ("timestamp", "uri", "slug", "path", "kind", "body_was_empty"):
        assert field in entry, f"missing field {field} in {entry}"
    assert entry["kind"] == "package"
    assert entry["slug"] == "pkg_pkg-a"
    assert entry["path"].endswith("pkg_pkg-a.md")
    assert entry["timestamp"].endswith("Z")
    assert "T" in entry["timestamp"]


def test_scan_lock_blocks_concurrent_writes(tmp_path):
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"

    holder_ready = threading.Event()
    release = threading.Event()

    def holder():
        with _acquire_scan_lock(tmp_path):
            holder_ready.set()
            release.wait(timeout=10.0)

    t = threading.Thread(target=holder)
    t.start()
    try:
        assert holder_ready.wait(timeout=2.0)
        start = time.time()
        with pytest.raises(WriteLockHeldError):
            write_entities(conn, wiki_root, ADMITTED_KINDS)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"LOCK_NB should fail fast; took {elapsed:.3f}s"
    finally:
        release.set()
        t.join(timeout=5.0)


def test_determinism_second_run_all_unchanged(tmp_path):
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"
    r1 = write_entities(conn, wiki_root, ADMITTED_KINDS)
    r2 = write_entities(conn, wiki_root, ADMITTED_KINDS)
    assert r2.created == []
    assert r2.updated == []
    assert r2.deleted == []
    assert len(r2.unchanged) == len(r1.created)


def test_needs_narrative_round_trip(tmp_path):
    """needs_narrative populated on create (run 1) and empty on no-op (run 2)."""
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"
    r1 = write_entities(conn, wiki_root, ADMITTED_KINDS)
    assert len(r1.needs_narrative) >= 7
    r2 = write_entities(conn, wiki_root, ADMITTED_KINDS)
    assert r2.needs_narrative == set()

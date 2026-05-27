"""Plugin ingestion: .graph-wiki.yaml plugins[] -> kind:plugin nodes (Phase 43 D-03)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from graph_io import plugins, store
from graph_io.uri import RepoContext


_CTX = RepoContext(org="test", repo="repo")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def test_plugins_emit_handles_missing_manifest(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """No `.graph-wiki.yaml` present -> emit returns silently; graph has zero plugin nodes."""
    plugins.emit(conn, workspace_root=tmp_path, ctx=_CTX)
    count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='plugin'").fetchone()[0]
    assert count == 0


def test_plugins_emit_handles_empty_plugins(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """`.graph-wiki.yaml` with empty plugins: [] -> zero plugin nodes."""
    (tmp_path / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: '2026-05-26'\nplugins: []\n"
    )
    plugins.emit(conn, workspace_root=tmp_path, ctx=_CTX)
    count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='plugin'").fetchone()[0]
    assert count == 0


def test_plugin_ingestion_from_manifest(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """A populated plugins: list emits one node per entry with the expected attrs."""
    (tmp_path / ".graph-wiki.yaml").write_text(
        "version: 2\n"
        "initialized_at: '2026-05-26'\n"
        "plugins:\n"
        "  - name: graph-wiki\n"
        "    installed_version: '0.1.0'\n"
        "    applied_version: '0.1.0'\n"
    )
    plugins.emit(conn, workspace_root=tmp_path, ctx=_CTX)
    rows = conn.execute(
        "SELECT name, attrs_json, uri FROM nodes WHERE kind='plugin'"
    ).fetchall()
    assert len(rows) == 1
    name, attrs_json, uri = rows[0]
    attrs = json.loads(attrs_json)
    assert name == "graph-wiki"
    assert uri == "plugin:graph-wiki"
    assert attrs["ecosystem"] == "claude-code"
    assert attrs["installed_version"] == "0.1.0"
    assert attrs["applied_version"] == "0.1.0"


def test_plugin_emit_skips_entries_without_name(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """Entries lacking `name` are skipped silently; only valid entries land in the graph."""
    (tmp_path / ".graph-wiki.yaml").write_text(
        "version: 2\n"
        "initialized_at: '2026-05-26'\n"
        "plugins:\n"
        "  - name: foo\n"
        "  - installed_version: 'x'\n"
    )
    plugins.emit(conn, workspace_root=tmp_path, ctx=_CTX)
    rows = conn.execute(
        "SELECT name FROM nodes WHERE kind='plugin' ORDER BY name"
    ).fetchall()
    assert [r[0] for r in rows] == ["foo"]


def test_plugin_emit_has_no_inbound_edges(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """D-03 invariant: plugin nodes have NO inbound used_by edges from packages."""
    (tmp_path / ".graph-wiki.yaml").write_text(
        "version: 2\n"
        "initialized_at: '2026-05-26'\n"
        "plugins:\n"
        "  - name: graph-wiki\n"
        "    installed_version: '0.1.0'\n"
        "    applied_version: '0.1.0'\n"
    )
    plugins.emit(conn, workspace_root=tmp_path, ctx=_CTX)
    inbound = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes p ON e.dst = p.id "
        "WHERE p.kind='plugin'"
    ).fetchone()[0]
    assert inbound == 0

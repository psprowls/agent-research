"""Tests for run_export in graph_wiki_core.commands.graph."""

from __future__ import annotations

from pathlib import Path

from graph_io import store
from graph_wiki_core.commands.graph import run_export
from workspace_io.paths import graph_dir


def _seeded_workspace(tmp_path: Path) -> Path:
    """Create a minimal initialized workspace with one node and one edge."""
    db_path = graph_dir(tmp_path) / "code.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = store.connect(db_path, create=True)
    with conn:
        cur = conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
            ("file", "a.py", "a.py", None, None, "file:a.py"),
        )
        a = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
            ("file", "b.py", "b.py", None, None, "file:b.py"),
        )
        b = cur.lastrowid
        conn.execute(
            "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?,?,?,?)",
            (a, b, "imports", None),
        )
    conn.close()
    return tmp_path


def test_run_export_writes_file(tmp_path: Path) -> None:
    workspace = _seeded_workspace(tmp_path)
    out_path = tmp_path / "out.graphml"
    exit_code, stdout, stderr = run_export(workspace, out_path)
    assert exit_code == 0
    assert stderr == ""
    assert "wrote 2 nodes, 1 edges" in stdout
    assert str(out_path) in stdout
    assert out_path.exists()
    content = out_path.read_text()
    assert "graphml" in content
    assert "directed" in content


def test_run_export_stdout_mode(tmp_path: Path) -> None:
    workspace = _seeded_workspace(tmp_path)
    exit_code, stdout, stderr = run_export(workspace, Path("-"))
    assert exit_code == 0
    assert "graphml" in stdout
    assert "directed" in stdout
    # No file written when out_path is "-"
    assert not (tmp_path / "graph.graphml").exists()


def test_run_export_default_path(tmp_path: Path) -> None:
    workspace = _seeded_workspace(tmp_path)
    default_out = graph_dir(workspace) / "graph.graphml"
    exit_code, stdout, stderr = run_export(workspace, default_out)
    assert exit_code == 0
    assert default_out.exists()


def test_run_export_not_initialized(tmp_path: Path) -> None:
    from graph_io import exit_codes

    # No DB at all → NOT_INITIALIZED
    exit_code, stdout, stderr = run_export(tmp_path, tmp_path / "out.graphml")
    assert exit_code == exit_codes.NOT_INITIALIZED
    assert stdout == ""
    assert "error:" in stderr

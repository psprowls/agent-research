"""Tests for gw graph suggest-resources (architecture-resource-nodes Phase 2)."""

from __future__ import annotations

from pathlib import Path

from graph_io import packages, store
from graph_io.uri import RepoContext
from graph_wiki_core.commands.suggest_resources import compute_and_write
from workspace_io.paths import graph_dir

CTX = RepoContext(org="testorg", repo="testrepo")

_MANIFEST = (
    "version: 2\n"
    "initialized_at: '2026-06-20'\n"
    "graph:\n"
    "  resources:\n"
    "    aws:\n"  # already declared → must be EXCLUDED from suggestions
    "      resource_kind: cloud_service\n"
    "  resource_matchers:\n"
    "    - name: aws-already\n"
    "      when: {consumer_depends_on: boto3}\n"
    "      emit: {resource: aws, role: consumes}\n"
    "    - name: bedrock-new\n"
    "      when: {consumer_depends_on: boto3}\n"
    "      emit: {resource: bedrock, resource_kind: cloud_service, scope: external, role: consumes}\n"
)


def _build_workspace(tmp_path: Path) -> Path:
    # repo == workspace == tmp_path for the test.
    pkg_src = tmp_path / "packages" / "model-adapter" / "src" / "model_adapter"
    pkg_src.mkdir(parents=True, exist_ok=True)
    (pkg_src / "__init__.py").write_text("")
    (tmp_path / "packages" / "model-adapter" / "pyproject.toml").write_text(
        '[project]\nname = "model-adapter"\nversion = "0.0.0"\nrequires-python = ">=3.11"\n'
        '[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    )
    db_path = graph_dir(tmp_path) / "code.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = store.connect(db_path, create=True)
    with store.transaction(conn):
        packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    # Insert a dependency 'boto3' + used_by edge from model-adapter.
    with conn:
        cur = conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
            ("dependency", "boto3", None, None, None, "dependency:pypi/boto3"),
        )
        dep_id = cur.lastrowid
        pkg_id = conn.execute("SELECT id FROM nodes WHERE kind='package' AND name='model-adapter'").fetchone()[0]
        conn.execute(
            "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?,?,?,?)", (pkg_id, dep_id, "used_by", None)
        )
    conn.close()
    (tmp_path / ".graph-wiki.yaml").write_text(_MANIFEST, encoding="utf-8")
    return tmp_path


def test_compute_and_write_excludes_declared(tmp_path: Path) -> None:
    workspace = _build_workspace(tmp_path)
    out_path, n = compute_and_write(workspace)
    assert out_path == graph_dir(workspace) / "resources.proposed.yaml"
    assert out_path.exists()
    text = out_path.read_text()
    # 'bedrock' is new → suggested; 'aws' is already declared → excluded.
    assert "bedrock" in text
    assert "graph:" in text and "resources:" in text
    assert n == 1


def test_no_new_suggestions_writes_note(tmp_path: Path) -> None:
    # Only the already-declared 'aws' rule → nothing new.
    workspace = _build_workspace(tmp_path)
    manifest_no_new = _MANIFEST.replace(
        "    - name: bedrock-new\n"
        "      when: {consumer_depends_on: boto3}\n"
        "      emit: {resource: bedrock, resource_kind: cloud_service, scope: external, role: consumes}\n",
        "",
    )
    (workspace / ".graph-wiki.yaml").write_text(manifest_no_new, encoding="utf-8")
    out_path, n = compute_and_write(workspace)
    assert n == 0
    assert "no new resources suggested" in out_path.read_text()

"""Tests for gw graph suggest-resources (architecture-resource-nodes Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from graph_io import packages, store
from graph_io.store import GraphNotInitializedError
from graph_io.uri import RepoContext
from graph_wiki_core.commands import suggest_resources as suggest_resources_mod
from graph_wiki_core.commands.suggest_resources import compute_and_write
from workspace_io.paths import graph_dir

CTX = RepoContext(org="testorg", repo="testrepo")

_MANIFEST = (
    "version: 2\n"
    "initialized_at: '2026-06-20'\n"
    "graph:\n"
    "  resources:\n"
    "    declared-svc:\n"  # already declared → must be EXCLUDED
    "      resource_kind: service\n"
    "  resource_matchers:\n"
    "    - name: boto3-consumers\n"
    "      when: {depends_on: boto3}\n"
    "      capture: {from: literal}\n"
    "      emit: {kind: service, subtype: aws, role: consumes}\n"
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
    text = out_path.read_text()
    assert "declared-svc" not in text  # already declared → excluded
    assert "graph:" in text and "resources:" in text
    assert n == 1


def test_provider_and_consumer_coalesce(tmp_path: Path) -> None:
    workspace = _build_workspace(tmp_path)
    # Two rules both named 'device' (literal capture → rule name), same kind queue:
    # one provides, one consumes → coalesce into ONE entry carrying both edges.
    manifest = (
        "version: 2\n"
        "initialized_at: '2026-06-20'\n"
        "graph:\n"
        "  resource_matchers:\n"
        "    - name: device\n"
        "      when: {depends_on: boto3}\n"
        "      capture: {from: literal}\n"
        "      emit: {kind: queue, role: provides}\n"
        "    - name: device\n"
        "      when: {depends_on: boto3}\n"
        "      capture: {from: literal}\n"
        "      emit: {kind: queue, role: consumes}\n"
    )
    (workspace / ".graph-wiki.yaml").write_text(manifest, encoding="utf-8")
    out_path, n = compute_and_write(workspace)
    body = out_path.read_text()
    assert n == 1
    assert "device:" in body and "provided_by:" in body and "consumed_by:" in body


def test_subtype_emitted(tmp_path: Path) -> None:
    workspace = _build_workspace(tmp_path)
    out_path, n = compute_and_write(workspace)  # uses _MANIFEST: subtype aws
    assert "subtype: aws" in out_path.read_text()


def test_invalid_rule_exits_2_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    workspace = _build_workspace(tmp_path)
    bad_manifest = (
        "version: 2\n"
        "initialized_at: '2026-06-20'\n"
        "graph:\n"
        "  resource_matchers:\n"
        "    - name: bad\n"
        "      when: {depends_on: boto3}\n"
        "      capture: {from: literal}\n"
        "      emit: {kind: nope, role: consumes}\n"  # unknown kind
    )
    (workspace / ".graph-wiki.yaml").write_text(bad_manifest, encoding="utf-8")
    out_path = graph_dir(workspace) / "resources.proposed.yaml"
    if out_path.exists():
        out_path.unlink()
    monkeypatch.setattr(suggest_resources_mod, "_resolve_paths", lambda _ws: (workspace, workspace))
    with pytest.raises(typer.Exit) as excinfo:
        suggest_resources_mod.suggest_resources_cmd(workspace=str(workspace))
    assert excinfo.value.exit_code == 2
    assert not out_path.exists()  # nothing written on invalid rules


def test_cmd_exits_2_when_graph_not_initialized(tmp_path: Path, monkeypatch) -> None:
    # Mirrors propose_domains: an uninitialized graph DB yields a clean exit 2,
    # not a raw GraphNotInitializedError traceback.
    monkeypatch.setattr(suggest_resources_mod, "_resolve_paths", lambda _ws: (tmp_path, tmp_path))

    def _raise(_workspace_root: Path):
        raise GraphNotInitializedError("graph DB not found")

    monkeypatch.setattr(suggest_resources_mod, "compute_and_write", _raise)
    with pytest.raises(typer.Exit) as excinfo:
        suggest_resources_mod.suggest_resources_cmd(workspace=str(tmp_path))
    assert excinfo.value.exit_code == 2

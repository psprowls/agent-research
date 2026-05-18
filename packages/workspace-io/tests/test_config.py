"""Tests for workspace_io.config — workspace resolution."""
import subprocess
import sys
from pathlib import Path

import pytest

from workspace_io.config import GraphWikiConfig, resolve


def _make_repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    return root


def _seed_manifest(workspace: Path) -> None:
    """Write a minimal v2 .graph-wiki.yaml so resolve()'s strict check passes (D-03)."""
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: 2026-05-17\nplugins: []\n",
        encoding="utf-8",
    )


def test_no_local_yaml_falls_back_to_repo_graph_wiki(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    _seed_manifest(repo / "graph-wiki")
    cfg = resolve(repo)
    assert cfg.repo_root == repo.resolve()
    assert cfg.workspace == (repo / "graph-wiki").resolve()


def test_local_yaml_present_but_key_missing_falls_back(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    (repo / ".graph-wiki.local.yaml").write_text("future-key: value\n")
    _seed_manifest(repo / "graph-wiki")
    cfg = resolve(repo)
    assert cfg.workspace == (repo / "graph-wiki").resolve()


def test_local_yaml_with_absolute_path(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _seed_manifest(elsewhere)
    (repo / ".graph-wiki.local.yaml").write_text(f"graph-wiki-directory: {elsewhere}\n")
    cfg = resolve(repo)
    assert cfg.workspace == elsewhere.resolve()


def test_local_yaml_with_relative_path(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    _seed_manifest(repo.parent / "sidecar")
    (repo / ".graph-wiki.local.yaml").write_text("graph-wiki-directory: ../sidecar\n")
    cfg = resolve(repo)
    assert cfg.workspace == (repo.parent / "sidecar").resolve()


def test_local_yaml_with_tilde_expansion(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    repo = _make_repo(tmp_path / "repo")
    _seed_manifest(fake_home / "graph-wiki" / "myproject")
    (repo / ".graph-wiki.local.yaml").write_text("graph-wiki-directory: ~/graph-wiki/myproject\n")
    cfg = resolve(repo)
    assert cfg.workspace == (fake_home / "graph-wiki" / "myproject").resolve()


def test_walks_up_to_find_git(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    _seed_manifest(repo / "graph-wiki")
    nested = repo / "a" / "b" / "c"
    nested.mkdir(parents=True)
    cfg = resolve(nested)
    assert cfg.repo_root == repo.resolve()
    assert cfg.workspace == (repo / "graph-wiki").resolve()


def test_no_git_found_uses_cwd_as_repo_root(tmp_path, monkeypatch):
    # Patch _find_repo_root so the test doesn't depend on whether TMPDIR
    # happens to be inside a git repo on the host machine.
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    monkeypatch.setattr("workspace_io.config._find_repo_root", lambda _: None)
    _seed_manifest(tmp_path / "graph-wiki")
    cfg = resolve(tmp_path)
    assert cfg.repo_root == tmp_path.resolve()
    assert cfg.workspace == (tmp_path / "graph-wiki").resolve()


def test_resolve_with_no_arg_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    _seed_manifest(repo / "graph-wiki")
    monkeypatch.chdir(repo)
    cfg = resolve()
    assert cfg.repo_root == repo.resolve()


def test_cli_prints_workspace_to_stdout(tmp_path):
    repo = _make_repo(tmp_path)
    _seed_manifest(repo / "graph-wiki")
    result = subprocess.run(
        [sys.executable, "-m", "workspace_io.config"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str((repo / "graph-wiki").resolve())


def test_resolve_raises_when_no_manifest_found(tmp_path, monkeypatch):
    """D-03: strict — resolve() raises RuntimeError naming code-wiki-agent init."""
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    repo = _make_repo(tmp_path)
    with pytest.raises(RuntimeError, match="code-wiki-agent init"):
        resolve(repo)

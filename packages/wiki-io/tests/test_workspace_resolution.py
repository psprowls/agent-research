"""Tests for wiki_io._workspace.resolve_wiki_and_repo — explicit-workspace branch.

Covers:
  1. With explicit workspace_path + repo-directory: pin in manifest → returns pinned repo
  2. With explicit workspace_path + no pin → returns cwd-discovered repo
  3. Explicit repo_path arg overrides the pin (explicit arg wins over manifest)
  4. repo-directory: with ~ expansion is honored
"""
from __future__ import annotations

from pathlib import Path

import pytest

from wiki_io._workspace import resolve_wiki_and_repo


def _seed_manifest_with(workspace: Path, extra_lines: str = "") -> None:
    """Write a minimal v2 .graph-wiki.yaml, optionally appending extra_lines."""
    workspace.mkdir(parents=True, exist_ok=True)
    content = "version: 2\ninitialized_at: 2026-05-30\nplugins: []\n" + extra_lines
    (workspace / ".graph-wiki.yaml").write_text(content, encoding="utf-8")


def _make_fake_repo(path: Path) -> Path:
    """Create a directory that looks like a git repo (has .git)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()
    return path


# ---------------------------------------------------------------------------
# Test 1: explicit workspace with repo-directory: pin → returns pinned repo
# ---------------------------------------------------------------------------


def test_explicit_workspace_honors_repo_directory_pin(tmp_path, monkeypatch):
    """With workspace_path + repo-directory: pin, returns the pinned repo_root (not workspace)."""
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)

    workspace = tmp_path / "wiki-vault"
    _make_fake_repo(workspace)  # workspace has its own .git (the repo≠workspace layout)

    source_repo = tmp_path / "source-code"
    _make_fake_repo(source_repo)

    _seed_manifest_with(workspace, f"repo-directory: {source_repo}\n")

    # Monkeypatch _find_repo_root so test doesn't depend on host's git layout.
    # Without the fix, this branch ignores the pin and returns cwd repo (workspace.git).
    fake_cwd_repo = tmp_path / "cwd-repo"
    _make_fake_repo(fake_cwd_repo)
    monkeypatch.setattr("wiki_io._workspace._find_repo_root", lambda _: fake_cwd_repo)

    wiki, repo = resolve_wiki_and_repo(workspace_path=workspace)

    # The pin must win over cwd discovery
    assert repo == source_repo.resolve()
    assert wiki == workspace / "wiki"


# ---------------------------------------------------------------------------
# Test 2: explicit workspace without pin → returns cwd-discovered repo
# ---------------------------------------------------------------------------


def test_explicit_workspace_no_pin_uses_cwd_repo(tmp_path, monkeypatch):
    """With workspace_path + no repo-directory: pin, returns cwd-discovered repo."""
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)

    workspace = tmp_path / "wiki-vault"
    workspace.mkdir(parents=True, exist_ok=True)
    _seed_manifest_with(workspace)  # no repo-directory: key

    fake_cwd_repo = tmp_path / "cwd-repo"
    _make_fake_repo(fake_cwd_repo)
    monkeypatch.setattr("wiki_io._workspace._find_repo_root", lambda _: fake_cwd_repo)

    wiki, repo = resolve_wiki_and_repo(workspace_path=workspace)

    assert repo == fake_cwd_repo
    assert wiki == workspace / "wiki"


# ---------------------------------------------------------------------------
# Test 3: explicit repo_path arg overrides pin
# ---------------------------------------------------------------------------


def test_explicit_repo_path_overrides_pin(tmp_path, monkeypatch):
    """When repo_path is explicitly passed, it wins over any repo-directory: pin."""
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)

    workspace = tmp_path / "wiki-vault"
    _make_fake_repo(workspace)

    source_repo = tmp_path / "source-code"
    _make_fake_repo(source_repo)

    explicit_repo = tmp_path / "explicit-repo"
    _make_fake_repo(explicit_repo)

    _seed_manifest_with(workspace, f"repo-directory: {source_repo}\n")

    monkeypatch.setattr("wiki_io._workspace._find_repo_root", lambda _: tmp_path / "cwd-repo")

    wiki, repo = resolve_wiki_and_repo(workspace_path=workspace, repo_path=explicit_repo)

    # Explicit repo_path wins over the pin
    assert repo == explicit_repo
    assert wiki == workspace / "wiki"


# ---------------------------------------------------------------------------
# Test 4: repo-directory: with ~ expands correctly
# ---------------------------------------------------------------------------


def test_explicit_workspace_tilde_pin_expands(tmp_path, monkeypatch):
    """repo-directory: ~/source-code expands via ~ (HOME is controlled)."""
    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    workspace = tmp_path / "wiki-vault"
    _make_fake_repo(workspace)

    source_repo = fake_home / "source-code"
    _make_fake_repo(source_repo)

    _seed_manifest_with(workspace, "repo-directory: ~/source-code\n")

    monkeypatch.setattr("wiki_io._workspace._find_repo_root", lambda _: tmp_path / "cwd-repo")

    wiki, repo = resolve_wiki_and_repo(workspace_path=workspace)

    assert repo == source_repo.resolve()
    assert wiki == workspace / "wiki"

"""Tests for wiki_io.git_state.short_commit (Item 1 — short commit hashes)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from wiki_io.git_state import head_commit, is_ancestor, is_clean_on_branches, short_commit


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> str:
    """Init a one-commit git repo; return its full HEAD SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    full = head_commit(repo)
    assert full is not None and len(full) == 40
    return full


def test_short_commit_returns_resolvable_prefix(tmp_path):
    repo = tmp_path / "repo"
    full = _init_repo(repo)
    short = short_commit(repo, full)
    assert short != full
    assert len(short) < 40
    assert full.startswith(short)
    # git still resolves the short form back to the full SHA
    out = subprocess.run(["git", "rev-parse", short], cwd=repo, capture_output=True, text=True)
    assert out.stdout.strip() == full


def test_short_commit_bogus_sha_returns_input(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert short_commit(repo, "deadbeefdeadbeef") == "deadbeefdeadbeef"


def test_short_commit_non_git_dir_returns_input(tmp_path):
    non_repo = tmp_path / "plain"
    non_repo.mkdir()
    sha = "a" * 40
    assert short_commit(non_repo, sha) == sha


def _init_repo_on_branch(repo: Path, branch: str) -> None:
    """Init a one-commit git repo with HEAD on `branch` (clean tree)."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")
    _git(repo, "branch", "-M", branch)


def test_is_clean_on_branches_allowed_branch_clean(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    assert is_clean_on_branches(repo, ["main", "develop"]) == (True, "")


def test_is_clean_on_branches_matches_non_first_entry(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "develop")
    assert is_clean_on_branches(repo, ["main", "develop"]) == (True, "")


def test_is_clean_on_branches_branch_not_listed(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "feature-x")
    ok, reason = is_clean_on_branches(repo, ["main"])
    assert ok is False
    assert "not in" in reason
    assert "feature-x" in reason


def test_is_clean_on_branches_dirty_tree(tmp_path):
    repo = tmp_path / "repo"
    _init_repo_on_branch(repo, "main")
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    assert is_clean_on_branches(repo, ["main"]) == (False, "working tree is dirty")


def test_is_clean_on_branches_non_git_dir(tmp_path):
    non_repo = tmp_path / "plain"
    non_repo.mkdir()
    ok, reason = is_clean_on_branches(non_repo, ["main"])
    assert ok is False
    assert reason == "not a git repo"


def _commit_file(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", name)


def test_is_ancestor_straight_line_history(tmp_path):
    repo = tmp_path / "repo"
    first = _init_repo(repo)
    _commit_file(repo, "g.txt", "second\n")
    second = head_commit(repo)
    assert is_ancestor(repo, first, second) is True
    assert is_ancestor(repo, second, first) is False


def test_is_ancestor_self_is_ancestor_of_self(tmp_path):
    repo = tmp_path / "repo"
    sha = _init_repo(repo)
    assert is_ancestor(repo, sha, sha) is True


def test_is_ancestor_sibling_branches_are_not_ancestors(tmp_path):
    repo = tmp_path / "repo"
    base = _init_repo(repo)
    _git(repo, "checkout", "-b", "branch-a")
    _commit_file(repo, "a.txt", "on branch a\n")
    branch_a = head_commit(repo)
    _git(repo, "checkout", "-b", "branch-b", base)
    _commit_file(repo, "b.txt", "on branch b\n")
    branch_b = head_commit(repo)
    assert is_ancestor(repo, branch_a, branch_b) is False
    assert is_ancestor(repo, branch_b, branch_a) is False


def test_is_ancestor_invalid_sha_raises(tmp_path):
    repo = tmp_path / "repo"
    sha = _init_repo(repo)
    with pytest.raises(RuntimeError):
        is_ancestor(repo, "deadbeef" * 5, sha)

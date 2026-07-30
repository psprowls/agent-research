"""Tests for wiki_io.git_state.short_commit (Item 1 — short commit hashes)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from wiki_io.git_state import (
    changed_names_since,
    diff_since,
    head_commit,
    is_ancestor,
    is_clean_on_branches,
    short_commit,
    truncate_diff,
)


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


def test_diff_since_returns_hunks_for_changed_paths(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "a.py").write_text("one\n", encoding="utf-8")
    _commit_file(repo, "pkg/a.py", "one\n")
    sha = head_commit(repo)
    (repo / "pkg" / "a.py").write_text("two\n", encoding="utf-8")
    _commit_file(repo, "pkg/a.py", "two\n")
    diff = diff_since(repo, sha, ["pkg"])
    assert diff is not None and "-one" in diff and "+two" in diff


def test_diff_since_empty_when_clean(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "f.py").write_text("x\n", encoding="utf-8")
    _commit_file(repo, "f.py", "x\n")
    sha = head_commit(repo)
    assert diff_since(repo, sha, ["f.py"]) == ""


def test_diff_since_none_on_unknown_sha_or_empty_paths(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "f.py").write_text("x\n", encoding="utf-8")
    _commit_file(repo, "f.py", "x\n")
    assert diff_since(repo, "0000000000000000000000000000000000000000", ["f.py"]) is None
    assert diff_since(repo, head_commit(repo), []) is None
    assert diff_since(repo, "", ["f.py"]) is None


def test_changed_names_since_multi_path(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a").mkdir()
    (repo / "b").mkdir()
    _commit_file(repo, "a/x.py", "1\n")
    _commit_file(repo, "b/y.py", "1\n")
    sha = head_commit(repo)
    _commit_file(repo, "a/x.py", "2\n")
    _commit_file(repo, "b/y.py", "2\n")
    assert changed_names_since(repo, sha, ["a", "b"]) == ["a/x.py", "b/y.py"]


def _fake_file_chunk(path: str, hunks: int, hunk_body: str = "+line\n") -> str:
    head = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
    return head + "".join(f"@@ -{i} +{i} @@\n{hunk_body}" for i in range(1, hunks + 1))


def test_truncate_diff_under_budget_unchanged():
    diff = _fake_file_chunk("a.py", 2)
    assert truncate_diff(diff, budget=10_000) == diff


def test_truncate_diff_cuts_at_boundary_with_tail():
    big = _fake_file_chunk("a.py", 1, hunk_body="+x\n" * 50)
    dropped = _fake_file_chunk("z.py", 1)
    diff = big + dropped
    out = truncate_diff(diff, budget=len(big) + 10)
    assert out.startswith("diff --git a/a.py")
    assert "diff --git a/z.py" not in out
    assert "(diff truncated; also changed: z.py)" in out


def test_truncate_diff_partial_file_cut_at_hunk_boundary():
    chunk = _fake_file_chunk("a.py", 4, hunk_body="+x\n" * 30)
    out = truncate_diff(chunk, budget=len(chunk) // 2)
    assert out.count("@@") < chunk.count("@@")
    assert "(diff truncated; also changed: a.py)" in out

"""Tests for wiki_io.git_state.short_commit (Item 1 — short commit hashes)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from wiki_io.git_state import head_commit, short_commit


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

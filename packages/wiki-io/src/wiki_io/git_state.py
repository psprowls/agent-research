#!/usr/bin/env python3
"""
git_state.py — Minimal git helpers for sync-state tracking.

All functions accept a Path to a directory inside a git repo and return None
when git is unavailable or the path isn't tracked. This matches the existing
pattern in scan_monorepo._git_ls_files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(repo: Path, *args: str) -> tuple[int, str, str] | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.returncode, result.stdout, result.stderr


def head_commit(repo: Path) -> str | None:
    """Return full HEAD SHA, or None if repo isn't a git checkout."""
    out = _run(repo, "rev-parse", "HEAD")
    if out is None or out[0] != 0:
        return None
    sha = out[1].strip()
    return sha or None


def is_clean_main(repo: Path) -> tuple[bool, str]:
    """Return (True, "") iff working tree is clean AND HEAD is on `main`.

    Otherwise (False, "<reason>"). Used by /graph-wiki:scan and /graph-wiki:ingest to
    decide whether to write new sync-state to vault frontmatter.
    """
    branch_out = _run(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch_out is None or branch_out[0] != 0:
        return False, "not a git repo"
    branch = branch_out[1].strip()
    if branch != "main":
        return False, f"branch is {branch!r}, not 'main'"
    status_out = _run(repo, "status", "--porcelain")
    if status_out is None or status_out[0] != 0:
        return False, "git status failed"
    if status_out[1].strip():
        return False, "working tree is dirty"
    return True, ""


def changed_files_since(repo: Path, since_sha: str, sub_path: str) -> list[str] | None:
    """Return repo-relative paths under sub_path that changed between since_sha
    and HEAD.

    - Returns [] when there are no changes.
    - Returns None when git is unavailable, the SHA is unknown, or sub_path
      isn't tracked.
    """
    if not since_sha:
        return None
    out = _run(repo, "diff", "--name-only", f"{since_sha}..HEAD", "--", sub_path)
    if out is None or out[0] != 0:
        return None
    return [line.strip() for line in out[1].splitlines() if line.strip()]

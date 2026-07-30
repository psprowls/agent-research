#!/usr/bin/env python3
"""
git_state.py — Minimal git helpers for sync-state tracking.

All functions accept a Path to a directory inside a git repo and return None
when git is unavailable or the path isn't tracked. This matches the existing
pattern in scan_monorepo._git_ls_files.
"""

from __future__ import annotations

import re
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


def short_commit(repo: Path, sha: str) -> str:
    """Abbreviate a SHA to git's canonical short form (adaptive length).

    Returns the input unchanged on any git failure — a full SHA is still
    git-resolvable, so callers never break. Mirrors the other _run-based
    helpers in this module.
    """
    out = _run(repo, "rev-parse", "--short", sha)
    if out is None or out[0] != 0 or not out[1].strip():
        return sha
    return out[1].strip()


def is_clean_on_branches(repo: Path, branches: list[str]) -> tuple[bool, str]:
    """Return (True, "") iff working tree is clean AND HEAD is on a listed branch.

    Otherwise (False, "<reason>"). Used by /graph-wiki:scan and /graph-wiki:ingest
    (via compute_state_gate) to decide whether to write new sync-state to vault
    frontmatter. `branches` is the configured allow-list from .graph-wiki.yaml.
    """
    branch_out = _run(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch_out is None or branch_out[0] != 0:
        return False, "not a git repo"
    branch = branch_out[1].strip()
    if branch not in branches:
        return False, f"branch is {branch!r}, not in {branches}"
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


def is_ancestor(repo: Path, ancestor_sha: str, descendant_sha: str) -> bool:
    """True iff ``ancestor_sha`` is a git ancestor of (or equal to)
    ``descendant_sha``, via ``git merge-base --is-ancestor``.

    Exit code 0 -> True, exit code 1 -> False (this also covers unrelated /
    diverged history, which fails open — the caller still writes a drift
    proposal rather than silently suppressing it). Any other outcome (bad SHA,
    git unavailable, corrupted repo) raises RuntimeError instead of returning
    False, unlike every other helper in this module: silently treating a real
    git error as "not an ancestor" would risk masking a drift proposal that
    should have fired.
    """
    out = _run(repo, "merge-base", "--is-ancestor", ancestor_sha, descendant_sha)
    if out is None:
        raise RuntimeError(f"git unavailable while checking ancestry in {repo}")
    returncode, _stdout, stderr = out
    if returncode == 0:
        return True
    if returncode == 1:
        return False
    raise RuntimeError(f"git merge-base --is-ancestor failed (exit {returncode}): {stderr.strip()}")


# Character budget for the hunks handed to the prose-refresh agent. Past it the
# diff is cut at a hunk boundary and remaining changed files are name-listed.
PROSE_DIFF_CHAR_BUDGET = 20_000

_DIFF_TARGET_RE = re.compile(r"^diff --git a/.* b/(.*)$", re.MULTILINE)


def diff_since(repo: Path, since_sha: str, sub_paths: list[str]) -> str | None:
    """Return `git diff <sha>..HEAD -- <paths…>` hunk text.

    - Returns "" when there are no changes.
    - Returns None when git is unavailable, the SHA is unknown to this repo
      (history rewrite), or ``sub_paths`` is empty — same None semantics as
      ``changed_files_since``.
    """
    if not since_sha or not sub_paths:
        return None
    out = _run(repo, "diff", f"{since_sha}..HEAD", "--", *sub_paths)
    if out is None or out[0] != 0:
        return None
    return out[1]


def changed_names_since(repo: Path, since_sha: str, sub_paths: list[str]) -> list[str] | None:
    """Multi-path variant of ``changed_files_since`` (same None semantics)."""
    if not since_sha or not sub_paths:
        return None
    out = _run(repo, "diff", "--name-only", f"{since_sha}..HEAD", "--", *sub_paths)
    if out is None or out[0] != 0:
        return None
    return [line.strip() for line in out[1].splitlines() if line.strip()]


def truncate_diff(diff: str, budget: int = PROSE_DIFF_CHAR_BUDGET) -> str:
    """Cap ``diff`` at ``budget`` chars of hunks.

    Whole per-file chunks are kept while they fit; the first chunk that crosses
    the budget is cut at its last fitting ``@@`` hunk boundary; every file whose
    chunk was dropped or cut is name-listed in a
    ``(diff truncated; also changed: …)`` tail.
    """
    if len(diff) <= budget:
        return diff
    chunks = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    kept: list[str] = []
    omitted: list[str] = []
    used = 0
    exhausted = False
    for chunk in chunks:
        if not chunk:
            continue
        m = _DIFF_TARGET_RE.match(chunk)
        target = m.group(1) if m else None
        if not exhausted and used + len(chunk) <= budget:
            kept.append(chunk)
            used += len(chunk)
            continue
        if not exhausted:
            # First overflowing chunk: keep its hunks up to the last fitting @@.
            window = chunk[: max(budget - used, 0)]
            cut = window.rfind("\n@@ ")
            if cut > 0:
                kept.append(chunk[: cut + 1])
            exhausted = True
        if target:
            omitted.append(target)
    tail = f"\n(diff truncated; also changed: {', '.join(omitted)})\n" if omitted else ""
    return "".join(kept) + tail

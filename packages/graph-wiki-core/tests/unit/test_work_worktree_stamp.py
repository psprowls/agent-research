from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest
from work_io.frontmatter import parse


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A real throwaway repo with one linked worktree on branch `feature/x`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("hi\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")

    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "feature/x", str(wt))
    return repo, wt


def _workspace(tmp_path: Path, repo: Path, **fm_extra) -> tuple[Path, str]:
    ws = tmp_path / "ws"
    work = ws / "wiki" / "work"
    work.mkdir(parents=True)
    (ws / ".graph-wiki.yaml").write_text(f"version: 2\ninitialized_at: '2026-08-05'\nrepo-directory: {repo}\n")
    slug = "2026-08-05-feature-thing"
    lines = [
        "---",
        "title: t",
        "category: work",
        "kind: feature",
        "summary: s",
        "status: accepted",
        "affects: []",
        "owner: pat",
        "opened: '2026-08-05'",
        "updated: '2026-08-05'",
        "tags: []",
        "phase: execute",
        "plan_doc: wiki/work/x/02-plan-plan.md",
    ]
    lines += [f"{k}: {v}" for k, v in fm_extra.items()]
    lines += ["---", "", "## Summary", "b", ""]
    (work / f"{slug}.md").write_text("\n".join(lines))
    return ws, slug


def _advance(ws: Path, slug: str, cwd: Path):
    from graph_wiki_core.commands.work import run_work_advance

    original = Path.cwd()
    import os

    os.chdir(cwd)
    try:
        return asyncio.run(run_work_advance(workspace_path=ws, slug=slug))
    finally:
        os.chdir(original)


def test_stamps_worktree_and_branch_from_a_linked_worktree(tmp_path, repo_and_worktree) -> None:
    repo, wt = repo_and_worktree
    ws, slug = _workspace(tmp_path, repo)

    result = _advance(ws, slug, wt)

    assert result.stamped["worktree"] == str(wt.resolve())
    assert result.stamped["branch"] == "feature/x"
    fm, _ = parse((ws / "wiki" / "work" / f"{slug}.md").read_text())
    assert fm["worktree"] == str(wt.resolve())
    assert fm["branch"] == "feature/x"


def test_does_not_stamp_from_the_main_checkout(tmp_path, repo_and_worktree) -> None:
    repo, _wt = repo_and_worktree
    ws, slug = _workspace(tmp_path, repo)

    result = _advance(ws, slug, repo)

    assert "worktree" not in result.stamped
    assert "branch" not in result.stamped


def test_does_not_stamp_from_a_submodule(tmp_path, repo_and_worktree) -> None:
    repo, _wt = repo_and_worktree
    inner = tmp_path / "inner"
    inner.mkdir()
    _git(inner, "init", "-b", "main")
    _git(inner, "config", "user.email", "t@example.com")
    _git(inner, "config", "user.name", "t")
    (inner / "f.txt").write_text("x\n")
    _git(inner, "add", "f.txt")
    _git(inner, "commit", "-m", "init")
    _git(repo, "-c", "protocol.file.allow=always", "submodule", "add", str(inner), "sub")
    _git(repo, "commit", "-m", "add submodule")

    ws, slug = _workspace(tmp_path, repo)
    result = _advance(ws, slug, repo / "sub")

    assert "worktree" not in result.stamped


def test_does_not_stamp_a_worktree_of_an_unrelated_repo(tmp_path, repo_and_worktree) -> None:
    repo, _wt = repo_and_worktree
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "main")
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "t")
    (other / "f.txt").write_text("x\n")
    _git(other, "add", "f.txt")
    _git(other, "commit", "-m", "init")
    other_wt = tmp_path / "other-wt"
    _git(other, "worktree", "add", "-b", "other/x", str(other_wt))

    ws, slug = _workspace(tmp_path, repo)
    result = _advance(ws, slug, other_wt)

    assert "worktree" not in result.stamped


def test_does_not_repoint_a_live_recorded_worktree(tmp_path, repo_and_worktree) -> None:
    repo, wt = repo_and_worktree
    existing = tmp_path / "already-there"
    existing.mkdir()
    ws, slug = _workspace(tmp_path, repo, worktree=str(existing), branch="feature/old")

    result = _advance(ws, slug, wt)

    assert "worktree" not in result.stamped
    fm, _ = parse((ws / "wiki" / "work" / f"{slug}.md").read_text())
    assert fm["worktree"] == str(existing)
    assert fm["branch"] == "feature/old"


def test_repoints_when_the_recorded_worktree_is_gone(tmp_path, repo_and_worktree) -> None:
    repo, wt = repo_and_worktree
    ws, slug = _workspace(tmp_path, repo, worktree=str(tmp_path / "vanished"), branch="feature/old")

    result = _advance(ws, slug, wt)

    assert result.stamped["worktree"] == str(wt.resolve())
    assert result.stamped["branch"] == "feature/x"


def test_detached_head_stamps_nothing(tmp_path, repo_and_worktree) -> None:
    repo, wt = repo_and_worktree
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    _git(wt, "checkout", "--detach", head)

    ws, slug = _workspace(tmp_path, repo)
    result = _advance(ws, slug, wt)

    assert "worktree" not in result.stamped


def test_non_git_cwd_degrades_silently(tmp_path, repo_and_worktree) -> None:
    repo, _wt = repo_and_worktree
    plain = tmp_path / "plain"
    plain.mkdir()
    ws, slug = _workspace(tmp_path, repo)
    # `status: accepted` (the _workspace default) only completes the on_dispatch
    # half of _execute's route (status -> in-progress) on a single advance call;
    # reaching phase=finish needs status already in-progress so on_complete
    # fires instead (see test_commands_work.py's documented advance-count-per-
    # phase pattern). Rewritten directly rather than via _workspace's fm_extra
    # to avoid relying on duplicate-frontmatter-key resolution order.
    page = ws / "wiki" / "work" / f"{slug}.md"
    page.write_text(page.read_text().replace("status: accepted", "status: in-progress", 1))

    result = _advance(ws, slug, plain)

    assert "worktree" not in result.stamped
    assert result.phase == "finish"
